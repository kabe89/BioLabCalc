"""Unit tests for Sequence Storage, Catalog, Immutability, and FASTA I/O in BioLabCalc."""

import os
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError

# Ensure src directory is in sys.path
_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.sequence_store import (
    DEFAULT_SEQUENCE_CATALOG,
    SequenceAnnotation,
    SequenceRecord,
    delete_sequence,
    export_fasta,
    get_sequence,
    import_fasta,
    list_sequences,
    save_sequence,
)


class TestSequenceStore(unittest.TestCase):
    """Test suite for SequenceRecord, SequenceAnnotation, Catalog, and Persistence."""

    def test_sequence_annotation_immutability(self):
        """SequenceAnnotation must be frozen and reject mutation."""
        ann = SequenceAnnotation("Promoter_1", "promoter", 1, 25, 1, "T7 variant")
        self.assertEqual(ann.name, "Promoter_1")
        self.assertEqual(ann.feature_type, "promoter")
        self.assertEqual(ann.start, 1)
        self.assertEqual(ann.end, 25)
        self.assertEqual(ann.strand, 1)
        self.assertEqual(ann.notes, "T7 variant")

        with self.assertRaises(FrozenInstanceError):
            ann.name = "Mutated_Promoter"  # type: ignore

        with self.assertRaises(FrozenInstanceError):
            ann.start = 5  # type: ignore

    def test_sequence_record_immutability(self):
        """SequenceRecord must be frozen and reject mutation."""
        rec = SequenceRecord(
            id="SEQ_001",
            name="Test Oligo",
            sequence="ATGCATGC",
            seq_type="dna",
        )
        self.assertEqual(rec.id, "SEQ_001")
        self.assertEqual(rec.length, 8)

        with self.assertRaises(FrozenInstanceError):
            rec.name = "Altered Name"  # type: ignore

        with self.assertRaises(FrozenInstanceError):
            rec.sequence = "TTTTTT"  # type: ignore

    def test_sequence_record_post_init_metrics(self):
        """Verification of checksum, length, GC percent, and MW across sequence types."""
        # DNA linear
        dna_rec = SequenceRecord(
            id="DNA_1",
            name="DNA Fragment",
            sequence="GATTACA",
            seq_type="dna",
            topology="linear",
        )
        self.assertEqual(dna_rec.length, 7)
        self.assertEqual(len(dna_rec.checksum), 16)
        self.assertAlmostEqual(dna_rec.gc_percent, 28.57, places=2)
        self.assertGreater(dna_rec.molecular_weight_da, 2000.0)

        # dsDNA
        dsdna_rec = SequenceRecord(
            id="DSDNA_1",
            name="Double Stranded DNA",
            sequence="GATTACA",
            seq_type="dna",
            topology="dsdna",
        )
        self.assertGreater(dsdna_rec.molecular_weight_da, dna_rec.molecular_weight_da)

        # RNA
        rna_rec = SequenceRecord(
            id="RNA_1",
            name="Transcript",
            sequence="GAUUACA",
            seq_type="rna",
        )
        self.assertEqual(rna_rec.length, 7)
        self.assertAlmostEqual(rna_rec.gc_percent, 28.57, places=2)
        self.assertGreater(rna_rec.molecular_weight_da, 2000.0)

        # Protein
        prot_rec = SequenceRecord(
            id="PROT_1",
            name="Peptide",
            sequence="MKLLVVLF",
            seq_type="protein",
        )
        self.assertEqual(prot_rec.length, 8)
        self.assertGreater(prot_rec.molecular_weight_da, 900.0)

        # Sequence cleaning in post_init (removes whitespace, numbers, lowercase)
        dirty_rec = SequenceRecord(
            id="DIRTY_1",
            name="Dirty DNA",
            sequence="  atg cga 123 tcg  ",
            seq_type="dna",
        )
        self.assertEqual(dirty_rec.sequence, "ATGCGATCG")
        self.assertEqual(dirty_rec.length, 9)

    def test_annotations_converted_to_tuple(self):
        """Passing a list of SequenceAnnotation must convert to an immutable tuple."""
        ann_list = [
            SequenceAnnotation("Feat1", "misc_feature", 1, 10, 1),
            SequenceAnnotation("Feat2", "CDS", 11, 20, 1),
        ]
        rec = SequenceRecord(
            id="SEQ_ANN",
            name="Annotated Seq",
            sequence="A" * 30,
            annotations=ann_list,  # type: ignore
        )
        self.assertIsInstance(rec.annotations, tuple)
        self.assertEqual(len(rec.annotations), 2)
        self.assertEqual(rec.annotations[0].name, "Feat1")

    def test_default_sequence_catalog(self):
        """Verify all 10 required standard catalog sequences are present and biologically valid."""
        required_keys = [
            "T7_PROMOTER",
            "SP6_PROMOTER",
            "T3_PROMOTER",
            "GLUK2_EXON1_AMPLICON",
            "GLUA1_LBD_CDS",
            "AB9SR_APTAMER",
            "EGFP_CDS",
            "HIS6_TEV_TAG",
            "KANR_CDS",
            "AMPR_CDS",
        ]
        for key in required_keys:
            self.assertIn(key, DEFAULT_SEQUENCE_CATALOG, f"Missing required catalog sequence: {key}")
            rec = DEFAULT_SEQUENCE_CATALOG[key]
            self.assertIsInstance(rec, SequenceRecord)
            self.assertGreater(rec.length, 0)
            self.assertGreater(rec.molecular_weight_da, 0.0)
            self.assertEqual(len(rec.checksum), 16)

        # Specific biological invariants
        t7 = DEFAULT_SEQUENCE_CATALOG["T7_PROMOTER"]
        self.assertEqual(t7.sequence, "TAATACGACTCACTATAGGG")
        self.assertEqual(t7.length, 20)

        sp6 = DEFAULT_SEQUENCE_CATALOG["SP6_PROMOTER"]
        self.assertEqual(sp6.sequence, "ATTTAGGTGACACTATAGAAGNG")
        self.assertEqual(sp6.length, 23)

        t3 = DEFAULT_SEQUENCE_CATALOG["T3_PROMOTER"]
        self.assertEqual(t3.sequence, "AATTAACCCTCACTAAAGGG")
        self.assertEqual(t3.length, 20)

        gluk2 = DEFAULT_SEQUENCE_CATALOG["GLUK2_EXON1_AMPLICON"]
        self.assertEqual(gluk2.length, 120)
        self.assertEqual(gluk2.topology, "dsdna")

        egfp = DEFAULT_SEQUENCE_CATALOG["EGFP_CDS"]
        self.assertEqual(egfp.length, 720)
        self.assertTrue(egfp.sequence.startswith("ATG"))
        self.assertTrue(egfp.sequence.endswith("TAA"))

        his6 = DEFAULT_SEQUENCE_CATALOG["HIS6_TEV_TAG"]
        self.assertEqual(his6.sequence, "CATCATCATCATCATCACGAAAACCTGTACTTCCAAGGC")
        self.assertEqual(his6.length, 39)

        kanr = DEFAULT_SEQUENCE_CATALOG["KANR_CDS"]
        self.assertEqual(kanr.length, 816)

        ampr = DEFAULT_SEQUENCE_CATALOG["AMPR_CDS"]
        self.assertEqual(ampr.length, 861)

        ab9sr = DEFAULT_SEQUENCE_CATALOG["AB9SR_APTAMER"]
        self.assertEqual(ab9sr.seq_type, "rna")

    def test_get_sequence_catalog_fallback(self):
        """get_sequence should retrieve catalog records with case-insensitivity."""
        rec1 = get_sequence("T7_PROMOTER")
        self.assertEqual(rec1.id, "T7_PROMOTER")

        rec2 = get_sequence("t7_promoter")
        self.assertEqual(rec2.id, "T7_PROMOTER")

        rec3 = get_sequence("T7 Promoter")  # By name
        self.assertEqual(rec3.id, "T7_PROMOTER")

        with self.assertRaises(KeyError):
            get_sequence("NON_EXISTENT_SEQUENCE_ID_XYZ")

    def test_json_store_crud_lifecycle(self):
        """Test save, get, list, and delete in an isolated temporary storage file."""
        with tempfile.TemporaryDirectory() as td:
            store_path = os.path.join(td, "custom_sequences.json")

            rec_a = SequenceRecord(
                id="MY_GENE_1",
                name="Gene A",
                sequence="ATGGCCTAA",
                seq_type="dna",
                description="Custom cloned gene",
                annotations=(SequenceAnnotation("CDS", "CDS", 1, 9, 1),),
            )

            # 1. Save
            saved_id = save_sequence(rec_a, filepath=store_path)
            self.assertEqual(saved_id, "MY_GENE_1")
            self.assertTrue(os.path.exists(store_path))

            # 2. Get by ID and by Name
            loaded_by_id = get_sequence("MY_GENE_1", filepath=store_path)
            self.assertEqual(loaded_by_id.name, "Gene A")
            self.assertEqual(loaded_by_id.sequence, "ATGGCCTAA")
            self.assertEqual(len(loaded_by_id.annotations), 1)

            loaded_by_name = get_sequence("gene a", filepath=store_path)
            self.assertEqual(loaded_by_name.id, "MY_GENE_1")

            # 3. List
            all_records = list_sequences(filepath=store_path)
            ids = [r.id for r in all_records]
            self.assertIn("MY_GENE_1", ids)
            self.assertIn("T7_PROMOTER", ids)  # Merged with default catalog

            # 4. Delete
            self.assertTrue(delete_sequence("MY_GENE_1", filepath=store_path))
            self.assertFalse(delete_sequence("MY_GENE_1", filepath=store_path))

            # After deletion, lookup in user store should fail (or fall back to catalog)
            with self.assertRaises(KeyError):
                get_sequence("MY_GENE_1", filepath=store_path)

    def test_fasta_export_and_import(self):
        """Verify FASTA export and round-trip import from string and file."""
        with tempfile.TemporaryDirectory() as td:
            fasta_path = os.path.join(td, "exported.fasta")
            store_path = os.path.join(td, "imported_store.json")

            records = [
                SequenceRecord(
                    id="REC_ALPHA",
                    name="Alpha Construct",
                    sequence="ATGC" * 20,  # 80 bp
                    description="Synthetic sequence alpha",
                ),
                SequenceRecord(
                    id="REC_BETA",
                    name="Beta Construct",
                    sequence="GGCC" * 15,  # 60 bp
                    description="Synthetic sequence beta",
                ),
            ]

            # Export to file
            exported_text = export_fasta(records, filepath=fasta_path)
            self.assertTrue(os.path.exists(fasta_path))
            self.assertIn(">REC_ALPHA Synthetic sequence alpha", exported_text)
            self.assertIn(">REC_BETA Synthetic sequence beta", exported_text)

            # Import from file with store persistence
            imported = import_fasta(fasta_path, filepath=store_path)
            self.assertEqual(len(imported), 2)
            self.assertEqual(imported[0].id, "REC_ALPHA")
            self.assertEqual(imported[0].length, 80)
            self.assertEqual(imported[1].id, "REC_BETA")
            self.assertEqual(imported[1].length, 60)

            # Verify persisted in store
            retrieved = get_sequence("REC_ALPHA", filepath=store_path)
            self.assertEqual(retrieved.sequence, "ATGC" * 20)

            # Import from raw string
            raw_fasta = ">RAW_1 Test raw import\nACGTACGT\nACGTACGT\n"
            raw_imported = import_fasta(raw_fasta)
            self.assertEqual(len(raw_imported), 1)
            self.assertEqual(raw_imported[0].id, "RAW_1")
            self.assertEqual(raw_imported[0].sequence, "ACGTACGTACGTACGT")
            self.assertEqual(raw_imported[0].length, 16)


if __name__ == "__main__":
    unittest.main()
