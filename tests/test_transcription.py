import unittest
from biolabcalc.transcription import (
    calculate_ivt_yield,
    detect_and_trim_promoter,
    evaluate_initiation_efficiency,
)

class TestTranscription(unittest.TestCase):
    def test_ivt_stoichiometry(self):
        res = calculate_ivt_yield(
            rna_seq="GGGAAUGCAUGCAUGC",
            reaction_volume_ul=20.0,
            measured_yield_ug=35.0,
            template_dna_ng=500.0,
            template_dna_length_bp=3000,
        )
        self.assertEqual(res.rna_length, 16)
        self.assertGreater(res.rna_yield_pmol, 5000.0)
        self.assertEqual(res.limiting_ntp, "GTP")
        self.assertGreater(res.pyrophosphate_released_nmol, 50.0)
        self.assertTrue(0.0 < res.overall_efficiency_percent <= 100.0)
        self.assertIsNotNone(res.transcript_turnover_ratio)

    def test_zero_sequence_error(self):
        with self.assertRaises(ValueError):
            calculate_ivt_yield(rna_seq="")

    def test_promoter_trimming(self):
        full_seq = "TAATACGACTCACTATAGGGAGACCCAAGCUGGCC"
        tx, name, trimmed = detect_and_trim_promoter(full_seq)
        self.assertEqual(name, "T7")
        self.assertEqual(trimmed, 17)
        self.assertEqual(tx, "GGGAGACCCAAGCUGGCC")

        sp6_seq = "ATTTAGGTGACACTATAGGAUCC"
        tx_sp6, name_sp6, trimmed_sp6 = detect_and_trim_promoter(sp6_seq)
        self.assertEqual(name_sp6, "SP6")
        self.assertEqual(trimmed_sp6, 17)
        self.assertEqual(tx_sp6, "GGAUCC")

    def test_ivt_auto_trim_and_gg_optimization(self):
        seq_with_promoter = "TAATACGACTCACTATAAUGCAUGC"
        res = calculate_ivt_yield(
            rna_seq=seq_with_promoter,
            auto_trim_promoter=True,
            add_5prime_gg=2,
            measured_yield_ug=20.0,
        )
        self.assertEqual(res.promoter_detected, "T7")
        self.assertEqual(res.promoter_trimmed_nt, 17)
        self.assertEqual(res.rna_length, 10)
        self.assertEqual(res.added_5prime_gs, 2)
        self.assertTrue(res.rna_sequence.startswith("GGAUGCAUGC"))
        self.assertEqual(res.initiation_efficiency_rating, "High")

    def test_initiation_efficiency_ratings(self):
        opt = evaluate_initiation_efficiency("GGGAGACCC")
        self.assertEqual(opt.efficiency_rating, "Optimal")
        self.assertEqual(opt.relative_efficiency_percent, 100.0)

        high = evaluate_initiation_efficiency("GGAUGCAUGC")
        self.assertEqual(high.efficiency_rating, "High")
        self.assertEqual(high.relative_efficiency_percent, 85.0)

        mod = evaluate_initiation_efficiency("GAUGCAUGC")
        self.assertEqual(mod.efficiency_rating, "Moderate")
        self.assertEqual(mod.relative_efficiency_percent, 60.0)

        poor = evaluate_initiation_efficiency("CAUGCAUGC")
        self.assertEqual(poor.efficiency_rating, "Poor")
        self.assertEqual(poor.relative_efficiency_percent, 10.0)
        self.assertEqual(poor.added_leading_gs, 2)

if __name__ == '__main__':
    unittest.main()
