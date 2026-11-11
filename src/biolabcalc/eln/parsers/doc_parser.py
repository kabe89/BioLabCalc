"""
Module: biolabcalc.eln.parsers.doc_parser
Component: Legacy Document Parser (.docx and .pdf)
Agent: @agent: eln-parser-agent
Architectural Role: Extracts structured content (paragraphs, formatted tables, and embedded images)
from legacy Microsoft Word (.docx) and Adobe Portable Document Format (.pdf) files using pure-Python
parsers without external system dependencies.
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from biolabcalc.eln.storage.blob_store import BlobStore


@dataclass
class DocumentImage:
    """
    Representation of an image or figure extracted from a document.

    Attributes:
        filename (str): Extracted filename or resource identifier.
        mime_type (str): Image MIME media type (e.g. 'image/png', 'image/jpeg').
        data_bytes (bytes): Raw binary content of the image.
        sha256 (str): SHA-256 digest of the image bytes.
        width (Optional[int]): Detected pixel width if resolvable.
        height (Optional[int]): Detected pixel height if resolvable.

    Architectural Role:
        Encapsulates extracted visual evidence for CAS ingestion.
        @agent: eln-parser-agent
    """

    filename: str
    mime_type: str
    data_bytes: bytes
    sha256: str
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class DocumentParagraph:
    """
    Representation of a text paragraph with structural typography.

    Attributes:
        text (str): Cleaned paragraph text.
        style (str): Style designation ('Normal', 'Heading 1', 'Heading 2', 'List Bullet', etc.).
        heading_level (int): Heading level (1-6 for headings, 0 for regular body text).

    Architectural Role:
        Represents sequential narrative flow in lab reports.
        @agent: eln-parser-agent
    """

    text: str
    style: str = "Normal"
    heading_level: int = 0


@dataclass
class DocumentResult:
    """
    Aggregated extraction output from a parsed Word or PDF document.

    Attributes:
        file_format (str): Document format identifier ('DOCX', 'PDF').
        title (str): Inferred or extracted document title.
        paragraphs (List[DocumentParagraph]): Ordered paragraphs.
        tables (List[List[List[str]]]): 2D tabular cell matrices (Table -> Row -> Cell).
        images (List[DocumentImage]): Extracted figures and embedded diagrams.
        raw_metadata (Dict[str, Any]): Supplementary metadata (author, created date, page count).

    Architectural Role:
        Standard structured output enabling transformation into ELN entries.
        @agent: eln-parser-agent
    """

    file_format: str
    title: str
    paragraphs: List[DocumentParagraph] = field(default_factory=list)
    tables: List[List[List[str]]] = field(default_factory=list)
    images: List[DocumentImage] = field(default_factory=list)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """
        Convert the document structure into clean, standard Markdown.

        Returns:
            str: Markdown formatted document including headings, paragraphs, and tables.
        """
        md_lines = []

        if self.title:
            md_lines.append(f"# {self.title}\n")

        for p in self.paragraphs:
            if p.heading_level > 0:
                prefix = "#" * min(6, p.heading_level)
                md_lines.append(f"\n{prefix} {p.text}\n")
            elif p.style == "List Bullet":
                md_lines.append(f"- {p.text}")
            else:
                md_lines.append(f"{p.text}\n")

        for t_idx, table in enumerate(self.tables):
            if not table:
                continue
            md_lines.append(f"\n**Table {t_idx + 1}**\n")
            # Format header
            header = table[0]
            md_lines.append("| " + " | ".join(header) + " |")
            md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
            for row in table[1:]:
                # Normalize row length to match header
                norm_row = [row[i] if i < len(row) else "" for i in range(len(header))]
                md_lines.append("| " + " | ".join(norm_row) + " |")
            md_lines.append("")

        if self.images:
            md_lines.append("\n### Embedded Figures\n")
            for img in self.images:
                md_lines.append(f"- Figure: `{img.filename}` ({img.mime_type}, {len(img.data_bytes):,} bytes)")

        return "\n".join(md_lines).strip()

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize document summary to dictionary.

        Returns:
            Dict[str, Any]: Structured summary dictionary.
        """
        return {
            "file_format": self.file_format,
            "title": self.title,
            "paragraph_count": len(self.paragraphs),
            "table_count": len(self.tables),
            "image_count": len(self.images),
            "images": [
                {"filename": img.filename, "mime_type": img.mime_type, "sha256": img.sha256}
                for img in self.images
            ],
            "metadata": self.raw_metadata,
        }


class DocParser:
    """
    Pure-Python parser for Microsoft Word (.docx) and Adobe PDF (.pdf) documents.

    Architectural Role:
        Ingests legacy protocol archives, SOPs, and lab reports into modern ELN structures.
        @agent: eln-parser-agent
    """

    @classmethod
    def parse(cls, source: Union[bytes, str, Path], filename: str = "") -> DocumentResult:
        """
        Parse Word or PDF document from path or byte buffer.

        Args:
            source (Union[bytes, str, Path]): Path or raw file bytes.
            filename (str): Optional filename to aid format detection.

        Returns:
            DocumentResult: Extracted paragraphs, tables, and images.
        """
        if isinstance(source, (str, Path)):
            p = Path(source)
            if not filename:
                filename = p.name
            with open(p, "rb") as f:
                data = f.read()
        elif isinstance(source, bytes):
            data = source
        else:
            raise TypeError(f"Unsupported source type: {type(source).__name__}")

        lower_fn = filename.lower()

        if lower_fn.endswith(".docx") or (data[:4] == b"PK\x03\x04" and b"word/document.xml" in data):
            return cls._parse_docx(data)
        elif lower_fn.endswith(".pdf") or data.startswith(b"%PDF-"):
            return cls._parse_pdf(data)
        else:
            # Fallback signature sniffing
            if data.startswith(b"PK\x03\x04"):
                return cls._parse_docx(data)
            return cls._parse_pdf(data)

    @classmethod
    def _parse_docx(cls, data: bytes) -> DocumentResult:
        """Parse Microsoft Word .docx OpenXML container."""
        paragraphs: List[DocumentParagraph] = []
        tables: List[List[List[str]]] = []
        images: List[DocumentImage] = []
        doc_title = ""

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            namelist = zf.namelist()

            # 1. Extract embedded media files from word/media/
            media_files = [n for n in namelist if n.startswith("word/media/")]
            for m_path in media_files:
                img_bytes = zf.read(m_path)
                fn = Path(m_path).name
                mime = BlobStore.detect_mime_type(fn)
                sha = BlobStore.compute_sha256(img_bytes)
                images.append(
                    DocumentImage(
                        filename=fn,
                        mime_type=mime,
                        data_bytes=img_bytes,
                        sha256=sha,
                    )
                )

            # 2. Parse word/document.xml
            if "word/document.xml" in namelist:
                doc_xml = zf.read("word/document.xml")
                root = ET.fromstring(doc_xml)

                w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

                # Parse body elements in sequential order
                body = root.find(f"{w_ns}body")
                if body is not None:
                    for child in body:
                        tag = child.tag
                        if tag == f"{w_ns}p":
                            # Paragraph
                            p_text = "".join(child.itertext()).strip()
                            if not p_text:
                                continue

                            # Detect style
                            style_name = "Normal"
                            heading_level = 0
                            p_style = child.find(f".//{w_ns}pStyle")
                            if p_style is not None:
                                s_val = p_style.get(f"{w_ns}val", "")
                                style_name = s_val
                                if "heading" in s_val.lower():
                                    num_match = re.search(r"(\d+)", s_val)
                                    heading_level = int(num_match.group(1)) if num_match else 1
                                elif "title" in s_val.lower():
                                    heading_level = 1
                                    if not doc_title:
                                        doc_title = p_text

                            if heading_level == 1 and not doc_title:
                                doc_title = p_text

                            paragraphs.append(
                                DocumentParagraph(
                                    text=p_text,
                                    style=style_name,
                                    heading_level=heading_level,
                                )
                            )

                        elif tag == f"{w_ns}tbl":
                            # Table
                            table_grid: List[List[str]] = []
                            for row in child.findall(f"{w_ns}tr"):
                                row_cells: List[str] = []
                                for cell in row.findall(f"{w_ns}tc"):
                                    c_text = "".join(cell.itertext()).strip()
                                    row_cells.append(c_text)
                                if row_cells:
                                    table_grid.append(row_cells)
                            if table_grid:
                                tables.append(table_grid)

        return DocumentResult(
            file_format="DOCX",
            title=doc_title,
            paragraphs=paragraphs,
            tables=tables,
            images=images,
            raw_metadata={"embedded_image_count": len(images)},
        )

    @classmethod
    def _parse_pdf(cls, data: bytes) -> DocumentResult:
        """
        Pure-Python PDF parser extracting text streams, tables, and embedded images.
        """
        paragraphs: List[DocumentParagraph] = []
        tables: List[List[List[str]]] = []
        images: List[DocumentImage] = []
        doc_title = ""

        # Extract text objects: look for streams in PDF
        # Locate stream blocks: stream ... endstream
        stream_matches = re.finditer(rb"stream[\r\n]+(.*?)[\r\n]+endstream", data, re.DOTALL)

        extracted_text_blocks: List[str] = []

        for match in stream_matches:
            stream_raw = match.group(1)
            # Try FlateDecode decompress
            decompressed: Optional[bytes] = None
            try:
                decompressed = zlib.decompress(stream_raw)
            except Exception:
                try:
                    decompressed = zlib.decompress(stream_raw, -15)
                except Exception:
                    decompressed = stream_raw

            if not decompressed:
                continue

            # Check if text content
            if b"BT" in decompressed and b"ET" in decompressed:
                # Extract Tj and TJ strings
                # Standard Tj: (Text) Tj
                tj_matches = re.findall(rb"\((.*?)\)\s*Tj", decompressed)
                for t in tj_matches:
                    text_str = t.decode("latin1", errors="ignore").strip()
                    if text_str:
                        extracted_text_blocks.append(text_str)

                # Array TJ: [(T) 10 (e) 10 (x) 10 (t)] TJ
                tj_array_matches = re.findall(rb"\[(.*?)\]\s*TJ", decompressed)
                for arr in tj_array_matches:
                    parts = re.findall(rb"\((.*?)\)", arr)
                    combined = "".join([p.decode("latin1", errors="ignore") for p in parts]).strip()
                    if combined:
                        extracted_text_blocks.append(combined)

            # Check for embedded JPEG images: look for JFIF header inside raw or decompressed stream
            if b"\xff\xd8\xff" in stream_raw:
                jpeg_start = stream_raw.find(b"\xff\xd8\xff")
                jpeg_bytes = stream_raw[jpeg_start:]
                sha = BlobStore.compute_sha256(jpeg_bytes)
                images.append(
                    DocumentImage(
                        filename=f"pdf_img_{sha[:8]}.jpg",
                        mime_type="image/jpeg",
                        data_bytes=jpeg_bytes,
                        sha256=sha,
                    )
                )

        # Reconstruct paragraphs and tables from extracted text blocks
        full_text = "\n".join(extracted_text_blocks)
        raw_lines = [l.strip() for l in full_text.splitlines() if l.strip()]

        current_table_lines: List[List[str]] = []

        for line in raw_lines:
            # Check for table line (delimiters like | or tabs or > 2 columns)
            if "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 2:
                    current_table_lines.append(cells)
                    continue
            elif "\t" in line:
                cells = [c.strip() for c in line.split("\t") if c.strip()]
                if len(cells) >= 2:
                    current_table_lines.append(cells)
                    continue

            # If we were collecting table lines, flush them
            if len(current_table_lines) >= 2:
                tables.append(list(current_table_lines))
                current_table_lines.clear()

            # Heading detection heuristics
            heading_lvl = 0
            if line.isupper() and len(line) < 60:
                heading_lvl = 2
            elif re.match(r"^(?:Section|\d+\.|\bProtocol\b|\bMethod\b)", line, re.IGNORECASE):
                heading_lvl = 2

            if heading_lvl > 0 and not doc_title:
                doc_title = line

            paragraphs.append(
                DocumentParagraph(
                    text=line,
                    style=f"Heading {heading_lvl}" if heading_lvl else "Normal",
                    heading_level=heading_lvl,
                )
            )

        if len(current_table_lines) >= 2:
            tables.append(current_table_lines)

        return DocumentResult(
            file_format="PDF",
            title=doc_title,
            paragraphs=paragraphs,
            tables=tables,
            images=images,
            raw_metadata={"text_block_count": len(extracted_text_blocks)},
        )
