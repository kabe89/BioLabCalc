"""
Module: biolabcalc.eln.rag.chunker
Component: Multi-Entity Semantic Chunker with Biological Provenance Extraction
Agent: @agent: eln-rag-agent
Architectural Role: Ingests notebook daily entries, kinetic timepoints, FPLC
chromatograms, NanoDrop spectra, Bio-Rad gels, and SOPs; extracts dense text,
sparse lexical tokens, and structured biological entities (constructs, primers,
columns, elution volumes, yields, mutations, catalog numbers).
"""

import copy
import dataclasses
from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Set, Union


@dataclass
class ProvenanceMetadata:
    """
    Structured laboratory provenance metadata tracking experimental origin,
    researcher ownership, campaign chronology, and instrument logs.

    Parameters
    ----------
    author_id : str
        Unique identifier for the researcher (e.g. 'rf_franklin').
    author_name : str
        Full name of the author (e.g. 'Dr. Rosalind Franklin').
    project_tag : str
        Project identifier (e.g. 'T7RNAP_Expression').
    campaign_id : str
        Laboratory campaign or study code (e.g. 'CAMP-2024-Q3').
    campaign_day : Union[int, str]
        Day index or label within campaign (e.g. 4 or 'Day 4').
    recorded_at : str
        ISO 8601 timestamp string (e.g. '2024-05-12T14:30:00Z').
    entity_type : str
        Lab entity classification ('daily_entry', 'kinetic_log',
        'fplc_chromatogram', 'nanodrop_record', 'biorad_gel', 'sop').
    author_status : str
        Status of the author ('current' or 'alumni'), default 'current'.
    instrument_record : Optional[str]
        Instrument model and run ID (e.g. 'AKTA pure 25 M1', 'NanoDrop One').
    source_file : Optional[str]
        File path of the originating notebook or exported raw record.
    extra : Dict[str, Any]
        Additional arbitrary metadata tags.

    Agent
    -----
    @agent: eln-rag-agent
    """

    author_id: str
    author_name: str
    project_tag: str
    campaign_id: str
    campaign_day: Union[int, str]
    recorded_at: str
    entity_type: str
    author_status: str = "current"
    instrument_record: Optional[str] = None
    source_file: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary representation."""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvenanceMetadata":
        """Instantiate ProvenanceMetadata from a dictionary."""
        d = dict(data)
        extra = d.pop("extra", {})
        known_keys = {f.name for f in dataclasses.fields(cls)}
        init_kwargs = {k: v for k, v in d.items() if k in known_keys}
        leftover = {k: v for k, v in d.items() if k not in known_keys}
        extra.update(leftover)
        init_kwargs["extra"] = extra
        return cls(**init_kwargs)


@dataclass
class DocumentChunk:
    """
    Unified dense-sparse document chunk carrying dense narrative content,
    token-frequency map for BM25, extracted lab entities, and provenance metadata.

    Parameters
    ----------
    chunk_id : str
        Unique identifier for the chunk.
    content : str
        Dense text representation for vector indexing and LLM context.
    metadata : ProvenanceMetadata
        Provenance tracking record.
    sparse_tokens : Dict[str, int]
        Lexical token frequency mapping for sparse inverted index.
    extracted_entities : Dict[str, List[str]]
        Normalized biological entities (constructs, primers, columns,
        elution_volumes, yields, mutations, catalog_numbers, buffers).
    embedding : Optional[List[float]]
        Optional precomputed dense embedding vector.

    Agent
    -----
    @agent: eln-rag-agent
    """

    chunk_id: str
    content: str
    metadata: ProvenanceMetadata
    sparse_tokens: Dict[str, int] = field(default_factory=dict)
    extracted_entities: Dict[str, List[str]] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert DocumentChunk to serializable dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "metadata": self.metadata.to_dict(),
            "sparse_tokens": self.sparse_tokens,
            "extracted_entities": self.extracted_entities,
            "embedding": self.embedding,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentChunk":
        """Reconstruct DocumentChunk from dictionary."""
        meta_dict = data.get("metadata", {})
        meta = (
            meta_dict
            if isinstance(meta_dict, ProvenanceMetadata)
            else ProvenanceMetadata.from_dict(meta_dict)
        )
        return cls(
            chunk_id=data["chunk_id"],
            content=data["content"],
            metadata=meta,
            sparse_tokens=data.get("sparse_tokens", {}),
            extracted_entities=data.get("extracted_entities", {}),
            embedding=data.get("embedding"),
        )


class LaboratoryEntityExtractor:
    """
    Regex and heuristic entity extractor specialized for biochemical,
    molecular biology, and chromatography terminology.

    Extracts:
    - Constructs (e.g. pET-28a-T7RNAP, pGEX-4T-1, pUC19)
    - Primer codes (e.g. T7-fwd, T7-Term-rev, oBR102)
    - Chromatography columns (e.g. Superdex 200 10/300 GL, HisTrap HP 5mL, Mono Q)
    - Elution volumes (e.g. Ve=13.2 mL, 13.2 mL)
    - Yields (e.g. 45.6 mg, 45.6 mg/L, 2.5 mg/mL)
    - Mutation codes (e.g. S65T, D538G, K103N)
    - Catalog numbers (e.g. Cat# 28-9909-44, #M0273S)
    - Buffers (e.g. 50 mM Tris-HCl pH 8.0, 100 mM NaCl, PBS)

    Agent
    -----
    @agent: eln-rag-agent
    """

    PATTERNS = {
        "constructs": re.compile(
            r"\b(?:p[A-Z0-9]+(?:-[A-Za-z0-9_().+]+)+|pUC[0-9]+|pET-[0-9]+[a-z]?(?:\([+]?\))?-[A-Za-z0-9_-]+)\b",
            re.IGNORECASE,
        ),
        "primers": re.compile(
            r"\b(?:o[A-Z0-9_]{2,}|[A-Za-z0-9_]+-(?:fwd|rev|forward|reverse|F|R)|primer-[A-Za-z0-9_-]+)\b",
        ),
        "columns": re.compile(
            r"\b(?:Superdex\s*(?:75|200)(?:\s*(?:Increase|pg|GL|10/300(?:\s*GL)?|16/600|5/150))?|HisTrap\s*(?:HP|FF|excel)?(?:\s*\d+\s*m[Ll])?|Mono\s*[QS](?:\s*\d+/\d+)?|Capto\s*[A-Za-z0-9]+|Ni-NTA\s*(?:Superflow|agarose|column)?|HiTrap\s*[A-Za-z0-9\s]+)\b",
            re.IGNORECASE,
        ),
        "elution_volumes": re.compile(
            r"(?:Ve\s*=\s*\d+(?:\.\d+)?\s*m[Ll]|\b\d+(?:\.\d+)?\s*m[Ll]\s*(?:elution|peak|fraction|Ve)|Ve\s*=\s*\d+(?:\.\d+)?\s*(?:uL|ul))",
            re.IGNORECASE,
        ),
        "yields": re.compile(
            r"(?:yield(?:\s*[:=]|\s+of)?\s*)?(\b\d+(?:\.\d+)?\s*(?:mg/mL|mg/ml|mg/L|mg/l|mg|ug/uL|ug/ml|ug|g/L|%))\b",
            re.IGNORECASE,
        ),
        "mutations": re.compile(
            r"\b[A-Z]\d{1,4}[A-Z]\b",
        ),
        "catalog_numbers": re.compile(
            r"(?:Cat(?:alog)?(?:[.\s]*#[.\s]*|[.\s]*No[.\s]*:?|[.\s]*:?\s*)|#)([A-Za-z0-9-]{4,20})",
            re.IGNORECASE,
        ),
        "buffers": re.compile(
            r"\b(?:\d+(?:\.\d+)?\s*(?:mM|M|%)\s+[A-Za-z0-9-]+(?:\s*pH\s*\d+(?:\.\d+)?)?|PBS|TBS|TBST|HEPES|Tris-HCl|TE\s+buffer)\b",
            re.IGNORECASE,
        ),
    }

    @classmethod
    def extract_entities(cls, text: str) -> Dict[str, List[str]]:
        """
        Extract biological entities from text into structured dictionary.

        Parameters
        ----------
        text : str
            Laboratory text content.

        Returns
        -------
        Dict[str, List[str]]
            Category-mapped unique extracted entity strings.
        """
        entities: Dict[str, List[str]] = {}
        for category, pattern in cls.PATTERNS.items():
            matches = pattern.findall(text)
            cleaned = []
            for m in matches:
                if isinstance(m, tuple):
                    m = next((item for item in m if item), "")
                val = str(m).strip()
                if val and val not in cleaned:
                    cleaned.append(val)
                # If elution volume contains Ve = X mL, also extract bare volume X mL
                if category == "elution_volumes" and "ve" in val.lower():
                    sub_vol = re.search(r"(\d+(?:\.\d+)?\s*(?:m[Ll]|u[Ll]))", val)
                    if sub_vol:
                        v_clean = sub_vol.group(1).strip()
                        if v_clean not in cleaned:
                            cleaned.append(v_clean)
            if cleaned:
                entities[category] = cleaned
        return entities

    @classmethod
    def compute_sparse_tokens(cls, text: str, extracted_entities: Optional[Dict[str, List[str]]] = None) -> Dict[str, int]:
        """
        Tokenize text into sparse term frequencies, boosting extracted biological entities.

        Parameters
        ----------
        text : str
            Raw content text.
        extracted_entities : Optional[Dict[str, List[str]]]
            Pre-extracted biological entities to preserve and boost.

        Returns
        -------
        Dict[str, int]
            Map of token -> frequency.
        """
        freqs: Dict[str, int] = {}
        # Clean words
        words = re.findall(r"[A-Za-z0-9_#.:\-=]+", text)
        for w in words:
            tok = w.lower()
            if len(tok) >= 2:
                freqs[tok] = freqs.get(tok, 0) + 1

        # Preserve exact case & symbols for biological entities
        if extracted_entities:
            for cat, ents in extracted_entities.items():
                for ent in ents:
                    e_raw = ent.strip()
                    # Store exact entity token
                    freqs[e_raw] = freqs.get(e_raw, 0) + 3
                    # Also normalized lowercase
                    e_lower = e_raw.lower()
                    freqs[e_lower] = freqs.get(e_lower, 0) + 2

        return freqs


class DocumentChunker:
    """
    Semantic chunker specialized for multi-modal ELN & LIMS data entries:
    daily entries, kinetic timepoints, FPLC peaks, NanoDrop spectral records,
    Bio-Rad gels, and SOPs.

    Agent
    -----
    @agent: eln-rag-agent
    """

    def __init__(self, default_chunk_size: int = 500) -> None:
        """
        Initialize the Document Chunker.

        Parameters
        ----------
        default_chunk_size : int
            Character target budget per textual sub-chunk.
        """
        self.default_chunk_size = default_chunk_size
        self.extractor = LaboratoryEntityExtractor()

    def _create_chunk(
        self,
        content: str,
        metadata: ProvenanceMetadata,
        index: int,
    ) -> DocumentChunk:
        """
        Helper method to instantiate a DocumentChunk with extracted tokens and entities.

        Parameters
        ----------
        content : str
            Dense textual representation.
        metadata : ProvenanceMetadata
            Provenance metadata.
        index : int
            Chunk sub-index.

        Returns
        -------
        DocumentChunk
            Constructed chunk.
        """
        clean_content = content.strip()
        entities = self.extractor.extract_entities(clean_content)
        sparse_tokens = self.extractor.compute_sparse_tokens(clean_content, entities)

        day_tag = f"d{metadata.campaign_day}".replace(" ", "_")
        safe_entity = metadata.entity_type.lower().replace(" ", "_")
        chunk_id = f"{metadata.campaign_id}_{safe_entity}_{day_tag}_{index:03d}"

        return DocumentChunk(
            chunk_id=chunk_id,
            content=clean_content,
            metadata=copy.deepcopy(metadata),
            sparse_tokens=sparse_tokens,
            extracted_entities=entities,
        )

    def chunk_daily_entry(
        self,
        text: str,
        metadata: ProvenanceMetadata,
        max_chunk_size: Optional[int] = None,
    ) -> List[DocumentChunk]:
        """
        Chunk a laboratory notebook daily entry by semantic sections (e.g.
        Objectives, Protocols, Observations, Results).

        Parameters
        ----------
        text : str
            Full daily notebook entry text.
        metadata : ProvenanceMetadata
            Entry provenance metadata.
        max_chunk_size : Optional[int]
            Target maximum size per chunk.

        Returns
        -------
        List[DocumentChunk]
            List of generated semantic chunks.
        """
        meta = copy.deepcopy(metadata)
        if not meta.entity_type or meta.entity_type in ("daily_entry", "daily_log", "notebook_entry"):
            meta.entity_type = "daily_entry"
        size = max_chunk_size or self.default_chunk_size

        # Split by markdown headers or double newlines
        sections = re.split(r"(?:\r?\n){2,}|(?=^#{1,4}\s+)", text, flags=re.MULTILINE)
        chunks: List[DocumentChunk] = []
        current_buffer: List[str] = []
        current_len = 0
        idx = 1

        for sec in sections:
            sec_clean = sec.strip()
            if not sec_clean:
                continue

            if current_len + len(sec_clean) > size and current_buffer:
                content = "\n\n".join(current_buffer)
                chunks.append(self._create_chunk(content, meta, idx))
                idx += 1
                current_buffer = [sec_clean]
                current_len = len(sec_clean)
            else:
                current_buffer.append(sec_clean)
                current_len += len(sec_clean)

        if current_buffer:
            content = "\n\n".join(current_buffer)
            chunks.append(self._create_chunk(content, meta, idx))

        return chunks if chunks else [self._create_chunk(text, meta, 1)]

    def chunk_kinetic_log(
        self,
        data: Union[Dict[str, Any], str],
        metadata: ProvenanceMetadata,
    ) -> List[DocumentChunk]:
        """
        Convert enzyme kinetic timepoint logs into dense structured chunks.

        Parameters
        ----------
        data : Union[Dict[str, Any], str]
            Kinetic assay dictionary or formatted log string.
        metadata : ProvenanceMetadata
            Provenance metadata.

        Returns
        -------
        List[DocumentChunk]
            Kinetic log chunks.
        """
        meta = copy.deepcopy(metadata)
        meta.entity_type = "kinetic_log"

        if isinstance(data, str):
            content = data
        else:
            assay_name = data.get("assay_name", "Enzyme Kinetics Assay")
            substrate = data.get("substrate", "Substrate")
            enzyme = data.get("enzyme", "Enzyme")
            vmax = data.get("vmax", "N/A")
            km = data.get("km", "N/A")
            temperature = data.get("temperature", "25 C")
            timepoints = data.get("timepoints", [])

            tp_lines = []
            for tp in timepoints[:10]:
                tp_lines.append(f"- t={tp.get('time', 0)} min: OD={tp.get('od', 0.0)}")
            tp_summary = "\n".join(tp_lines)

            content = (
                f"Assay: {assay_name}\n"
                f"Enzyme: {enzyme} | Substrate: {substrate}\n"
                f"Temperature: {temperature}\n"
                f"Kinetic Parameters: Vmax = {vmax}, Km = {km}\n"
                f"Timepoints:\n{tp_summary}\n"
                f"Notes: {data.get('notes', 'Kinetic profile recorded.')}"
            )

        return [self._create_chunk(content, meta, 1)]

    def chunk_fplc_peaks(
        self,
        peaks_data: Union[List[Dict[str, Any]], Dict[str, Any], str],
        metadata: ProvenanceMetadata,
    ) -> List[DocumentChunk]:
        """
        Chunk FPLC chromatography run information, capturing columns,
        elution volumes (Ve), yields, buffer systems, and peak purity.

        Parameters
        ----------
        peaks_data : Union[List[Dict[str, Any]], Dict[str, Any], str]
            Chromatogram run record.
        metadata : ProvenanceMetadata
            Provenance metadata.

        Returns
        -------
        List[DocumentChunk]
            FPLC peak chunks.
        """
        meta = copy.deepcopy(metadata)
        meta.entity_type = "fplc_chromatogram"

        if isinstance(peaks_data, str):
            content = peaks_data
        elif isinstance(peaks_data, dict):
            col = peaks_data.get("column", "Superdex 200")
            flow = peaks_data.get("flow_rate", "0.5 mL/min")
            buffer = peaks_data.get("buffer", "50 mM Tris-HCl pH 8.0, 100 mM NaCl, 1 mM DTT")
            target = peaks_data.get("target_protein", "Target Protein")
            peaks = peaks_data.get("peaks", [])
            lines = [
                f"FPLC Purification Run - Protein: {target}",
                f"Chromatography Column: {col}",
                f"Flow Rate: {flow}",
                f"Buffer: {buffer}",
            ]
            for p in peaks:
                ve = p.get("ve", p.get("elution_volume", "N/A"))
                p_yield = p.get("yield", "N/A")
                area = p.get("area", "N/A")
                frac = p.get("fractions", "N/A")
                lines.append(
                    f"Peak {p.get('peak_number', 1)}: Elution Volume Ve = {ve}, "
                    f"Yield = {p_yield}, Peak Area = {area}, Fractions = {frac}"
                )
            content = "\n".join(lines)
        else:
            # List of peaks
            lines = ["FPLC Peak Summary:"]
            for idx, p in enumerate(peaks_data, 1):
                lines.append(f"Peak {idx}: {json.dumps(p)}")
            content = "\n".join(lines)

        return [self._create_chunk(content, meta, 1)]

    def chunk_nanodrop_record(
        self,
        records: Union[List[Dict[str, Any]], Dict[str, Any], str],
        metadata: ProvenanceMetadata,
    ) -> List[DocumentChunk]:
        """
        Chunk NanoDrop spectrophotometer absorbance records (A260, A280, 260/280, 260/230, yield).

        Parameters
        ----------
        records : Union[List[Dict[str, Any]], Dict[str, Any], str]
            Spectral record data.
        metadata : ProvenanceMetadata
            Provenance metadata.

        Returns
        -------
        List[DocumentChunk]
            NanoDrop spectral chunks.
        """
        meta = copy.deepcopy(metadata)
        meta.entity_type = "nanodrop_record"

        if isinstance(records, str):
            content = records
        elif isinstance(records, dict):
            sample = records.get("sample_name", "Protein Sample")
            conc = records.get("concentration", records.get("conc_mg_ml", "N/A"))
            a280 = records.get("a280", "N/A")
            a260_a280 = records.get("ratio_260_280", records.get("a260_a280", "N/A"))
            ext_coeff = records.get("extinction_coeff", "N/A")
            total_yield = records.get("total_yield", records.get("yield", "N/A"))
            content = (
                f"NanoDrop Spectrophotometry Measurement:\n"
                f"Sample: {sample}\n"
                f"Concentration: {conc} mg/mL | Total Yield: {total_yield}\n"
                f"Absorbance A280: {a280}\n"
                f"Purity Ratio A260/A280: {a260_a280}\n"
                f"Molar Extinction Coefficient: {ext_coeff}"
            )
        else:
            lines = ["NanoDrop Spectral Measurements:"]
            for r in records:
                lines.append(
                    f"Sample {r.get('sample_name')}: Conc={r.get('concentration')} mg/mL, "
                    f"A260/A280={r.get('ratio_260_280')}, Yield={r.get('yield')}"
                )
            content = "\n".join(lines)

        return [self._create_chunk(content, meta, 1)]

    def chunk_biorad_gel(
        self,
        gel_data: Union[Dict[str, Any], str],
        metadata: ProvenanceMetadata,
    ) -> List[DocumentChunk]:
        """
        Chunk Bio-Rad ChemiDoc / Criterion gel records including ladder,
        lanes, molecular weight band estimations, and purity percentages.

        Parameters
        ----------
        gel_data : Union[Dict[str, Any], str]
            Gel run dictionary or descriptive string.
        metadata : ProvenanceMetadata
            Provenance metadata.

        Returns
        -------
        List[DocumentChunk]
            Bio-Rad gel chunks.
        """
        meta = copy.deepcopy(metadata)
        meta.entity_type = "biorad_gel"

        if isinstance(gel_data, str):
            content = gel_data
        else:
            gel_type = gel_data.get("gel_type", "4-20% SDS-PAGE")
            stain = gel_data.get("staining", "Coomassie Brilliant Blue")
            ladder = gel_data.get("ladder", "Bio-Rad Precision Plus Protein Standard")
            lanes = gel_data.get("lanes", [])
            lines = [
                f"Electrophoresis Gel Record - Bio-Rad ChemiDoc MP",
                f"Gel Chemistry: {gel_type} | Staining: {stain}",
                f"Molecular Weight Ladder: {ladder}",
                "Lanes:",
            ]
            for lane in lanes:
                lane_num = lane.get("lane_number", 1)
                sample = lane.get("sample", "Sample")
                mw = lane.get("apparent_mw", "N/A")
                purity = lane.get("purity_percent", "N/A")
                lines.append(f"- Lane {lane_num}: {sample} (Apparent MW: {mw}, Purity: {purity}%)")
            content = "\n".join(lines)

        return [self._create_chunk(content, meta, 1)]

    def chunk_sop(
        self,
        sop_text: str,
        metadata: ProvenanceMetadata,
        section_size: Optional[int] = None,
    ) -> List[DocumentChunk]:
        """
        Chunk a Standard Operating Procedure (SOP) into logically cohesive sections.

        Parameters
        ----------
        sop_text : str
            Full SOP text.
        metadata : ProvenanceMetadata
            Provenance metadata.
        section_size : Optional[int]
            Maximum target section size.

        Returns
        -------
        List[DocumentChunk]
            SOP chunks.
        """
        meta = copy.deepcopy(metadata)
        meta.entity_type = "sop"
        return self.chunk_daily_entry(sop_text, meta, max_chunk_size=section_size or 600)

    def chunk_document(
        self,
        content: Union[str, Dict[str, Any], List[Dict[str, Any]], None] = None,
        entity_type: str = "daily_entry",
        metadata: Optional[ProvenanceMetadata] = None,
        text: Optional[str] = None,
        provenance: Optional[Union[Dict[str, Any], ProvenanceMetadata]] = None,
    ) -> List[DocumentChunk]:
        """
        Unified dispatcher routing document to specialized chunker based on entity_type.

        Parameters
        ----------
        content : Union[str, Dict[str, Any], List[Dict[str, Any]], None]
            Document payload.
        entity_type : str
            Laboratory entity type.
        metadata : Optional[ProvenanceMetadata]
            Provenance metadata object.
        text : Optional[str]
            Text alias for content.
        provenance : Optional[Union[Dict[str, Any], ProvenanceMetadata]]
            Provenance metadata object or dictionary.

        Returns
        -------
        List[DocumentChunk]
            Generated document chunks.
        """
        payload = text if text is not None else content
        if payload is None:
            payload = ""

        prov = provenance if provenance is not None else metadata
        if isinstance(prov, ProvenanceMetadata):
            meta = copy.deepcopy(prov)
        elif isinstance(prov, dict):
            meta = ProvenanceMetadata(
                author_id=prov.get("author_id", "anonymous_user"),
                author_name=prov.get("author_name", "Anonymous Researcher"),
                project_tag=prov.get("project_tag", "General"),
                campaign_id=prov.get("campaign_id", "CAMP-DEFAULT"),
                campaign_day=prov.get("campaign_day", 1),
                recorded_at=prov.get("recorded_at", "2026-11-02T00:00:00Z"),
                entity_type=entity_type,
                author_status=prov.get("author_status", "current"),
                instrument_record=prov.get("instrument_record", None),
                source_file=prov.get("source_file", None),
                extra=prov.get("extra", {}),
            )
        else:
            meta = ProvenanceMetadata(
                author_id="anonymous_user",
                author_name="Anonymous Researcher",
                project_tag="General",
                campaign_id="CAMP-DEFAULT",
                campaign_day=1,
                recorded_at="2026-11-02T00:00:00Z",
                entity_type=entity_type,
            )

        clean_type = entity_type.lower().strip()
        meta.entity_type = clean_type

        if clean_type in ("daily_entry", "daily_log", "notebook_entry"):
            return self.chunk_daily_entry(str(payload), meta)
        elif clean_type in ("kinetic_log", "kinetics", "kinetic_assay"):
            return self.chunk_kinetic_log(payload, meta)
        elif clean_type in ("fplc_chromatogram", "fplc_peaks", "fplc", "chromatography"):
            return self.chunk_fplc_peaks(payload, meta)
        elif clean_type in ("nanodrop_record", "nanodrop", "spectroscopy"):
            return self.chunk_nanodrop_record(payload, meta)
        elif clean_type in ("biorad_gel", "gel", "sds_page"):
            return self.chunk_biorad_gel(payload, meta)
        elif clean_type in ("sop", "protocol"):
            return self.chunk_sop(str(payload), meta)
        else:
            return self.chunk_daily_entry(str(payload), meta)
