"""
Tests for SnapGene (.dna) Binary Parser
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

from biolabcalc.plasmid import PlasmidRecord, parse_snapgene_dna


def create_synthetic_snapgene_dna(
    sequence: str = "ATGCGTACGTTAGCTAGCTAGCTA",
    circular: bool = True,
    features_xml: str = '<Features><Feature name="AmpR" type="CDS" directionality="1"><Segment range="1-24" color="#3B82F6"/></Feature></Features>',
    notes_xml: str = "Synthetic Test Construct",
) -> bytes:
    """Create a minimal valid synthetic SnapGene .dna binary byte stream."""
    out = bytearray()

    # Packet 0x09: Header
    header_content = b"SnapGene"
    out.append(0x09)
    out.extend(struct.pack(">I", len(header_content)))
    out.extend(header_content)

    # Packet 0x00: DNA sequence and topology
    # 1 byte flags: 0x01 = circular, 0x00 = linear
    flags = 0x01 if circular else 0x00
    dna_bytes = bytes([flags]) + sequence.encode("ascii")
    out.append(0x00)
    out.extend(struct.pack(">I", len(dna_bytes)))
    out.extend(dna_bytes)

    # Packet 0x0A: Features XML
    if features_xml:
        xml_bytes = features_xml.encode("utf-8")
        out.append(0x0A)
        out.extend(struct.pack(">I", len(xml_bytes)))
        out.extend(xml_bytes)

    # Packet 0x06: Notes
    if notes_xml:
        n_bytes = notes_xml.encode("utf-8")
        out.append(0x06)
        out.extend(struct.pack(">I", len(n_bytes)))
        out.extend(n_bytes)

    return bytes(out)


class TestSnapGeneParser(unittest.TestCase):
    def test_parse_snapgene_bytes(self):
        seq = "ATGCGTACGTTAGCTAGCTAGCTA"
        raw = create_synthetic_snapgene_dna(sequence=seq, circular=True)
        record = parse_snapgene_dna(raw)

        self.assertIsInstance(record, PlasmidRecord)
        self.assertEqual(record.sequence, seq)
        self.assertEqual(record.topology, "circular")
        self.assertIsInstance(record.features, tuple)
        self.assertEqual(len(record.features), 1)
        feat = record.features[0]
        self.assertEqual(feat.name, "AmpR")
        self.assertEqual(feat.feature_type, "CDS")
        self.assertEqual(feat.start, 1)
        self.assertEqual(feat.end, 24)
        self.assertEqual(feat.strand, 1)

    def test_parse_snapgene_linear(self):
        seq = "GGATCCGAATTC"
        raw = create_synthetic_snapgene_dna(sequence=seq, circular=False, features_xml="")
        record = parse_snapgene_dna(raw)

        self.assertEqual(record.sequence, seq)
        self.assertEqual(record.topology, "linear")
        self.assertEqual(len(record.features), 0)

    def test_parse_snapgene_file(self):
        seq = "CCCGGGAAATTT"
        raw = create_synthetic_snapgene_dna(sequence=seq, circular=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_plasmid.dna"
            file_path.write_bytes(raw)

            record = parse_snapgene_dna(file_path)
            self.assertEqual(record.name, "test_plasmid")
            self.assertEqual(record.sequence, seq)
            self.assertEqual(record.topology, "circular")

    def test_frozen_immutability(self):
        raw = create_synthetic_snapgene_dna()
        record = parse_snapgene_dna(raw)
        with self.assertRaises(FrozenInstanceError):
            record.name = "Mutated"
        with self.assertRaises(FrozenInstanceError):
            record.features[0].name = "MutatedFeature"


if __name__ == "__main__":
    unittest.main()
