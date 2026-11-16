"""Unit tests for Automated Gene Expression Plasmid Engineering Engine (v0.4.0)."""

import unittest
from biolabcalc.plasmid import STANDARD_PLASMID_CATALOG, PlasmidRecord, get_plasmid
from biolabcalc.plasmid_engineering import (
    CodonUsageAnalysis,
    EngineeredPlasmidResult,
    ExpressionCassetteResult,
    design_expression_cassette,
    domesticate_restriction_sites,
    engineer_plasmid,
    evaluate_codon_usage,
    optimize_codons,
)
from biolabcalc.seq_utils import translate_dna


class TestPlasmidEngineering(unittest.TestCase):
    """Test suite for codon optimization, expression cassette design, and plasmid assembly."""

    def setUp(self) -> None:
        # Standard EGFP CDS (720 bp, 240 codons including stop)
        self.egfp_cds = (
            "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTAAACGGCCACAAGTTCAGCGTGTCCGGC"
            "GAGGGCGAGGGCGATGCCACCTACGGCAAGCTGACCCTGAAGTTCATCTGCACCACCGGCAAGCTGCCCGTGCCCTGGCCCACCCTCGTGACCACC"
            "CTGACCTACGGCGTGCAGTGCTTCAGCCGCTACCCCGACCACATGAAGCAGCACGACTTCTTCAAGTCCGCCATGCCCGAAGGCTACGTCCAGGAG"
            "CGCACCATCTTCTTCAAGGACGACGGCAACTACAAGACCCGCGCCGAGGTGAAGTTCGAGGGCGACACCCTGGTGAACCGCATCGAGCTGAAGGGC"
            "ATCGACTTCAAGGAGGACGGCAACATCCTGGGGCACAAGCTGGAGTACAACTACAACAGCCACAACGTCTATATCATGGCCGACAAGCAGAAGAAC"
            "GGCATCAAGGTGAACTTCAAGATCCGCCACAACATCGAGGACGGCAGCGTGCAGCTCGCCGACCACTACCAGCAGAACACCCCCATCGGCGACGGC"
            "CCCGTGCTGCTGCCCGACAACCACTACCTGAGCACCCAGTCCGCCCTGAGCAAAGACCCCAACGAGAAGCGCGATCACATGGTCCTGCTGGAGTTC"
            "GTGACCGCCGCCGGGATCACTCTCGGCATGGACGAGCTGTACAAGTAA"
        )

        # GLUK2 (GRIK2) N-terminal snippet CDS (240 bp, 80 codons)
        self.gluk2_snippet = (
            "ATGAAGATTATTTTCCCGGTTGTAAGCGCCATTCTTTTTCTGGTTTCCTTCATTCGCGGCGACTCGGAGGTAAACCTCATGGACAGCAGC"
            "CACATTTTTGGCACCAACATCGACGAATCGAACCAGTACTGCTACTACCGCGTGGCCACCGGCAAGGACGAGCTCGTCATCCACGTCTCG"
            "CACGGCTTCTTCCTCAAGGAGCATGTCGGCGTCGGCATCGTGAGCAACACCGAGTACTGCAAGTGATAA"
        )

    def test_codon_usage_evaluation(self) -> None:
        """Evaluate CAI, GC content, and rare codons for E. coli."""
        analysis = evaluate_codon_usage(self.egfp_cds, host="ecoli")
        self.assertIsInstance(analysis, CodonUsageAnalysis)
        self.assertGreater(analysis.cai, 0.40)
        self.assertLessEqual(analysis.cai, 1.0)
        self.assertGreater(analysis.gc_content, 50.0)
        self.assertIsInstance(analysis.rare_codons, tuple)

        # Sequence with deliberate rare E. coli codons (AGG, AGA, CTA, ATA)
        rare_seq = "ATGAGGAGACTAATATAA"
        rare_analysis = evaluate_codon_usage(rare_seq, host="ecoli")
        self.assertGreater(rare_analysis.rare_codon_count, 0)
        self.assertGreater(rare_analysis.unfavorable_pairs, 0)

    def test_codon_optimization_from_protein(self) -> None:
        """Reverse-translate protein sequence using preferred host codons."""
        protein = "MVSKGEELFT"
        opt_dna = optimize_codons(protein, host="ecoli")
        self.assertEqual(len(opt_dna), 30)
        self.assertTrue(opt_dna.startswith("ATG"))
        self.assertEqual(translate_dna(opt_dna), protein)

    def test_silent_restriction_domestication(self) -> None:
        """Domestication mutates restriction sites while maintaining exact amino acid translation."""
        # Insert containing BsaI (GGTCTC) and BamHI (GGATCC)
        dna_with_sites = "ATGGTGAGCAAGGGCGAGGGTCTCTTCACCGGATCCGTGGTGCCC"
        orig_protein = translate_dna(dna_with_sites)

        domesticated = optimize_codons(
            dna_with_sites,
            host="ecoli",
            avoid_enzymes=["BsaI-HFv2", "BamHI"],
        )
        self.assertNotIn("GGTCTC", domesticated)
        self.assertNotIn("GAGACC", domesticated)
        self.assertNotIn("GGATCC", domesticated)
        # Protein sequence must be 100% identical
        dom_protein = translate_dna(domesticated)
        self.assertEqual(dom_protein, orig_protein)

    def test_expression_cassette_designer(self) -> None:
        """Design T7 expression cassette with 6xHis tag and TEV protease cleavage site."""
        cassette = design_expression_cassette(
            target_seq="MVSKGEELFT",
            is_protein=True,
            host="ecoli",
            promoter="T7",
            n_tag="6xHis",
            protease_site="TEV",
        )
        self.assertIsInstance(cassette, ExpressionCassetteResult)
        self.assertEqual(cassette.promoter, "T7")
        self.assertIn("TAATACGACTCACTATAGGG", cassette.cassette_seq)
        self.assertIn("CATCATCATCATCATCAC", cassette.cassette_seq)
        self.assertGreater(cassette.protein_mw_da, 1000.0)
        self.assertGreaterEqual(cassette.extinction_coeff_280, 0)
        self.assertTrue(len(cassette.features) >= 5)

    def test_directional_cloning_egfp_in_pet28a(self) -> None:
        """Directional BamHI + XhoI cloning of EGFP into pET-28a(+)."""
        result = engineer_plasmid(
            vector="pET-28a(+)",
            insert_seq=self.egfp_cds,
            gene_name="EGFP",
            mode="restriction_ligation",
            enzyme_5prime="BamHI",
            enzyme_3prime="XhoI",
        )
        self.assertIsInstance(result, EngineeredPlasmidResult)
        self.assertEqual(result.target_gene_name, "EGFP")
        self.assertEqual(result.mode, "restriction_ligation")
        self.assertTrue(result.in_frame)
        self.assertTrue(result.has_start_codon)
        self.assertTrue(result.has_stop_codon)
        self.assertEqual(result.premature_stops, 0)
        self.assertTrue(result.ori_intact)
        self.assertTrue(result.marker_intact)
        self.assertTrue(result.rbs_or_kozak_ok)

        # Check primers
        self.assertIn("GGATCC", result.forward_primer_full_seq)
        self.assertIn("CTCGAG", result.reverse_primer_full_seq)
        self.assertGreater(result.forward_primer.tm_celsius, 50.0)
        self.assertGreater(result.reverse_primer.tm_celsius, 50.0)

        # Colony PCR amplicon
        self.assertGreater(result.colony_pcr_amplicon_bp, 700)
        self.assertGreater(result.predicted_expression_yield_mg_l, 10.0)

    def test_frame_synchronization_and_padding_nucleotide(self) -> None:
        """Reading frame synchronization automatically inserts padding nucleotides when required."""
        # Using HindIII as 5' enzyme in pET-28a(+), where delta_frame=1 requires 2 bp pad 'GC'
        result = engineer_plasmid(
            vector="pET-28a(+)",
            insert_seq=self.egfp_cds,
            gene_name="EGFP_HindIII",
            mode="restriction_ligation",
            enzyme_5prime="HindIII",
            enzyme_3prime="XhoI",
        )
        self.assertTrue(result.in_frame)
        self.assertEqual(result.premature_stops, 0)
        # Check that pad was inserted into forward primer
        self.assertIn("CGCAAGCTTGC", result.forward_primer_full_seq)
        self.assertTrue(any("Inserted 2 bp pad" in note for note in result.notes))

    def test_gibson_assembly_mode(self) -> None:
        """Gibson assembly generates 25 bp vector homology tails."""
        result = engineer_plasmid(
            vector="pUC19",
            insert_seq=self.egfp_cds,
            gene_name="EGFP",
            mode="gibson",
        )
        self.assertIsInstance(result, EngineeredPlasmidResult)
        self.assertEqual(result.mode, "gibson")
        # Forward primer should have 25 bp homology arm + annealing core
        self.assertGreaterEqual(len(result.forward_primer_full_seq), 35)
        self.assertGreaterEqual(len(result.reverse_primer_full_seq), 35)
        self.assertTrue(result.ori_intact)
        self.assertTrue(result.marker_intact)

    def test_golden_gate_assembly_with_domestication(self) -> None:
        """Golden Gate assembly in destination vector with automatic silent domestication."""
        # Insert carrying internal BsaI recognition site
        egfp_with_bsai = self.egfp_cds[:60] + "GGTCTC" + self.egfp_cds[66:]

        result = engineer_plasmid(
            vector="pGoldenGate-Dest",
            insert_seq=egfp_with_bsai,
            gene_name="EGFP_GG",
            mode="golden_gate",
            type_iis_enzyme="BsaI-HFv2",
            auto_domesticate=True,
        )
        self.assertIsInstance(result, EngineeredPlasmidResult)
        self.assertEqual(result.mode, "golden_gate")
        # Internal BsaI site must have been silenced
        self.assertNotIn("GGTCTC", result.expressed_protein_seq)
        # Primers must contain BsaI site
        self.assertIn("GGTCTC", result.forward_primer_full_seq)
        self.assertIn("GGTCTC", result.reverse_primer_full_seq)

    def test_frameshift_detection(self) -> None:
        """Audit detects frame-shift when insert length is not a multiple of 3."""
        # 13 bp insert
        out_of_frame_insert = "ATGGTGAGCAAGA"
        result = engineer_plasmid(
            vector="pET-28a(+)",
            insert_seq=out_of_frame_insert,
            gene_name="Frameshift_Gene",
        )
        self.assertFalse(result.in_frame)
        self.assertTrue(any("Frame shift detected" in w for w in result.warnings))

    def test_seven_point_audit_complete(self) -> None:
        """7-point quality audit verifies all essential expression vector checkpoints."""
        result = engineer_plasmid(
            vector="pET-28a(+)",
            insert_seq=self.gluk2_snippet,
            gene_name="GLUK2",
            mode="restriction_ligation",
            enzyme_5prime="BamHI",
            enzyme_3prime="XhoI",
        )
        # Check all 7 points
        self.assertTrue(result.in_frame)
        self.assertTrue(result.has_start_codon)
        self.assertTrue(result.has_stop_codon)
        self.assertEqual(result.premature_stops, 0)
        self.assertTrue(result.rbs_or_kozak_ok)
        self.assertTrue(result.ori_intact)
        self.assertTrue(result.marker_intact)

    def test_short_peptide_optimization_not_misclassified_as_dna(self):
        """Verify short peptide like 'CAT' is reverse translated and not treated as a 3-nt DNA codon."""
        opt = optimize_codons("CAT", host="ecoli")
        self.assertEqual(len(opt), 9)
        self.assertEqual(opt, "TGCGCGACC")

        opt2 = optimize_codons("CAT", host="ecoli", seq_type="protein")
        self.assertEqual(opt2, "TGCGCGACC")


if __name__ == "__main__":
    unittest.main()
