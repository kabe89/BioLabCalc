"""
Tests for Sanger .ab1 Chromatogram Parser and Construct Verification
"""

import os
import struct
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.eln.parsers.ab1_parser import (
    AB1Parser,
    AB1TraceResult,
    ConstructVerificationResult,
    verify_construct_sequencing,
)
from biolabcalc.plasmid import PlasmidFeature, PlasmidRecord


def create_synthetic_abif(
    seq: str = "ATGCGATCGATCGATC",
    phred_scores: list[int] = None,
    sample_name: str = "Trace_Sample_01",
) -> bytes:
    """Generate a valid synthetic ABIF binary byte stream."""
    if phred_scores is None:
        phred_scores = [35] * len(seq)

    # We will build data payload at offset >= 128
    header = bytearray(128)
    header[0:4] = b"ABIF"
    struct.pack_into(">H", header, 4, 101)  # Version

    # Directory entries:
    # 1. PBAS 1: sequence
    # 2. PCON 1: phred scores
    # 3. PLOC 1: peak locations (uint16 for each base)
    # 4. DATA 9: G trace (dummy uint16 array)
    # 5. DATA 10: A trace
    # 6. DATA 11: T trace
    # 7. DATA 12: C trace
    # 8. SMPL 1: sample name (Pascal string: 1 byte len + str)

    seq_bytes = seq.encode("ascii")
    pcon_bytes = bytes(phred_scores)
    ploc_data = bytearray()
    for i in range(len(seq)):
        ploc_data.extend(struct.pack(">H", (i + 1) * 10))
    ploc_bytes = bytes(ploc_data)

    dummy_trace = bytearray()
    for _ in range(len(seq) * 10):
        dummy_trace.extend(struct.pack(">h", 100))
    trace_bytes = bytes(dummy_trace)

    smpl_bytes = bytes([len(sample_name)]) + sample_name.encode("ascii")

    # Layout after header:
    # First directory table: 8 records * 28 bytes = 224 bytes
    dir_offset = 128
    num_records = 8
    data_start = dir_offset + (num_records * 28)

    data_blocks = [
        ("PBAS", 1, 2, 1, len(seq_bytes), seq_bytes),
        ("PCON", 1, 2, 1, len(pcon_bytes), pcon_bytes),
        ("PLOC", 1, 4, 2, len(seq), ploc_bytes),
        ("DATA", 9, 4, 2, len(dummy_trace) // 2, trace_bytes),
        ("DATA", 10, 4, 2, len(dummy_trace) // 2, trace_bytes),
        ("DATA", 11, 4, 2, len(dummy_trace) // 2, trace_bytes),
        ("DATA", 12, 4, 2, len(dummy_trace) // 2, trace_bytes),
        ("SMPL", 1, 2, 1, len(smpl_bytes), smpl_bytes),
    ]

    struct.pack_into(">I", header, 18, num_records)
    struct.pack_into(">I", header, 26, dir_offset)

    dir_table = bytearray()
    curr_data_offset = data_start
    data_section = bytearray()

    for tag, num, el_type, el_size, n_elem, b_val in data_blocks:
        d_len = len(b_val)
        entry = bytearray(28)
        entry[0:4] = tag.encode("latin1")
        struct.pack_into(">I", entry, 4, num)
        struct.pack_into(">H", entry, 8, el_type)
        struct.pack_into(">H", entry, 10, el_size)
        struct.pack_into(">I", entry, 12, n_elem)
        struct.pack_into(">I", entry, 16, d_len)

        if d_len <= 4:
            entry[20 : 20 + d_len] = b_val
        else:
            struct.pack_into(">I", entry, 20, curr_data_offset)
            data_section.extend(b_val)
            curr_data_offset += d_len

        dir_table.extend(entry)

    return bytes(header + dir_table + data_section)


class TestAB1Parser(unittest.TestCase):
    def test_parse_ab1_trace(self):
        seq = "ATGCGATCGATCGATC"
        raw = create_synthetic_abif(seq=seq, sample_name="Synthetic_Sample")
        res = AB1Parser.parse(raw)

        self.assertIsInstance(res, AB1TraceResult)
        self.assertEqual(res.sequence, seq)
        self.assertEqual(res.sample_name, "Synthetic_Sample")
        self.assertEqual(len(res.phred_scores), len(seq))
        self.assertTrue(all(q == 35 for q in res.phred_scores))
        self.assertEqual(len(res.peak_locations), len(seq))
        self.assertEqual(len(res.channel_a), len(seq) * 10)
        self.assertIsInstance(res.phred_scores, tuple)

    def test_parse_ab1_file(self):
        seq = "GCATGCATGCAT"
        raw = create_synthetic_abif(seq=seq, sample_name="File_Sample")
        with tempfile.TemporaryDirectory() as tmpdir:
            f_path = Path(tmpdir) / "test_trace.ab1"
            f_path.write_bytes(raw)

            res = AB1Parser.parse(f_path)
            self.assertEqual(res.sample_name, "File_Sample")
            self.assertEqual(res.sequence, seq)

    def test_verify_construct_sequencing(self):
        plasmid_seq = "NNNNNATGCGATCGATCGATCNNNNN"
        feat = PlasmidFeature(name="Insert", feature_type="CDS", start=6, end=21)
        plasmid = PlasmidRecord(
            id="pTest",
            name="pTest",
            sequence=plasmid_seq,
            topology="circular",
            features=(feat,),
        )

        trace = AB1Parser.parse(create_synthetic_abif(seq="ATGCGATCGATCGATC"))
        verify_res = verify_construct_sequencing(plasmid, [trace], min_phred=20)

        self.assertIsInstance(verify_res, ConstructVerificationResult)
        self.assertGreater(verify_res.coverage_percent, 50.0)
        self.assertGreaterEqual(verify_res.mean_phred_quality, 30.0)
        self.assertTrue(verify_res.junctions_verified)
        self.assertIsInstance(verify_res.mutations_found, tuple)

    def test_frozen_immutability(self):
        res = AB1Parser.parse(create_synthetic_abif())
        with self.assertRaises(FrozenInstanceError):
            res.sequence = "MUTATED"
        with self.assertRaises(FrozenInstanceError):
            res.sample_name = "Hacked"


if __name__ == "__main__":
    unittest.main()
