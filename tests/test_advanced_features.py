import unittest
from biolabcalc.cloning import calculate_golden_gate_assembly, get_restriction_enzyme
from biolabcalc.primers import check_heterodimer, design_primers
from biolabcalc.precipitation import calculate_precipitation, calculate_phenol_chloroform_extraction
from biolabcalc.spectroscopy import assess_nanodrop_purity
from biolabcalc.gels import simulate_gel, LADDER_CATALOG
from biolabcalc.transcription import calculate_ivt_yield
from biolabcalc.easy import golden_gate, phenol_chloroform, nanodrop_purity

class TestAdvancedFeatures(unittest.TestCase):
    def test_golden_gate_assembly(self):
        # Test Type IIS enzyme catalog lookup
        enz = get_restriction_enzyme("BsaI-HFv2")
        self.assertEqual(enz.recognition_site, "GGTCTC(1/5)")

        # Test Golden Gate reaction stoichiometry
        res = calculate_golden_gate_assembly(
            vector_length_bp=4000,
            insert_lengths_bp=[1000, 500],
            target_vector_fmol=20.0,
            insert_to_vector_ratio=2.0,
            type_iis_enzyme="BsaI-HFv2",
        )
        self.assertEqual(res.vector_fmol, 20.0)
        self.assertEqual(res.vector_mass_ng, 52.0)
        self.assertEqual(res.insert_fmols, [40.0, 40.0])
        self.assertEqual(res.insert_masses_ng, [26.0, 13.0])
        self.assertEqual(res.total_dna_mass_ng, 91.0)
        self.assertIn("BsaI-HFv2", res.enzyme)
        self.assertIn("Assembly Cycling", res.thermocycling_protocol[0])

        # Test easy helper
        res_easy = golden_gate(vector_bp=3000, insert_bps=[800])
        self.assertGreater(res_easy.vector_mass_ng, 0)

    def test_primer_heterodimer_detection(self):
        # Exact reverse-complement primers (100% heterodimer)
        fwd = "ATGCCGTCCAGGCTGCT"
        rev = "AGCCTGGACGGCATAAA"
        max_m, tp_m, desc = check_heterodimer(fwd, rev)
        self.assertGreaterEqual(max_m, 10)
        self.assertIn("Severe", desc)

        # Poly-A vs Poly-A (zero cross-dimer)
        max_m2, tp_m2, desc2 = check_heterodimer("AAAAAAAAAAAAAAAA", "AAAAAAAAAAAAAAAA")
        self.assertEqual(tp_m2, 0)
        self.assertIn("Low", desc2)

    def test_licl_no_alcohol_and_pci(self):
        # LiCl precipitation must NOT add alcohol
        res_licl = calculate_precipitation(sample_volume_ul=100.0, nucleic_acid="rna", salt="licl")
        self.assertEqual(res_licl.alcohol_volume_ul, 0.0)
        self.assertEqual(res_licl.salt_volume_ul, 50.0)
        self.assertIn("None", res_licl.alcohol_type)

        # Phenol Chloroform Extraction
        pci_rna = calculate_phenol_chloroform_extraction(sample_volume_ul=150.0, nucleic_acid="rna")
        self.assertEqual(pci_rna.pci_volume_ul, 150.0)
        self.assertEqual(pci_rna.chloroform_volume_ul, 150.0)
        self.assertIn("Acid", pci_rna.phenol_type)
        self.assertIn("RNA", pci_rna.aqueous_phase_layer)

        pci_dna = calculate_phenol_chloroform_extraction(sample_volume_ul=100.0, nucleic_acid="dna")
        self.assertIn("Buffered", pci_dna.phenol_type)

        # Test easy helper
        pci_ez = phenol_chloroform("200 uL", nucleic_acid="rna")
        self.assertEqual(pci_ez.sample_volume_ul, 200.0)

    def test_nanodrop_purity_assessment(self):
        # Pure RNA (A260/A280 ~ 2.0, A260/A230 ~ 2.1)
        res_pure = assess_nanodrop_purity(a260=2.0, a280=1.0, a230=0.95, sample_type="rna")
        self.assertEqual(res_pure.purity_status, "Pure")
        self.assertFalse(res_pure.protein_contamination)
        self.assertFalse(res_pure.salt_or_solvent_contamination)
        self.assertEqual(res_pure.corrected_concentration_ng_ul, 80.0)

        # Protein contaminated
        res_prot = assess_nanodrop_purity(a260=1.5, a280=1.1, a230=0.75, sample_type="rna")
        self.assertTrue(res_prot.protein_contamination)
        self.assertIn("protein", "".join(res_prot.diagnostic_feedback).lower())

        # Phenol risk
        res_phen = assess_nanodrop_purity(a260=1.0, a280=0.7, a230=0.8, sample_type="rna")
        self.assertTrue(res_phen.phenol_contamination_risk)

        # Easy helper
        res_ez = nanodrop_purity(a260=1.0, a280=0.5, a230=0.5, sample_type="rna")
        self.assertEqual(res_ez.purity_status, "Pure")

    def test_rna_ladders(self):
        self.assertIn("ssrna_ladder", LADDER_CATALOG)
        self.assertIn("low_range_rna", LADDER_CATALOG)
        self.assertIn("microrna_ladder", LADDER_CATALOG)

        sim = simulate_gel(sample_sizes=[250.0, 750.0], ladder_key="low_range_rna")
        self.assertIn("Low Range ssRNA Ladder", sim.ladder_name)
        self.assertIn("Urea-PAGE", sim.recommended_gel_percentage)

    def test_ivt_cap_and_modified_ntps(self):
        # m1Psi increases molecular weight
        res_unmod = calculate_ivt_yield("GGGAGACCCAAGCUGGCC", reaction_volume_ul=20, measured_yield_ug=30)
        res_m1psi = calculate_ivt_yield("GGGAGACCCAAGCUGGCC", reaction_volume_ul=20, measured_yield_ug=30, modified_ntp="m1Psi")
        self.assertGreater(res_m1psi.rna_mw, res_unmod.rna_mw)
        self.assertIsNotNone(res_m1psi.modified_mw)
        self.assertEqual(res_m1psi.modified_ntp, "N1-methylpseudouridine (m1Ψ)")

        # CleanCap AG
        res_cc = calculate_ivt_yield("AGUACGAUGCAUGC", reaction_volume_ul=20, measured_yield_ug=30, cap_analog="CleanCap_AG")
        self.assertEqual(res_cc.predicted_capping_efficiency_percent, 95.0)
        self.assertIn("CleanCap AG", res_cc.cap_analog)

        # Antisense strand promoter trimming
        # Coding: 5'-TAATACGACTCACTATA GGGAGACCC-3'
        # Reverse complement antisense: 5'-GGGTCTCCC TATAGTGAGTCGTATTA-3'
        from biolabcalc.seq_utils import reverse_complement
        coding_tmpl = "TAATACGACTCACTATAGGGAGACCCAAGCUGGCC"
        rc_tmpl = reverse_complement(coding_tmpl, seq_type="dna")
        res_rc = calculate_ivt_yield(rc_tmpl, reaction_volume_ul=20, measured_yield_ug=30)
        self.assertEqual(res_rc.rna_length, 18)
        self.assertIn("antisense", res_rc.promoter_detected.lower())



    def test_rna_mw_3prime_triphosphate_and_monophosphate_backbone(self):
        from biolabcalc.molecular_weight import calculate_rna_mw
        seq = "GGGAAUGCAUGCAUGC"
        # Standard IVT: 5'-triphosphate, 3'-hydroxyl, monophosphate backbone
        std_res = calculate_rna_mw(seq, end_5="triphosphate", end_3="hydroxyl", backbone="monophosphate")
        self.assertEqual(std_res.average_mw, 5400.13)
        self.assertEqual(std_res.end_5, "triphosphate")
        self.assertEqual(std_res.end_3, "hydroxyl")
        self.assertEqual(std_res.backbone, "monophosphate")

        # 5'-monophosphate with monophosphate backbone and 3'-triphosphate
        res_p5_ppp3 = calculate_rna_mw(seq, end_5="monophosphate", end_3="triphosphate", backbone="monophosphate")
        self.assertEqual(res_p5_ppp3.average_mw, 5480.11)
        self.assertEqual(res_p5_ppp3.end_5, "monophosphate")
        self.assertEqual(res_p5_ppp3.end_3, "triphosphate")
        # Diff between 5'-p/3'-ppp and 5'-ppp/3'-OH is +79.98 Da (one extra monophosphate group net)
        self.assertAlmostEqual(res_p5_ppp3.average_mw - std_res.average_mw, 79.98, places=2)

        # 5'-hydroxyl with 3'-triphosphate (mass matches 5'-ppp/3'-OH)
        res_oh5_ppp3 = calculate_rna_mw(seq, end_5="hydroxyl", end_3="triphosphate", backbone="monophosphate")
        self.assertEqual(res_oh5_ppp3.average_mw, std_res.average_mw)

        # Phosphorothioate backbone
        res_ps = calculate_rna_mw(seq, end_5="triphosphate", end_3="hydroxyl", backbone="phosphorothioate")
        # 15 linkages * 16.066 Da = 240.99 Da
        self.assertAlmostEqual(res_ps.average_mw - std_res.average_mw, 240.99, places=1)

    def test_transcription_time_optimization(self):
        from biolabcalc.transcription import optimize_transcription_time
        # Small aptamer (75 nt)
        t_apt = optimize_transcription_time(transcript_length_nt=75, temperature_celsius=37.0)
        self.assertLessEqual(t_apt.recommended_time_hours, 2.0)
        self.assertIn("N+1", t_apt.risk_of_3prime_heterogeneity)
        self.assertGreaterEqual(len(t_apt.time_course_predictions), 5)

        # Long mRNA (2500 nt)
        t_mrna = optimize_transcription_time(transcript_length_nt=2500, temperature_celsius=37.0)
        self.assertGreaterEqual(t_mrna.recommended_time_hours, 2.5)

        # 42°C reaction
        t_hot = optimize_transcription_time(transcript_length_nt=75, temperature_celsius=42.0)
        self.assertLessEqual(t_hot.recommended_time_hours, 1.5)

    def test_hepes_ivt_buffer_calculation(self):
        from biolabcalc.buffers import calculate_hepes_ivt_buffer, calculate_buffer_recipe
        res = calculate_hepes_ivt_buffer(target_volume_ml=50.0, stock_multiplier=10, target_ph_37c=7.50)
        self.assertEqual(res.stock_multiplier, 10)
        self.assertEqual(res.hepes_conc_mm, 400.0)
        self.assertEqual(res.target_ph_37c, 7.50)
        self.assertEqual(res.preparation_ph_25c, 7.67) # temperature compensation
        self.assertAlmostEqual(res.reagent_masses_and_volumes["HEPES (free acid)"], 4.766, places=2)
        self.assertGreater(res.reagent_masses_and_volumes["5.0 M KOH"], 1.0)
        self.assertIn("HEPES vs Tris", res.buffering_capacity_comparison)

        # Catalog lookup
        cat_buf = calculate_buffer_recipe("10X_HEPES_IVT", target_volume_ml=100.0)
        self.assertIn("HEPES-KOH", cat_buf.name)

    def test_easy_new_helpers(self):
        from biolabcalc.easy import hepes_buffer, ivt_time, rna_mw
        b_res = hepes_buffer("50 mL", stock=10)
        self.assertEqual(b_res.stock_multiplier, 10)

        t_res = ivt_time(85, temp_c=37.0)
        self.assertLessEqual(t_res.recommended_time_hours, 2.0)

        m_res = rna_mw("GGGAAUGCAUGCAUGC", end_5="monophosphate", end_3="triphosphate", backbone="monophosphate")
        self.assertEqual(m_res.average_mw, 5480.11)

if __name__ == "__main__":
    unittest.main()
