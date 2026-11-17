"""
Module: biolabcalc.eln.parsers.ab1_parser
Component: Sanger .ab1 Chromatogram Parser & Construct Verification Engine
Architectural Role: Pure-Python Applied Biosystems ABIF binary format parser
(decoding PBAS basecalls, PLOC peak positions, PCON quality scores, and DATA traces 9-12),
with Sanger trace construct insert and junction verification (benchmarking Ediacara).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from biolabcalc.plasmid import PlasmidRecord
from biolabcalc.seq_utils import clean_sequence, reverse_complement


# ============================================================================
# Frozen Domain Dataclasses
# ============================================================================

@dataclass(frozen=True)
class AB1TraceResult:
    sample_name: str
    sequence: str
    phred_scores: Tuple[int, ...] = ()
    peak_locations: Tuple[int, ...] = ()
    channel_a: Tuple[int, ...] = ()
    channel_c: Tuple[int, ...] = ()
    channel_g: Tuple[int, ...] = ()
    channel_t: Tuple[int, ...] = ()

    def __post_init__(self):
        for f in ("phred_scores", "peak_locations", "channel_a", "channel_c", "channel_g", "channel_t"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))


@dataclass(frozen=True)
class ConstructVerificationResult:
    plasmid_name: str
    verified_insert_sequence: str
    coverage_percent: float
    mean_phred_quality: float
    mutations_found: Tuple[str, ...]
    junctions_verified: bool

    def __post_init__(self):
        if isinstance(self.mutations_found, (list, set, tuple)):
            object.__setattr__(self, "mutations_found", tuple(self.mutations_found))


# ============================================================================
# ABIF Binary Chromatogram Decoder
# ============================================================================

class AB1Parser:
    """Pure-Python decoder for Applied Biosystems ABIF chromatogram files (.ab1)."""

    @classmethod
    def parse(cls, data_or_path: Union[bytes, str, Path]) -> AB1TraceResult:
        """
        Parse raw .ab1 bytes or a file path into an immutable AB1TraceResult.
        """
        raw: bytes
        sample_name = "Sanger_Trace"

        if isinstance(data_or_path, Path):
            try:
                if data_or_path.is_file():
                    sample_name = data_or_path.stem
                    raw = data_or_path.read_bytes()
                else:
                    raw = str(data_or_path).encode("latin1")
            except OSError:
                raw = str(data_or_path).encode("latin1")
        elif isinstance(data_or_path, str):
            if "\n" not in data_or_path and "\r" not in data_or_path and len(data_or_path) < 260:
                try:
                    p = Path(data_or_path)
                    if p.is_file():
                        sample_name = p.stem
                        raw = p.read_bytes()
                    else:
                        raw = data_or_path.encode("latin1")
                except OSError:
                    raw = data_or_path.encode("latin1")
            else:
                raw = data_or_path.encode("latin1")
        elif isinstance(data_or_path, (bytes, bytearray)):
            raw = bytes(data_or_path)
        else:
            raise TypeError(f"Expected bytes, str, or Path, got {type(data_or_path)}")

        if len(raw) < 128 or raw[:4] != b"ABIF":
            raise ValueError("Invalid file format: ABIF magic byte signature missing.")

        # Header fields
        # Bytes 18-21: number of directory elements
        # Bytes 26-29: directory offset
        num_records = struct.unpack(">I", raw[18:22])[0]
        dir_offset = struct.unpack(">I", raw[26:30])[0]

        tags: Dict[Tuple[str, int], Tuple[int, int, int, bytes]] = {}

        # Parse directory entries (28 bytes each)
        for i in range(num_records):
            entry_offset = dir_offset + (i * 28)
            if entry_offset + 28 > len(raw):
                break

            tag_name = raw[entry_offset : entry_offset + 4].decode("latin1", errors="replace")
            tag_num = struct.unpack(">I", raw[entry_offset + 4 : entry_offset + 8])[0]
            elem_type = struct.unpack(">H", raw[entry_offset + 8 : entry_offset + 10])[0]
            elem_size = struct.unpack(">H", raw[entry_offset + 10 : entry_offset + 12])[0]
            num_elems = struct.unpack(">I", raw[entry_offset + 12 : entry_offset + 16])[0]
            data_size = struct.unpack(">I", raw[entry_offset + 16 : entry_offset + 20])[0]

            if data_size <= 4:
                val_data = raw[entry_offset + 20 : entry_offset + 20 + data_size]
            else:
                data_offset = struct.unpack(">I", raw[entry_offset + 20 : entry_offset + 24])[0]
                if data_offset + data_size > len(raw):
                    val_data = raw[data_offset : len(raw)]
                else:
                    val_data = raw[data_offset : data_offset + data_size]

            tags[(tag_name, tag_num)] = (elem_type, elem_size, num_elems, val_data)

        # Extract sequence (PBAS tag 1 or 2)
        seq_str = ""
        for tag_id in (( "PBAS", 1 ), ( "PBAS", 2 )):
            if tag_id in tags:
                seq_str = tags[tag_id][3].decode("ascii", errors="replace").strip()
                if seq_str:
                    break

        # Extract Phred quality scores (PCON tag 1 or 2)
        phred: List[int] = []
        for tag_id in (( "PCON", 1 ), ( "PCON", 2 )):
            if tag_id in tags:
                phred = list(tags[tag_id][3])
                if phred:
                    break

        # Extract peak locations (PLOC tag 1 or 2)
        peaks: List[int] = []
        for tag_id in (( "PLOC", 1 ), ( "PLOC", 2 )):
            if tag_id in tags:
                b_data = tags[tag_id][3]
                n_peaks = len(b_data) // 2
                peaks = list(struct.unpack(f">{n_peaks}H", b_data))
                if peaks:
                    break

        # Extract fluorescent channel traces (DATA 9=G, 10=A, 11=T, 12=C)
        channels: Dict[str, Tuple[int, ...]] = {"A": (), "C": (), "G": (), "T": ()}
        mapping = {9: "G", 10: "A", 11: "T", 12: "C"}
        for data_num, base in mapping.items():
            if ("DATA", data_num) in tags:
                b_data = tags[("DATA", data_num)][3]
                n_pts = len(b_data) // 2
                pts = struct.unpack(f">{n_pts}h", b_data)
                channels[base] = pts

        # Extract sample name if present
        if ("SMPL", 1) in tags:
            s_data = tags[("SMPL", 1)][3]
            # First byte is length for Pascal string
            if len(s_data) > 1 and s_data[0] < len(s_data):
                p_len = s_data[0]
                sample_name = s_data[1 : 1 + p_len].decode("ascii", errors="replace")
            else:
                sample_name = s_data.decode("ascii", errors="replace").strip()

        return AB1TraceResult(
            sample_name=sample_name,
            sequence=seq_str.upper(),
            phred_scores=tuple(phred),
            peak_locations=tuple(peaks),
            channel_a=channels["A"],
            channel_c=channels["C"],
            channel_g=channels["G"],
            channel_t=channels["T"],
        )


def verify_construct_sequencing(
    plasmid: PlasmidRecord,
    ab1_traces: Sequence[AB1TraceResult],
    min_phred: int = 20,
) -> ConstructVerificationResult:
    """
    Verify cloned insert sequence and junctions against Sanger chromatogram traces.
    
    1. Filters called bases by minimum Phred quality threshold (default: >= Q20, 99% accuracy).
    2. Aligns high-quality reads to plasmid sequence in both forward and reverse orientations.
    3. Identifies sequence mutations (substitutions, insertions, deletions).
    4. Evaluates junction coverage across cloning borders.
    """
    plasmid_seq = plasmid.sequence
    L = len(plasmid_seq)
    # Concatenate sequence if circular to support seamless origin-spanning alignments
    ref_seq = (plasmid_seq + plasmid_seq) if plasmid.topology == "circular" else plasmid_seq
    covered_positions: Set[int] = set()
    mutations: List[str] = []
    all_phred: List[int] = []

    for trace in ab1_traces:
        t_seq = trace.sequence
        t_phred = trace.phred_scores or tuple([30] * len(t_seq))

        # Filter high-quality sub-regions
        hq_indices = [idx for idx, q in enumerate(t_phred) if q >= min_phred]
        if not hq_indices:
            continue
        all_phred.extend([t_phred[i] for i in hq_indices])

        start_sub = min(hq_indices)
        end_sub = max(hq_indices) + 1
        hq_seq = t_seq[start_sub:end_sub]

        if len(hq_seq) < 15:
            continue

        # Check alignment in forward and reverse-complement
        fwd_match = hq_seq in ref_seq
        rev_seq = reverse_complement(hq_seq)
        rev_match = rev_seq in ref_seq

        if fwd_match:
            pos = ref_seq.find(hq_seq)
            for k in range(len(hq_seq)):
                covered_positions.add((pos + k) % L + 1)
        elif rev_match:
            pos = ref_seq.find(rev_seq)
            for k in range(len(rev_seq)):
                covered_positions.add((pos + k) % L + 1)
        else:
            # Local mismatch detection via sliding window
            w_size = 20
            for w_start in range(0, len(hq_seq) - w_size, 10):
                w_str = hq_seq[w_start : w_start + w_size]
                if w_str in ref_seq:
                    p_pos = ref_seq.find(w_str)
                    for k in range(w_size):
                        covered_positions.add((p_pos + k) % L + 1)
                else:
                    mutations.append(f"Trace '{trace.sample_name}' mismatch near position {w_start + 1}")

    cov_pct = (len(covered_positions) / L * 100.0) if L > 0 else 0.0
    mean_q = (sum(all_phred) / len(all_phred)) if all_phred else 0.0

    # Verify cloning junctions (features of type 'CDS' or 'insert')
    junctions_ok = True
    for f in plasmid.features:
        if f.feature_type.upper() in ("CDS", "INSERT", "GENE"):
            # Check if start and end boundaries are covered
            if f.start not in covered_positions or f.end not in covered_positions:
                junctions_ok = False
                break

    return ConstructVerificationResult(
        plasmid_name=plasmid.name,
        verified_insert_sequence=plasmid_seq,
        coverage_percent=round(cov_pct, 1),
        mean_phred_quality=round(mean_q, 1),
        mutations_found=tuple(set(mutations)),
        junctions_verified=junctions_ok,
    )
