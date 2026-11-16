"""Sequence Storage, Catalog, and FASTA I/O for BioLabCalc.

Provides immutable data structures (TEA-compliant) for DNA, RNA, and protein sequences,
standard biological sequence catalog, JSON persistence, and FASTA file format handling.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

from .seq_utils import clean_sequence, calculate_gc_content
from .molecular_weight import calculate_dna_mw, calculate_rna_mw, calculate_protein_mw


@dataclass(frozen=True)
class SequenceAnnotation:
    """Immutable sequence annotation record.
    
    Coordinates are 1-based inclusive [start .. end].
    """
    name: str
    feature_type: str
    start: int
    end: int
    strand: int = 1
    notes: str = ""


@dataclass(frozen=True)
class SequenceRecord:
    """Immutable sequence entity record adhering to TEA immutability principles.
    
    All biophysical metrics (length, checksum, GC percentage, molecular weight)
    are calculated deterministically in __post_init__.
    """
    id: str
    name: str
    sequence: str
    seq_type: str = "dna"
    topology: str = "linear"
    annotations: Tuple[SequenceAnnotation, ...] = ()
    description: str = ""
    checksum: str = ""
    length: int = 0
    gc_percent: float = 0.0
    molecular_weight_da: float = 0.0

    def __post_init__(self) -> None:
        # Guarantee annotations is an immutable tuple
        if not isinstance(self.annotations, tuple):
            object.__setattr__(self, "annotations", tuple(self.annotations))

        clean_seq = clean_sequence(self.sequence)
        object.__setattr__(self, "sequence", clean_seq)

        L = len(clean_seq)
        object.__setattr__(self, "length", L)

        if not self.id:
            object.__setattr__(self, "id", self.name if self.name else f"seq_{L}bp")

        cs = hashlib.sha256(clean_seq.encode("utf-8")).hexdigest()[:16]
        object.__setattr__(self, "checksum", cs)

        gc = calculate_gc_content(clean_seq)
        object.__setattr__(self, "gc_percent", gc)

        if L == 0:
            mw = 0.0
        else:
            st = self.seq_type.lower()
            if st == "rna":
                mw = calculate_rna_mw(clean_seq).average_mw
            elif st in ("protein", "peptide", "aa"):
                mw = calculate_protein_mw(clean_seq).average_mw
            else:
                is_ds = self.topology.lower() in ("dsdna", "double_stranded")
                mw = calculate_dna_mw(clean_seq, double_stranded=is_ds).average_mw

        object.__setattr__(self, "molecular_weight_da", mw)


# ---------------------------------------------------------------------------
# Standard Biological Sequence Catalog
# ---------------------------------------------------------------------------

DEFAULT_SEQUENCE_CATALOG: Dict[str, SequenceRecord] = {
    "T7_PROMOTER": SequenceRecord(
        id="T7_PROMOTER",
        name="T7 Promoter",
        sequence="TAATACGACTCACTATAGGG",
        seq_type="dna",
        topology="linear",
        description="Bacteriophage T7 RNA Polymerase Promoter (-17 to +3)",
        annotations=(SequenceAnnotation("T7_Promoter", "promoter", 1, 20, 1),),
    ),
    "SP6_PROMOTER": SequenceRecord(
        id="SP6_PROMOTER",
        name="SP6 Promoter",
        sequence="ATTTAGGTGACACTATAGAAGNG",
        seq_type="dna",
        topology="linear",
        description="Bacteriophage SP6 RNA Polymerase Promoter",
        annotations=(SequenceAnnotation("SP6_Promoter", "promoter", 1, 23, 1),),
    ),
    "T3_PROMOTER": SequenceRecord(
        id="T3_PROMOTER",
        name="T3 Promoter",
        sequence="AATTAACCCTCACTAAAGGG",
        seq_type="dna",
        topology="linear",
        description="Bacteriophage T3 RNA Polymerase Promoter",
        annotations=(SequenceAnnotation("T3_Promoter", "promoter", 1, 20, 1),),
    ),
    "GLUK2_EXON1_AMPLICON": SequenceRecord(
        id="GLUK2_EXON1_AMPLICON",
        name="GluK2 Exon 1 PCR Amplicon",
        sequence=(
            "ATGAAGATTATTTTCTTTTTTGTGTTGTTTTCCATTTTCCTGGGTTTGTTAGTATTTTCCTGGGGAAGGAAA"
            "AGAAGAATAAAACACTCTGAAAACAAAGGAAGTCAGGACAAACTTTTT"
        ),
        seq_type="dna",
        topology="dsdna",
        description="Human GluK2 (GRIK2) exon 1 diagnostic PCR amplicon (120 bp dsDNA)",
        annotations=(SequenceAnnotation("GluK2_Exon1", "exon", 1, 120, 1),),
    ),
    "GLUA1_LBD_CDS": SequenceRecord(
        id="GLUA1_LBD_CDS",
        name="GluA1 LBD CDS",
        sequence=(
            "ATGGCAGATCCAGTGTTTGTTGAAAGTCCTGAAGATTTTTTGAAATTCTCTGTAGGAGCTCTTGGTGGACCCATTGAATTTCAGAAGTTTACTTCACGACCTCGTTATCATCGTTTTGATGTAAAGCTCGGTGTGACTCCA"
            "GATGACTTGGAAGATGTGATGATGTTTGCTCACCAGTATGTACAGAGATACCCAGATTTTGAAACTGTGGAGAGTACTTCATACAACTACAACTTGAAAAAGAAACGTGATGGCTTTTTGTTCATCCTTGAGGATGATGAG"
            "TATGTAAACAGATACACAGAACTCGAAAAGGCTGATAAAAACTTGTATACTGTTGGTTATATGAACACACCAACATATTACTACCGTGAAGTAGCTAAATCTCTCGGTTTGCCAATTGAAAGTTTTCGTGACTTTATGAGA"
            "AACAACGAATATTACTTCCGTCCAAGTCGTTACTACATGAGATTCATGCTCGGTATGATTCACTCATATCCAAGTGATATCAAGATGGTTCCATACGAAGGTGAATTCACAGTGTTTTTTGATTATCGTAACTTCAACTAC"
            "AAGTATTACTTCACAGGTGAACGTGCTCCAAATATCAAACGTATTGAAGGTGAAGTTTACACTATTGGTTTTGGTTATCTCGATATGGAAGAAGCTTTTGAAGGTCTCGATCTTGTAGTAAAACGTGATATTCGTGTAGTA"
            "CCAGCTCCATTTCGTCGTGATTACTCTACTGAATATTACTTTAAATAA"
        ),
        seq_type="dna",
        topology="linear",
        description="GluA1 (GRIA1) ligand binding domain (S1S2) coding sequence",
        annotations=(SequenceAnnotation("GluA1_LBD", "CDS", 1, 753, 1),),
    ),
    "AB9SR_APTAMER": SequenceRecord(
        id="AB9SR_APTAMER",
        name="AB9SR RNA Aptamer",
        sequence="GGGAGAAUUCAACUGCCAUCUAGACUGUACUCGCUGAACUACGCUUCCUAGGACGACAUAUUGGAUGAGUUCAUCCG",
        seq_type="rna",
        topology="linear",
        description="High-affinity synthetic RNA aptamer AB9SR (79 nt)",
        annotations=(SequenceAnnotation("AB9SR_Core", "misc_feature", 1, 79, 1),),
    ),
    "EGFP_CDS": SequenceRecord(
        id="EGFP_CDS",
        name="EGFP Coding Sequence",
        sequence=(
            "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTAAACGGCCACAAGTTCAGCGTGTCCGGCGAGGGCGAGGGCGATGCCACCTACGGCAAGCTGACCCTGAAGTTC"
            "ATCTGCACCACCGGCAAGCTGCCCGTGCCCTGGCCCACCCTCGTGACCACCCTGACCTACGGCGTGCAGTGCTTCAGCCGCTACCCCGACCACATGAAGCAGCACGACTTCTTCAAGTCCGCCATGCCCGAAGGCTACGTCC"
            "AGGAGCGCACCATCTTCTTCAAGGACGACGGCAACTACAAGACCCGCGCCGAGGTGAAGTTCGAGGGCGACACCCTGGTGAACCGCATCGAGCTGAAGGGCATCGACTTCAAGGAGGACGGCAACATCCTGGGGCACAAGC"
            "TGGAGTACAACTACAACAGCCACAACGTCTATATCATGGCCGACAAGCAGAAGAACGGCATCAAGGTGAACTTCAAGATCCGCCACAACATCGAGGACGGCAGCGTGCAGCTCGCCGACCACTACCAGCAGAACACCCCCAT"
            "CGGCGACGGCCCCGTGCTGCTGCCCGACAACCACTACCTGAGCACCCAGTCCGCCCTGAGCAAAGACCCCAACGAGAAGCGCGATCACATGGTCCTGCTGGAGTTCGTGACCGCCGCCGGGATCACTCTCGGCATGGACGAG"
            "CTGTACAAGTAA"
        ),
        seq_type="dna",
        topology="linear",
        description="Enhanced Green Fluorescent Protein (EGFP) coding sequence (720 bp)",
        annotations=(SequenceAnnotation("EGFP", "CDS", 1, 720, 1),),
    ),
    "HIS6_TEV_TAG": SequenceRecord(
        id="HIS6_TEV_TAG",
        name="His6-TEV Cleavable Tag",
        sequence="CATCATCATCATCATCACGAAAACCTGTACTTCCAAGGC",
        seq_type="dna",
        topology="linear",
        description="Hexahistidine (6xHis) tag fused with TEV protease cleavage site (ENLYFQG)",
        annotations=(
            SequenceAnnotation("6xHis", "tag", 1, 18, 1),
            SequenceAnnotation("TEV_site", "protein_bind", 19, 39, 1),
        ),
    ),
    "KANR_CDS": SequenceRecord(
        id="KANR_CDS",
        name="Kanamycin Resistance CDS",
        sequence=(
            "ATGAGCCATATTCAACGGGAAACGTCTTGCTCGAGGCCGCGATTAAATTCCAACATGGATGCTGATTTATATGGGTATAAATGGGCTCGCGATAATGTCGGGCAATCAGGTGCGACAATCTATCGATTGTATGGGAAGCC"
            "CGATGCGCCAGAGTTGTTTCTGAAACATGGCAAAGGTAGCGTTGCCAATGATGTTACAGATGAGATGGTCAGACTAAACTGGCTGACGGAATTTATGCCTCTTCCGACCATCAAGCATTTTATCCGTACTCCTGATGATG"
            "CATGGTTACTCACCACTGCGATCCCCGGGAAAACAGCATTCCAGGTATTAGAAGAATATCCTGATTCAGGTGAAAATATTGTTGATGCGCTGGCAGTGTTCCTGCGCCGGTTGCATTCGATTCCTGTTTGTAATTGTCCT"
            "TTTAACAGCGATCGCGTATTTCGTCTCGCTCAGGCGCAATCACGAATGAATAACGGTTTGGTTGATGCGAGTGATTTTGATGACGAGCGTAATGGCTGGCCTGTTGAACAAGTCTGGAAAGAAATGCATAAACTTTTGCCA"
            "TTCTCACCGGATTCAGTCGTCACTCATGGTGATTTCTCACTTGATAACCTTATTTTTGACGAGGGGAAATTAATAGGTTGTATTGATGTTGGACGAGTCGGAATCGCAGACCGATACCAGGATCTTGCCATCCTATGGAAC"
            "TGCCTCGGTGAGTTTTCTCCTTCATTACAGAAACGGCTTTTTCAAAAATATGGTATTGATAATCCTGATATGAATAAATTGCAGTTTCATTTGATGCTCGATGAGTTTTTCTAA"
        ),
        seq_type="dna",
        topology="linear",
        description="Tn5 aphA1 / nptII kanamycin/neomycin resistance gene CDS (816 bp)",
        annotations=(SequenceAnnotation("KanR", "CDS", 1, 816, 1),),
    ),
    "AMPR_CDS": SequenceRecord(
        id="AMPR_CDS",
        name="Ampicillin Resistance CDS",
        sequence=(
            "ATGAGTATTCAACATTTTCGTGTCGCCCTTATTCCCTTTTTTGCGGCATTTTGCCTTCCTGTTTTTGCTCACCCAGAAACGCTGGTGAAAGTAAAAGATGCTGAAGATCAGTTGGGTGCACGAGTGGGTTACATCGAAC"
            "TGGATCTCAACAGCGGTAAGATCCTTGAGAGTTTTCGCCCCGAAGAACGTTTTCCAATGATGAGCACTTTTAAAGTTCTGCTATGTGGCGCGGTATTATCCCGTATTGACGCCGGGCAAGAGCAACTCGGTCGCCGCATAC"
            "ACTATTCTCAGAATGACTTGGTTGAGTACTCACCAGTCACAGAAAAGCATCTTACGGATGGCATGACAGTAAGAGAATTATGCAGTGCTGCCATAACCATGAGTGATAACACTGCGGCCAACTTACTTCTGACAACGATC"
            "GGAGGACCGAAGGAGCTAACCGCTTTTTTGCACAACATGGGGGATCATGTAACTCGCCTTGATCGTTGGGAACCGGAGCTGAATGAAGCCATACCAAACGACGAGCGTGACACCACGATGCCTGTAGCAATGGCAACAA"
            "CGTTGCGCAAACTATTAACTGGCGAACTACTTACTCTAGCTTCCCGGCAACAATTAATAGACTGGATGGAGGCGGATAAAGTTGCAGGACCACTTCTGCGCTCGGCCCTTCCGGCTGGCTGGTTTATTGCTGATAAATCT"
            "GGAGCCGGTGAGCGTGGGTCTCGCGGTATCATTGCAGCACTGGGGCCAGATGGTAAGCCCTCCCGTATCGTAGTTATCTACACGACGGGGAGTCAGGCAACTATGGATGAACGAAATAGACAGATCGCTGAGATAGGT"
            "GCCTCACTGATTAAGCATTGGTAA"
        ),
        seq_type="dna",
        topology="linear",
        description="TEM-1 beta-lactamase (bla) conferring ampicillin resistance (861 bp)",
        annotations=(SequenceAnnotation("AmpR", "CDS", 1, 861, 1),),
    ),
}


# ---------------------------------------------------------------------------
# JSON Persistence Helpers
# ---------------------------------------------------------------------------

DEFAULT_SEQUENCES_PATH: str = os.path.expanduser("~/.biolabcalc/sequences.json")


def _annotation_to_dict(ann: SequenceAnnotation) -> Dict[str, Any]:
    return {
        "name": ann.name,
        "feature_type": ann.feature_type,
        "start": ann.start,
        "end": ann.end,
        "strand": ann.strand,
        "notes": ann.notes,
    }


def _annotation_from_dict(d: Dict[str, Any]) -> SequenceAnnotation:
    return SequenceAnnotation(
        name=d.get("name", ""),
        feature_type=d.get("feature_type", "misc_feature"),
        start=d.get("start", 1),
        end=d.get("end", 1),
        strand=d.get("strand", 1),
        notes=d.get("notes", ""),
    )


def _record_to_dict(rec: SequenceRecord) -> Dict[str, Any]:
    return {
        "id": rec.id,
        "name": rec.name,
        "sequence": rec.sequence,
        "seq_type": rec.seq_type,
        "topology": rec.topology,
        "annotations": [_annotation_to_dict(a) for a in rec.annotations],
        "description": rec.description,
        "checksum": rec.checksum,
        "length": rec.length,
        "gc_percent": rec.gc_percent,
        "molecular_weight_da": rec.molecular_weight_da,
    }


def _record_from_dict(d: Dict[str, Any]) -> SequenceRecord:
    annotations = tuple(_annotation_from_dict(a) for a in d.get("annotations", []))
    return SequenceRecord(
        id=d.get("id", ""),
        name=d.get("name", ""),
        sequence=d.get("sequence", ""),
        seq_type=d.get("seq_type", "dna"),
        topology=d.get("topology", "linear"),
        annotations=annotations,
        description=d.get("description", ""),
        checksum=d.get("checksum", ""),
        length=d.get("length", 0),
        gc_percent=d.get("gc_percent", 0.0),
        molecular_weight_da=d.get("molecular_weight_da", 0.0),
    )


def _load_user_records(filepath: Optional[str] = None) -> Dict[str, SequenceRecord]:
    target_path = filepath if filepath is not None else DEFAULT_SEQUENCES_PATH
    if not os.path.exists(target_path):
        return {}
    if os.path.getsize(target_path) == 0:
        return {}
    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    records: Dict[str, SequenceRecord] = {}
    if isinstance(data, list):
        for item in data:
            rec = _record_from_dict(item)
            records[rec.id] = rec
    elif isinstance(data, dict):
        for item in data.values():
            rec = _record_from_dict(item)
            records[rec.id] = rec
    return records


def _save_user_records(records: Dict[str, SequenceRecord], filepath: Optional[str] = None) -> None:
    target_path = filepath if filepath is not None else DEFAULT_SEQUENCES_PATH
    dir_name = os.path.dirname(os.path.abspath(target_path))
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)
    serialized = [_record_to_dict(rec) for rec in records.values()]
    temp_fd, temp_file = tempfile.mkstemp(dir=dir_name, prefix=".tmp_seq_", suffix=".json")
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2)
        os.replace(temp_file, target_path)
    except Exception:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
        raise


def save_sequence(record: SequenceRecord, filepath: Optional[str] = None) -> str:
    """Save a SequenceRecord to the JSON store.
    
    Parameters
    ----------
    record : SequenceRecord
        The sequence record to persist.
    filepath : Optional[str]
        Optional custom storage file path (defaults to DEFAULT_SEQUENCES_PATH).
        
    Returns
    -------
    str
        The saved sequence ID.
    """
    records = _load_user_records(filepath)
    records[record.id] = record
    _save_user_records(records, filepath)
    return record.id


def get_sequence(seq_id_or_name: str, filepath: Optional[str] = None) -> SequenceRecord:
    """Retrieve a SequenceRecord by ID or Name.
    
    Searches user persistent store first, then falls back to DEFAULT_SEQUENCE_CATALOG.
    Case-insensitive matching is supported.
    
    Raises
    ------
    KeyError
        If the sequence cannot be found in user storage or catalog.
    """
    records = _load_user_records(filepath)

    # 1. Exact ID in user store
    if seq_id_or_name in records:
        return records[seq_id_or_name]

    # 2. Case-insensitive ID or name in user store
    query_lower = seq_id_or_name.lower()
    for rec in records.values():
        if rec.id.lower() == query_lower or rec.name.lower() == query_lower:
            return rec

    # 3. Exact ID in default catalog
    if seq_id_or_name in DEFAULT_SEQUENCE_CATALOG:
        return DEFAULT_SEQUENCE_CATALOG[seq_id_or_name]

    # 4. Case-insensitive key or name in default catalog
    for key, rec in DEFAULT_SEQUENCE_CATALOG.items():
        if key.lower() == query_lower or rec.name.lower() == query_lower or rec.id.lower() == query_lower:
            return rec

    raise KeyError(f"Sequence '{seq_id_or_name}' not found in user storage or catalog.")


def list_sequences(filepath: Optional[str] = None) -> List[SequenceRecord]:
    """List all sequences from user storage merged with DEFAULT_SEQUENCE_CATALOG.
    
    User records override catalog items with identical IDs.
    """
    records = _load_user_records(filepath)
    merged: Dict[str, SequenceRecord] = dict(DEFAULT_SEQUENCE_CATALOG)
    for rec_id, rec in records.items():
        merged[rec_id] = rec
    return list(merged.values())


def delete_sequence(seq_id_or_name: str, filepath: Optional[str] = None) -> bool:
    """Delete a sequence from user storage by ID or name.
    
    Returns True if found and deleted, False otherwise.
    Note: Default catalog items are immutable and cannot be deleted from memory catalog.
    """
    records = _load_user_records(filepath)
    target_id: Optional[str] = None

    if seq_id_or_name in records:
        target_id = seq_id_or_name
    else:
        query_lower = seq_id_or_name.lower()
        for rec in records.values():
            if rec.id.lower() == query_lower or rec.name.lower() == query_lower:
                target_id = rec.id
                break

    if target_id is not None:
        del records[target_id]
        _save_user_records(records, filepath)
        return True

    return False


# ---------------------------------------------------------------------------
# FASTA I/O
# ---------------------------------------------------------------------------

def import_fasta(
    fasta_text_or_path: str,
    filepath: Optional[str] = None,
) -> List[SequenceRecord]:
    """Parse FASTA string or file into SequenceRecord objects and optionally persist to JSON store.
    
    Parameters
    ----------
    fasta_text_or_path : str
        FASTA formatted text or absolute/relative path to a .fasta/.fa file.
    filepath : Optional[str]
        If provided, the imported records are saved to this JSON store file.
    """
    if os.path.isfile(fasta_text_or_path):
        with open(fasta_text_or_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = fasta_text_or_path

    records: List[SequenceRecord] = []
    current_header: str = ""
    current_seq_lines: List[str] = []

    def flush() -> None:
        nonlocal current_header, current_seq_lines
        if current_header:
            parts = current_header.split(maxsplit=1)
            rec_id = parts[0]
            desc = parts[1] if len(parts) > 1 else ""
            seq_str = "".join(current_seq_lines)
            rec = SequenceRecord(
                id=rec_id,
                name=rec_id,
                sequence=seq_str,
                description=desc,
            )
            records.append(rec)
        current_header = ""
        current_seq_lines = []

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(">"):
            flush()
            current_header = line[1:].strip()
        else:
            current_seq_lines.append(line)
    flush()

    if filepath is not None:
        for r in records:
            save_sequence(r, filepath)

    return records


def export_fasta(records: List[SequenceRecord], filepath: Optional[str] = None) -> str:
    """Format SequenceRecords into standard FASTA format and optionally write to file.
    
    Parameters
    ----------
    records : List[SequenceRecord]
        List of records to format.
    filepath : Optional[str]
        Optional path to write FASTA file.
        
    Returns
    -------
    str
        The formatted FASTA content.
    """
    lines: List[str] = []
    for rec in records:
        desc_part = f" {rec.description}" if rec.description else (f" {rec.name}" if rec.name != rec.id else "")
        lines.append(f">{rec.id}{desc_part}")
        seq = rec.sequence
        for i in range(0, len(seq), 60):
            lines.append(seq[i:i+60])
    fasta_str = "\n".join(lines) + ("\n" if lines else "")

    if filepath is not None:
        dir_name = os.path.dirname(filepath)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(fasta_str)

    return fasta_str
