"""Sequence utilities for DNA, RNA, and protein manipulation."""

from __future__ import annotations
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

# S (C/G) complement is S (G/C); W (A/T) complement is W (T/A)
DNA_COMPLEMENT = str.maketrans("ACGTURYSWKMBDHVNacgturyswkmbdhvn", "TGCAAYRSWMKVHDBNtgcaayrswmkvhdbn")
RNA_COMPLEMENT = str.maketrans("ACGTURYSWKMBDHVNacgturyswkmbdhvn", "UGCAAYRSWMKVHDBNugcaayrswmkvhdbn")

CODON_TABLE: Dict[str, str] = {
    'ATA':'I', 'ATC':'I', 'ATT':'I', 'ATG':'M',
    'ACA':'T', 'ACC':'T', 'ACG':'T', 'ACT':'T',
    'AAC':'N', 'AAT':'N', 'AAA':'K', 'AAG':'K',
    'AGC':'S', 'AGT':'S', 'AGA':'R', 'AGG':'R',
    'CTA':'L', 'CTC':'L', 'CTG':'L', 'CTT':'L',
    'CCA':'P', 'CCC':'P', 'CCG':'P', 'CCT':'P',
    'CAC':'H', 'CAT':'H', 'CAA':'Q', 'CAG':'Q',
    'CGA':'R', 'CGC':'R', 'CGG':'R', 'CGT':'R',
    'GTA':'V', 'GTC':'V', 'GTG':'V', 'GTT':'V',
    'GCA':'A', 'GCC':'A', 'GCG':'A', 'GCT':'A',
    'GAC':'D', 'GAT':'D', 'GAA':'E', 'GAG':'E',
    'GGA':'G', 'GGC':'G', 'GGG':'G', 'GGT':'G',
    'TCA':'S', 'TCC':'S', 'TCG':'S', 'TCT':'S',
    'TTC':'F', 'TTT':'F', 'TTA':'L', 'TTG':'L',
    'TAC':'Y', 'TAT':'Y', 'TAA':'*', 'TAG':'*',
    'TGC':'C', 'TGT':'C', 'TGA':'*', 'TGG':'W',
}


def clean_sequence(seq: str) -> str:
    """Strip FASTA header lines, GenBank metadata/coordinates, whitespace, numbers, and special characters, converting to uppercase."""
    if not seq:
        return ""
    # If GenBank format is detected (contains ORIGIN block)
    origin_match = re.search(r'\bORIGIN\b', seq, re.IGNORECASE)
    if origin_match:
        seq_part = seq[origin_match.end():]
        end_idx = seq_part.find("//")
        if end_idx != -1:
            seq_part = seq_part[:end_idx]
        lines = seq_part.splitlines()
    else:
        lines = []
        for line in seq.splitlines():
            s = line.strip()
            # Skip FASTA headers, comment lines, and GenBank record terminators
            if not s or s.startswith('>') or s.startswith(';') or s.startswith('#') or s == '//':
                continue
            # Skip obvious GenBank header lines if pasted without ORIGIN
            first_word = s.split()[0].upper() if s.split() else ""
            if first_word in {
                "LOCUS", "DEFINITION", "ACCESSION", "VERSION", "DBLINK",
                "KEYWORDS", "SOURCE", "ORGANISM", "REFERENCE", "AUTHORS",
                "TITLE", "JOURNAL", "PUBMED", "REMARK", "COMMENT",
                "FEATURES", "BASE"
            }:
                continue
            lines.append(s)

    joined = "".join(lines)
    return re.sub(r'[^A-Za-z*]', '', joined).upper()


def validate_sequence(seq: str, seq_type: str = "dna") -> bool:
    """Validate whether sequence characters match standard IUPAC conventions."""
    cleaned = clean_sequence(seq)
    if not cleaned:
        return False
    seq_type_lower = seq_type.lower()
    if seq_type_lower in ("dna", "ssdna", "dsdna"):
        return bool(re.fullmatch(r'[ACGTNRYWSKMBDHV]+', cleaned))
    elif seq_type_lower == "rna":
        return bool(re.fullmatch(r'[ACGUNRYWSKMBDHV]+', cleaned))
    elif seq_type_lower in ("protein", "peptide", "aa"):
        return bool(re.fullmatch(r'[ACDEFGHIKLMNPQRSTVWYUO*]+', cleaned))
    else:
        raise ValueError(f"Unknown sequence type: {seq_type}. Expected 'dna', 'rna', or 'protein'.")


def reverse_complement(seq: str, seq_type: str = "dna") -> str:
    """Return the 5' -> 3' reverse complement of a DNA or RNA sequence."""
    cleaned = clean_sequence(seq)
    if seq_type.lower() == "rna":
        cleaned = cleaned.replace("T", "U")
        return cleaned.translate(RNA_COMPLEMENT)[::-1]
    cleaned = cleaned.replace("U", "T")
    return cleaned.translate(DNA_COMPLEMENT)[::-1]


def count_bases(seq: str) -> Dict[str, int]:
    """Count occurrence of individual bases or residues."""
    cleaned = clean_sequence(seq)
    counts: Dict[str, int] = {}
    for char in cleaned:
        counts[char] = counts.get(char, 0) + 1
    return counts


def calculate_gc_content(seq: str) -> float:
    """Calculate GC percentage of a DNA or RNA sequence (0.0 to 100.0)."""
    cleaned = clean_sequence(seq)
    if not cleaned:
        return 0.0
    gc_count = cleaned.count("G") + cleaned.count("C")
    return round((gc_count / len(cleaned)) * 100.0, 2)


def translate_dna(seq: str, frame: int = 1, to_stop: bool = False) -> str:
    """Translate DNA sequence to amino acids.

    Parameters
    ----------
    seq : str
        Input DNA nucleotide sequence.
    frame : int
        Reading frame (+1, +2, +3 for forward; -1, -2, -3 for reverse strand).
    to_stop : bool
        If True, terminates translation upon encountering the first stop codon '*'.
    """
    if frame not in (1, 2, 3, -1, -2, -3):
        raise ValueError(f"Reading frame must be 1, 2, 3, -1, -2, or -3 (got {frame}).")

    if frame > 0:
        cleaned = clean_sequence(seq).replace("U", "T")
        start = frame - 1
    else:
        cleaned = reverse_complement(seq, seq_type="dna")
        start = abs(frame) - 1

    protein = []
    for i in range(start, len(cleaned) - 2, 3):
        codon = cleaned[i:i+3]
        amino_acid = CODON_TABLE.get(codon, "X")
        if to_stop and amino_acid == "*":
            break
        protein.append(amino_acid)
    return "".join(protein)


def transcribe(dna_seq: str) -> str:
    """Transcribe DNA sequence to RNA by replacing T with U.

    Strips whitespace, numbers, FASTA headers, and converts to uppercase.
    """
    cleaned = clean_sequence(dna_seq)
    return cleaned.replace("T", "U")


def reverse_transcribe(rna_seq: str) -> str:
    """Reverse transcribe RNA sequence to cDNA/DNA by replacing U with T.

    Strips whitespace, numbers, FASTA headers, and converts to uppercase.
    """
    cleaned = clean_sequence(rna_seq)
    return cleaned.replace("U", "T")


def six_frame_translation(seq: str, to_stop: bool = False) -> Dict[int, str]:
    """Translate nucleotide sequence in all six reading frames (+1, +2, +3, -1, -2, -3).

    Parameters
    ----------
    seq : str
        Input nucleotide sequence (DNA or RNA).
    to_stop : bool
        If True, terminates translation upon encountering the first stop codon in each frame.

    Returns
    -------
    Dict[int, str]
        Dictionary with keys +1, +2, +3, -1, -2, -3 mapped to translated protein sequences.
    """
    return {
        1: translate_dna(seq, frame=1, to_stop=to_stop),
        2: translate_dna(seq, frame=2, to_stop=to_stop),
        3: translate_dna(seq, frame=3, to_stop=to_stop),
        -1: translate_dna(seq, frame=-1, to_stop=to_stop),
        -2: translate_dna(seq, frame=-2, to_stop=to_stop),
        -3: translate_dna(seq, frame=-3, to_stop=to_stop),
    }


@dataclass(frozen=True)
class ORF:
    frame: int
    start_nt: int
    end_nt: int
    length_nt: int
    length_aa: int
    dna_sequence: str
    protein_sequence: str


def find_orfs(seq: str, min_length_aa: int = 30) -> List[ORF]:
    """Scan reading frames (+1, +2, +3, -1, -2, -3) for ATG start codons up to in-frame stops.

    Parameters
    ----------
    seq : str
        Input nucleotide sequence (DNA or RNA).
    min_length_aa : int
        Minimum protein length in amino acids (excluding stop codon) to report. Default is 30.

    Returns
    -------
    List[ORF]
        List of identified ORF objects containing frame, coordinates, lengths, and sequences.
    """
    cleaned = clean_sequence(seq).replace("U", "T")
    seq_len = len(cleaned)
    if seq_len < 3:
        return []

    orfs: List[ORF] = []

    for frame in (1, 2, 3, -1, -2, -3):
        strand_seq = cleaned if frame > 0 else reverse_complement(cleaned, seq_type="dna")
        offset = abs(frame) - 1
        i = offset
        while i <= len(strand_seq) - 3:
            if strand_seq[i:i+3] == "ATG":
                stop_idx = None
                for j in range(i + 3, len(strand_seq) - 2, 3):
                    if strand_seq[j:j+3] in ("TAA", "TAG", "TGA"):
                        stop_idx = j
                        break
                if stop_idx is not None:
                    dna_sub = strand_seq[i:stop_idx + 3]
                    prot_sub = translate_dna(dna_sub, to_stop=True)
                    if len(prot_sub) >= min_length_aa:
                        length_nt = len(dna_sub)
                        length_aa = len(prot_sub)
                        if frame > 0:
                            start_nt = i + 1
                            end_nt = stop_idx + 3
                        else:
                            start_nt = seq_len - (stop_idx + 3) + 1
                            end_nt = seq_len - i
                        orfs.append(
                            ORF(
                                frame=frame,
                                start_nt=start_nt,
                                end_nt=end_nt,
                                length_nt=length_nt,
                                length_aa=length_aa,
                                dna_sequence=dna_sub,
                                protein_sequence=prot_sub,
                            )
                        )
                    i = stop_idx + 3
                    continue
            i += 3

    return orfs


def parse_fasta(text_or_path: str) -> List[Tuple[str, str]]:
    """Parse FASTA formatted text or a FASTA file into a list of (header, sequence) tuples.

    Parameters
    ----------
    text_or_path : str
        FASTA formatted string or path to a FASTA file.

    Returns
    -------
    List[Tuple[str, str]]
        List of (header, sequence) tuples. Header excludes leading '>'.
        Sequence is cleaned of whitespace and converted to uppercase.
    """
    if not text_or_path:
        return []

    content = text_or_path
    if not (">" in text_or_path and "\n" in text_or_path):
        try:
            if os.path.exists(text_or_path) and os.path.isfile(text_or_path):
                with open(text_or_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
        except (ValueError, OSError):
            content = text_or_path

    records: List[Tuple[str, str]] = []
    current_header: Optional[str] = None
    current_seq_parts: List[str] = []

    for line in content.splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        if line_str.startswith(">"):
            if current_header is not None:
                seq = "".join(current_seq_parts).replace(" ", "").upper()
                records.append((current_header, seq))
            current_header = line_str[1:].strip()
            current_seq_parts = []
        else:
            if current_header is not None:
                current_seq_parts.append(line_str)

    if current_header is not None:
        seq = "".join(current_seq_parts).replace(" ", "").upper()
        records.append((current_header, seq))

    return records


def format_fasta(header: str, seq: str, line_length: int = 60) -> str:
    """Format a header and sequence into standard FASTA format.

    Parameters
    ----------
    header : str
        Description or identifier line (leading '>' is added if absent).
    seq : str
        Nucleotide or amino acid sequence.
    line_length : int
        Maximum number of sequence characters per line (default: 60).
        If <= 0, sequence is formatted on a single line.

    Returns
    -------
    str
        Formatted FASTA string.
    """
    h = header.strip()
    if not h.startswith(">"):
        h = f">{h}"
    cleaned = re.sub(r'[^A-Za-z*]', '', seq).upper()
    if line_length <= 0 or not cleaned:
        return f"{h}\n{cleaned}" if cleaned else f"{h}\n"

    lines = [cleaned[i:i + line_length] for i in range(0, len(cleaned), line_length)]
    return f"{h}\n" + "\n".join(lines)
