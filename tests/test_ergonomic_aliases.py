"""Tests for ergonomic property aliases and class aliases across BioLabCalc dataclasses."""

import json
import unittest
import biolabcalc as blc
from biolabcalc.primers import analyze_primer, design_primers, PrimerAnalysis, PrimerPair
from biolabcalc.molecular_weight import calculate_dna_mw, calculate_protein_mw, MolecularWeightResult
from biolabcalc.restriction_engine import (
    predict_restriction_digest,
    DigestedFragment,
    RestrictionCutSite,
    RestrictionDigestPrediction,
    DigestionPrediction,
    RestrictionDigestResult,
    RestrictionFragment,
)
from biolabcalc.gels import simulate_gel, GelBand, GelLaneSimulation
from biolabcalc.pcr import calculate_pcr_kinetics, build_master_mix, PCRResult, PCRReaction, MasterMixItem, PCRMasterMix
from biolabcalc.cloning import (
    calculate_golden_gate_assembly,
    plan_restriction_digest,
    calculate_ligation,
    calculate_gibson_assembly,
    GoldenGateResult,
    GoldenGatePlan,
    DigestSetupResult,
    LigationSetupResult,
    GibsonAssemblyResult,
)
from biolabcalc.protein import fit_standard_curve, StandardCurveResult, ProteinYieldResult


class TestErgonomicAliases(unittest.TestCase):

    def test_primer_analysis_aliases(self):
        analysis = analyze_primer("ATGCGATCGATCGATC")
        self.assertEqual(analysis.length_nt, analysis.length)
        self.assertEqual(analysis.length_nt, 16)
        self.assertEqual(analysis.tm, analysis.tm_celsius)
        self.assertEqual(analysis.gc, analysis.gc_percent)
        self.assertEqual(analysis.gc_pct, analysis.gc_percent)
        self.assertEqual(analysis.seq, analysis.sequence)

    def test_primer_pair_aliases(self):
        pairs = design_primers("ATGCGATCGATCGATCGATCGATCGATC" * 5, target_tm=55.0)
        self.assertGreater(len(pairs), 0)
        pair = pairs[0]
        self.assertEqual(pair.forward, pair.forward_primer)
        self.assertEqual(pair.reverse, pair.reverse_primer)
        self.assertEqual(pair.fwd, pair.forward_primer)
        self.assertEqual(pair.rev, pair.reverse_primer)
        self.assertEqual(pair.amplicon_bp, pair.amplicon_length_bp)
        self.assertEqual(pair.length_bp, pair.amplicon_length_bp)
        self.assertEqual(pair.delta_tm, pair.tm_difference)

    def test_molecular_weight_result_aliases(self):
        dna_res = calculate_dna_mw("ATGC", double_stranded=True)
        self.assertEqual(dna_res.molecular_weight, dna_res.average_mw)
        self.assertEqual(dna_res.mw, dna_res.average_mw)
        self.assertEqual(dna_res.molecular_weight_da, dna_res.average_mw)
        self.assertEqual(dna_res.mw_da, dna_res.average_mw)
        self.assertEqual(dna_res.avg_mw, dna_res.average_mw)
        self.assertEqual(dna_res.mono_mw, dna_res.monoisotopic_mw)
        self.assertEqual(dna_res.monoisotopic_mw_da, dna_res.monoisotopic_mw)
        self.assertEqual(dna_res.gc, dna_res.gc_content)
        self.assertEqual(dna_res.gc_pct, dna_res.gc_content)
        self.assertEqual(dna_res.seq, dna_res.sequence)

        prot_res = calculate_protein_mw("MRSIDRSID")
        self.assertEqual(prot_res.molecular_weight, prot_res.average_mw)
        self.assertEqual(prot_res.molecular_weight_da, prot_res.average_mw)
        self.assertEqual(prot_res.mw, prot_res.average_mw)

    def test_digested_fragment_aliases(self):
        digest = predict_restriction_digest("GAATTCAAAAGGATCC", ["EcoRI", "BamHI"], circular=False)
        self.assertGreater(len(digest.fragments), 0)
        frag = digest.fragments[0]
        self.assertEqual(frag.start_pos, frag.start_1based)
        self.assertEqual(frag.end_pos, frag.end_1based)
        self.assertEqual(frag.start, frag.start_1based)
        self.assertEqual(frag.end, frag.end_1based)
        self.assertEqual(frag.length, frag.length_bp)
        self.assertEqual(frag.size_bp, frag.length_bp)
        self.assertEqual(frag.size, frag.length_bp)
        self.assertEqual(frag.mw_da, frag.molecular_weight_da)
        self.assertEqual(frag.mw, frag.molecular_weight_da)
        self.assertEqual(frag.molecular_weight, frag.molecular_weight_da)

    def test_restriction_cut_site_aliases(self):
        digest = predict_restriction_digest("GAATTCGGATCC", ["EcoRI"], circular=False)
        self.assertGreater(len(digest.cut_sites), 0)
        site = digest.cut_sites[0]
        self.assertEqual(site.start, site.recognition_start)
        self.assertEqual(site.end, site.recognition_end)
        self.assertEqual(site.pos, site.cut_pos_top)
        self.assertEqual(site.position, site.cut_pos_top)

    def test_restriction_digest_prediction_aliases_and_types(self):
        digest = predict_restriction_digest("GAATTC" + ("A" * 1000) + "GGATCC" + ("T" * 2000), ["EcoRI", "BamHI"], circular=True)
        self.assertEqual(digest.count, digest.fragment_count)
        self.assertEqual(digest.num_fragments, digest.fragment_count)
        self.assertEqual(digest.length_bp, digest.total_length_bp)
        self.assertEqual(digest.size_bp, digest.total_length_bp)
        self.assertEqual(digest.length, digest.total_length_bp)
        self.assertEqual(digest.size, digest.total_length_bp)
        self.assertFalse(digest.is_linearized)
        self.assertFalse(digest.is_uncut)

        # Single cutter linearizes circular plasmid
        linear_digest = predict_restriction_digest("GAATTC" + ("A" * 1000), ["EcoRI"], circular=True)
        self.assertTrue(linear_digest.is_linearized)

        # Non cutter
        uncut_digest = predict_restriction_digest("AAAAA", ["EcoRI"], circular=True)
        self.assertTrue(uncut_digest.is_uncut)

        # Class aliases
        self.assertIs(DigestionPrediction, RestrictionDigestPrediction)
        self.assertIs(RestrictionDigestResult, RestrictionDigestPrediction)
        self.assertIs(RestrictionFragment, DigestedFragment)

    def test_gel_aliases(self):
        sim = simulate_gel(sample_sizes=[1000, 2000], ladder_key="1kb_dna")
        self.assertEqual(sim.bands, sim.sample_bands)
        self.assertEqual(sim.ladder, sim.ladder_bands)
        self.assertEqual(sim.ladder_key, sim.ladder_name)
        self.assertEqual(sim.ascii, sim.ascii_visualization)
        self.assertEqual(sim.gel_percentage, sim.recommended_gel_percentage)

        band = sim.bands[0]
        self.assertEqual(band.rf, band.relative_migration_rf)
        self.assertEqual(band.size_bp, band.size)
        self.assertEqual(band.length_bp, band.size)

    def test_pcr_aliases_and_types(self):
        res = calculate_pcr_kinetics(amplicon_len_bp=500, template_ng=10.0, cycles=25)
        self.assertEqual(res.length_bp, res.amplicon_length_bp)
        self.assertEqual(res.size_bp, res.amplicon_length_bp)
        self.assertEqual(res.length, res.amplicon_length_bp)
        self.assertEqual(res.size, res.amplicon_length_bp)
        self.assertEqual(res.mw, res.amplicon_mw)
        self.assertEqual(res.molecular_weight, res.amplicon_mw)
        self.assertEqual(res.yield_ng, res.amplicon_yield_ng)
        self.assertEqual(res.yield_pmol, res.amplicon_yield_pmol)
        self.assertEqual(res.cycles, res.cycles_run)

        mix = build_master_mix(num_reactions=5, reaction_volume_ul=25.0)
        item = mix[0]
        self.assertEqual(item.name, item.component)
        self.assertEqual(item.volume_ul, item.volume_per_reaction_ul)
        self.assertEqual(item.per_rxn_ul, item.volume_per_reaction_ul)
        self.assertEqual(item.total_ul, item.total_volume_ul)
        self.assertEqual(item.conc, item.final_concentration)

        self.assertIs(PCRReaction, PCRResult)
        self.assertIs(PCRMasterMix, MasterMixItem)

    def test_cloning_aliases(self):
        gg = calculate_golden_gate_assembly(vector_length_bp=3000, insert_lengths_bp=[1000, 500])
        self.assertEqual(gg.vector_ng, gg.vector_mass_ng)
        self.assertEqual(gg.insert_ng, gg.insert_masses_ng)
        self.assertEqual(gg.total_ng, gg.total_dna_mass_ng)
        self.assertEqual(gg.vector_bp, gg.vector_length_bp)
        self.assertEqual(gg.insert_bp, gg.insert_lengths_bp)
        self.assertEqual(gg.volume_ul, gg.reaction_volume_ul)
        self.assertEqual(gg.ratio, gg.insert_to_vector_ratio)
        self.assertIs(GoldenGatePlan, GoldenGateResult)

        digest_plan = plan_restriction_digest(dna_mass_ug=1.0, reaction_volume_ul=50.0)
        self.assertEqual(digest_plan.volume_ul, digest_plan.reaction_volume_ul)
        self.assertEqual(digest_plan.mass_ug, digest_plan.dna_mass_ug)
        self.assertEqual(digest_plan.buffer, digest_plan.recommended_buffer)
        self.assertEqual(digest_plan.temp_celsius, digest_plan.incubation_temp_celsius)
        self.assertEqual(digest_plan.time_min, digest_plan.incubation_time_min)

        lig = calculate_ligation(vector_length_bp=3000, insert_length_bp=1000, vector_mass_ng=50.0)
        self.assertEqual(lig.vector_bp, lig.vector_length_bp)
        self.assertEqual(lig.insert_bp, lig.insert_length_bp)
        self.assertEqual(lig.vector_ng, lig.vector_mass_ng)
        self.assertEqual(lig.insert_ng, lig.insert_mass_ng)
        self.assertEqual(lig.ratio, lig.molar_ratio_insert_to_vector)

        gib = calculate_gibson_assembly(vector_length_bp=3000, insert_lengths_bp=[1000, 500])
        self.assertEqual(gib.vector_bp, gib.vector_length_bp)
        self.assertEqual(gib.vector_ng, gib.vector_mass_ng)
        self.assertEqual(gib.insert_bp, gib.insert_lengths_bp)
        self.assertEqual(gib.insert_ng, gib.insert_masses_ng)
        self.assertEqual(gib.total_pmol, gib.total_dna_pmol)

    def test_protein_aliases(self):
        standards = [(0.0, 0.045), (125.0, 0.142), (250.0, 0.238), (500.0, 0.420), (1000.0, 0.795)]
        curve = fit_standard_curve(standards, assay_type="Bradford")
        self.assertEqual(curve.r2, curve.r_squared)
        self.assertEqual(curve.m, curve.slope)
        self.assertEqual(curve.b, curve.intercept)

        pred = curve.predict(0.500, protein_mw=25000.0)
        self.assertEqual(pred.conc_mg_ml, pred.concentration_mg_ml)
        self.assertEqual(pred.conc_ug_ml, pred.concentration_ug_ml)
        self.assertEqual(pred.mw, pred.molecular_weight)
        self.assertEqual(pred.yield_mg, pred.total_yield_mg)
        self.assertEqual(pred.yield_ug, pred.total_yield_ug)
        self.assertEqual(pred.yield_ng, pred.total_yield_ng)

    def test_quickstart_cookbook_execution(self):
        import io
        import contextlib
        from pathlib import Path

        nb_path = Path(__file__).resolve().parent.parent / "examples" / "quickstart_cookbook.ipynb"
        if not nb_path.exists():
            nb_path = Path("examples/quickstart_cookbook.ipynb")
        if not nb_path.exists():
            self.skipTest("examples/quickstart_cookbook.ipynb not found (e.g. in stripped distribution)")

        with open(nb_path, encoding="utf-8") as f:
            nb = json.load(f)
        exec_env = {"__name__": "__main__"}
        f_stdout = io.StringIO()
        with contextlib.redirect_stdout(f_stdout):
            for i, cell in enumerate(nb["cells"]):
                if cell.get("cell_type") == "code":
                    code = "".join(cell.get("source", []))
                    lines = [l for l in code.splitlines() if not l.strip().startswith("!") and not l.strip().startswith("%")]
                    exec("\n".join(lines), exec_env)
        captured = f_stdout.getvalue()
        self.assertIn("dsDNA MW:", captured)
        self.assertIn("PCR Amplification Yield:", captured)
        self.assertIn("Enzymes: EcoRI + BamHI", captured)


if __name__ == "__main__":
    unittest.main()
