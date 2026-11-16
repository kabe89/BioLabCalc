"""Unit tests for Circular Plasmid Storage, Modulo-L Coordinates, Annotation, and GenBank I/O."""

import os
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError

# Ensure src directory is in sys.path
_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.plasmid import (
    STANDARD_PLASMID_CATALOG,
    PlasmidFeature,
    PlasmidRecord,
    auto_annotate_plasmid,
    delete_plasmid,
    export_genbank,
    extract_subsequence,
    find_orfs,
    get_plasmid,
    insert_subsequence,
    list_plasmids,
    parse_genbank,
    rotate_origin,
    save_plasmid,
)


class TestPlasmidStorageAndCoordinates(unittest.TestCase):
    """Test suite for PlasmidRecord, PlasmidFeature, Circular Coordinates, and GenBank."""

    def test_plasmid_feature_immutability_and_length(self):
        """PlasmidFeature must be frozen and calculate lengths correctly for linear and origin-spanning."""
        feat_linear = PlasmidFeature("AmpR", "CDS", 100, 200, 1, "#3B82F6", "linear feature", plasmid_length=1000)
        self.assertFalse(feat_linear.spans_origin)
        self.assertEqual(feat_linear.length, 101)
        self.assertEqual(feat_linear.get_length(1000), 101)

        with self.assertRaises(FrozenInstanceError):
            feat_linear.start = 105  # type: ignore

        # Origin-spanning feature: start (950) > end (50) in 1000 bp plasmid
        feat_spanning = PlasmidFeature("Ori_Spanner", "promoter", 950, 50, 1, "#EF4444", "origin spanning", plasmid_length=1000)
        self.assertTrue(feat_spanning.spans_origin)
        # Length = (1000 - 950 + 1) + 50 = 51 + 50 = 101
        self.assertEqual(feat_spanning.length, 101)
        self.assertEqual(feat_spanning.get_length(1000), 101)

    def test_plasmid_record_immutability_and_metrics(self):
        """PlasmidRecord must be frozen and compute length, checksum, GC %, and MW automatically."""
        seq = "ATGC" * 250  # 1000 bp
        plasmid = PlasmidRecord(
            id="pTest_1000",
            name="pTest_1000",
            sequence=seq,
            topology="circular",
        )
        self.assertEqual(plasmid.length, 1000)
        self.assertEqual(len(plasmid.checksum), 16)
        self.assertEqual(plasmid.gc_percent, 50.0)
        self.assertGreater(plasmid.molecular_weight_da, 600000.0)

        with self.assertRaises(FrozenInstanceError):
            plasmid.topology = "linear"  # type: ignore

        with self.assertRaises(FrozenInstanceError):
            plasmid.sequence = "ACGT"  # type: ignore

    def test_extract_subsequence_linear_and_circular(self):
        """extract_subsequence should handle linear slices, circular wrap-around, and reverse strands."""
        seq = "ABCDEFGHIJ"  # L = 10
        # 1-based:
        # 1: A, 2: B, 3: C, 4: D, 5: E, 6: F, 7: G, 8: H, 9: I, 10: J
        # Normal slice 2..5 -> BCDE
        self.assertEqual(extract_subsequence(seq, 2, 5), "BCDE")

        # Origin-spanning slice 8..3 -> HIJ + ABC = HIJABC
        self.assertEqual(extract_subsequence(seq, 8, 3), "HIJABC")

        # Reverse strand on DNA sequence
        dna_seq = "ATGCATGCAT"  # L = 10
        # Slice 1..4 = ATGC, reverse complement = GCAT
        self.assertEqual(extract_subsequence(dna_seq, 1, 4, strand=1), "ATGC")
        self.assertEqual(extract_subsequence(dna_seq, 1, 4, strand=-1), "GCAT")

        # Origin spanning on DNA: 9..2 -> AT + AT = ATAT, RC = ATAT
        self.assertEqual(extract_subsequence(dna_seq, 9, 2, strand=1), "ATAT")

    def test_rotate_origin_invariance(self):
        """rotate_origin must preserve sequence content, feature lengths, and extracted DNA sequences."""
        seq = "A" * 100 + "G" * 100 + "C" * 100 + "T" * 100  # L = 400
        # Linear feature in G block: 101..200 (length 100)
        f_linear = PlasmidFeature("G_Block", "CDS", 101, 200, 1)
        # Origin-spanning feature in T+A block: 351..50 (length: (400-351+1)+50 = 100)
        f_spanning = PlasmidFeature("TA_Block", "promoter", 351, 50, 1)

        plasmid = PlasmidRecord(
            id="pRotTest",
            name="pRotTest",
            sequence=seq,
            topology="circular",
            features=(f_linear, f_spanning),
        )

        # Rotate origin to position 150 (inside G-block)
        rotated = rotate_origin(plasmid, 150)
        self.assertEqual(rotated.length, 400)
        self.assertIn("Rotated origin to position 150", rotated.cloning_history[0])

        # Sequence invariance: rotated[1] must match original[150]
        self.assertEqual(rotated.sequence[0], plasmid.sequence[149])

        # Feature count preserved
        self.assertEqual(len(rotated.features), 2)
        rot_g = [f for f in rotated.features if f.name == "G_Block"][0]
        rot_ta = [f for f in rotated.features if f.name == "TA_Block"][0]

        # Invariance: Feature lengths must remain exactly 100 bp!
        self.assertEqual(rot_g.length, 100)
        self.assertEqual(rot_ta.length, 100)

        # Coordinate transformation:
        # G_Block was 101..200. With new_origin = 150:
        # new_start = ((101 - 150) % 400) + 1 = (-49 % 400) + 1 = 351 + 1 = 352
        # new_end = ((200 - 150) % 400) + 1 = (50 % 400) + 1 = 51
        # Now G_Block spans the new origin (352 > 51)!
        self.assertTrue(rot_g.spans_origin)
        self.assertEqual(rot_g.start, 352)
        self.assertEqual(rot_g.end, 51)
        # Length: (400 - 352 + 1) + 51 = 49 + 51 = 100
        self.assertEqual(rot_g.length, 100)

        # Subsequence extracted from rotated plasmid must match subsequence from original
        orig_seq_g = extract_subsequence(plasmid, f_linear.start, f_linear.end)
        rot_seq_g = extract_subsequence(rotated, rot_g.start, rot_g.end)
        self.assertEqual(orig_seq_g, rot_seq_g)

    def test_insert_subsequence(self):
        """insert_subsequence should support insertion, range replacement, and coordinate updates."""
        seq = "AAAAATTTTT"  # L = 10
        f1 = PlasmidFeature("A_Block", "misc_feature", 1, 5, 1)
        f2 = PlasmidFeature("T_Block", "misc_feature", 6, 10, 1)

        plasmid = PlasmidRecord(
            id="pInsTest",
            name="pInsTest",
            sequence=seq,
            topology="circular",
            features=(f1, f2),
        )

        # 1. Pure insertion at position 6 (between A's and T's)
        inserted = insert_subsequence(plasmid, 6, "GGGG")
        self.assertEqual(inserted.length, 14)
        self.assertEqual(inserted.sequence, "AAAAAGGGGTTTTT")
        # Feature 1 (1..5) should be unchanged
        self.assertEqual(inserted.features[0].start, 1)
        self.assertEqual(inserted.features[0].end, 5)
        # Feature 2 (6..10) was at insertion point -> shifted by 4 to 10..14
        self.assertEqual(inserted.features[1].start, 10)
        self.assertEqual(inserted.features[1].end, 14)

        # 2. Range replacement: replace 6..10 with 'CCCC'
        replaced = insert_subsequence(plasmid, 6, "CCCC", replace_end_1based=10)
        self.assertEqual(replaced.length, 9)
        self.assertEqual(replaced.sequence, "AAAAACCCC")
        self.assertIn("Replaced region 6..10", replaced.cloning_history[0])

    def test_find_orfs_circular(self):
        """find_orfs must detect both linear ORFs and circular ORFs wrapping around base 1."""
        # Create an artificial sequence with an ORF that wraps across base 1
        # L = 210 bp.
        # ORF part 1 at end: ATG + 15 aa codons = 48 nt (positions 163..210)
        # ORF part 2 at beginning: 20 aa codons + TAA = 63 nt (positions 1..63)
        # Total ORF length = 48 + 63 = 111 nt (36 aa excluding stop)
        orf_tail = "ATG" + "GCA" * 15  # 48 nt
        spacer = "T" * 99  # 99 nt
        orf_head = "GCA" * 20 + "TAA"  # 63 nt
        circ_seq = orf_head + spacer + orf_tail  # Total len = 63 + 99 + 48 = 210 nt

        orfs = find_orfs(circ_seq, min_aa=30, circular=True)
        wrapping_orfs = [o for o in orfs if o.start_nt > o.end_nt]
        self.assertGreater(len(wrapping_orfs), 0, "Failed to identify circular origin-spanning ORF")
        w_orf = wrapping_orfs[0]
        self.assertEqual(w_orf.start_nt, 163)
        self.assertEqual(w_orf.end_nt, 63)
        self.assertEqual(w_orf.length_aa, 36)
        self.assertTrue(w_orf.protein_sequence.startswith("M"))

        # When circular=False, this wrapping ORF should not be detected
        linear_orfs = find_orfs(circ_seq, min_aa=30, circular=False)
        linear_wrapping = [o for o in linear_orfs if o.start_nt > o.end_nt]
        self.assertEqual(len(linear_wrapping), 0)

    def test_standard_plasmid_catalog(self):
        """Verify the 4 standard plasmids in STANDARD_PLASMID_CATALOG."""
        required = ["pUC19", "pET-28a(+)", "pcDNA3.1(+)", "pGoldenGate-Dest"]
        for name in required:
            self.assertIn(name, STANDARD_PLASMID_CATALOG)
            p = STANDARD_PLASMID_CATALOG[name]
            self.assertIsInstance(p, PlasmidRecord)
            self.assertEqual(p.topology, "circular")
            self.assertGreater(p.length, 1000)
            self.assertGreater(len(p.features), 0)
            self.assertGreater(p.molecular_weight_da, 500000.0)

        # pUC19 specific checks
        puc19 = STANDARD_PLASMID_CATALOG["pUC19"]
        self.assertEqual(puc19.length, 2686)
        feat_names = [f.name for f in puc19.features]
        self.assertIn("AmpR", feat_names)
        self.assertIn("ColE1_ori", feat_names)
        self.assertIn("MCS", feat_names)
        self.assertIn("lacZ_alpha", feat_names)

        # pET-28a(+) specific checks
        pet28 = STANDARD_PLASMID_CATALOG["pET-28a(+)"]
        self.assertEqual(pet28.length, 5369)
        pet_feats = [f.name for f in pet28.features]
        self.assertIn("T7_promoter", pet_feats)
        self.assertIn("KanR", pet_feats)

        # pGoldenGate-Dest specific checks
        pgg = STANDARD_PLASMID_CATALOG["pGoldenGate-Dest"]
        pgg_feats = [f.name for f in pgg.features]
        self.assertIn("BsaI_site_5p", pgg_feats)
        self.assertIn("BsaI_site_3p", pgg_feats)
        self.assertIn("ccdB_dropout", pgg_feats)

    def test_auto_annotate_plasmid(self):
        """auto_annotate_plasmid should automatically locate promoters, origins, and markers."""
        puc19 = STANDARD_PLASMID_CATALOG["pUC19"]
        annotated = auto_annotate_plasmid(puc19.sequence, name="pUC19_auto")
        self.assertEqual(annotated.length, 2686)

        found_types = {f.feature_type for f in annotated.features}
        self.assertIn("operator", found_types)
        self.assertIn("promoter", found_types)
        self.assertIn("rep_origin", found_types)
        self.assertIn("CDS", found_types)

        found_names = {f.name for f in annotated.features}
        self.assertIn("lac Operator", found_names)
        self.assertIn("ColE1/pUC Origin", found_names)
        self.assertIn("AmpR (bla)", found_names)

    def test_genbank_export_and_roundtrip_parsing(self):
        """export_genbank and parse_genbank should produce identical records upon roundtrip."""
        puc19 = STANDARD_PLASMID_CATALOG["pUC19"]

        with tempfile.TemporaryDirectory() as td:
            gb_file = os.path.join(td, "puc19.gb")

            # 1. Export
            gb_text = export_genbank(puc19, filepath=gb_file)
            self.assertTrue(os.path.exists(gb_file))
            self.assertIn("LOCUS       pUC19", gb_text)
            self.assertIn("ORIGIN", gb_text)
            self.assertIn("//", gb_text)

            # 2. Parse from file
            parsed_from_file = parse_genbank(gb_file)
            self.assertEqual(parsed_from_file.name, "pUC19")
            self.assertEqual(parsed_from_file.length, 2686)
            self.assertEqual(parsed_from_file.topology, "circular")
            self.assertEqual(parsed_from_file.sequence, puc19.sequence)
            self.assertEqual(len(parsed_from_file.features), len(puc19.features))

            # Verify features match
            for orig_f, parsed_f in zip(puc19.features, parsed_from_file.features):
                self.assertEqual(orig_f.name, parsed_f.name)
                self.assertEqual(orig_f.start, parsed_f.start)
                self.assertEqual(orig_f.end, parsed_f.end)
                self.assertEqual(orig_f.strand, parsed_f.strand)

            # 3. Parse origin-spanning feature roundtrip
            circ_feat = PlasmidFeature("SpanningFeat", "misc_feature", 2600, 50, 1, plasmid_length=2686)
            custom_plasmid = PlasmidRecord(
                id="pCirc",
                name="pCirc",
                sequence=puc19.sequence,
                topology="circular",
                features=(circ_feat,),
            )
            circ_gb = export_genbank(custom_plasmid)
            self.assertIn("join(2600..2686,1..50)", circ_gb)

            parsed_circ = parse_genbank(circ_gb)
            self.assertEqual(len(parsed_circ.features), 1)
            self.assertEqual(parsed_circ.features[0].start, 2600)
            self.assertEqual(parsed_circ.features[0].end, 50)
            self.assertTrue(parsed_circ.features[0].spans_origin)

    def test_plasmid_json_store_crud(self):
        """Test save_plasmid, get_plasmid, list_plasmids, and delete_plasmid."""
        with tempfile.TemporaryDirectory() as td:
            store_path = os.path.join(td, "plasmids.json")

            custom_p = PlasmidRecord(
                id="pCUSTOM_01",
                name="Custom Plasmid 01",
                sequence="ATGCATGCATGC",
                topology="circular",
                features=(PlasmidFeature("Tag", "tag", 1, 6, 1),),
                description="Custom research plasmid",
            )

            # 1. Save
            saved_id = save_plasmid(custom_p, filepath=store_path)
            self.assertEqual(saved_id, "pCUSTOM_01")
            self.assertTrue(os.path.exists(store_path))

            # 2. Get by ID and Name
            loaded_id = get_plasmid("pCUSTOM_01", filepath=store_path)
            self.assertEqual(loaded_id.name, "Custom Plasmid 01")
            self.assertEqual(loaded_id.length, 12)
            self.assertEqual(len(loaded_id.features), 1)

            loaded_name = get_plasmid("custom plasmid 01", filepath=store_path)
            self.assertEqual(loaded_name.id, "pCUSTOM_01")

            # 3. List
            all_plasmids = list_plasmids(filepath=store_path)
            ids = [p.id for p in all_plasmids]
            self.assertIn("pCUSTOM_01", ids)
            self.assertIn("pUC19", ids)  # Standard catalog merged

            # 4. Delete
            self.assertTrue(delete_plasmid("pCUSTOM_01", filepath=store_path))
            self.assertFalse(delete_plasmid("pCUSTOM_01", filepath=store_path))

            with self.assertRaises(KeyError):
                get_plasmid("pCUSTOM_01", filepath=store_path)


if __name__ == "__main__":
    unittest.main()
