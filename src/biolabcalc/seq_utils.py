"""Sequence utilities for DNA, RNA, and protein manipulation."""

from __future__ import annotations
import re
from typing import Dict

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
    """Strip FASTA header lines, whitespace, numbers, and special characters, converting to uppercase."""
    lines = [line.strip() for line in seq.splitlines() if not line.strip().startswith('>')]
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
        return bool(re.fullmatch(r'[ACDEFGHIKLMNPQRSTVWY*]+', cleaned))
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
