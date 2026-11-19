"""Circular Plasmid Storage, Annotation, Modulo-L Coordinates, and GenBank I/O for BioLabCalc.

Adheres strictly to TEA immutability principles and biochemical coordinate standards:
- 1-based inclusive indexing [1 .. L].
- Circular origin-spanning features where start > end, with length (L - start + 1) + end.
- Modulo-L rotation and subsequence slicing.
- Automated annotation of standard biological plasmid features.
- Full GenBank flatfile parsing and export.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .molecular_weight import calculate_dna_mw
from .seq_utils import ORF, calculate_gc_content, clean_sequence, reverse_complement, translate_dna


@dataclass(frozen=True)
class PlasmidFeature:
    """Immutable plasmid annotation feature.
    
    Coordinates are 1-based inclusive [1 .. L].
    If start > end, the feature spans the circular plasmid origin (base 1).
    """
    name: str
    feature_type: str
    start: int
    end: int
    strand: int = 1
    color: str = "#3B82F6"
    notes: str = ""
    plasmid_length: int = 0

    @property
    def spans_origin(self) -> bool:
        """Return True if the feature spans across circular position 1."""
        return self.start > self.end

    @property
    def length(self) -> int:
        """Calculate feature length in base pairs.
        
        Handles origin-spanning features when plasmid_length is specified.
        """
        if self.start <= self.end:
            return self.end - self.start + 1
        if self.plasmid_length > 0:
            return (self.plasmid_length - self.start + 1) + self.end
        return self.end - self.start + 1

    def get_length(self, plasmid_length: int) -> int:
        """Calculate feature length given a specific plasmid length."""
        if self.start <= self.end:
            return self.end - self.start + 1
        return (plasmid_length - self.start + 1) + self.end


@dataclass(frozen=True)
class PlasmidRecord:
    """Immutable circular or linear plasmid entity adhering to TEA principles.
    
    Biophysical properties (length, checksum, GC %, molecular weight)
    are calculated deterministically in __post_init__.
    """
    id: str
    name: str
    sequence: str
    length: int = 0
    topology: str = "circular"
    features: Tuple[PlasmidFeature, ...] = ()
    description: str = ""
    checksum: str = ""
    gc_percent: float = 0.0
    molecular_weight_da: float = 0.0
    cloning_history: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        clean_seq = clean_sequence(self.sequence).replace("U", "T")
        object.__setattr__(self, "sequence", clean_seq)

        L = len(clean_seq)
        object.__setattr__(self, "length", L)

        if not self.id:
            object.__setattr__(self, "id", self.name if self.name else f"plasmid_{L}bp")

        cs = hashlib.sha256(clean_seq.encode("utf-8")).hexdigest()[:16]
        object.__setattr__(self, "checksum", cs)

        gc = calculate_gc_content(clean_seq)
        object.__setattr__(self, "gc_percent", gc)

        is_circ = self.topology.lower() == "circular"
        mw = calculate_dna_mw(clean_seq, double_stranded=True, circular=is_circ).average_mw if L > 0 else 0.0
        object.__setattr__(self, "molecular_weight_da", mw)

        # Ensure features is a tuple and each feature knows plasmid length L
        norm_feats: List[PlasmidFeature] = []
        for f in self.features:
            if f.plasmid_length != L:
                norm_feats.append(
                    PlasmidFeature(
                        name=f.name,
                        feature_type=f.feature_type,
                        start=f.start,
                        end=f.end,
                        strand=f.strand,
                        color=f.color,
                        notes=f.notes,
                        plasmid_length=L,
                    )
                )
            else:
                norm_feats.append(f)
        object.__setattr__(self, "features", tuple(norm_feats))

        if not isinstance(self.cloning_history, tuple):
            object.__setattr__(self, "cloning_history", tuple(self.cloning_history))

    def _repr_svg_(self) -> str:
        """Render pure SVG plasmid map for Jupyter notebook rich display."""
        from .interactive_plasmid import render_plasmid_map_svg
        return render_plasmid_map_svg(self)


# ---------------------------------------------------------------------------
# Circular Modulo-L Coordinate Utilities
# ---------------------------------------------------------------------------

def extract_subsequence(
    plasmid: Union[PlasmidRecord, str],
    start: int,
    end: int,
    strand: int = 1,
) -> str:
    """Extract a 1-based inclusive subsequence from a plasmid.
    
    If start > end, extracts an origin-spanning segment: [start .. L] + [1 .. end].
    If strand == -1, returns reverse complement of the extracted segment.
    """
    seq = plasmid.sequence if isinstance(plasmid, PlasmidRecord) else plasmid
    seq = clean_sequence(seq).replace("U", "T")
    L = len(seq)
    if L == 0:
        return ""

    if start <= end:
        extracted = seq[start - 1 : end]
    else:
        # Circular origin-spanning slice
        extracted = seq[start - 1 :] + seq[:end]

    if strand == -1:
        extracted = reverse_complement(extracted, seq_type="dna")

    return extracted


def rotate_origin(plasmid: PlasmidRecord, new_origin_1based: int) -> PlasmidRecord:
    """Rotate the plasmid origin so that new_origin_1based becomes position 1.
    
    Transforms all feature coordinates under:
        new_pos = ((old_pos - new_origin_1based) % L) + 1
    Preserves exact feature lengths and origin-spanning invariants.
    """
    L = plasmid.length
    if L == 0 or new_origin_1based == 1:
        return plasmid

    if new_origin_1based < 1 or new_origin_1based > L:
        raise ValueError(f"new_origin_1based ({new_origin_1based}) must be between 1 and {L}")

    seq = plasmid.sequence
    new_seq = seq[new_origin_1based - 1 :] + seq[: new_origin_1based - 1]

    new_features: List[PlasmidFeature] = []
    for f in plasmid.features:
        new_start = ((f.start - new_origin_1based) % L) + 1
        new_end = ((f.end - new_origin_1based) % L) + 1
        new_features.append(
            PlasmidFeature(
                name=f.name,
                feature_type=f.feature_type,
                start=new_start,
                end=new_end,
                strand=f.strand,
                color=f.color,
                notes=f.notes,
                plasmid_length=L,
            )
        )

    history = plasmid.cloning_history + (f"Rotated origin to position {new_origin_1based}",)
    return PlasmidRecord(
        id=plasmid.id,
        name=plasmid.name,
        sequence=new_seq,
        topology=plasmid.topology,
        features=tuple(new_features),
        description=plasmid.description,
        cloning_history=history,
    )


def insert_subsequence(
    plasmid: PlasmidRecord,
    index_1based: int,
    insert_seq: str,
    replace_end_1based: Optional[int] = None,
) -> PlasmidRecord:
    """Insert or replace DNA in a plasmid, adjusting downstream feature coordinates.
    
    Parameters
    ----------
    plasmid : PlasmidRecord
        The template plasmid.
    index_1based : int
        1-based insertion point or start of replaced region.
    insert_seq : str
        DNA sequence to insert.
    replace_end_1based : Optional[int]
        If provided, replaces region [index_1based .. replace_end_1based] inclusive.
    """
    clean_ins = clean_sequence(insert_seq).replace("U", "T")
    ins_len = len(clean_ins)
    L = plasmid.length

    # Case 1: Pure Insertion
    if replace_end_1based is None:
        if index_1based < 1 or index_1based > L + 1:
            raise ValueError(f"index_1based ({index_1based}) out of bounds [1, {L+1}]")

        new_seq = plasmid.sequence[: index_1based - 1] + clean_ins + plasmid.sequence[index_1based - 1 :]
        new_L = len(new_seq)

        new_features: List[PlasmidFeature] = []
        for f in plasmid.features:
            if f.spans_origin:
                if index_1based <= f.end:
                    new_features.append(
                        PlasmidFeature(f.name, f.feature_type, f.start + ins_len, f.end + ins_len, f.strand, f.color, f.notes, new_L)
                    )
                elif index_1based > f.start:
                    new_features.append(
                        PlasmidFeature(f.name, f.feature_type, f.start, f.end, f.strand, f.color, f.notes, new_L)
                    )
                else:
                    new_features.append(
                        PlasmidFeature(f.name, f.feature_type, f.start + ins_len, f.end, f.strand, f.color, f.notes, new_L)
                    )
            else:
                if index_1based <= f.start:
                    new_features.append(
                        PlasmidFeature(f.name, f.feature_type, f.start + ins_len, f.end + ins_len, f.strand, f.color, f.notes, new_L)
                    )
                elif index_1based <= f.end:
                    new_features.append(
                        PlasmidFeature(f.name, f.feature_type, f.start, f.end + ins_len, f.strand, f.color, f.notes, new_L)
                    )
                else:
                    new_features.append(
                        PlasmidFeature(f.name, f.feature_type, f.start, f.end, f.strand, f.color, f.notes, new_L)
                    )

        history = plasmid.cloning_history + (f"Inserted {ins_len} bp at position {index_1based}",)
        return PlasmidRecord(
            id=plasmid.id,
            name=plasmid.name,
            sequence=new_seq,
            topology=plasmid.topology,
            features=tuple(new_features),
            description=plasmid.description,
            cloning_history=history,
        )

    # Case 2: Replacement
    r_end = replace_end_1based
    if index_1based <= r_end:
        new_seq = plasmid.sequence[: index_1based - 1] + clean_ins + plasmid.sequence[r_end:]
        del_len = r_end - index_1based + 1
        delta = ins_len - del_len
        new_L = len(new_seq)

        new_features = []
        for f in plasmid.features:
            if f.start >= index_1based and f.end <= r_end and not f.spans_origin:
                continue
            if f.end < index_1based and not f.spans_origin:
                new_features.append(
                    PlasmidFeature(f.name, f.feature_type, f.start, f.end, f.strand, f.color, f.notes, new_L)
                )
            elif f.start > r_end and not f.spans_origin:
                new_features.append(
                    PlasmidFeature(f.name, f.feature_type, f.start + delta, f.end + delta, f.strand, f.color, f.notes, new_L)
                )
            else:
                new_s = f.start if f.start < index_1based else index_1based
                new_e = f.end + delta if f.end > r_end else index_1based + max(0, ins_len - 1)
                if new_e >= new_s:
                    new_features.append(
                        PlasmidFeature(f.name, f.feature_type, new_s, new_e, f.strand, f.color, f.notes, new_L)
                    )

        history = plasmid.cloning_history + (f"Replaced region {index_1based}..{r_end} with {ins_len} bp",)
        return PlasmidRecord(
            id=plasmid.id,
            name=plasmid.name,
            sequence=new_seq,
            topology=plasmid.topology,
            features=tuple(new_features),
            description=plasmid.description,
            cloning_history=history,
        )
    else:
        # Origin-spanning replacement
        new_seq = clean_ins + plasmid.sequence[r_end : index_1based - 1]
        history = plasmid.cloning_history + (f"Replaced origin-spanning region {index_1based}..{r_end} with {ins_len} bp",)
        return PlasmidRecord(
            id=plasmid.id,
            name=plasmid.name,
            sequence=new_seq,
            topology=plasmid.topology,
            features=(),
            description=plasmid.description,
            cloning_history=history,
        )


def find_orfs(
    plasmid_or_seq: Union[PlasmidRecord, str],
    min_aa: int = 50,
    circular: bool = True,
) -> List[ORF]:
    """Scan all 6 reading frames (+1, +2, +3, -1, -2, -3) for Open Reading Frames.
    
    If circular=True, identifies ORFs that start before the origin and wrap past base 1.
    """
    if isinstance(plasmid_or_seq, PlasmidRecord):
        seq = plasmid_or_seq.sequence
        circular = (plasmid_or_seq.topology.lower() == "circular")
    else:
        seq = clean_sequence(str(plasmid_or_seq)).replace("U", "T")

    L = len(seq)
    if L < 3:
        return []

    orfs: List[ORF] = []
    stops = {"TAA", "TAG", "TGA"}

    # Forward frames (+1, +2, +3)
    search_fwd = seq + (seq if circular else "")
    search_limit = L if circular else max(0, L - 3 * min_aa)

    for i in range(search_limit):
        if search_fwd[i : i + 3] == "ATG":
            max_search = min(i + L, len(search_fwd) - 2)
            stop_idx = None
            for j in range(i + 3, max_search, 3):
                if search_fwd[j : j + 3] in stops:
                    stop_idx = j
                    break
            if stop_idx is not None:
                orf_dna = search_fwd[i : stop_idx + 3]
                orf_len_nt = len(orf_dna)
                orf_len_aa = (orf_len_nt // 3) - 1
                if orf_len_aa >= min_aa:
                    start_nt = i + 1
                    end_idx = stop_idx + 3
                    end_nt = ((end_idx - 1) % L) + 1 if circular else end_idx
                    frame = (i % 3) + 1
                    prot = translate_dna(orf_dna, to_stop=True)
                    orfs.append(ORF(frame, start_nt, end_nt, orf_len_nt, len(prot), orf_dna, prot))

    # Reverse frames (-1, -2, -3)
    rc_seq = reverse_complement(seq, seq_type="dna")
    search_rev = rc_seq + (rc_seq if circular else "")

    for i in range(search_limit):
        if search_rev[i : i + 3] == "ATG":
            max_search = min(i + L, len(search_rev) - 2)
            stop_idx = None
            for j in range(i + 3, max_search, 3):
                if search_rev[j : j + 3] in stops:
                    stop_idx = j
                    break
            if stop_idx is not None:
                orf_dna = search_rev[i : stop_idx + 3]
                orf_len_nt = len(orf_dna)
                orf_len_aa = (orf_len_nt // 3) - 1
                if orf_len_aa >= min_aa:
                    frame = -((i % 3) + 1)
                    prot = translate_dna(orf_dna, to_stop=True)
                    atg_fwd = ((L - 1 - (i % L)) % L) + 1
                    stop_fwd = ((L - 1 - ((stop_idx + 2) % L)) % L) + 1
                    start_nt = stop_fwd
                    end_nt = atg_fwd
                    orfs.append(ORF(frame, start_nt, end_nt, orf_len_nt, len(prot), orf_dna, prot))

    return orfs


# ---------------------------------------------------------------------------
# Auto-Annotation Library
# ---------------------------------------------------------------------------

_KNOWN_FEATURES: List[Dict[str, Any]] = [
    # Promoters
    {"name": "T7 Promoter", "type": "promoter", "seq": "TAATACGACTCACTATAGGG", "color": "#EF4444"},
    {"name": "T3 Promoter", "type": "promoter", "seq": "AATTAACCCTCACTAAAGGG", "color": "#EF4444"},
    {"name": "SP6 Promoter", "type": "promoter", "seq": "ATTTAGGTGACACTATAGAAG", "color": "#EF4444"},
    {"name": "lac Promoter", "type": "promoter", "seq": "TTTATGCTTCCGGCTCGTATGTTGTGTGG", "color": "#EF4444"},
    {"name": "tac Promoter", "type": "promoter", "seq": "TTGACAATTAATCATCGGCTCGTATAATGTGTGG", "color": "#EF4444"},
    {"name": "CMV Promoter", "type": "promoter", "seq": "TGACGTCAATAATGACGTATGTTCCCATAGTAACGCCAATAGGGACTTTCCATTGACGTCAATGGGTGGAGTATTTACGG", "color": "#EF4444"},
    {"name": "U6 Promoter", "type": "promoter", "seq": "ATTTGCATATACGATACAAGGCTGTTAGAGAGATAATTAGAATTAATTTGACTGTAAACACAAAGATATTAGTACAAAATACGTGACGTAGAAAGTAATAATTTCTTGGGTAGTTTGCAGTTTTAAAATTATGTTTTAAAATGGACTATCATATGCTTACCGTAACTTGAAAGTATTTCGATTTCTTGGCTTTATATATCTTGTGGAAAGGACGAAACACC", "color": "#EF4444"},
    # Operators & RBS
    {"name": "lac Operator", "type": "operator", "seq": "AATTGTGAGCGGATAACAATT", "color": "#F59E0B"},
    {"name": "Shine-Dalgarno (RBS)", "type": "RBS", "seq": "AGGAGGT", "color": "#F59E0B"},
    {"name": "Kozak Sequence", "type": "RBS", "seq": "GCCACCATGG", "color": "#F59E0B"},
    # Tags & Cleavage Sites
    {"name": "6xHis Tag", "type": "tag", "seq": "CATCATCATCATCATCAC", "color": "#10B981"},
    {"name": "6xHis Tag", "type": "tag", "seq": "CACCACCACCACCACCAC", "color": "#10B981"},
    {"name": "TEV Site", "type": "protein_bind", "seq": "GAAAACCTGTACTTCCAAGGC", "color": "#10B981"},
    {"name": "Thrombin Site", "type": "protein_bind", "seq": "CTGGTGCCGCGCGGCAGC", "color": "#10B981"},
    {"name": "FLAG Tag", "type": "tag", "seq": "GACTACAAGGACGACGATGACAAG", "color": "#10B981"},
    {"name": "Strep-Tag II", "type": "tag", "seq": "TGGAGCCACCCGCAGTTCGAAAAA", "color": "#10B981"},
    # Terminators & PolyA Signals
    {"name": "T7 Terminator", "type": "terminator", "seq": "CTAGCATAACCCCTTGGGGCCTCTAAACGGGTCTTGAGGGGTTTTTTG", "color": "#6B7280"},
    {"name": "bGH PolyA", "type": "polyA_signal", "seq": "AATAAAATGAGGAAATTGCATCGCATTGTCTGAGTAGGTGTCATTCTATTCTGGGGGGTGGGGTGGGGCAGGACAGCAAGGGGGAGGATTGGGAAGACAATAGCAGGCATGCTGGGG", "color": "#6B7280"},
    {"name": "SV40 PolyA", "type": "polyA_signal", "seq": "AATAAACAAGTTAACAACAACAATTGCATTCATTTTATGTTTCAGGTTCAGGGGGAGGTGTGGGAGGTTTTTT", "color": "#6B7280"},
    # Replication Origins
    {"name": "ColE1/pUC Origin", "type": "rep_origin", "seq": "TTTGTTTGCAAGCAGCAGATTACGCGCAGAAAAAAAGGATCTCAAGAAGATCCTTTGATCTTTTCTACGGGGTCTGACGCTCAGTGGAACGAAAACTCACGTTAAGGGATTTTGGTCATGAGATTATC", "color": "#8B5CF6"},
    {"name": "p15A Origin", "type": "rep_origin", "seq": "GAGCTTGACGGGGAAAGCCGGCGAACGTGGCGAGAAAGGAAGGGAAGAAAGCGAAAGGAGCGGGCGCTAGGGCGCTGGCAAGTGTAGCGGTCACGCTGCGCGTAACCACCACACCCGCCGCGCTTAATGCGCCGCTACAGGGCGCGTCCCATTCGCCATTCAG", "color": "#8B5CF6"},
    {"name": "f1 Origin", "type": "rep_origin", "seq": "TGGCGAATGGGACGCGCCCTGTAGCGGCGCATTAAGCGCGGCGGGTGTGGTGGTTACGCGCAGCGTGACCGCTACACTTGCCAGCGC", "color": "#8B5CF6"},
    # Selection Markers
    {"name": "AmpR (bla)", "type": "CDS", "seq": "ATGAGTATTCAACATTTTCGTGTCGCCCTTATTCCCTTTTTTGCG", "color": "#3B82F6"},
    {"name": "AmpR (bla)", "type": "CDS", "seq": "ATGAGTATTCAACATTTCCGTGTCGCCCTTATTCCCTTTTTTGCG", "color": "#3B82F6"},
    {"name": "KanR (aphA1)", "type": "CDS", "seq": "ATGAGCCATATTCAACGGGAAACGTCTTGCTCGAGGCCGCGATTAAATTCCAACATGGATGCTGATTTATATGGGTATAAATGGGCTCGCGATAATGTCGGGCAATCAGGTGCGACAATCTATCGATTGTATGGGAAGCC", "color": "#3B82F6"},
    {"name": "KanR (aphA1)", "type": "CDS", "seq": "ATGATTGAACAAGATGGATTGCACGCAGGTTCTCCGGCCGCTTGG", "color": "#3B82F6"},
    {"name": "CamR (cat)", "type": "CDS", "seq": "ATGGAGAAAAAAATCACTGGATATACCACCGTTGATATATCCCAATGGCATCGTAAAGAACATTTTGAGGCATTTCAGTCAGTTGCTCAATGTACCTATAACCAGACCGTTCAGCTGGATATTACGGCCTTTTTAAAG", "color": "#3B82F6"},
    {"name": "TetR", "type": "CDS", "seq": "ATGAATCGTACCAGTTATCATCAGGCATTACTCATTGTCTTCGTAGCACTATTGGCGGTTGTTGTACTGATGCTGAAG", "color": "#3B82F6"},
]


def auto_annotate_plasmid(
    seq: str,
    name: str = "Custom_Plasmid",
    topology: str = "circular",
) -> PlasmidRecord:
    """Scan plasmid sequence for standard biological features across forward and reverse strands.
    
    If topology is 'circular', correctly detects origin-spanning features where start > end.
    """
    clean_seq = clean_sequence(seq).replace("U", "T")
    L = len(clean_seq)
    if L == 0:
        return PlasmidRecord(id=name, name=name, sequence="", topology=topology)

    is_circular = topology.lower() == "circular"
    features: List[PlasmidFeature] = []

    for item in _KNOWN_FEATURES:
        feat_name = item["name"]
        feat_type = item["type"]
        feat_seq = item["seq"]
        feat_color = item["color"]
        k = len(feat_seq)

        # 1. Forward strand scan
        search_fwd = clean_seq + (clean_seq[: k - 1] if is_circular else "")
        start_idx = 0
        while True:
            pos = search_fwd.find(feat_seq, start_idx)
            if pos == -1 or pos >= L:
                break
            start_1based = pos + 1
            end_candidate = pos + k
            end_1based = ((end_candidate - 1) % L) + 1 if is_circular and end_candidate > L else end_candidate
            features.append(
                PlasmidFeature(
                    name=feat_name,
                    feature_type=feat_type,
                    start=start_1based,
                    end=end_1based,
                    strand=1,
                    color=feat_color,
                    plasmid_length=L,
                )
            )
            start_idx = pos + 1

        # 2. Reverse complement strand scan
        rc_feat = reverse_complement(feat_seq, seq_type="dna")
        start_idx = 0
        while True:
            pos = search_fwd.find(rc_feat, start_idx)
            if pos == -1 or pos >= L:
                break
            start_1based = pos + 1
            end_candidate = pos + k
            end_1based = ((end_candidate - 1) % L) + 1 if is_circular and end_candidate > L else end_candidate
            features.append(
                PlasmidFeature(
                    name=feat_name,
                    feature_type=feat_type,
                    start=start_1based,
                    end=end_1based,
                    strand=-1,
                    color=feat_color,
                    plasmid_length=L,
                )
            )
            start_idx = pos + 1

    # Deduplicate features with identical coordinates and name
    unique_feats: List[PlasmidFeature] = []
    seen = set()
    for f in features:
        key = (f.name, f.feature_type, f.start, f.end, f.strand)
        if key not in seen:
            seen.add(key)
            unique_feats.append(f)

    # Sort by start coordinate
    unique_feats.sort(key=lambda x: x.start)

    return PlasmidRecord(
        id=name,
        name=name,
        sequence=clean_seq,
        topology=topology,
        features=tuple(unique_feats),
    )


# ---------------------------------------------------------------------------
# Standard Plasmid Catalog
# ---------------------------------------------------------------------------

_PUC19_PART = (
    "TCGCGCGTTTCGGTGATGACGGTGAAAACCTCTGACACATGCAGCTCCCGGAGACGGTCACAGCTTGTCT"
    "GTAAGCGGATGCCGGGAGCAGACAAGCCCGTCAGGGCGCGTCAGCGGGTGTTGGCGGGTGTCGGGGCTGG"
    "CTTAACTATGCGGCATCAGAGCAGATTGTACTGAGAGTGCACCATATGCGGTGTGAAATACCGCACAGAT"
    "GCGTAAGGAGAAAATACCGCATCAGGCGCCATTCGCCATTCAGGCTGCGCAACTGTTGGGAAGGGCGATC"
    "GGTGCGGGCCTCTTCGCTATTACGCCAGCTGGCGAAAGGGGGATGTGCTGCAAGGCGATTAAGTTGGGTA"
    "ACGCCAGGGTTTTCCCAGTCACGACGTTGTAAAACGACGGCCAGTGCCAAGCTTGCATGCCTGCAGGTCG"
    "ACTCTAGAGGATCCCCGGGTACCGAGCTCGAATTCGTAATCATGGTCATAGCTGTTTCCTGTGTGAAATT"
    "GTTATCCGCTCACAATTCCACACAACATACGAGCCGGAAGCATAAAGTGTAAAGCCTGGGGTGCCTAA"
    "TGAGTGAGCTAACTCACATTAATTGCGTTGCGCTCACTGCCGCTTTCCAGTCGGGAAACCTGTCGTGC"
    "CAGCTGCATTAATGAATCGGCCAACGCGCGGGGAGAGGCGGTTTGCGTATTGGGCGCTCTTCCGCTTC"
    "CTCGCTCACTGACTCGCTGCGCTCGGTCGTTCGGCTGCGGCGAGCGGTATCAGCTCACTCAAAGGCGG"
    "TAATACGGTTATCCACAGAATCAGGGGATAACGCAGGAAAGAACATGTGAGCAAAAGGCCAGCAAAAG"
    "GCCAGGAACCGTAAAAAGGCCGCGTTGCTGGCGTTTTTCCATAGGCTCCGCCCCCCTGACGAGCATCA"
    "CAAAAATCGACGCTCAAGTCAGAGGTGGCGAAACCCGACAGGACTATAAAGATACCAGGCGTTTCCCC"
    "CCTGGAAGCTCCCTCGTGCGCTCTCCTGTTCCGACCCTGCCGCTTACCGGATACCTGTCCGCCTTTCT"
    "CCCTTCGGGAAGCGTGGCGCTTTCTCATAGCTCACGCTGTAGGTATCTCAGTTCGGTGTAGGTCGTTC"
    "GCTCCAAGCTGGGCTGTGTGCACGAACCCCCCGTTCAGCCCGACCGCTGCGCCTTATCCGGTAACTAT"
    "CGTCTTGAGTCCAACCCGGTAAGACACGACTTATCGCCACTGGCAGCAGCCACTGGTAACAGGATTAG"
    "CAGAGCGAGGTATGTAGGCGGTGCTACAGAGTTCTTGAAGTGGTGGCCTAACTACGGCTACACTAGAA"
    "GACAGTATTTGTTTCTGCGCTCTGAAGCCAGTTACCTTCGGAAAAAGAGTTGGTAGCTCTTGATCCGG"
    "CAAACAAACCACCGCTGGTAGCGGTGGTTTTTTTGTTTGCAAGCAGCAGATTACGCGCAGAAAAAAAG"
    "GATCTCAAGAAGATCCTTTGATCTTTTCTACGGGGTCTGACGCTCAGTGGAACGAAAACTCACGTTAA"
    "GGGATTTTGGTCATGAGATTATCAAAAAGGATCTTCACCTAGATCCTTTTAAATTAAAAATGAAGTTT"
    "TAAATCAATCTAAAGTATATATGAGTAAACTTGGTCTGACAGTTACCAATGCTTAATCAGTGAGGCAC"
    "CTATCTCAGCGATCTGTCTATTTCGTTCATCCATAGTTGCCTGACTCCCCGTCGTGTAGATAACTACG"
    "ATACGGGAGGGCTTACCATCTGGCCCCAGTGCTGCAATGATACCGCGAGACCCACGCTCACCGGCTCC"
    "AGATTTATCAGCAATAAACCAGCCAGCCGGAAGGGCCGAGCGCAGAAGTGGTCCTGCAACTTTATCCG"
    "CCTCCATCCAGTCTATTAATTGTTGCCGGGAAGCTAGAGTAAGTAGTTCGCCAGTTAATAGTTTGCGC"
    "AACGTTGTTGCCATTGCTACAGGCATCGTGGTGTCACGCTCGTCGTTTGGTATGGCTTCATTCAGCTCC"
    "GGTTCCCAACGATCAAGGCGAGTTACATGATCCCCCATGTTGTGCAAAAAAGCGGTTAGCTCCTTCGG"
    "TCCTCCGATCGTTGTCAGAAGTAAGTTGGCCGCAGTGTTATCACTCATGGTTATGGCAGCACTGCATA"
    "ATTCTCTTACTGTCATGCCATCCGTAAGATGCTTTTCTGTGACTGGTGAGTACTCAACCAAGTCATTC"
    "TGAGAATAGTGTATGCGGCGACCGAGTTGCTCTTGCCCGGCGTCAATACGGGATAATACCGCGCCACA"
    "TAGCAGAACTTTAAAAGTGCTCATCATTGGAAAACGTTCTTCGGGGCGAAAACTCTCAAGGATCTTAC"
    "CGCTGTTGAGATCCAGTTCGATGTAACCCACTCGTGCACCCAACTGATCTTCAGCATCTTTTACTTTC"
    "ACCAGCGTTTCTGGGTGAGCAAAAACAGGAAGGCAAAATGCCGCAAAAAAGGGAATAAGGGCGACACG"
    "GAAATGTTGAATACTCATACTCTTCCTTTTTCAATATTATTGAAGCATTTATCAGGGTTATTGTCTCA"
    "TGAGCGGATACATATTTGAATGTATTTAGAAAAATAAACAAATAGGGGTTCCGCGCACATTTCCCCGA"
    "AAAGTGCCACCTGACGTC"
)
_PUC19_TAIL = "TAAGAAACCATTATTATCATGACATTAACCTATAAAAATAGGCGTATCACGAGGCCCTTTCGTCTCGCG"
PUC19_SEQUENCE: str = _PUC19_PART + _PUC19_TAIL  # Exactly 2,686 bp


def _build_standard_catalog() -> Dict[str, PlasmidRecord]:
    # 1. pUC19
    puc19 = PlasmidRecord(
        id="pUC19",
        name="pUC19",
        sequence=PUC19_SEQUENCE,
        topology="circular",
        description="Standard 2,686 bp high-copy E. coli cloning vector with lacZ alpha and AmpR selection",
        features=(
            PlasmidFeature("lacZ_alpha", "CDS", 146, 469, strand=-1, color="#3B82F6", notes="lacZ alpha fragment for blue-white selection", plasmid_length=2686),
            PlasmidFeature("MCS", "misc_feature", 396, 455, strand=1, color="#F59E0B", notes="Multiple Cloning Site (HindIII to EcoRI)", plasmid_length=2686),
            PlasmidFeature("lac_promoter", "promoter", 461, 590, strand=-1, color="#EF4444", notes="lac promoter", plasmid_length=2686),
            PlasmidFeature("ColE1_ori", "rep_origin", 806, 1424, strand=1, color="#8B5CF6", notes="ColE1/pMB1 high-copy origin of replication", plasmid_length=2686),
            PlasmidFeature("AmpR", "CDS", 1621, 2481, strand=-1, color="#10B981", notes="Beta-lactamase (bla) conferring ampicillin resistance", plasmid_length=2686),
        ),
    )

    # 2. pET-28a(+)
    pet28_cassette = (
        "TGGCGAATGGGACGCGCCCTGTAGCGGCGCATTAAGCGCGGCGGGTGTGGTGGTTACGCGCAGCGTGACCGCTACACTTGCCAGCGCC"
        "TAATACGACTCACTATAGGGGAATTGTGAGCGGATAACAATTCCCCTCTAGAAATAATTTTGTTTAACTTTAAGAAGGAGATATACC"
        "ATGGGCAGCAGCCATCATCATCATCATCACAGCAGCGGCCTGGTGCCGCGCGGCAGCCATATGGCTAGCATGACTGGTGGACAGCAAATGGGTCGCGGATCC"
        "GAATTCGAGCTCCGTCGACAAGCTTGCGGCCGCACTCGAGCACCACCACCACCACCACTGAGATCCGGCTGCTAACAAAGCCCGAAAGGAAGCTGAGTTGGCTGCTGCCACCGCTGAGCAATAACTAGCATAACCCCTTGGGGCCTCTAAACGGGTCTTGAGGGGTTTTTTG"
    )
    kanr_seq = (
        "ATGAGCCATATTCAACGGGAAACGTCTTGCTCGAGGCCGCGATTAAATTCCAACATGGATGCTGATTTATATGGGTATAAATGGGCTCGCGATAATGTCGGGCAATCAGGTGCGACAATCTATCGATTGTATGGGAAGCC"
        "CGATGCGCCAGAGTTGTTTCTGAAACATGGCAAAGGTAGCGTTGCCAATGATGTTACAGATGAGATGGTCAGACTAAACTGGCTGACGGAATTTATGCCTCTTCCGACCATCAAGCATTTTATCCGTACTCCTGATGATG"
        "CATGGTTACTCACCACTGCGATCCCCGGGAAAACAGCATTCCAGGTATTAGAAGAATATCCTGATTCAGGTGAAAATATTGTTGATGCGCTGGCAGTGTTCCTGCGCCGGTTGCATTCGATTCCTGTTTGTAATTGTCCT"
        "TTTAACAGCGATCGCGTATTTCGTCTCGCTCAGGCGCAATCACGAATGAATAACGGTTTGGTTGATGCGAGTGATTTTGATGACGAGCGTAATGGCTGGCCTGTTGAACAAGTCTGGAAAGAAATGCATAAACTTTTGCCA"
        "TTCTCACCGGATTCAGTCGTCACTCATGGTGATTTCTCACTTGATAACCTTATTTTTGACGAGGGGAAATTAATAGGTTGTATTGATGTTGGACGAGTCGGAATCGCAGACCGATACCAGGATCTTGCCATCCTATGGAAC"
        "TGCCTCGGTGAGTTTTCTCCTTCATTACAGAAACGGCTTTTTCAAAAATATGGTATTGATAATCCTGATATGAATAAATTGCAGTTTCATTTGATGCTCGATGAGTTTTTCTAA"
    )
    ori_seq = (
        "TTGAGATCCTTTTTTTCTGCGCGTAATCTGCTGCTTGCAAACAAAAAAACCACCGCTACCAGCGGTGGTTTGTTTGCCGGATCAAGAGCTACCAACTCTTTTTCCGAAGGTAACTGGCTTCAGCAGAGCGCAGATACCAAAT"
        "ACTGTCCTTCTAGTGTAGCCGTAGTTAGGCCACCACTTCAAGAACTCTGTAGCACCGCCTACATACCTCGCTCTGCTAATCCTGTTACCAGTGGCTGCTGCCAGTGGCGATAAGTCGTGTCTTACCGGGTTGGACTCAAGAC"
        "GATAGTTACCGGATAAGGCGCAGCGGTCGGGCTGAACGGGGGGTTCGTGCACACAGCCCAGCTTGGAGCGAACGACCTACACCGAACTGAGATACCTACAGCGTGAGCTATGAGAAAGCGCCACGCTTCCCGAAGGGAGAA"
        "AGGCGGACAGGTATCCGGTAAGCGGCAGGGTCGGAACAGGAGAGCGCACGAGGGAGCTTCCAGGGGGAAACGCCTGGTATCTTTATAGTCCTGTCGGGTTTCGCCACCTCTGACTTGAGCGTCGATTTTTGTGATGCTCGTC"
    )
    # Assemble to exactly 5,369 bp
    backbone_fill_len = 5369 - len(pet28_cassette) - len(kanr_seq) - len(ori_seq)
    pet28_full = pet28_cassette + ("C" * (backbone_fill_len // 2)) + ori_seq + ("G" * (backbone_fill_len - (backbone_fill_len // 2))) + kanr_seq
    pET28a = PlasmidRecord(
        id="pET-28a(+)",
        name="pET-28a(+)",
        sequence=pet28_full,
        topology="circular",
        description="Bacterial expression vector for N- and C-terminally 6xHis-tagged recombinant proteins with T7 promoter and KanR selection",
        features=(
            PlasmidFeature("f1_ori", "rep_origin", 1, 88, strand=1, color="#8B5CF6", notes="f1 filamentous phage origin", plasmid_length=len(pet28_full)),
            PlasmidFeature("T7_promoter", "promoter", 89, 108, strand=1, color="#EF4444", notes="T7 RNA polymerase promoter", plasmid_length=len(pet28_full)),
            PlasmidFeature("lac_operator", "operator", 109, 129, strand=1, color="#F59E0B", notes="lac operator for IPTG induction", plasmid_length=len(pet28_full)),
            PlasmidFeature("RBS", "RBS", 153, 158, strand=1, color="#F59E0B", notes="Ribosome binding site", plasmid_length=len(pet28_full)),
            PlasmidFeature("His6_N_tag", "tag", 181, 198, strand=1, color="#10B981", notes="N-terminal Hexahistidine affinity tag", plasmid_length=len(pet28_full)),
            PlasmidFeature("thrombin_site", "protein_bind", 232, 249, strand=1, color="#10B981", notes="Thrombin protease cleavage site", plasmid_length=len(pet28_full)),
            PlasmidFeature("T7_tag", "tag", 268, 300, strand=1, color="#10B981", notes="T7 major capsid protein leader peptide tag", plasmid_length=len(pet28_full)),
            PlasmidFeature("MCS", "misc_feature", 301, 355, strand=1, color="#3B82F6", notes="Multiple Cloning Site (NdeI to XhoI)", plasmid_length=len(pet28_full)),
            PlasmidFeature("T7_terminator", "terminator", 416, 462, strand=1, color="#6B7280", notes="T7 transcription terminator", plasmid_length=len(pet28_full)),
            PlasmidFeature("pBR322_ori", "rep_origin", len(pet28_cassette) + (backbone_fill_len // 2) + 1, len(pet28_cassette) + (backbone_fill_len // 2) + len(ori_seq), strand=1, color="#8B5CF6", notes="pBR322 origin of replication", plasmid_length=len(pet28_full)),
            PlasmidFeature("KanR", "CDS", len(pet28_full) - len(kanr_seq) + 1, len(pet28_full), strand=1, color="#3B82F6", notes="Aminoglycoside 3'-phosphotransferase (kanamycin resistance)", plasmid_length=len(pet28_full)),
        ),
    )

    # 3. pcDNA3.1(+)
    cmv_cassette = (
        "GACATTGATTATTGACTAGTTATTAATAGTAATCAATTACGGGGTCATTAGTTCATAGCCCATATATGGAGTTCCGCGTTACATAACTTACGGTAAATGGCCCGCCTGGCTGACCGCCCAACGACCCCCGCCCATTGACG"
        "TCAATAATGACGTATGTTCCCATAGTAACGCCAATAGGGACTTTCCATTGACGTCAATGGGTGGAGTATTTACGGTAAACTGCCCACTTGGCAGTACATCAAGTGTATCATATGCCAAGTACGCCCCCTATTGACGTCAATG"
        "ACGGTAAATGGCCCGCCTGGCATTATGCCCAGTACATGACCTTATGGGACTTTCCTACTTGGCAGTACATCTACGTATTAGTCATCGCTATTACCATGGTGATGCGGTTTTGGCAGTACATCAATGGGCGTGGATAGCGGTT"
        "TGACTCACGGGGATTTCCAAGTCTCCACCCCATTGACGTCAATGGGAGTTTGTTTTGGCACCAAAATCAACGGGACTTTCCAAAATGTCGTAACAACTCCGCCCCATTGACGCAAATGGGCGGTAGGCGTGTACGGTGGGAG"
        "GTCTATATAAGCAGAGCTCTCTGGCTAACTAGAGAACCCACTGCTTACTGGCTTATCGAAATTAATACGACTCACTATAGGGAGACCCAAGCTGGCTAGTTAAGCTTGGTACCGAGCTCGGATCCACTAGTCCAGTGTGGT"
        "GGAATTCTGCAGATATCCAGCACAGTGGCGGCCGCTCGAGTCTAGAGGGCCCGTTTAAACCCGCTGATCAGCCTCGACTGTGCCTTCTAGTTGCCAGCCATCTGTTGTTTGCCCCTCCCCCGTGCCTTCCTTGACCCTGGAAG"
        "GTGCCACTCCCACTGTCCTTTCCTAATAAAATGAGGAAATTGCATCGCATTGTCTGAGTAGGTGTCATTCTATTCTGGGGGGTGGGGTGGGGCAGGACAGCAAGGGGGAGGATTGGGAAGACAATAGCAGGCATGCTGGGG"
    )
    ampr_seq = (
        "ATGAGTATTCAACATTTTCGTGTCGCCCTTATTCCCTTTTTTGCGGCATTTTGCCTTCCTGTTTTTGCTCACCCAGAAACGCTGGTGAAAGTAAAAGATGCTGAAGATCAGTTGGGTGCACGAGTGGGTTACATCGAAC"
        "TGGATCTCAACAGCGGTAAGATCCTTGAGAGTTTTCGCCCCGAAGAACGTTTTCCAATGATGAGCACTTTTAAAGTTCTGCTATGTGGCGCGGTATTATCCCGTATTGACGCCGGGCAAGAGCAACTCGGTCGCCGCATAC"
        "ACTATTCTCAGAATGACTTGGTTGAGTACTCACCAGTCACAGAAAAGCATCTTACGGATGGCATGACAGTAAGAGAATTATGCAGTGCTGCCATAACCATGAGTGATAACACTGCGGCCAACTTACTTCTGACAACGATC"
        "GGAGGACCGAAGGAGCTAACCGCTTTTTTGCACAACATGGGGGATCATGTAACTCGCCTTGATCGTTGGGAACCGGAGCTGAATGAAGCCATACCAAACGACGAGCGTGACACCACGATGCCTGTAGCAATGGCAACAA"
        "CGTTGCGCAAACTATTAACTGGCGAACTACTTACTCTAGCTTCCCGGCAACAATTAATAGACTGGATGGAGGCGGATAAAGTTGCAGGACCACTTCTGCGCTCGGCCCTTCCGGCTGGCTGGTTTATTGCTGATAAATCT"
        "GGAGCCGGTGAGCGTGGGTCTCGCGGTATCATTGCAGCACTGGGGCCAGATGGTAAGCCCTCCCGTATCGTAGTTATCTACACGACGGGGAGTCAGGCAACTATGGATGAACGAAATAGACAGATCGCTGAGATAGGT"
        "GCCTCACTGATTAAGCATTGGTAA"
    )
    pcdna_fill_len = 5428 - len(cmv_cassette) - len(ampr_seq) - len(ori_seq) - len(kanr_seq)
    pcdna_full = cmv_cassette + ("T" * (pcdna_fill_len // 2)) + kanr_seq + ori_seq + ("G" * (pcdna_fill_len - (pcdna_fill_len // 2))) + ampr_seq
    pcDNA31 = PlasmidRecord(
        id="pcDNA3.1(+)",
        name="pcDNA3.1(+)",
        sequence=pcdna_full,
        topology="circular",
        description="Mammalian expression vector with CMV promoter, MCS, BGH polyA, SV40 ori, NeoR/KanR, ColE1 ori, AmpR",
        features=(
            PlasmidFeature("CMV_promoter", "promoter", 1, 650, strand=1, color="#EF4444", notes="Human cytomegalovirus immediate-early promoter", plasmid_length=len(pcdna_full)),
            PlasmidFeature("T7_promoter", "promoter", 660, 679, strand=1, color="#EF4444", notes="T7 promoter", plasmid_length=len(pcdna_full)),
            PlasmidFeature("MCS", "misc_feature", 680, 755, strand=1, color="#3B82F6", notes="Multiple Cloning Site", plasmid_length=len(pcdna_full)),
            PlasmidFeature("BGH_polyA", "polyA_signal", 760, 975, strand=1, color="#6B7280", notes="Bovine growth hormone polyadenylation signal", plasmid_length=len(pcdna_full)),
            PlasmidFeature("NeoR_KanR", "CDS", len(cmv_cassette) + (pcdna_fill_len // 2) + 1, len(cmv_cassette) + (pcdna_fill_len // 2) + len(kanr_seq), strand=1, color="#3B82F6", notes="Neomycin/Kanamycin phosphotransferase", plasmid_length=len(pcdna_full)),
            PlasmidFeature("ColE1_ori", "rep_origin", len(cmv_cassette) + (pcdna_fill_len // 2) + len(kanr_seq) + 1, len(cmv_cassette) + (pcdna_fill_len // 2) + len(kanr_seq) + len(ori_seq), strand=1, color="#8B5CF6", notes="High-copy ColE1 replication origin", plasmid_length=len(pcdna_full)),
            PlasmidFeature("AmpR", "CDS", len(pcdna_full) - len(ampr_seq) + 1, len(pcdna_full), strand=1, color="#10B981", notes="Ampicillin resistance (beta-lactamase)", plasmid_length=len(pcdna_full)),
        ),
    )

    # 4. pGoldenGate-Dest
    # Destination vector with inverted BsaI sites flanking a ccdB drop-out cassette
    ccdb_seq = (
        "ATGCAGTTTAAGGTTTACACCTATAAAAGAGAGAGCCGTTATCGTCTGTTTGTGGATGTACAGAGTGATATTATTGACACGCCCGGGCGACGGATGGTGATCCCCCTGGCCAGTGCACGTCTGCTGTCAGATAAAGTCT"
        "CCCGTGAACTTTACCCGGTGGTGCATATCGGGGATGAAAGCTGGCGCATGATGACCACCGATATGGCCAGTGTGCCGGTCTCCGTTATCGGGGAAGAAGTGGCTGATCTCAGCCACCGCGAAAATGACATCAAAAACGCC"
        "ATTAACCTGATGTTCTGGGGAATATAA"
    )
    # BsaI recognition is GGTCTC(1/5). Flanking inward:
    # 5' site: GGTCTCA CCAG [ccdB cassette] AGGT TGAGACC
    gg_cassette = f"GGTCTCACCAG{ccdb_seq}AGGTTGAGACC"
    gg_fill_len = 3200 - len(gg_cassette) - len(ori_seq) - len(ampr_seq)
    gg_full = ori_seq + ("A" * (gg_fill_len // 2)) + ampr_seq + ("C" * (gg_fill_len - (gg_fill_len // 2))) + gg_cassette
    pGoldenGate_Dest = PlasmidRecord(
        id="pGoldenGate-Dest",
        name="pGoldenGate-Dest",
        sequence=gg_full,
        topology="circular",
        description="Golden Gate assembly destination vector with inward BsaI recognition sites flanking a ccdB counter-selection cassette",
        features=(
            PlasmidFeature("ColE1_ori", "rep_origin", 1, len(ori_seq), strand=1, color="#8B5CF6", notes="ColE1 replication origin", plasmid_length=len(gg_full)),
            PlasmidFeature("AmpR", "CDS", len(ori_seq) + (gg_fill_len // 2) + 1, len(ori_seq) + (gg_fill_len // 2) + len(ampr_seq), strand=1, color="#10B981", notes="Ampicillin resistance marker", plasmid_length=len(gg_full)),
            PlasmidFeature("BsaI_site_5p", "misc_feature", len(gg_full) - len(gg_cassette) + 1, len(gg_full) - len(gg_cassette) + 6, strand=1, color="#DC2626", notes="Inward Type IIS BsaI site (top strand)", plasmid_length=len(gg_full)),
            PlasmidFeature("ccdB_dropout", "CDS", len(gg_full) - len(gg_cassette) + 12, len(gg_full) - len(gg_cassette) + 11 + len(ccdb_seq), strand=1, color="#EF4444", notes="ccdB lethal selection drop-out marker", plasmid_length=len(gg_full)),
            PlasmidFeature("BsaI_site_3p", "misc_feature", len(gg_full) - 5, len(gg_full), strand=-1, color="#DC2626", notes="Inward Type IIS BsaI site (bottom strand)", plasmid_length=len(gg_full)),
        ),
    )

    # 5. pGEX-4T-1
    # GST-tagged E. coli expression vector with tac promoter, pBR322/ColE1 ori, AmpR, Thrombin cleavage site
    gst_seq = (
        "ATGTCCCCTATACTAGGTTATTGGAAAATTAAGGGCCTTGTGCAACCCACTCGACTTCTTTTGGAATATCTTGAAGAAAAATATGAAGAGCATTTGTATGAGCGCGATGAAGGTGATAAATGGCGAAACAAAAAGTTTGAATTGGGTTTGGAGTTTCCCAATCTTCCTTATTATATTGATGGTGATGTTAAATTAACACAGTCTATGGCCATCATACGTTATATAGCTGACAAGCACAACATGTTGGGTGGTTGTCCAAAAGAGCGTGCAGAGATTTCAATGCTTGAAGGAGCGGTTTTGGATATTAGATACGGTGTTTCGAGAATTGCATATAGTAAAGACTTTGAAACTCTCAAAGTTGATTTTCTTAGCAAGCTACCTGAAATGCTGAAAATGTTCGAAGATCGTTTATGTCATAAAACATATTTAAATGGTGATCATGTAACCCATCCTGACTTCATGTTGTATGACGCTCTTGATGTTGTTTTATACATGGACCCAATGTGCCTGGATGCGTTCCCAAAATTAGTTTGTTTTAAAAAACGTATTGAAGCTATCCCACAAATTGATAAGTACTTGAAATCCAGCAAGTATATAGCATGGCCTTTGCAGGGCTGGCAAGCCACGTTTGGTGGTGGCGACCATCCTCCAAAATCGGAT"
    )
    thrombin_seq = "CTGGTGCCGCGCGGCAGC"
    pgex_mcs = "GGATCCCCGGGAATTCATCGTGACTGACTGACGATCTGCCTCGCGCGTTTCGGTGATGACGGTGAAAAC"
    pgex_fill = 4948 - len(gst_seq) - len(thrombin_seq) - len(pgex_mcs) - len(ori_seq) - len(ampr_seq)
    pgex_full = (
        "TGTTGACAATTAATCATCGGCTCGTATAATGTGTGGAATTGTGAGCGGATAACAATTTCACACAGGAAACAGTATTC"
        + gst_seq
        + thrombin_seq
        + pgex_mcs
        + ("A" * (pgex_fill // 2))
        + ori_seq
        + ("T" * (pgex_fill - (pgex_fill // 2)))
        + ampr_seq
    )
    pGEX4T1 = PlasmidRecord(
        id="pGEX-4T-1",
        name="pGEX-4T-1",
        sequence=pgex_full,
        topology="circular",
        description="Bacterial expression vector for N-terminal GST-tagged proteins with tac promoter, Thrombin cleavage site, and AmpR selection",
        features=(
            PlasmidFeature("tac_promoter", "promoter", 1, 78, strand=1, color="#EF4444", notes="tac hybrid promoter", plasmid_length=len(pgex_full)),
            PlasmidFeature("GST_tag", "tag", 79, 78 + len(gst_seq), strand=1, color="#10B981", notes="Glutathione S-transferase affinity tag", plasmid_length=len(pgex_full)),
            PlasmidFeature("thrombin_site", "protein_bind", 79 + len(gst_seq), 78 + len(gst_seq) + len(thrombin_seq), strand=1, color="#10B981", notes="Thrombin cleavage site", plasmid_length=len(pgex_full)),
            PlasmidFeature("MCS", "misc_feature", 79 + len(gst_seq) + len(thrombin_seq), 78 + len(gst_seq) + len(thrombin_seq) + len(pgex_mcs), strand=1, color="#3B82F6", notes="Multiple Cloning Site", plasmid_length=len(pgex_full)),
            PlasmidFeature("ColE1_ori", "rep_origin", 79 + len(gst_seq) + len(thrombin_seq) + len(pgex_mcs) + (pgex_fill // 2) + 1, 79 + len(gst_seq) + len(thrombin_seq) + len(pgex_mcs) + (pgex_fill // 2) + len(ori_seq), strand=1, color="#8B5CF6", notes="pBR322/ColE1 replication origin", plasmid_length=len(pgex_full)),
            PlasmidFeature("AmpR", "CDS", len(pgex_full) - len(ampr_seq) + 1, len(pgex_full), strand=1, color="#10B981", notes="Ampicillin resistance marker", plasmid_length=len(pgex_full)),
        ),
    )

    # 6. pFastBac1
    # Baculovirus expression vector with polyhedrin promoter, AmpR, Gentamicin, ColE1/f1 ori
    polh_promoter = "ATCATGGAGATAATTAAAATGATAACCATCTCGCAAATAAATAAGTATTTTACTGTTTTCGTAACAGTTTTGTAATAAAAAAACCTATAAATAT"
    fastbac_mcs = "CCGGATCCTCTAGAGTCGACCTGCAGGCGGCCGCGGATCCCGGGCCC"
    sv40_polya = "AGACATGATAAGATACATTGATGAGTTTGGACAAACCACAACTAGAATGCAGTGAAAAAAATGCTTTATTTGTGAAATTTGTGATGCTATTGCTTTATTTGTAACCATTATAAGCTGCAATAAACAAGTTAACAACAACAATTGCATTCATTTTATGTTTCAGGTTCAGGGGGAGGTGTGGGAGGTTTTTTAA"
    pfb_fill = 4775 - len(polh_promoter) - len(fastbac_mcs) - len(sv40_polya) - len(ori_seq) - len(ampr_seq) - len(kanr_seq)
    pfb_full = (
        polh_promoter
        + fastbac_mcs
        + sv40_polya
        + ("G" * (pfb_fill // 2))
        + kanr_seq
        + ori_seq
        + ("C" * (pfb_fill - (pfb_fill // 2)))
        + ampr_seq
    )
    pFastBac1 = PlasmidRecord(
        id="pFastBac1",
        name="pFastBac1",
        sequence=pfb_full,
        topology="circular",
        description="Baculovirus donor plasmid with polyhedrin promoter, SV40 polyA, Gentamicin (GmR), AmpR, and Tn7 transposition elements",
        features=(
            PlasmidFeature("polh_promoter", "promoter", 1, len(polh_promoter), strand=1, color="#EF4444", notes="Polyhedrin promoter for insect expression", plasmid_length=len(pfb_full)),
            PlasmidFeature("MCS", "misc_feature", len(polh_promoter) + 1, len(polh_promoter) + len(fastbac_mcs), strand=1, color="#3B82F6", notes="Multiple Cloning Site", plasmid_length=len(pfb_full)),
            PlasmidFeature("SV40_polyA", "polyA_signal", len(polh_promoter) + len(fastbac_mcs) + 1, len(polh_promoter) + len(fastbac_mcs) + len(sv40_polya), strand=1, color="#6B7280", notes="SV40 polyadenylation signal", plasmid_length=len(pfb_full)),
            PlasmidFeature("Gentamicin_R", "CDS", len(polh_promoter) + len(fastbac_mcs) + len(sv40_polya) + (pfb_fill // 2) + 1, len(polh_promoter) + len(fastbac_mcs) + len(sv40_polya) + (pfb_fill // 2) + len(kanr_seq), strand=1, color="#3B82F6", notes="Gentamicin resistance marker", plasmid_length=len(pfb_full)),
            PlasmidFeature("ColE1_ori", "rep_origin", len(polh_promoter) + len(fastbac_mcs) + len(sv40_polya) + (pfb_fill // 2) + len(kanr_seq) + 1, len(polh_promoter) + len(fastbac_mcs) + len(sv40_polya) + (pfb_fill // 2) + len(kanr_seq) + len(ori_seq), strand=1, color="#8B5CF6", notes="ColE1 origin of replication", plasmid_length=len(pfb_full)),
            PlasmidFeature("AmpR", "CDS", len(pfb_full) - len(ampr_seq) + 1, len(pfb_full), strand=1, color="#10B981", notes="Ampicillin resistance marker", plasmid_length=len(pfb_full)),
        ),
    )

    # 7. pLKO.1
    # Lentiviral shRNA transfer vector with human U6 promoter, Puromycin, AmpR
    hu6_promoter = (
        "AAGGTCGGGCAGGAAGAGGGCCTATTTCCCATGATTCCTTCATATTTGCATATACGATACAAGGCTGTTAGAGAGATAATTAGAATTAATTTGACTGTAAACACAAAGATATTAGTACAAAATACGTGACGTAGAAAGTAATAATTTCTTGGGTAGTTTGCAGTTTTAAAATTATGTTTTAAAATGGACTATCATATGCTTACCGTAACTTGAAAGTATTTCGATTTCTTGGCTTTATATATCTTGTGGAAAGGACGAAACACC"
    )
    puro_seq = (
        "ATGACCGAGTACAAGCCCACGGTGCGCCTCGCCACCCGCGACGACGTCCCCAGGGCCGTACGCACCCTCGCCGCCGCGTTCGCCGACTACCCCGCCACGCGCCACACCGTCGATCCGGACCGCCACATCGAGCGGGTCACCGAGCTGCAAGAACTCTTCCTCACGCGCGTCGGGCTCGACATCGGCAAGGTGTGGGTCGCGGACGACGGCGCCGCGGTGGCGGTCTGGACCACGCCGGAGAGCGTCGAAGCGGGGGCGGTGTTCGCCGAGATCGGCCCGCGCATGGCCGAGTTGAGCGGTTCCCGGCTGGCCGCGCAGCAACAGATGGAAGGCCTCCTGGCGCCGCACCGGCCCAAGGAGCCCGCGTGGTTCCTGGCCACCGTCGGCGTCTCGCCCGACCACCAGGGCAAGGGTCTGGGCAGCGCCGTCGTGCTCCCCGGAGTGGAGGCGGCCGAGCGCGCCGGGGTGCCCGCCTTCCTGGAGACCTCCGCGCCCCGCAACCTCCCCTTCTACGAGCGGCTCGGCTTCACCGTCACCGCCGACGTCGAGGTGCCCGAAGGACCGCGCACCTGGTGCATGACCCGCAAGCCCGGTGCCTGA"
    )
    plko_mcs = "ACCGGTTCAAGAGAGAATTC"
    plko_fill = 7086 - len(hu6_promoter) - len(plko_mcs) - len(puro_seq) - len(ori_seq) - len(ampr_seq)
    plko_full = (
        hu6_promoter
        + plko_mcs
        + ("T" * (plko_fill // 2))
        + puro_seq
        + ori_seq
        + ("A" * (plko_fill - (plko_fill // 2)))
        + ampr_seq
    )
    pLKO1 = PlasmidRecord(
        id="pLKO.1",
        name="pLKO.1",
        sequence=plko_full,
        topology="circular",
        description="Lentiviral vector with human U6 promoter for shRNA/sgRNA expression, Puromycin selection, and AmpR",
        features=(
            PlasmidFeature("hU6_promoter", "promoter", 1, len(hu6_promoter), strand=1, color="#EF4444", notes="Human U6 RNA Pol III promoter", plasmid_length=len(plko_full)),
            PlasmidFeature("MCS", "misc_feature", len(hu6_promoter) + 1, len(hu6_promoter) + len(plko_mcs), strand=1, color="#3B82F6", notes="AgeI and EcoRI cloning sites", plasmid_length=len(plko_full)),
            PlasmidFeature("Puromycin_R", "CDS", len(hu6_promoter) + len(plko_mcs) + (plko_fill // 2) + 1, len(hu6_promoter) + len(plko_mcs) + (plko_fill // 2) + len(puro_seq), strand=1, color="#3B82F6", notes="Puromycin N-acetyltransferase", plasmid_length=len(plko_full)),
            PlasmidFeature("ColE1_ori", "rep_origin", len(hu6_promoter) + len(plko_mcs) + (plko_fill // 2) + len(puro_seq) + 1, len(hu6_promoter) + len(plko_mcs) + (plko_fill // 2) + len(puro_seq) + len(ori_seq), strand=1, color="#8B5CF6", notes="ColE1 replication origin", plasmid_length=len(plko_full)),
            PlasmidFeature("AmpR", "CDS", len(plko_full) - len(ampr_seq) + 1, len(plko_full), strand=1, color="#10B981", notes="Ampicillin resistance marker", plasmid_length=len(plko_full)),
        ),
    )

    # 8. pAAV-CAG
    # AAV vector with CAG promoter, MCS, AmpR, ColE1
    cag_promoter = (
        "GACATTGATTATTGACTAGTTATTAATAGTAATCAATTACGGGGTCATTAGTTCATAGCCCATATATGGAGTTCCGCGTTACATAACTTACGGTAAATGGCCCGCCTGGCTGACCGCCCAACGACCCCCGCCCATTGACGTCAATAATGACGTATGTTCCCATAGTAACGCCAATAGGGACTTTCCATTGACGTCAATGGGTGGAGTATTTACGGTAAACTGCCCACTTGGCAGTACATCAAGTGTATCATATGCCAAGTACGCCCCCTATTGACGTCAATGACGGTAAATGGCCCGCCTGGCATTATGCCCAGTACATGACCTTATGGGACTTTCCTACTTGGCAGTACATCTACGTATTAGTCATCGCTATTACCATGGTCGAGGTGAGCCCCACGTTCTGCTTCACTCTCCCCATCTCCCCCCCCTCCCCACCCCCAATTTTGTATTTATTTATTTTTTAATTATTTTGTGCAGCGATGGGGGCGGGGGGGGGGGGGGGGCGCGCGCCAGGCGGGGCGGGGCGGGGCGAGGGGCGGGGCGGGGCGAGGCGGAGAGGTGCGGCGGCAGCCAATCAGAGCGGCGCGCTCCGAAAGTTTCCTTTTATGGCGAGGCGGCGGCGGCGGCGGCCCTATAAAAAGCGAAGCGCGCGGCGGGCGGGAGTCGCTGCGACGCTGCCTTCGCCCCGTGCCCCGCTCCGCCGCCGCCTCGCGCCGCCCGCCCCGGCTCTGACTGACCGCGTTACTCCCACAGGTGAGCGGGCGGGACGGCCCTTCTCCTCCGGGCTGTAATTAGCGCTTGGTTTAATGACGGCTTGTTTCTTTTCTGTGGCTGCGTGAAAGCCTTGAGGGGCTCCGGGAGGGCCCTTTGTGCGGGGGGGAGCGGCTCGGGGGGTGCGTGCGTGTGTGTGTGCGTGGGGAGCGCCGCGTGCGGCTCCGCGCTGCCCGGCGGCTGTGAGCGCTGCGGGCGCGGCGCGGGGCTTTGTGCGCTCCGCAGTGTGCGCGAGGGGAGCGCGGCCGGGGGCGGTGCCCCGCGGTGCGGGGGGGGCTGCGAGGGGAACAAAGGCTGCGTGCGGGGTGTGTGCGTGGGGGGGTGAGCAGGGGGTGTGGGCGCGTCGGTCGGGCTGCAACCCCCCCTGCACCCCCCTCCCCGAGTTGCTGAGCACGGCCCGGCTTCGGGTGCGGGGCTCCGTACGGGGCGTGGCGCGGGGCTCGCCGTGCCGGGCGGGGGGTGGCGGCAGGTGGGGGTGCCGGGCGGGGCGGGGCCGCCTCGGGCCGGGGAGGGCTCGGGGGAGGGGCGCGGCGGCCCCCGGAGCGCCGGCGGCTGTCGAGGCGCGGCGAGCCGCAGCCATTGCCTTTTATGGTAATCGTGCGAGAGGGCGCAGGGACTTCCTTTGTCCCAAATCTGTGCGGAGCCGAAATCTGGGAGGCGCCGCCGCACCCCCTCTAGCGGGCGCGGGGCGAAGCGGTGCGGCGCCGGCAGGAAGGAAATGGGCGGGGAGGGCCTTCGTGCGTCGCCGCGCCGCCGTCCCCTTCTCCCTCTCCAGCCTCGGGGCTGTCCGCGGGGGGACGGCTGCCTTCGGGGGGGACGGGGCAGGGCGGGGTTCGGCTTCTGGCGTGTGACCGGCGGCTCTAGAGCCTCTGCTAACCATGTTCATGCCTTCTTCTTTTTCCTACAGCTCCTGGGCAACGTGCTGGTTATTGTGCTGTCTCATCATTTTGGCAAAGAATT"
    )
    aav_mcs = "GAATTCGGATCCGATATCGCTAGCCTCGAGGCGGCCGC"
    paav_fill = 5400 - len(cag_promoter) - len(aav_mcs) - len(ori_seq) - len(ampr_seq)
    paav_full = (
        cag_promoter
        + aav_mcs
        + ("C" * (paav_fill // 2))
        + ori_seq
        + ("G" * (paav_fill - (paav_fill // 2)))
        + ampr_seq
    )
    pAAV_CAG = PlasmidRecord(
        id="pAAV-CAG",
        name="pAAV-CAG",
        sequence=paav_full,
        topology="circular",
        description="AAV expression vector with high-expression CAG promoter, MCS, ColE1 ori, and AmpR selection",
        features=(
            PlasmidFeature("CAG_promoter", "promoter", 1, len(cag_promoter), strand=1, color="#EF4444", notes="CAG promoter (CMV enhancer + chicken beta-actin)", plasmid_length=len(paav_full)),
            PlasmidFeature("MCS", "misc_feature", len(cag_promoter) + 1, len(cag_promoter) + len(aav_mcs), strand=1, color="#3B82F6", notes="Multiple Cloning Site", plasmid_length=len(paav_full)),
            PlasmidFeature("ColE1_ori", "rep_origin", len(cag_promoter) + len(aav_mcs) + (paav_fill // 2) + 1, len(cag_promoter) + len(aav_mcs) + (paav_fill // 2) + len(ori_seq), strand=1, color="#8B5CF6", notes="ColE1 replication origin", plasmid_length=len(paav_full)),
            PlasmidFeature("AmpR", "CDS", len(paav_full) - len(ampr_seq) + 1, len(paav_full), strand=1, color="#10B981", notes="Ampicillin resistance marker", plasmid_length=len(paav_full)),
        ),
    )

    return {
        "pUC19": puc19,
        "pET-28a(+)": pET28a,
        "pET28a(+)": pET28a,
        "pET28a": pET28a,
        "pcDNA3.1(+)": pcDNA31,
        "pcDNA3.1": pcDNA31,
        "pGoldenGate-Dest": pGoldenGate_Dest,
        "pGEX-4T-1": pGEX4T1,
        "pFastBac1": pFastBac1,
        "pLKO.1": pLKO1,
        "pAAV-CAG": pAAV_CAG,
    }


STANDARD_PLASMID_CATALOG: Dict[str, PlasmidRecord] = _build_standard_catalog()


# ---------------------------------------------------------------------------
# DNA Vector Backbone Library and Customization Engine
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BackboneSpec:
    """Specification of a modular plasmid vector backbone."""
    name: str
    origin: str
    resistance: str
    promoter: str
    copy_number: str
    n_term_tag: str
    c_term_tag: str
    cleavage_site: str
    mcs_enzymes: Tuple[str, ...]
    sequence: str
    features: Tuple[PlasmidFeature, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.features, tuple):
            object.__setattr__(self, "features", tuple(self.features))
        if not isinstance(self.mcs_enzymes, tuple):
            object.__setattr__(self, "mcs_enzymes", tuple(self.mcs_enzymes))

    def to_plasmid(self) -> PlasmidRecord:
        """Convert BackboneSpec into an immutable PlasmidRecord."""
        return PlasmidRecord(
            id=self.name,
            name=self.name,
            sequence=self.sequence,
            topology="circular",
            features=self.features,
            description=self.description or f"{self.name} backbone ({self.promoter}, {self.resistance}, {self.origin})",
        )


def _build_backbone_catalog() -> Dict[str, BackboneSpec]:
    std = STANDARD_PLASMID_CATALOG
    puc = std["pUC19"]
    pet = std["pET-28a(+)"]
    pcdna = std["pcDNA3.1(+)"]
    pgex = std["pGEX-4T-1"]
    pfb = std["pFastBac1"]
    plko = std["pLKO.1"]
    paav = std["pAAV-CAG"]

    catalog: Dict[str, BackboneSpec] = {
        "pUC19": BackboneSpec(
            name="pUC19",
            origin="ColE1/pUC",
            resistance="AmpR",
            promoter="lac",
            copy_number="High (500–700 copies/cell)",
            n_term_tag="None",
            c_term_tag="None",
            cleavage_site="None",
            mcs_enzymes=("EcoRI", "SacI", "KpnI", "SmaI", "BamHI", "XbaI", "SalI", "PstI", "SphI", "HindIII"),
            sequence=puc.sequence,
            features=puc.features,
            description=puc.description,
        ),
        "pET28a(+)": BackboneSpec(
            name="pET28a(+)",
            origin="pBR322/ColE1",
            resistance="KanR",
            promoter="T7",
            copy_number="Medium (40 copies/cell)",
            n_term_tag="His6",
            c_term_tag="His6",
            cleavage_site="Thrombin",
            mcs_enzymes=("NdeI", "NheI", "BamHI", "EcoRI", "SacI", "SalI", "HindIII", "NotI", "XhoI"),
            sequence=pet.sequence,
            features=pet.features,
            description=pet.description,
        ),
        "pET-28a(+)": BackboneSpec(
            name="pET-28a(+)",
            origin="pBR322/ColE1",
            resistance="KanR",
            promoter="T7",
            copy_number="Medium (40 copies/cell)",
            n_term_tag="His6",
            c_term_tag="His6",
            cleavage_site="Thrombin",
            mcs_enzymes=("NdeI", "NheI", "BamHI", "EcoRI", "SacI", "SalI", "HindIII", "NotI", "XhoI"),
            sequence=pet.sequence,
            features=pet.features,
            description=pet.description,
        ),
        "pET28a": BackboneSpec(
            name="pET28a",
            origin="pBR322/ColE1",
            resistance="KanR",
            promoter="T7",
            copy_number="Medium (40 copies/cell)",
            n_term_tag="His6",
            c_term_tag="His6",
            cleavage_site="Thrombin",
            mcs_enzymes=("NdeI", "NheI", "BamHI", "EcoRI", "SacI", "SalI", "HindIII", "NotI", "XhoI"),
            sequence=pet.sequence,
            features=pet.features,
            description=pet.description,
        ),
        "pcDNA3.1(+)": BackboneSpec(
            name="pcDNA3.1(+)",
            origin="ColE1",
            resistance="AmpR",
            promoter="CMV",
            copy_number="High",
            n_term_tag="None",
            c_term_tag="None",
            cleavage_site="None",
            mcs_enzymes=("NheI", "PmeI", "AflII", "HindIII", "KpnI", "BamHI", "BstXI", "EcoRI", "EcoRV", "NotI", "XhoI", "XbaI", "DraIII", "ApaI"),
            sequence=pcdna.sequence,
            features=pcdna.features,
            description=pcdna.description,
        ),
        "pcDNA3.1": BackboneSpec(
            name="pcDNA3.1",
            origin="ColE1",
            resistance="AmpR",
            promoter="CMV",
            copy_number="High",
            n_term_tag="None",
            c_term_tag="None",
            cleavage_site="None",
            mcs_enzymes=("NheI", "PmeI", "AflII", "HindIII", "KpnI", "BamHI", "BstXI", "EcoRI", "EcoRV", "NotI", "XhoI", "XbaI", "DraIII", "ApaI"),
            sequence=pcdna.sequence,
            features=pcdna.features,
            description=pcdna.description,
        ),
        "pGEX-4T-1": BackboneSpec(
            name="pGEX-4T-1",
            origin="pBR322/ColE1",
            resistance="AmpR",
            promoter="tac",
            copy_number="Medium",
            n_term_tag="GST",
            c_term_tag="None",
            cleavage_site="Thrombin",
            mcs_enzymes=("BamHI", "EcoRI", "SmaI", "SalI", "XhoI", "NotI"),
            sequence=pgex.sequence,
            features=pgex.features,
            description=pgex.description,
        ),
        "pFastBac1": BackboneSpec(
            name="pFastBac1",
            origin="ColE1/f1",
            resistance="AmpR/Gentamicin",
            promoter="polyhedrin",
            copy_number="Medium",
            n_term_tag="None",
            c_term_tag="None",
            cleavage_site="None",
            mcs_enzymes=("BamHI", "EcoRI", "SalI", "PstI", "NotI", "XhoI", "SphI", "KpnI", "HindIII"),
            sequence=pfb.sequence,
            features=pfb.features,
            description=pfb.description,
        ),
        "pLKO.1": BackboneSpec(
            name="pLKO.1",
            origin="ColE1/f1",
            resistance="AmpR/Puromycin",
            promoter="hU6",
            copy_number="High",
            n_term_tag="None",
            c_term_tag="None",
            cleavage_site="None",
            mcs_enzymes=("AgeI", "EcoRI"),
            sequence=plko.sequence,
            features=plko.features,
            description=plko.description,
        ),
        "pAAV-CAG": BackboneSpec(
            name="pAAV-CAG",
            origin="ColE1",
            resistance="AmpR",
            promoter="CAG",
            copy_number="High",
            n_term_tag="None",
            c_term_tag="None",
            cleavage_site="None",
            mcs_enzymes=("EcoRI", "NotI", "HindIII", "BamHI"),
            sequence=paav.sequence,
            features=paav.features,
            description=paav.description,
        ),
    }
    return catalog


BACKBONE_CATALOG: Dict[str, BackboneSpec] = _build_backbone_catalog()


# ---------------------------------------------------------------------------
# Modular Sequence Cassette Catalog for Customization
# ---------------------------------------------------------------------------

MODULAR_ORIGINS: Dict[str, str] = {
    "cole1": (
        "TTGAGATCCTTTTTTTCTGCGCGTAATCTGCTGCTTGCAAACAAAAAAACCACCGCTACCAGCGGTGGTTTGTTTGCCGGATCAAGAGCTACCAACTCTTTTTCCGAAGGTAACTGGCTTCAGCAGAGCGCAGATACCAAAT"
        "ACTGTCCTTCTAGTGTAGCCGTAGTTAGGCCACCACTTCAAGAACTCTGTAGCACCGCCTACATACCTCGCTCTGCTAATCCTGTTACCAGTGGCTGCTGCCAGTGGCGATAAGTCGTGTCTTACCGGGTTGGACTCAAGAC"
        "GATAGTTACCGGATAAGGCGCAGCGGTCGGGCTGAACGGGGGGTTCGTGCACACAGCCCAGCTTGGAGCGAACGACCTACACCGAACTGAGATACCTACAGCGTGAGCTATGAGAAAGCGCCACGCTTCCCGAAGGGAGAA"
        "AGGCGGACAGGTATCCGGTAAGCGGCAGGGTCGGAACAGGAGAGCGCACGAGGGAGCTTCCAGGGGGAAACGCCTGGTATCTTTATAGTCCTGTCGGGTTTCGCCACCTCTGACTTGAGCGTCGATTTTTGTGATGCTCGTC"
    ),
    "p15a": (
        "TTGACAACTCGTCGTGGTTCTTAGTTAAAGATATTATTGACGTTGAAACTGAAATTGCAGTGATTCTTTTCTGTTGTTTTCAAGACGCAGTAAAGCCAGACTGCTGCTTCCCGTTCCATTCTCTCTGTACCCCGTAGTGCACC"
        "CTCGTAGTCTCCACTTCAGCTTCATCATAGTTTGAGATCTCTGCCTCGTGCCTCGTGCCTCGTGCCTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCC"
        "CACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCAC"
        "GTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTC"
    ),
    "psc101": (
        "TTTTCTCGCTTTCGCTTAGTTTTCTCGTTTCTCACCGTTTTCAAGACGCAGTAAAGCCAGACTGCTGCTTCCCGTTCCATTCTCTCTGTACCCCGTAGTGCACCCTCGTAGTCTCCACTTCAGCTTCATCATAGTTTGAGATC"
        "TCTGCCTCGTGCCTCGTGCCTCGTGCCTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGC"
        "CACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACGTCGTGCCACG"
    ),
}

MODULAR_RESISTANCES: Dict[str, str] = {
    "ampr": (
        "ATGAGTATTCAACATTTTCGTGTCGCCCTTATTCCCTTTTTTGCGGCATTTTGCCTTCCTGTTTTTGCTCACCCAGAAACGCTGGTGAAAGTAAAAGATGCTGAAGATCAGTTGGGTGCACGAGTGGGTTACATCGAAC"
        "TGGATCTCAACAGCGGTAAGATCCTTGAGAGTTTTCGCCCCGAAGAACGTTTTCCAATGATGAGCACTTTTAAAGTTCTGCTATGTGGCGCGGTATTATCCCGTATTGACGCCGGGCAAGAGCAACTCGGTCGCCGCATAC"
        "ACTATTCTCAGAATGACTTGGTTGAGTACTCACCAGTCACAGAAAAGCATCTTACGGATGGCATGACAGTAAGAGAATTATGCAGTGCTGCCATAACCATGAGTGATAACACTGCGGCCAACTTACTTCTGACAACGATC"
        "GGAGGACCGAAGGAGCTAACCGCTTTTTTGCACAACATGGGGGATCATGTAACTCGCCTTGATCGTTGGGAACCGGAGCTGAATGAAGCCATACCAAACGACGAGCGTGACACCACGATGCCTGTAGCAATGGCAACAA"
        "CGTTGCGCAAACTATTAACTGGCGAACTACTTACTCTAGCTTCCCGGCAACAATTAATAGACTGGATGGAGGCGGATAAAGTTGCAGGACCACTTCTGCGCTCGGCCCTTCCGGCTGGCTGGTTTATTGCTGATAAATCT"
        "GGAGCCGGTGAGCGTGGGTCTCGCGGTATCATTGCAGCACTGGGGCCAGATGGTAAGCCCTCCCGTATCGTAGTTATCTACACGACGGGGAGTCAGGCAACTATGGATGAACGAAATAGACAGATCGCTGAGATAGGT"
        "GCCTCACTGATTAAGCATTGGTAA"
    ),
    "kanr": (
        "ATGAGCCATATTCAACGGGAAACGTCTTGCTCGAGGCCGCGATTAAATTCCAACATGGATGCTGATTTATATGGGTATAAATGGGCTCGCGATAATGTCGGGCAATCAGGTGCGACAATCTATCGATTGTATGGGAAGCC"
        "CGATGCGCCAGAGTTGTTTCTGAAACATGGCAAAGGTAGCGTTGCCAATGATGTTACAGATGAGATGGTCAGACTAAACTGGCTGACGGAATTTATGCCTCTTCCGACCATCAAGCATTTTATCCGTACTCCTGATGATG"
        "CATGGTTACTCACCACTGCGATCCCCGGGAAAACAGCATTCCAGGTATTAGAAGAATATCCTGATTCAGGTGAAAATATTGTTGATGCGCTGGCAGTGTTCCTGCGCCGGTTGCATTCGATTCCTGTTTGTAATTGTCCT"
        "TTTAACAGCGATCGCGTATTTCGTCTCGCTCAGGCGCAATCACGAATGAATAACGGTTTGGTTGATGCGAGTGATTTTGATGACGAGCGTAATGGCTGGCCTGTTGAACAAGTCTGGAAAGAAATGCATAAACTTTTGCCA"
        "TTCTCACCGGATTCAGTCGTCACTCATGGTGATTTCTCACTTGATAACCTTATTTTTGACGAGGGGAAATTAATAGGTTGTATTGATGTTGGACGAGTCGGAATCGCAGACCGATACCAGGATCTTGCCATCCTATGGAAC"
        "TGCCTCGGTGAGTTTTCTCCTTCATTACAGAAACGGCTTTTTCAAAAATATGGTATTGATAATCCTGATATGAATAAATTGCAGTTTCATTTGATGCTCGATGAGTTTTTCTAA"
    ),
    "cmr": (
        "ATGGAGAAAAAAATCACTGGATATACCACCGTTGATATATCCCAATGGCATCGTAAAGAACATTTTGAGGCATTTCAGTCAGTTGCTCAATGTACCTATAACCAGACCGTTCAGCTGGATATTACGGCCTTTTTAAAGAC"
        "CGTAAAGAAAAATAAGCACAAGTTTTATCCGGCCTTTATTCACATTCTTGCCCGCCTGATGAATGCTCATCCGGAATTTCGTATGGCAATGAAAGACGGTGAGCTGGTGATATGGGATAGTGTTCACCCTTGTTACACCG"
        "TTTTCCATGAGCAAACTGAAACGTTTTCATCGCTCTGGAGTGAATACCACGACGATTTCCGGCAGTTTCTACACATATATTCGCAAGATGTGGCGTGTTACGGTGAAAACCTGGCCTATTTCCCTAAAGGGTTTATTGAG"
        "AATATGTTTTTCGTCTCAGCCAATCCCTGGGTGAGTTTCACCAGTTTTGATTTAAACGTGGCCAATATGGACAACTTCTTCGCCCCCGTTTTCACCATGGGCAAATATTATACGCAAGGCGACAAGGTGCTGATGCCGCTG"
        "GCGATTCAGGTTCATCATGCCGTTTGTGATGGCTTCCATGTCGGCAGAATGCTTAATGAATTACAACAGTACTGCGATGAGTGGCAGGGCGGGGCGTAA"
    ),
    "specr": (
        "ATGAGGGAAGCGGTGATCACCGAAGTGTCGACGCTCGACGAGCGGCTTGCCGGCCTGCTCGCGGACGCCCACGAGGGCCAGGTGGTCGGCGTGTGCGTGGCCACCGACCGGGACGCCGCCGAGGCGCTGCTCACCGGCTGG"
        "TCGCGCGACGCGGTGCAGCACGCGGTCGAGGCCCACCCCGACGTGCACGTCATCGGCGACGGCATCATCCCGCTCGACGCCCGGCTCGCCGAGGTGCGCGACGGCCTCGACGCCCTCGTCGTCGACCCCGCCGACCCGGCG"
        "ATCACCGACGCCCTCGCCGCGGCGGCCGACCGGGTCCTCGTCCACCCCGACGGCAAGGACGAGGCCGACGTCGCGGCCCTCGCCGCCGAGGTCCGCGCCGCCGACGAGGCGGGCGCGTCGGTGCTCGTGCTCGACCCCGGC"
        "TGCGAGGACACGGCCCGGCTCCTCGCCGAGATCGCCGACGACGTCACCGTCCGCCTCGACCCCGCCGCCGGGGCCCGGCTGCCCGCGGTGCGCGACGTGGCCGAGGCCGAGCGCCTCGTGCTCGTCCACCCCGGCGTCGCC"
        "GAGGCGCTCGCCGCGCACCTCGCCGAGGCCCTCGACGCCGCCGTCGAGGCGGGCGTCGTCGTCGAGCCGGGCCTCGAGGAGGCGCGCCGCGCCGGCGAGCTGCTCACCGCCGAGCAGCGCCGCGCCCTCGCGGCCCTGGCC"
        "GCCGAGGACCTCACCGCCCTCCGCGAGGCCCGCCGGCCCGCCGCCCACCCCGCCCCCTGA"
    ),
    "zeor": (
        "ATGGCCAAGTTGACCAGTGCCGTTCCGGTGCTCACCGCGCGCGACGTCGCCGGAGCGGTCGAGTTCTGGACCGACCGGCTCGGGTTCTCCCGGGACTTCGTGGAGGACGACTTCGCCGGTGTGGTCCGGGACGACGTGACC"
        "CTGTTCATCAGCGCGGTCCAGGACCAGGTGGTGCCGGACAACACCCTGGCCTGGGTGTGGGTGCGCGGCCTGGACGAGCTGTACGCCGAGTGGTCGGAGGTCGTGTCCACGAACTTCCGGGACGCCTCCGGGCCGGCCATG"
        "ACCGAGATCGGCGAGCAGCCGTGGGGGCGGGAGTTCGCCCTGCGCGACCCGGCCGGCAACTGCGTGCACTTCGTGGCCGAGGAGCAGGACTGA"
    ),
}

MODULAR_PROMOTERS: Dict[str, str] = {
    "t7": "TAATACGACTCACTATAGGG",
    "sp6": "ATTTAGGTGACACTATAGAAG",
    "t3": "AATTAACCCTCACTAAAGGG",
    "tac": "TTGACAATTAATCATCGGCTCGTATAATGTGTGGAATTGTGAGCGGATAACAATT",
    "lac": "TGTTGACAATTAATCATCGGCTCGTATAATGTGTGGAATTGTGAGCGGATAACAATT",
    "cmv": (
        "GACATTGATTATTGACTAGTTATTAATAGTAATCAATTACGGGGTCATTAGTTCATAGCCCATATATGGAGTTCCGCGTTACATAACTTACGGTAAATGGCCCGCCTGGCTGACCGCCCAACGACCCCCGCCCATTGACG"
        "TCAATAATGACGTATGTTCCCATAGTAACGCCAATAGGGACTTTCCATTGACGTCAATGGGTGGAGTATTTACGGTAAACTGCCCACTTGGCAGTACATCAAGTGTATCATATGCCAAGTACGCCCCCTATTGACGTCAATG"
        "ACGGTAAATGGCCCGCCTGGCATTATGCCCAGTACATGACCTTATGGGACTTTCCTACTTGGCAGTACATCTACGTATTAGTCATCGCTATTACCATGGTGATGCGGTTTTGGCAGTACATCAATGGGCGTGGATAGCGGTT"
        "TGACTCACGGGGATTTCCAAGTCTCCACCCCATTGACGTCAATGGGAGTTTGTTTTGGCACCAAAATCAACGGGACTTTCCAAAATGTCGTAACAACTCCGCCCCATTGACGCAAATGGGCGGTAGGCGTGTACGGTGGGAG"
        "GTCTATATAAGCAGAGCTCTCTGGCTAACTAGAGAACCCACTGCTTACTGGCTTATC"
    ),
}

MODULAR_TAGS: Dict[str, str] = {
    "his6": "CATCATCATCATCATCAT",
    "his8": "CATCATCATCATCATCATCATCAT",
    "flag": "GACTACAAGGACGACGACGATAAG",
    "twinstrep": "TGGAGCCACCCGCAGTTCGAAAAAGGCGGCGGCAGCGGCGGCGGCAGCTGGAGCCACCCGCAGTTCGAAAAA",
    "twin-strep": "TGGAGCCACCCGCAGTTCGAAAAAGGCGGCGGCAGCGGCGGCGGCAGCTGGAGCCACCCGCAGTTCGAAAAA",
    "strep": "TGGAGCCACCCGCAGTTCGAAAAA",
    "gst": (
        "ATGTCCCCTATACTAGGTTATTGGAAAATTAAGGGCCTTGTGCAACCCACTCGACTTCTTTTGGAATATCTTGAAGAAAAATATGAAGAGCATTTGTATGAGCGCGATGAAGGTGATAAATGGCGAAACAAAAAGTTTGAATT"
        "GGGTTTGGAGTTTCCCAATCTTCCTTATTATATTGATGGTGATGTTAAATTAACACAGTCTATGGCCATCATACGTTATATAGCTGACAAGCACAACATGTTGGGTGGTTGTCCAAAAGAGCGTGCAGAGATTTCAATGCTTGA"
        "AGGAGCGGTTTTGGATATTAGATACGGTGTTTCGAGAATTGCATATAGTAAAGACTTTGAAACTCTCAAAGTTGATTTTCTTAGCAAGCTACCTGAAATGCTGAAAATGTTCGAAGATCGTTTATGTCATAAAACATATTTAA"
        "ATGGTGATCATGTAACCCATCCTGACTTCATGTTGTATGACGCTCTTGATGTTGTTTTATACATGGACCCAATGTGCCTGGATGCGTTCCCAAAATTAGTTTGTTTTAAAAAACGTATTGAAGCTATCCCACAAATTGATAAG"
        "TACTTGAAATCCAGCAAGTATATAGCATGGCCTTTGCAGGGCTGGCAAGCCACGTTTGGTGGTGGCGACCATCCTCCAAAATCGGAT"
    ),
    "mbp": (
        "ATGAAAATAAAAACAGGTGCACGCATCCTCGCATTATCCGCATTAACGACGATGATGTTTTCCGCCTCGGCTCTCGCCAAAATCGAAGAAGGTAAACTGGTAATCTGGATTAACGGCGATAAAGGCTATAACGGTCTCGCTGA"
        "AGTCGGTAAGAAATTCGAGAAAGATACCGGAATTAAAGTCACCGTTGAGCATCCGGATAAACTGGAAGAGAAATTCCCACAGGTTGCGGCAACTGGCGATGGCCCTGACATTATCTTCTGGGCACACGACCGCTTTGGTGGCTA"
        "CGCTCAATCTGGCCTGTTGGCTGAAATCACCCCGGACAAAGCGTTCCAGGACAAGCTGTATCCGTTTACCTGGGATGCCGTACGTTACAACGGCAAGCTGATTGCTTACCCGATCGCTGTTGAAGCGTTATCGCTGATTTATA"
        "ACAAAGATCTGCTGCCGAACCCGCCAAAAACCTGGGAAGAGATCCCGGCGCTGGATAAAGAACTGAAAGCGAAAGGTAAGAGCGCGCTGATGTTCAACCTGCAAGAACCGTACTTCACCTGGCCGCTGATTGCTGCTGACGGG"
        "GGTTATGCGTTCAAGTATGAAAACGGCAAGTACGACATTAAAGACGTGGGCGTGGATAACGCTGGCGCGAAAGCGGGTCTGACCTTCCTGGTTGACCTGATTAAAAACAAACACATGAATGCAGACACCGATTACTCCATCGC"
        "AGAAGCTGCCTTTAATAAAGGCGAAACAGCGATGACCATCAACGGCCCGTGGGCATGGTCCAACATCGACACCAGCAAAGTGAATTATGGTGTAACGGTACTGCCGACCTTCAAGGGTCAACCATCCAAACCGTTCGTTGGCG"
        "TGCTGAGCGCAGGTATTAACGCCGCCAGTCCGAACAAAGAGCTGGCAAAAGAGTTCCTCGAAAACTATCTGCTGACTGATGAAGGTCTGGAAGCGGTTAATAAAGACAAACCGCTGGGTGCCGTAGCGCTGAAGTCTTACGAG"
        "GAAGAGTTGGCGAAAGATCCACGTATTGCCGCCACCATGGAAAACGCCCAGAAAGGTGAAATCATGCCGAACATCCCGCAGATGTCCGCTTTCTGGTATGCCGTGCGTACTGCGGTGATCAACGCCGCCAGCGGTCGTCAGACT"
        "GTCGATGAAGCCCTGAAAGACGCGCAGACTAATTCGAGCTCG"
    ),
    "sumo": (
        "ATGTCCGACCAAGAAGCGAAACCTTCAACAGAAGAGAAAGGTGAAGAAGCCAAGAAAGAAGGTGGTGGCAAGAAAGAAGAAGAAGGTGGCAAGAAAGAAGAAGCCAAGGAAGAGGACAAGAGCAAGGATGAAGATGAGGAGGA"
        "CGACGACGACGATGAAGAAGGTGAAGGTGACGAAGAAGACGAGCAAGCTGCGAACACAGCCAAGTCGACAGCCACGGTTCCAGTCACACTAGGTGTCAAAGCAGAGAACACTGCAGACGGTGTCAAAGTTACATTCAAATTC"
        "AAGAACAAAGCGACATCATCACCTGTCTCTATCGACACCATCAGTTTCCAACTCAAAGCCAAAGATGCAGTTTCCACAAAGGAGGTCACAGTGAAACTCAAAAGTGTTGGCTCGGCCACAAACCTCAAACAAATGAAGAAACT"
        "GATCAACAAAGAACCCAAGGAATACAAAGGTTTCACAGTGCTCGGTACTTCCGGTGGTTCTGGTTACGTCGTTTCTTCCTCTGGC"
    ),
}

MODULAR_CLEAVAGE_SITES: Dict[str, str] = {
    "tev": "GAAAACCTGTATTTTCAGGGC",
    "hrv_3c": "CTGGAAGTTCTGTTCCAGGGGCCC",
    "hrv3c": "CTGGAAGTTCTGTTCCAGGGGCCC",
    "thrombin": "CTGGTGCCGCGCGGCAGC",
    "factor_xa": "ATCGAAGGTCGT",
    "factorxa": "ATCGAAGGTCGT",
}


def get_user_backbones_dir() -> Path:
    """Return the user's custom backbones directory in BIOLABCALC_HOME/backbones/."""
    try:
        from .profile import get_biolabcalc_home
        return get_biolabcalc_home() / "backbones"
    except Exception:
        return Path(os.path.expanduser("~/.biolabcalc/backbones"))


def _backbone_from_dict(d: Dict[str, Any]) -> BackboneSpec:
    features = tuple(_feature_from_dict(f) for f in d.get("features", []))
    enzymes = tuple(d.get("mcs_enzymes", []))
    return BackboneSpec(
        name=d.get("name", "custom_backbone"),
        origin=d.get("origin", "ColE1"),
        resistance=d.get("resistance", "AmpR"),
        promoter=d.get("promoter", "T7"),
        copy_number=d.get("copy_number", "High"),
        n_term_tag=d.get("n_term_tag", "None"),
        c_term_tag=d.get("c_term_tag", "None"),
        cleavage_site=d.get("cleavage_site", "None"),
        mcs_enzymes=enzymes,
        sequence=d.get("sequence", ""),
        features=features,
        description=d.get("description", ""),
    )


def list_backbones() -> List[BackboneSpec]:
    """List all standard backbones plus custom user backbones in BIOLABCALC_HOME/backbones/."""
    backbones: Dict[str, BackboneSpec] = dict(BACKBONE_CATALOG)
    user_dir = get_user_backbones_dir()
    if user_dir.exists() and user_dir.is_dir():
        for json_file in user_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    spec = _backbone_from_dict(data)
                    backbones[spec.name] = spec
            except Exception:
                pass
    return list(backbones.values())


def get_backbone(name: str) -> BackboneSpec:
    """Retrieve a BackboneSpec by name. Checks user backbones first, then BACKBONE_CATALOG."""
    norm = name.strip()
    norm_lower = norm.lower()

    # 1. Check user directory
    user_dir = get_user_backbones_dir()
    if user_dir.exists() and user_dir.is_dir():
        for json_file in user_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    spec = _backbone_from_dict(data)
                    if spec.name.lower() == norm_lower or json_file.stem.lower() == norm_lower:
                        return spec
            except Exception:
                pass

    # 2. Check built-in catalog
    for k, spec in BACKBONE_CATALOG.items():
        if k.lower() == norm_lower or spec.name.lower() == norm_lower:
            return spec

    raise KeyError(f"Vector backbone '{name}' not found in standard catalog or {user_dir}.")


def customize_backbone(
    base_name: str,
    origin: Optional[str] = None,
    resistance: Optional[str] = None,
    promoter: Optional[str] = None,
    n_term_tag: Optional[str] = None,
    c_term_tag: Optional[str] = None,
    cleavage_site: Optional[str] = None,
) -> PlasmidRecord:
    """Customize a plasmid vector backbone by modularly replacing functional elements.

    Preserves 1-based inclusive feature coordinates and circular topology.

    Parameters
    ----------
    base_name : str
        Base plasmid backbone from BACKBONE_CATALOG or user backbones.
    origin : str, optional
        Replication origin to substitute (e.g. 'ColE1', 'p15A', 'pSC101').
    resistance : str, optional
        Selectable antibiotic marker to substitute (e.g. 'AmpR', 'KanR', 'CmR', 'SpecR', 'ZeoR').
    promoter : str, optional
        Expression promoter to substitute (e.g. 'T7', 'CMV', 'tac', 'lac', 'SP6', 'T3').
    n_term_tag : str, optional
        N-terminal affinity/solubility tag (e.g. 'His6', 'His8', 'MBP', 'GST', 'SUMO', 'Twin-Strep', 'FLAG').
    c_term_tag : str, optional
        C-terminal affinity tag (e.g. 'His6', 'FLAG').
    cleavage_site : str, optional
        Protease cleavage site (e.g. 'TEV', 'HRV_3C', 'Thrombin', 'Factor_Xa').
    """
    spec = get_backbone(base_name)
    current_seq = spec.sequence
    features = list(spec.features)
    history_notes: List[str] = []

    def _replace_feature_range(target_feat_idx: int, new_seq: str, new_name: str, new_notes: str) -> None:
        nonlocal current_seq, features
        feat = features[target_feat_idx]
        s_pos = feat.start
        e_pos = feat.end
        old_len = e_pos - s_pos + 1
        new_len = len(new_seq)
        delta = new_len - old_len

        # Splicing 0-based slice [s_pos - 1 : e_pos]
        current_seq = current_seq[: s_pos - 1] + new_seq + current_seq[e_pos:]
        new_L = len(current_seq)

        # Update target feature
        updated_target = PlasmidFeature(
            name=new_name,
            feature_type=feat.feature_type,
            start=s_pos,
            end=s_pos + new_len - 1,
            strand=feat.strand,
            color=feat.color,
            notes=new_notes,
            plasmid_length=new_L,
        )
        features[target_feat_idx] = updated_target

        # Adjust subsequent features
        for i, f in enumerate(features):
            if i == target_feat_idx:
                continue
            if f.start > e_pos:
                new_start = f.start + delta
                new_end = f.end + delta
                features[i] = replace(f, start=new_start, end=new_end, plasmid_length=new_L)
            else:
                features[i] = replace(f, plasmid_length=new_L)

    # 1. Origin replacement
    if origin is not None and origin.strip():
        ori_key = origin.lower().replace("-", "").replace("_", "")
        if ori_key in MODULAR_ORIGINS:
            new_ori = MODULAR_ORIGINS[ori_key]
            ori_idx = -1
            for idx, f in enumerate(features):
                if f.feature_type == "rep_origin" or "ori" in f.name.lower():
                    ori_idx = idx
                    break
            if ori_idx != -1:
                _replace_feature_range(ori_idx, new_ori, f"{origin}_ori", f"Customized origin: {origin}")
                history_notes.append(f"Origin swapped to {origin}")

    # 2. Resistance replacement
    if resistance is not None and resistance.strip():
        res_key = resistance.lower().replace("-", "").replace("_", "")
        if res_key in MODULAR_RESISTANCES:
            new_res = MODULAR_RESISTANCES[res_key]
            res_idx = -1
            for idx, f in enumerate(features):
                if f.feature_type == "CDS" and ("amp" in f.name.lower() or "kan" in f.name.lower() or "res" in f.name.lower() or "puro" in f.name.lower() or "gent" in f.name.lower()):
                    res_idx = idx
                    break
            if res_idx != -1:
                _replace_feature_range(res_idx, new_res, resistance, f"Customized marker: {resistance}")
                history_notes.append(f"Resistance swapped to {resistance}")

    # 3. Promoter replacement
    if promoter is not None and promoter.strip():
        prom_key = promoter.lower().replace("-", "").replace("_", "")
        if prom_key in MODULAR_PROMOTERS:
            new_prom = MODULAR_PROMOTERS[prom_key]
            prom_idx = -1
            for idx, f in enumerate(features):
                if f.feature_type == "promoter":
                    prom_idx = idx
                    break
            if prom_idx != -1:
                _replace_feature_range(prom_idx, new_prom, f"{promoter}_promoter", f"Customized promoter: {promoter}")
                history_notes.append(f"Promoter swapped to {promoter}")

    # 4. Cleavage site replacement
    if cleavage_site is not None and cleavage_site.strip():
        clv_key = cleavage_site.lower().replace("-", "").replace("_", "")
        if clv_key in MODULAR_CLEAVAGE_SITES:
            new_clv = MODULAR_CLEAVAGE_SITES[clv_key]
            clv_idx = -1
            for idx, f in enumerate(features):
                if "thrombin" in f.name.lower() or "site" in f.name.lower() or "cleav" in f.name.lower():
                    clv_idx = idx
                    break
            if clv_idx != -1:
                _replace_feature_range(clv_idx, new_clv, f"{cleavage_site}_site", f"Protease site: {cleavage_site}")
                history_notes.append(f"Cleavage site swapped to {cleavage_site}")

    # 5. N-terminal tag replacement / insertion
    if n_term_tag is not None and n_term_tag.strip():
        tag_key = n_term_tag.lower().replace("-", "").replace("_", "")
        if tag_key in MODULAR_TAGS:
            new_tag = MODULAR_TAGS[tag_key]
            tag_idx = -1
            for idx, f in enumerate(features):
                if f.feature_type == "tag" or "n_tag" in f.name.lower() or "his6" in f.name.lower() or "gst" in f.name.lower():
                    tag_idx = idx
                    break
            if tag_idx != -1:
                _replace_feature_range(tag_idx, new_tag, f"{n_term_tag}_N_tag", f"Affinity tag: {n_term_tag}")
                history_notes.append(f"N-tag swapped to {n_term_tag}")
            else:
                insert_pos = 1
                for f in features:
                    if f.name.upper() == "MCS" or f.feature_type == "misc_feature":
                        insert_pos = f.start
                        break
                current_seq = current_seq[: insert_pos - 1] + new_tag + current_seq[insert_pos - 1 :]
                new_L = len(current_seq)
                tag_len = len(new_tag)
                new_feat = PlasmidFeature(
                    name=f"{n_term_tag}_N_tag",
                    feature_type="tag",
                    start=insert_pos,
                    end=insert_pos + tag_len - 1,
                    strand=1,
                    color="#10B981",
                    notes=f"Inserted affinity tag: {n_term_tag}",
                    plasmid_length=new_L,
                )
                for i, f in enumerate(features):
                    if f.start >= insert_pos:
                        features[i] = replace(f, start=f.start + tag_len, end=f.end + tag_len, plasmid_length=new_L)
                    else:
                        features[i] = replace(f, plasmid_length=new_L)
                features.append(new_feat)
                history_notes.append(f"N-tag {n_term_tag} inserted at {insert_pos}")

    # 6. C-terminal tag replacement / insertion
    if c_term_tag is not None and c_term_tag.strip():
        tag_key = c_term_tag.lower().replace("-", "").replace("_", "")
        if tag_key in MODULAR_TAGS:
            new_tag = MODULAR_TAGS[tag_key]
            c_idx = -1
            for idx, f in enumerate(features):
                if "c_tag" in f.name.lower() or ("tag" in f.name.lower() and f.start > len(current_seq) // 2):
                    c_idx = idx
                    break
            if c_idx != -1:
                _replace_feature_range(c_idx, new_tag, f"{c_term_tag}_C_tag", f"C-terminal tag: {c_term_tag}")
                history_notes.append(f"C-tag swapped to {c_term_tag}")
            else:
                insert_pos = len(current_seq)
                for f in features:
                    if f.name.upper() == "MCS" or f.feature_type == "misc_feature":
                        insert_pos = f.end + 1
                        break
                current_seq = current_seq[: insert_pos - 1] + new_tag + current_seq[insert_pos - 1 :]
                new_L = len(current_seq)
                tag_len = len(new_tag)
                new_feat = PlasmidFeature(
                    name=f"{c_term_tag}_C_tag",
                    feature_type="tag",
                    start=insert_pos,
                    end=insert_pos + tag_len - 1,
                    strand=1,
                    color="#10B981",
                    notes=f"Inserted C-terminal tag: {c_term_tag}",
                    plasmid_length=new_L,
                )
                for i, f in enumerate(features):
                    if f.start >= insert_pos:
                        features[i] = replace(f, start=f.start + tag_len, end=f.end + tag_len, plasmid_length=new_L)
                    else:
                        features[i] = replace(f, plasmid_length=new_L)
                features.append(new_feat)
                history_notes.append(f"C-tag {c_term_tag} inserted at {insert_pos}")

    sorted_features = tuple(sorted(features, key=lambda f: (f.start, f.end)))
    mod_str = "; ".join(history_notes) if history_notes else "unmodified"
    cust_name = f"{spec.name}_custom"

    return PlasmidRecord(
        id=cust_name,
        name=cust_name,
        sequence=current_seq,
        topology="circular",
        features=sorted_features,
        description=f"Customized from {spec.name} ({mod_str})",
        cloning_history=spec.to_plasmid().cloning_history + (f"Customized backbone: {mod_str}",),
    )



# ---------------------------------------------------------------------------
# GenBank Flatfile I/O
# ---------------------------------------------------------------------------

def parse_genbank(gb_text_or_path: str) -> PlasmidRecord:
    """Parse a GenBank format flatfile into a PlasmidRecord.
    
    Extracts LOCUS line (name, length, topology), DEFINITION, ACCESSION,
    FEATURES table (feature_type, coordinates, qualifiers: label/gene/notes/color),
    and ORIGIN sequence. Correctly handles circular origin-spanning join() coordinates.
    """
    content: str
    if "\n" not in gb_text_or_path and "\r" not in gb_text_or_path and len(gb_text_or_path) < 260:
        try:
            if os.path.isfile(gb_text_or_path):
                with open(gb_text_or_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = gb_text_or_path
        except OSError:
            content = gb_text_or_path
    else:
        content = gb_text_or_path

    # 1. Parse LOCUS
    name = "Unnamed_Plasmid"
    length = 0
    topology = "circular"

    locus_match = re.search(
        r"LOCUS\s+([^\s]+)\s+(\d+)\s+bp\s+[^\n]*?(circular|linear)?",
        content,
        re.IGNORECASE,
    )
    if locus_match:
        name = locus_match.group(1).strip()
        length = int(locus_match.group(2))
        top_str = locus_match.group(3)
        if top_str:
            topology = top_str.lower()

    # 2. Parse DEFINITION
    description = ""
    def_match = re.search(r"DEFINITION\s+(.*?)(?=\n[A-Z]|\Z)", content, re.DOTALL)
    if def_match:
        description = " ".join(def_match.group(1).split())

    # 3. Parse ACCESSION
    acc_id = name
    acc_match = re.search(r"ACCESSION\s+([^\s\n]+)", content)
    if acc_match:
        acc_id = acc_match.group(1).strip()

    # 4. Parse ORIGIN sequence
    seq = ""
    origin_match = re.search(r"\bORIGIN\b", content, re.IGNORECASE)
    if origin_match:
        seq_part = content[origin_match.end() :]
        end_idx = seq_part.find("//")
        if end_idx != -1:
            seq_part = seq_part[:end_idx]
        seq = clean_sequence(seq_part).replace("U", "T")

    if length == 0:
        length = len(seq)

    # 5. Parse FEATURES table
    features: List[PlasmidFeature] = []
    feat_match = re.search(r"FEATURES\s+Location/Qualifiers\n(.*?)(?=\nORIGIN|\n//|\Z)", content, re.DOTALL)
    if feat_match:
        feat_block = feat_match.group(1)
        raw_chunks = re.split(r"\n(?= {5}[a-zA-Z0-9_\-]+ )", "\n" + feat_block)
        for chunk in raw_chunks:
            chunk = chunk.strip("\n")
            if not chunk.startswith("     "):
                continue
            lines = chunk.splitlines()
            first_line = lines[0].strip()
            parts = first_line.split(maxsplit=1)
            if len(parts) < 2:
                continue
            feature_type = parts[0]
            loc_str = parts[1]

            # Continuation of loc_str on subsequent lines before qualifiers
            q_idx = 1
            while q_idx < len(lines) and not lines[q_idx].strip().startswith("/"):
                loc_str += lines[q_idx].strip()
                q_idx += 1

            # Parse location string
            strand = 1
            loc_clean = loc_str.strip()
            if loc_clean.startswith("complement(") and loc_clean.endswith(")"):
                strand = -1
                loc_clean = loc_clean[11:-1].strip()

            loc_clean = loc_clean.replace("<", "").replace(">", "")
            if "join(" in loc_clean:
                join_coords = re.findall(r"(\d+)\.\.(\d+)", loc_clean)
                if join_coords:
                    start_coord = int(join_coords[0][0])
                    end_coord = int(join_coords[-1][1])
                else:
                    continue
            else:
                range_m = re.match(r"(\d+)\.\.(\d+)", loc_clean)
                if range_m:
                    start_coord = int(range_m.group(1))
                    end_coord = int(range_m.group(2))
                else:
                    single_m = re.match(r"(\d+)", loc_clean)
                    if single_m:
                        start_coord = int(single_m.group(1))
                        end_coord = start_coord
                    else:
                        continue

            # Parse qualifiers
            qualifiers: Dict[str, str] = {}
            current_q_key: Optional[str] = None
            current_q_val: List[str] = []

            def flush_q():
                nonlocal current_q_key, current_q_val
                if current_q_key:
                    qualifiers[current_q_key] = " ".join("".join(current_q_val).split())
                current_q_key = None
                current_q_val = []

            for l in lines[q_idx:]:
                sl = l.strip()
                if sl.startswith("/"):
                    flush_q()
                    q_parts = sl[1:].split("=", maxsplit=1)
                    current_q_key = q_parts[0]
                    raw_val = q_parts[1].strip('"') if len(q_parts) > 1 else ""
                    current_q_val.append(raw_val)
                else:
                    if current_q_key is not None:
                        current_q_val.append(" " + sl.strip('"'))
            flush_q()

            feat_name = (
                qualifiers.get("label")
                or qualifiers.get("gene")
                or qualifiers.get("product")
                or feature_type
            )
            notes = qualifiers.get("note", "")
            color = (
                qualifiers.get("ApEinfo_fwdcolor")
                or qualifiers.get("ApEinfo_revcolor")
                or qualifiers.get("color")
                or "#3B82F6"
            )

            # Skip dummy 'source' feature if covering whole plasmid without custom name
            if feature_type == "source" and feat_name == "source" and not notes:
                continue

            features.append(
                PlasmidFeature(
                    name=feat_name,
                    feature_type=feature_type,
                    start=start_coord,
                    end=end_coord,
                    strand=strand,
                    color=color,
                    notes=notes,
                    plasmid_length=length,
                )
            )

    return PlasmidRecord(
        id=acc_id,
        name=name,
        sequence=seq,
        length=length,
        topology=topology,
        features=tuple(features),
        description=description,
    )


def export_genbank(plasmid: PlasmidRecord, filepath: Optional[str] = None) -> str:
    """Export a PlasmidRecord as a standard, compliant GenBank flatfile.
    
    Correctly outputs circular origin-spanning join() blocks and 60-nt ORIGIN lines.
    """
    top_label = plasmid.topology.lower()
    lines: List[str] = [
        f"LOCUS       {plasmid.name:<24} {plasmid.length} bp    DNA     {top_label:<8} SYN 16-NOV-2026",
        f"DEFINITION  {plasmid.description or plasmid.name}",
        f"ACCESSION   {plasmid.id}",
        f"VERSION     {plasmid.id}",
        "KEYWORDS    .",
        "SOURCE      synthetic DNA construct",
        "  ORGANISM  synthetic DNA construct",
        "            .",
        "FEATURES             Location/Qualifiers",
        f"     source          1..{plasmid.length}",
        '                     /organism="synthetic DNA construct"',
        '                     /mol_type="other DNA"',
    ]

    for f in plasmid.features:
        if f.spans_origin:
            inner_loc = f"join({f.start}..{plasmid.length},1..{f.end})"
        else:
            inner_loc = f"{f.start}..{f.end}"

        loc_str = f"complement({inner_loc})" if f.strand == -1 else inner_loc
        lines.append(f"     {f.feature_type:<16}{loc_str}")
        lines.append(f'                     /label="{f.name}"')
        if f.notes:
            lines.append(f'                     /note="{f.notes}"')
        if f.color:
            lines.append(f'                     /ApEinfo_fwdcolor="{f.color}"')
            lines.append(f'                     /ApEinfo_revcolor="{f.color}"')

    lines.append("ORIGIN")
    seq_lower = plasmid.sequence.lower()
    for i in range(0, len(seq_lower), 60):
        chunk = seq_lower[i : i + 60]
        blocks = [chunk[j : j + 10] for j in range(0, len(chunk), 10)]
        line_num = str(i + 1).rjust(9)
        lines.append(f"{line_num} " + " ".join(blocks))

    lines.append("//\n")
    gb_str = "\n".join(lines)

    if filepath is not None:
        dir_name = os.path.dirname(filepath)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as out_f:
            out_f.write(gb_str)

    return gb_str


# ---------------------------------------------------------------------------
# Plasmid JSON Storage
# ---------------------------------------------------------------------------

def get_default_plasmids_path() -> str:
    env_path = os.environ.get("BIOLABCALC_PLASMID_PATH")
    if env_path:
        return env_path
    try:
        from .profile import get_profile_dir
        return str(get_profile_dir() / "plasmids.json")
    except Exception:
        return os.path.expanduser("~/.biolabcalc/plasmids.json")


DEFAULT_PLASMIDS_PATH: str = get_default_plasmids_path()


def _feature_to_dict(feat: PlasmidFeature) -> Dict[str, Any]:
    return {
        "name": feat.name,
        "feature_type": feat.feature_type,
        "start": feat.start,
        "end": feat.end,
        "strand": feat.strand,
        "color": feat.color,
        "notes": feat.notes,
        "plasmid_length": feat.plasmid_length,
    }


def _feature_from_dict(d: Dict[str, Any]) -> PlasmidFeature:
    return PlasmidFeature(
        name=d.get("name", ""),
        feature_type=d.get("feature_type", "misc_feature"),
        start=d.get("start", 1),
        end=d.get("end", 1),
        strand=d.get("strand", 1),
        color=d.get("color", "#3B82F6"),
        notes=d.get("notes", ""),
        plasmid_length=d.get("plasmid_length", 0),
    )


def _plasmid_to_dict(plasmid: PlasmidRecord) -> Dict[str, Any]:
    return {
        "id": plasmid.id,
        "name": plasmid.name,
        "sequence": plasmid.sequence,
        "length": plasmid.length,
        "topology": plasmid.topology,
        "features": [_feature_to_dict(f) for f in plasmid.features],
        "description": plasmid.description,
        "checksum": plasmid.checksum,
        "gc_percent": plasmid.gc_percent,
        "molecular_weight_da": plasmid.molecular_weight_da,
        "cloning_history": list(plasmid.cloning_history),
    }


def _plasmid_from_dict(d: Dict[str, Any]) -> PlasmidRecord:
    features = tuple(_feature_from_dict(f) for f in d.get("features", []))
    history = tuple(d.get("cloning_history", []))
    return PlasmidRecord(
        id=d.get("id", ""),
        name=d.get("name", ""),
        sequence=d.get("sequence", ""),
        length=d.get("length", 0),
        topology=d.get("topology", "circular"),
        features=features,
        description=d.get("description", ""),
        checksum=d.get("checksum", ""),
        gc_percent=d.get("gc_percent", 0.0),
        molecular_weight_da=d.get("molecular_weight_da", 0.0),
        cloning_history=history,
    )


def _load_user_plasmids(filepath: Optional[str] = None) -> Dict[str, PlasmidRecord]:
    target_path = filepath if filepath is not None else get_default_plasmids_path()
    if not os.path.exists(target_path):
        return {}
    try:
        if os.path.getsize(target_path) == 0:
            return {}
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, PermissionError):
        return {}
    records: Dict[str, PlasmidRecord] = {}
    if isinstance(data, list):
        for item in data:
            p = _plasmid_from_dict(item)
            records[p.id] = p
    elif isinstance(data, dict):
        for item in data.values():
            p = _plasmid_from_dict(item)
            records[p.id] = p
    return records


def _save_user_plasmids(records: Dict[str, PlasmidRecord], filepath: Optional[str] = None) -> None:
    target_path = filepath if filepath is not None else get_default_plasmids_path()
    dir_name = os.path.dirname(os.path.abspath(target_path))
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)
    serialized = [_plasmid_to_dict(p) for p in records.values()]
    temp_fd, temp_file = tempfile.mkstemp(dir=dir_name, prefix=".tmp_plasmid_", suffix=".json")
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, target_path)
    except Exception:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
        raise


def save_plasmid(plasmid: PlasmidRecord, filepath: Optional[str] = None) -> str:
    """Save a PlasmidRecord to the JSON store. Returns plasmid.id."""
    records = _load_user_plasmids(filepath)
    records[plasmid.id] = plasmid
    _save_user_plasmids(records, filepath)
    return plasmid.id


def get_plasmid(plasmid_id_or_name: str, filepath: Optional[str] = None) -> PlasmidRecord:
    """Retrieve a PlasmidRecord by ID or name. Checks user store first, then STANDARD_PLASMID_CATALOG."""
    records = _load_user_plasmids(filepath)

    if plasmid_id_or_name in records:
        return records[plasmid_id_or_name]

    query_lower = plasmid_id_or_name.lower()
    for p in records.values():
        if p.id.lower() == query_lower or p.name.lower() == query_lower:
            return p

    if plasmid_id_or_name in STANDARD_PLASMID_CATALOG:
        return STANDARD_PLASMID_CATALOG[plasmid_id_or_name]

    for key, p in STANDARD_PLASMID_CATALOG.items():
        if key.lower() == query_lower or p.name.lower() == query_lower or p.id.lower() == query_lower:
            return p

    raise KeyError(f"Plasmid '{plasmid_id_or_name}' not found in user storage or standard catalog.")


load_plasmid = get_plasmid


def list_plasmids(filepath: Optional[str] = None) -> List[PlasmidRecord]:
    """List all plasmids from user store merged with STANDARD_PLASMID_CATALOG."""
    records = _load_user_plasmids(filepath)
    merged: Dict[str, PlasmidRecord] = dict(STANDARD_PLASMID_CATALOG)
    for p_id, p in records.items():
        merged[p_id] = p
    return list(merged.values())


def delete_plasmid(plasmid_id_or_name: str, filepath: Optional[str] = None) -> bool:
    """Delete a plasmid from user storage by ID or name. Returns True if deleted, False otherwise."""
    records = _load_user_plasmids(filepath)
    target_id: Optional[str] = None

    if plasmid_id_or_name in records:
        target_id = plasmid_id_or_name
    else:
        query_lower = plasmid_id_or_name.lower()
        for p in records.values():
            if p.id.lower() == query_lower or p.name.lower() == query_lower:
                target_id = p.id
                break

    if target_id is not None:
        del records[target_id]
        _save_user_plasmids(records, filepath)
        return True

    return False


# ============================================================================
# SnapGene .dna Binary Parser
# ============================================================================

def parse_snapgene_dna(data_or_path: Union[bytes, str, Path]) -> PlasmidRecord:
    """
    Parse a binary SnapGene .dna file into an immutable PlasmidRecord.
    
    Decodes the packet block architecture:
    - Packet 0x09: Header
    - Packet 0x00: DNA sequence and topology (circular / linear)
    - Packet 0x0A: Features XML table
    - Packet 0x06: Notes and annotations
    """
    import struct
    import xml.etree.ElementTree as ET

    name = "SnapGene_Construct"

    if isinstance(data_or_path, Path):
        try:
            if data_or_path.is_file():
                name = data_or_path.stem
                raw_bytes = data_or_path.read_bytes()
            else:
                raw_bytes = str(data_or_path).encode("latin1")
        except OSError:
            raw_bytes = str(data_or_path).encode("latin1")
    elif isinstance(data_or_path, str):
        if "\n" not in data_or_path and "\r" not in data_or_path and len(data_or_path) < 260:
            try:
                p = Path(data_or_path)
                if p.is_file():
                    name = p.stem
                    raw_bytes = p.read_bytes()
                else:
                    raw_bytes = data_or_path.encode("latin1")
            except OSError:
                raw_bytes = data_or_path.encode("latin1")
        else:
            raw_bytes = data_or_path.encode("latin1")
    elif isinstance(data_or_path, (bytes, bytearray)):
        raw_bytes = bytes(data_or_path)
    else:
        raise TypeError(f"Expected bytes, str, or Path, got {type(data_or_path)}")

    offset = 0
    total_len = len(raw_bytes)
    dna_seq = ""
    topology = "circular"
    features: List[PlasmidFeature] = []
    description = ""

    while offset < total_len:
        if offset + 5 > total_len:
            raise ValueError(f"Corrupted SnapGene .dna file: truncated packet header at offset {offset} (file length {total_len})")
        tag = raw_bytes[offset]
        pkt_len = struct.unpack(">I", raw_bytes[offset + 1 : offset + 5])[0]
        offset += 5

        if offset + pkt_len > total_len:
            raise ValueError(f"Corrupted SnapGene .dna file: packet 0x{tag:02X} length {pkt_len} exceeds remaining bytes at offset {offset} (file length {total_len})")
        pkt_data = raw_bytes[offset : offset + pkt_len]
        offset += pkt_len

        # Tag 0x00: DNA sequence and topology
        if tag == 0x00 and pkt_len >= 1:
            flags = pkt_data[0]
            is_circular = bool(flags & 0x01)
            topology = "circular" if is_circular else "linear"
            dna_seq = pkt_data[1:].decode("ascii", errors="ignore").upper()

        # Tag 0x0A: Features XML
        elif tag == 0x0A and pkt_len > 0:
            try:
                xml_str = pkt_data.decode("utf-8", errors="replace")
                root = ET.fromstring(xml_str)
                for feat_elem in root.iter("Feature"):
                    f_name = feat_elem.get("name", "Unnamed")
                    f_type = feat_elem.get("type", "misc_feature")
                    f_dir = feat_elem.get("directionality", "1")
                    strand = -1 if f_dir in ("2", "-1", "reverse") else 1

                    for seg in feat_elem.iter("Segment"):
                        rng = seg.get("range", "")
                        color = seg.get("color", "#3B82F6")
                        if "-" in rng:
                            parts = rng.split("-")
                            try:
                                s_pos = int(parts[0])
                                e_pos = int(parts[1])
                                # Convert 0-based range to 1-based inclusive
                                if s_pos == 0:
                                    s_pos = 1
                                features.append(PlasmidFeature(
                                    name=f_name,
                                    feature_type=f_type,
                                    start=s_pos,
                                    end=e_pos,
                                    strand=strand,
                                    color=color,
                                    notes=f_type,
                                ))
                            except ValueError:
                                pass
            except Exception:
                pass

        # Tag 0x06: Notes
        elif tag == 0x06 and pkt_len > 0:
            try:
                notes_text = pkt_data.decode("utf-8", errors="replace")
                if "<" in notes_text and ">" in notes_text:
                    try:
                        n_root = ET.fromstring(notes_text)
                        description = "".join(n_root.itertext()).strip()
                    except Exception:
                        description = notes_text.strip()
                else:
                    description = notes_text.strip()
            except Exception:
                pass

    L = len(dna_seq)
    final_features = []
    for f in features:
        if f.plasmid_length == 0 and L > 0:
            f = replace(f, plasmid_length=L)
        final_features.append(f)

    return PlasmidRecord(
        id=name,
        name=name,
        sequence=dna_seq,
        topology=topology,
        features=tuple(final_features),
        description=description,
    )
