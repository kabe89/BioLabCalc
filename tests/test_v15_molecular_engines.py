"""Unit tests for BioLabCalc v1.5.0 Milestone 2 Molecular Engines.

Tests:
1. DNA Backbone Customization (BackboneSpec, BACKBONE_CATALOG, customize_backbone, 1-based coordinates).
2. Multi-RNA Polymerase IVT (RNAPolymeraseSpec, POLYMERASE_CATALOG, SP6, Syn5, T7_G47A, CleanCap_AU, mismatch detection).
3. Application-Specific Protein Recommender (pI, GRAVY, Cys disulfides, N-glycosylation, ranked hosts, buffer pH).
4. CLI integration and easy API surface.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from biolabcalc.easy import customize_backbone, recommend_protein
from biolabcalc.plasmid import (
    BackboneSpec,
    BACKBONE_CATALOG,
    STANDARD_PLASMID_CATALOG,
    get_backbone,
    list_backbones,
    PlasmidRecord,
)
from biolabcalc.protein_recommender import (
    ProteinBiophysicalProfile,
    ProteinRecommendationResult,
    analyze_protein_profile,
    calculate_gravy,
    calculate_isoelectric_point,
    find_n_glycosylation_sites,
    recommend_protein_strategy,
)
from biolabcalc.transcription import (
    POLYMERASE_CATALOG,
    RNAPolymeraseSpec,
    calculate_ivt_yield,
    get_rna_polymerase,
)


class TestBackboneCustomization(unittest.TestCase):
    """Test DNA Backbone Spec and modular customization engine."""

    def test_backbone_catalog_presets(self) -> None:
        expected = ["pUC19", "pET28a(+)", "pcDNA3.1(+)", "pGEX-4T-1", "pFastBac1", "pLKO.1", "pAAV-CAG"]
        for name in expected:
            self.assertIn(name, BACKBONE_CATALOG)
            spec = BACKBONE_CATALOG[name]
            self.assertIsInstance(spec, BackboneSpec)
            self.assertGreater(len(spec.sequence), 1000)
            self.assertGreater(len(spec.features), 2)
            # Immutability
            with self.assertRaises((TypeError, AttributeError)):
                spec.sequence = "ACGT"  # type: ignore

    def test_customize_backbone_origin_and_resistance(self) -> None:
        # Customize pET28a(+) by swapping origin to p15A and marker to AmpR
        rec = customize_backbone(
            base_name="pET28a(+)",
            origin="p15A",
            resistance="AmpR",
            cleavage_site="TEV",
        )
        self.assertIsInstance(rec, PlasmidRecord)
        self.assertEqual(rec.topology, "circular")
        self.assertIn("custom", rec.name)
        # Check that origin and resistance features were updated
        feat_names = [f.name for f in rec.features]
        self.assertTrue(any("p15A" in n for n in feat_names))
        self.assertTrue(any("AmpR" in n for n in feat_names))
        self.assertTrue(any("TEV" in n for n in feat_names))
        # Verify 1-based inclusive coordinates: start >= 1, end <= length
        for f in rec.features:
            self.assertGreaterEqual(f.start, 1)
            self.assertLessEqual(f.end, rec.length)
            if not f.spans_origin:
                self.assertLessEqual(f.start, f.end)

    def test_customize_backbone_promoter_and_tag(self) -> None:
        # Customize pUC19 with T7 promoter and His6 tag
        rec = customize_backbone(
            base_name="pUC19",
            promoter="T7",
            n_term_tag="His6",
        )
        self.assertIsInstance(rec, PlasmidRecord)
        feat_names = [f.name for f in rec.features]
        self.assertTrue(any("T7" in n for n in feat_names))
        self.assertTrue(any("His6" in n for n in feat_names))

    def test_user_custom_backbone_json_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_env = os.environ.get("BIOLABCALC_HOME")
            try:
                os.environ["BIOLABCALC_HOME"] = tmpdir
                backbone_dir = Path(tmpdir) / "backbones"
                backbone_dir.mkdir(parents=True, exist_ok=True)

                custom_json = backbone_dir / "my_vector.json"
                data = {
                    "name": "my_vector",
                    "origin": "pSC101",
                    "resistance": "ZeoR",
                    "promoter": "lac",
                    "copy_number": "Low",
                    "sequence": "ATGC" * 300,
                    "features": [
                        {"name": "pSC101_ori", "feature_type": "rep_origin", "start": 1, "end": 200},
                        {"name": "ZeoR", "feature_type": "CDS", "start": 300, "end": 600},
                    ],
                }
                custom_json.write_text(json.dumps(data), encoding="utf-8")

                spec = get_backbone("my_vector")
                self.assertEqual(spec.name, "my_vector")
                self.assertEqual(spec.origin, "pSC101")
                self.assertEqual(spec.resistance, "ZeoR")

                all_bb = list_backbones()
                self.assertTrue(any(b.name == "my_vector" for b in all_bb))
            finally:
                if orig_env:
                    os.environ["BIOLABCALC_HOME"] = orig_env
                else:
                    os.environ.pop("BIOLABCALC_HOME", None)


class TestMultiRNAPolymeraseIVT(unittest.TestCase):
    """Test multi-RNA polymerase spec catalog and IVT calculations."""

    def test_polymerase_catalog(self) -> None:
        expected = ["T7", "T7_G47A", "T7_Thermo", "SP6", "T3", "Syn5"]
        for name in expected:
            self.assertIn(name, POLYMERASE_CATALOG)
            spec = POLYMERASE_CATALOG[name]
            self.assertIsInstance(spec, RNAPolymeraseSpec)
            self.assertGreater(len(spec.promoter_consensus), 10)
            self.assertGreater(spec.recommended_mg_ntp_ratio, 1.0)
            self.assertGreater(len(spec.supported_caps), 0)

    def test_ivt_with_t7_g47a_and_cleancap_ag(self) -> None:
        seq = "TAATACGACTCACTATAAGGAGACCCAAGCTGGCTAGTTA"
        res = calculate_ivt_yield(
            rna_seq=seq,
            polymerase="T7_G47A",
            cap_analog="CleanCap_AG",
            atp_mm=5.0,
            mg_conc_mm=28.0,
        )
        self.assertEqual(res.polymerase, "T7_G47A")
        self.assertIn("CleanCap AG", res.cap_analog or "")
        self.assertEqual(res.predicted_capping_efficiency_percent, 95.0)
        self.assertFalse(any("reduced incorporation" in w for w in res.warnings))

    def test_ivt_with_t7_short_promoter_no_mismatch(self) -> None:
        # 16-mer T7_short promoter variant with T7 polymerase
        seq = "AATACGACTCACTATAGGGAAACCC"
        res = calculate_ivt_yield(rna_seq=seq, polymerase="T7")
        self.assertTrue(res.promoter_detected)
        self.assertIn("T7_short", res.promoter_detected)
        self.assertFalse(any("Promoter mismatch" in w for w in res.warnings))

    def test_ivt_cleancap_ag_with_wt_t7_no_incorporation_warning(self) -> None:
        seq = "GGGAGACCCAAGCT"
        res = calculate_ivt_yield(rna_seq=seq, cap_analog="CleanCap_AG", polymerase="T7")
        self.assertFalse(any("reduced incorporation" in w for w in res.warnings))

    def test_ivt_with_sp6_and_cleancap_au(self) -> None:
        seq = "ATTTAGGTGACACTATAGAAGAUCCCAAGCU"
        res = calculate_ivt_yield(
            rna_seq=seq,
            polymerase="SP6",
            cap_analog="CleanCap_AU",
            mg_conc_mm=30.0,
        )
        self.assertEqual(res.polymerase, "SP6")
        self.assertIn("CleanCap AU", res.cap_analog or "")
        self.assertEqual(res.predicted_capping_efficiency_percent, 92.0)

    def test_ivt_promoter_mismatch_warning(self) -> None:
        # Sequence has T7 promoter but polymerase is SP6
        seq = "TAATACGACTCACTATAGGGAGACCCAAGCT"
        res = calculate_ivt_yield(
            rna_seq=seq,
            polymerase="SP6",
        )
        self.assertTrue(any("Promoter mismatch" in w for w in res.warnings))

    def test_ivt_mg_ratio_warnings(self) -> None:
        # Low Mg2+ (10 mM Mg with 20 mM total NTP -> 0.5x ratio)
        seq = "GGGAGACCCAAGCU"
        res_low = calculate_ivt_yield(rna_seq=seq, mg_conc_mm=10.0, atp_mm=5.0, ctp_mm=5.0, gtp_mm=5.0, utp_mm=5.0)
        self.assertTrue(any("Suboptimal [Mg2+]" in w for w in res_low.warnings))

        # High Mg2+ (60 mM Mg with 20 mM total NTP -> 3.0x ratio)
        res_high = calculate_ivt_yield(rna_seq=seq, mg_conc_mm=60.0, atp_mm=5.0, ctp_mm=5.0, gtp_mm=5.0, utp_mm=5.0)
        self.assertTrue(any("High [Mg2+]" in w for w in res_high.warnings))


class TestProteinStrategyRecommender(unittest.TestCase):
    """Test biophysical profiling and application strategy recommendations."""

    def setUp(self) -> None:
        # Lysozyme-like model sequence with disulfides and known basic pI
        self.basic_seq = "KVFGRCELAAAMKRHGLDNYRGYSLGNWVCAAKFESNFNTQATNRNTDGSTDYGILQINSRWWCNDGRTPGSRNLCNIPCSALLSSDITASVNCAKKIVSDGNGMNAWVAWRNRCKGTDVQAWIRGCRL"
        # Acidic cytoplasmic protein sequence
        self.acidic_seq = "MDPEETEIIRKQWRELENKLAEFEANLEAQEVELEAELAELEAQLEAELEAK"

    def test_biophysical_metrics(self) -> None:
        p_basic = analyze_protein_profile(self.basic_seq)
        self.assertGreater(p_basic.isoelectric_point, 9.0)  # Basic pI
        self.assertEqual(p_basic.cysteine_count, 8)
        self.assertEqual(p_basic.predicted_disulfide_bonds, 4)
        self.assertFalse(p_basic.has_odd_cysteines)

        p_acidic = analyze_protein_profile(self.acidic_seq)
        self.assertLess(p_acidic.isoelectric_point, 5.0)  # Acidic pI
        self.assertLess(p_acidic.gravy_index, -0.5)  # Highly hydrophilic

    def test_odd_cysteine_and_glycosylation_detection(self) -> None:
        # Sequence with 3 cysteines (odd free thiol) and N-X-[S/T] glycosylation sequon (N-L-S)
        seq = "MKACDCPNLTS"
        profile = analyze_protein_profile(seq)
        self.assertEqual(profile.cysteine_count, 2)
        self.assertFalse(profile.has_odd_cysteines)

        seq_odd = "MKACDCPNLTSCA"
        profile_odd = analyze_protein_profile(seq_odd)
        self.assertEqual(profile_odd.cysteine_count, 3)
        self.assertTrue(profile_odd.has_odd_cysteines)
        self.assertIn(8, profile_odd.n_glycosylation_sites)  # Position of N in NLTS (index 8)

    def test_crystallography_recommendation(self) -> None:
        res = recommend_protein_strategy(self.basic_seq, application="xray_crystallography")
        self.assertIsInstance(res, ProteinRecommendationResult)
        self.assertEqual(res.application, "xray_crystallography")
        # Hosts should include E. coli
        hosts = [h[0] for h in res.recommended_hosts]
        self.assertTrue(any("E. coli" in h for h in hosts))
        # Buffer recommendation: pI is > 9.0, so buffer pH should be acidic/neutral (offset from pI)
        self.assertLess(res.recommended_sec_buffer_ph, res.biophysical_profile.isoelectric_point - 1.0)

    def test_cryo_em_membrane_recommendation(self) -> None:
        # Hydrophobic membrane target
        res = recommend_protein_strategy(
            sequence=self.basic_seq,
            application="cryo_em",
            is_membrane=True,
            target_name="IonChannel_Model",
        )
        self.assertEqual(res.application, "cryo_em")
        hosts = [h[0] for h in res.recommended_hosts]
        self.assertTrue(any("Expi293F" in h or "Mammalian" in h for h in hosts))
        # Detergent guidance present
        self.assertTrue(any("DDM" in g or "LMNG" in g for g in res.detergent_or_additive_guidance))

    def test_easy_convenience_api(self) -> None:
        rec_backbone = customize_backbone("pET28a(+)", resistance="AmpR")
        self.assertIsInstance(rec_backbone, PlasmidRecord)

        rec_prot = recommend_protein(self.basic_seq, application="enzymatic_assay")
        self.assertIsInstance(rec_prot, ProteinRecommendationResult)
        self.assertIn("enzymatic_assay", rec_prot._repr_html_())


class TestV15CLI(unittest.TestCase):
    """Test CLI commands for Milestone 2 features."""

    def test_cli_customize_backbone(self) -> None:
        from biolabcalc.cli import main
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["plasmid", "customize-backbone", "-b", "pET28a(+)", "--resistance", "AmpR", "--origin", "p15A"])
        out = buf.getvalue()
        self.assertIn("CUSTOMIZED PLASMID BACKBONE", out)
        self.assertIn("p15A", out)
        self.assertIn("AmpR", out)

    def test_cli_ivt_polymerase_and_cap(self) -> None:
        from biolabcalc.cli import main
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["ivt", "-s", "TAATACGACTCACTATAAGGAGACCCAAGCT", "--polymerase", "T7_G47A", "--cap", "CleanCap_AG"])
        out = buf.getvalue()
        self.assertIn("T7_G47A", out)
        self.assertIn("CleanCap AG", out)

    def test_cli_protein_recommend(self) -> None:
        from biolabcalc.cli import main
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["protein-recommend", "-s", "MKTIIALSYIFCLVFA", "-a", "cryo_em", "-m"])
        out = buf.getvalue()
        self.assertIn("PROTEIN EXPRESSION & PURIFICATION STRATEGY", out)
        self.assertIn("cryo_em", out)


if __name__ == "__main__":
    unittest.main()
