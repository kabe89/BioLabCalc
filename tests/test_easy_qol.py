"""Tests for BioLabCalc easy API and sequence/unit QoL improvements."""

from __future__ import annotations
import unittest
import tempfile
import os
import sys

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc import easy
from biolabcalc.seq_utils import clean_sequence
from biolabcalc.cloning import get_restriction_enzyme
from biolabcalc.units import UnitParser


class TestEasyQoL(unittest.TestCase):
    """Test suite verifying all easy API methods, unit conversions, and sequence cleaning."""

    def test_dna_mw(self):
        # Default is double_stranded=True
        res_ds = easy.dna_mw("ATGCGTACGTTAGC")
        self.assertEqual(res_ds.length, 14)
        self.assertEqual(res_ds.seq_type, "dsDNA")
        self.assertAlmostEqual(res_ds.gc_content, 50.0, places=1)
        self.assertGreater(res_ds.average_mw, 8000.0)

        # Single-stranded
        res_ss = easy.dna_mw("ATGCGTACGTTAGC", double_stranded=False)
        self.assertEqual(res_ss.seq_type, "ssDNA")
        self.assertAlmostEqual(res_ss.gc_content, 50.0, places=1)
        self.assertGreater(res_ss.average_mw, 4000.0)

    def test_protein_mw(self):
        # GFP sequence
        gfp_seq = "MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTLVTTFSYGVQCFSRYPDHMKQHDFFKSAMPEGYVQERTIFFKDDGNYKTRAEVKFEGDTLVNRIELKGIDFKEDGNILGHKLEYNYNSHNVYIMADKQKNGIKVNFKIRHNIEDGSVQLADHYQQNTPIGDGPVLLPDNHYLSTQSALSKDPNEKRDHMVLLEFVTAAGITHGMDELYK"
        res = easy.protein_mw(gfp_seq)
        self.assertEqual(res.length, 238)
        self.assertAlmostEqual(res.average_mw, 27445.0, delta=200.0)

    def test_pcr(self):
        res = easy.pcr(amplicon_bp=850, template_ng=10.0, cycles=30)
        self.assertEqual(res.amplicon_length_bp, 850)
        self.assertEqual(res.cycles_run, 30)
        self.assertGreater(res.amplicon_yield_ng, 100.0)

    def test_digest_and_flexible_enzymes(self):
        # Standard enzyme names
        d1 = easy.digest(dna_mass_ug=1.0, enzyme_1="EcoRI", enzyme_2="BamHI")
        self.assertEqual(d1.enzyme_1.name, "EcoRI")
        self.assertEqual(d1.enzyme_2.name, "BamHI")

        # Flexible enzyme names with -HF suffix and case insensitivity
        d2 = easy.digest(dna_mass_ug=1.0, enzyme_1="EcoRI-HF", enzyme_2="bamhi-hf")
        self.assertEqual(d2.enzyme_1.name, "EcoRI")
        self.assertEqual(d2.enzyme_2.name, "BamHI")

        # Type IIS enzyme with -v2 suffix
        bsai = get_restriction_enzyme("BsaI-HFv2")
        self.assertEqual(bsai.name, "BsaI-HFv2")

        # Case-insensitive without suffix resolves to same enzyme
        bsai_lower = get_restriction_enzyme("bsai")
        self.assertEqual(bsai_lower.name, "BsaI-HFv2")

    def test_ligation(self):
        res = easy.ligation(vector_bp=4000, insert_bp=1000, vector_ng=50.0, molar_ratio=3.0)
        self.assertEqual(res.vector_length_bp, 4000)
        self.assertEqual(res.insert_length_bp, 1000)
        self.assertAlmostEqual(res.insert_mass_ng, 37.5, places=2)

    def test_gibson(self):
        res = easy.gibson(vector_bp=5000, insert_bps=[1000, 1500], vector_ng=100.0)
        self.assertEqual(res.vector_length_bp, 5000)
        self.assertEqual(len(res.insert_masses_ng), 2)
        self.assertAlmostEqual(res.insert_masses_ng[0], 40.0, places=2)

    def test_growth(self):
        res = easy.growth(starter_od600=3.0, target_od600=0.05, target_volume_ml="500 mL")
        self.assertIn("starter_culture_volume_ml", res)
        self.assertIn("fresh_media_volume_ml", res)
        self.assertAlmostEqual(res["total_volume_ml"], 500.0)
        self.assertGreater(res["starter_culture_volume_ml"], 5.0)

    def test_convert_mass_and_moles(self):
        # Mass to mass
        self.assertAlmostEqual(easy.convert("500 ng", "ug"), 0.5, places=6)
        self.assertAlmostEqual(easy.convert("1.5 mg", "ug"), 1500.0, places=3)

        # Sub-microgram mass to grams without premature zeroing
        g_val = easy.convert("500 ng", "g")
        self.assertAlmostEqual(g_val, 5e-7, places=10)
        self.assertNotEqual(g_val, 0.0)

        # Mass to moles with MW
        # 500 ng of 50,000 Da molecule = 10 pmol (1e-11 mol = 10 pmol)
        pmol = easy.convert("500 ng", "pmol", mw=50000.0)
        self.assertAlmostEqual(pmol, 10.0, places=3)

        # Moles to mass with MW
        # 10 pmol of 50,000 Da = 500 ng
        ng = easy.convert("10 pmol", "ng", mw=50000.0)
        self.assertAlmostEqual(ng, 500.0, places=3)

        # Concentration conversions
        self.assertAlmostEqual(easy.convert("10 uM", "nM"), 10000.0, places=3)
        self.assertAlmostEqual(easy.convert("2.5 mg/mL", "ug/uL"), 2.5, places=3)

        # Volume conversions
        self.assertAlmostEqual(easy.convert("1000 uL", "mL"), 1.0, places=4)
        self.assertAlmostEqual(easy.convert("0.5 L", "mL"), 500.0, places=3)

    def test_clean_sequence_genbank_stripping(self):
        genbank_snippet = """LOCUS       SCU49845     5028 bp    DNA             PLN       21-JUN-1999
DEFINITION  Saccharomyces cerevisiae TCP1-beta gene, complete cds.
ACCESSION   U49845
VERSION     U49845.1  GI:1293613
ORIGIN      
        1 gatcctccat atacaacggt atctccacct caggtttaga tctcaacaac ggaaccattg
       61 ccgacatgag acagttaggt atcgtcgaga gttacaagct aaaacgagca gtagtcagct
//"""
        cleaned = clean_sequence(genbank_snippet)
        # Ensure header keywords, coordinates, spaces, and // were stripped
        self.assertNotIn("LOCUS", cleaned)
        self.assertNotIn("ORIGIN", cleaned)
        self.assertNotIn("1", cleaned)
        self.assertNotIn("61", cleaned)
        self.assertNotIn("/", cleaned)
        self.assertEqual(len(cleaned), 120)
        self.assertTrue(cleaned.startswith("GATCCTCCAT"))

    def test_batch_csv_engine(self):
        csv_text = """id,sequence,type
seq1,ATGCGTACGTTAGC,dna
seq2,GGGAGACCCAAGCUGGCC,rna
seq3,MSKGEELFTGVVPILVELD,protein
# Comment row to ignore
seq4,ACGTACGT,dna
"""
        with tempfile.TemporaryDirectory() as td:
            in_file = os.path.join(td, "test_input.csv")
            out_file = os.path.join(td, "test_output.csv")
            with open(in_file, "w", encoding="utf-8") as f:
                f.write(csv_text)

            summary = easy.batch_csv(in_file, out_file)
            self.assertEqual(summary["total_rows"], 5)
            self.assertEqual(summary["success_count"], 4)
            self.assertEqual(summary["error_count"], 0)
            self.assertTrue(os.path.exists(out_file))

            with open(out_file, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
                header = lines[0]
                self.assertIn("Length_bp_aa", header)
                self.assertIn("Molecular_Weight_Da", header)
                self.assertIn("GC_Content_Pct", header)
                self.assertEqual(len(lines), 6)  # header + 4 valid rows + 1 empty/comment row
                self.assertTrue(any("OK" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
