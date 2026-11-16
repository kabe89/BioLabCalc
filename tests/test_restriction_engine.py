import os
import sys
import unittest

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.restriction_engine import (
    PlasmidRecord,
    PlasmidFeature,
    RestrictionCutSite,
    DigestedFragment,
    RestrictionDigestPrediction,
    EnzymeScreenResult,
    compile_recognition_regex,
    find_restriction_sites,
    predict_restriction_digest,
    screen_restriction_enzymes,
)
from biolabcalc.molecular_weight import calculate_dna_mw

# Standard 2,686 bp pUC19 sequence (GenBank L09137.2)
PUC19_SEQ = (
    "TCGCGCGTTTCGGTGATGACGGTGAAAACCTCTGACACATGCAGCTCCCGGAGACGGTCACAGCTTGTCTGTAAGCGGATGCCGGGAGCAGACAAGCCCGTCAG"
    "GGCGCGTCAGCGGGTGTTGGCGGGTGTCGGGGCTGGCTTAACTATGCGGCATCAGAGCAGATTGTACTGAGAGTGCACCATATGCGGTGTGAAATACCGCACAG"
    "ATGCGTAAGGAGAAAATACCGCATCAGGCGCCATTCGCCATTCAGGCTGCGCAACTGTTGGGAAGGGCGATCGGTGCGGGCCTCTTCGCTATTACGCCAGCTGG"
    "CGAAAGGGGGATGTGCTGCAAGGCGATTAAGTTGGGTAACGCCAGGGTTTTCCCAGTCACGACGTTGTAAAACGACGGCCAGTGAATTCGAGCTCGGTACCCGG"
    "GGATCCTCTAGAGTCGACCTGCAGGCATGCAAGCTTGGCGTAATCATGGTCATAGCTGTTTCCTGTGTGAAATTGTTATCCGCTCACAATTCCACACAACATAC"
    "GAGCCGGAAGCATAAAGTGTAAAGCCTGGGGTGCCTAATGAGTGAGCTAACTCACATTAATTGCGTTGCGCTCACTGCCCGCTTTCCAGTCGGGAAACCTGTCG"
    "TGCCAGCTGCATTAATGAATCGGCCAACGCGCGGGGAGAGGCGGTTTGCGTATTGGGCGCTCTTCCGCTTCCTCGCTCACTGACTCGCTGCGCTCGGTCGTTCG"
    "GCTGCGGCGAGCGGTATCAGCTCACTCAAAGGCGGTAATACGGTTATCCACAGAATCAGGGGATAACGCAGGAAAGAACATGTGAGCAAAAGGCCAGCAAAAGG"
    "CCAGGAACCGTAAAAAGGCCGCGTTGCTGGCGTTTTTCCATAGGCTCCGCCCCCCTGACGAGCATCACAAAAATCGACGCTCAAGTCAGAGGTGGCGAAACCCG"
    "ACAGGACTATAAAGATACCAGGCGTTTCCCCCTGGAAGCTCCCTCGTGCGCTCTCCTGTTCCGACCCTGCCGCTTACCGGATACCTGTCCGCCTTTCTCCCTTC"
    "GGGAAGCGTGGCGCTTTCTCATAGCTCACGCTGTAGGTATCTCAGTTCGGTGTAGGTCGTTCGCTCCAAGCTGGGCTGTGTGCACGAACCCCCCGTTCAGCCCG"
    "ACCGCTGCGCCTTATCCGGTAACTATCGTCTTGAGTCCAACCCGGTAAGACACGACTTATCGCCACTGGCAGCAGCCACTGGTAACAGGATTAGCAGAGCGAGG"
    "TATGTAGGCGGTGCTACAGAGTTCTTGAAGTGGTGGCCTAACTACGGCTACACTAGAAGAACAGTATTTGGTATCTGCGCTCTGCTGAAGCCAGTTACCTTCGG"
    "AAAAAGAGTTGGTAGCTCTTGATCCGGCAAACAAACCACCGCTGGTAGCGGTGGTTTTTTTGTTTGCAAGCAGCAGATTACGCGCAGAAAAAAAGGATCTCAAG"
    "AAGATCCTTTGATCTTTTCTACGGGGTCTGACGCTCAGTGGAACGAAAACTCACGTTAAGGGATTTTGGTCATGAGATTATCAAAAAGGATCTTCACCTAGATC"
    "CTTTTAAATTAAAAATGAAGTTTTAAATCAATCTAAAGTATATATGAGTAAACTTGGTCTGACAGTTACCAATGCTTAATCAGTGAGGCACCTATCTCAGCGAT"
    "CTGTCTATTTCGTTCATCCATAGTTGCCTGACTCCCCGTCGTGTAGATAACTACGATACGGGAGGGCTTACCATCTGGCCCCAGTGCTGCAATGATACCGCGAG"
    "ACCCACGCTCACCGGCTCCAGATTTATCAGCAATAAACCAGCCAGCCGGAAGGGCCGAGCGCAGAAGTGGTCCTGCAACTTTATCCGCCTCCATCCAGTCTATT"
    "AATTGTTGCCGGGAAGCTAGAGTAAGTAGTTCGCCAGTTAATAGTTTGCGCAACGTTGTTGCCATTGCTACAGGCATCGTGGTGTCACGCTCGTCGTTTGGTAT"
    "GGCTTCATTCAGCTCCGGTTCCCAACGATCAAGGCGAGTTACATGATCCCCCATGTTGTGCAAAAAAGCGGTTAGCTCCTTCGGTCCTCCGATCGTTGTCAGAA"
    "GTAAGTTGGCCGCAGTGTTATCACTCATGGTTATGGCAGCACTGCATAATTCTCTTACTGTCATGCCATCCGTAAGATGCTTTTCTGTGACTGGTGAGTACTCA"
    "ACCAAGTCATTCTGAGAATAGTGTATGCGGCGACCGAGTTGCTCTTGCCCGGCGTCAATACGGGATAATACCGCGCCACATAGCAGAACTTTAAAAGTGCTCAT"
    "CATTGGAAAACGTTCTTCGGGGCGAAAACTCTCAAGGATCTTACCGCTGTTGAGATCCAGTTCGATGTAACCCACTCGTGCACCCAACTGATCTTCAGCATCTT"
    "TTACTTTCACCAGCGTTTCTGGGTGAGCAAAAACAGGAAGGCAAAATGCCGCAAAAAAGGGAATAAGGGCGACACGGAAATGTTGAATACTCATACTCTTCCTT"
    "TTTCAATATTATTGAAGCATTTATCAGGGTTATTGTCTCATGAGCGGATACATATTTGAATGTATTTAGAAAAATAAACAAATAGGGGTTCCGCGCACATTTCC"
    "CCGAAAAGTGCCACCTGACGTCTAAGAAACCATTATTATCATGACATTAACCTATAAAAATAGGCGTATCACGAGGCCCTTTCGTC"
)


class TestRestrictionEngine(unittest.TestCase):
    def test_puc19_sequence_integrity(self):
        self.assertEqual(len(PUC19_SEQ), 2686)

    def test_iupac_regex_compilation(self):
        # SfiI recognition motif: GGCCNNNNNGGCC
        pat = compile_recognition_regex("GGCCNNNNNGGCC")
        test_seq = "ACGGCCATATCGGCCAT"
        m = list(pat.finditer(test_seq))
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0].group(1), "GGCCATATCGGCC")

        # Overlapping sites: GATCGATC
        pat_dpn = compile_recognition_regex("GATC")
        m_dpn = list(pat_dpn.finditer("GATCGATC"))
        self.assertEqual(len(m_dpn), 2)
        self.assertEqual(m_dpn[0].start(), 0)
        self.assertEqual(m_dpn[1].start(), 4)

    def test_puc19_single_digest_ecori(self):
        # EcoRI single cutter in pUC19
        pred = predict_restriction_digest(PUC19_SEQ, ["EcoRI"], circular=True)
        self.assertEqual(pred.total_length_bp, 2686)
        self.assertEqual(pred.topology, "circular")
        self.assertEqual(len(pred.cut_sites), 1)

        cut = pred.cut_sites[0]
        self.assertEqual(cut.enzyme, "EcoRI")
        self.assertEqual(cut.cut_pos_top, 396)
        self.assertEqual(cut.cut_pos_bottom, 400)
        self.assertEqual(cut.recognition_start, 396)
        self.assertEqual(cut.recognition_end, 401)
        self.assertEqual(cut.overhang_type, "5' overhang")
        self.assertEqual(cut.overhang_seq, "AATT")

        # Must yield exactly 1 linearized fragment of 2686 bp
        self.assertEqual(pred.fragment_count, 1)
        self.assertEqual(len(pred.fragments), 1)
        frag = pred.fragments[0]
        self.assertEqual(frag.length_bp, 2686)
        self.assertEqual(frag.left_enzyme, "EcoRI")
        self.assertEqual(frag.right_enzyme, "EcoRI")
        self.assertEqual(frag.left_overhang_type, "5' overhang")
        self.assertEqual(frag.right_overhang_type, "5' overhang")
        self.assertEqual(frag.left_overhang_seq, "AATT")
        self.assertEqual(frag.right_overhang_seq, "AATT")

        expected_mw = calculate_dna_mw(length=2686, double_stranded=True).average_mw
        self.assertAlmostEqual(frag.molecular_weight_da, expected_mw, places=1)
        self.assertIsNotNone(pred.pipetting_plan)

    def test_puc19_double_digest_ecori_hindiii(self):
        # EcoRI + HindIII double digest
        pred = predict_restriction_digest(PUC19_SEQ, ["EcoRI", "HindIII"], circular=True)
        self.assertEqual(pred.total_length_bp, 2686)
        self.assertEqual(len(pred.cut_sites), 2)

        # Cuts at 396 (EcoRI) and 447 (HindIII)
        cuts = sorted(pred.cut_sites, key=lambda s: s.cut_pos_top)
        self.assertEqual(cuts[0].cut_pos_top, 396)
        self.assertEqual(cuts[1].cut_pos_top, 447)

        # Must produce exactly 2 bands: 51 bp and 2635 bp
        self.assertEqual(pred.fragment_count, 2)
        frag_lengths = [f.length_bp for f in pred.fragments]
        self.assertEqual(frag_lengths, [51, 2635])
        self.assertEqual(sum(frag_lengths), 2686)

        # Verify terminal overhang identities on fragments
        f_51 = pred.fragments[0]
        self.assertEqual(f_51.left_enzyme, "EcoRI")
        self.assertEqual(f_51.right_enzyme, "HindIII")
        self.assertEqual(f_51.left_overhang_seq, "AATT")
        self.assertEqual(f_51.right_overhang_seq, "AGCT")
        self.assertFalse(f_51.wraps_origin)

        f_2635 = pred.fragments[1]
        self.assertEqual(f_2635.left_enzyme, "HindIII")
        self.assertEqual(f_2635.right_enzyme, "EcoRI")
        self.assertTrue(f_2635.wraps_origin)

    def test_type_iis_bsai_dynamic_overhang_extraction(self):
        # Forward strand BsaI-HFv2 site: GGTCTC(1/5)
        # Sequence: ACGTGGTCTCATGCACCC
        # Motif starts at 5 (1-based: 5, GGTCTC). Base 11 is A, then overhang TGCA (bases 12-15)
        seq_fwd = "ACGTGGTCTCATGCACCC"
        sites_fwd = find_restriction_sites(seq_fwd, ["BsaI-HFv2"], circular=False)
        self.assertEqual(len(sites_fwd["BsaI-HFv2"]), 1)
        cut_fwd = sites_fwd["BsaI-HFv2"][0]
        self.assertEqual(cut_fwd.strand, 1)
        self.assertEqual(cut_fwd.overhang_type, "5' overhang")
        self.assertEqual(cut_fwd.overhang_seq, "TGCA")

        # Reverse strand BsaI-HFv2 site (GAGACC)
        # Sequence: ACGTGCATGAGACCCCC
        # Downstream 5' overhang of 4 nt to the left of GAGACC is TGCA
        seq_rev = "ACGTGCATGAGACCCCC"
        sites_rev = find_restriction_sites(seq_rev, ["BsaI-HFv2"], circular=False)
        self.assertEqual(len(sites_rev["BsaI-HFv2"]), 1)
        cut_rev = sites_rev["BsaI-HFv2"][0]
        self.assertEqual(cut_rev.strand, -1)
        self.assertEqual(cut_rev.overhang_type, "5' overhang")
        self.assertEqual(cut_rev.overhang_seq, "TGCA")

    def test_origin_spanning_cleavage(self):
        # Construct circular sequence where EcoRI site spans the origin:
        # End of sequence has 'G', start of sequence has 'AATTC'
        tail = "G"
        head = "AATTC"
        body = "A" * 94
        seq = head + body + tail  # length 100: AATTC (5) + 94 + G (1) = 100
        self.assertEqual(len(seq), 100)

        sites = find_restriction_sites(seq, ["EcoRI"], circular=True)
        self.assertEqual(len(sites["EcoRI"]), 1)
        cut = sites["EcoRI"][0]
        self.assertEqual(cut.recognition_start, 100)
        self.assertEqual(cut.recognition_end, 5)
        self.assertEqual(cut.cut_pos_top, 100)
        self.assertEqual(cut.cut_pos_bottom, 4)

        # Double digest on origin-spanning construct
        # Introduce a second EcoRI site inside the body at pos 40
        body_with_site = ("A" * 34) + "GAATTC" + ("A" * 54)  # 34 + 6 + 54 = 94
        seq2 = head + body_with_site + tail  # length 100
        pred2 = predict_restriction_digest(seq2, ["EcoRI"], circular=True)
        self.assertEqual(pred2.fragment_count, 2)
        frag_lens = [f.length_bp for f in pred2.fragments]
        self.assertEqual(sum(frag_lens), 100)
        self.assertTrue(any(f.wraps_origin for f in pred2.fragments))

    def test_dam_dcm_cpg_methylation_blocking(self):
        # 1. ClaI blocked by Dam methylation when overlapping GATC
        seq_clai_clean = "CCCAATCGATACCC"  # ATCGAT flanked by A: no GATC
        seq_clai_dam = "CCCGATCGATACCC"    # GATCGAT: overlaps GATC

        # Unmethylated: both cut
        res_unmeth_clean = find_restriction_sites(seq_clai_clean, ["ClaI"], dam_methylated=False)["ClaI"]
        res_unmeth_dam = find_restriction_sites(seq_clai_dam, ["ClaI"], dam_methylated=False)["ClaI"]
        self.assertEqual(len(res_unmeth_clean), 1)
        self.assertEqual(len(res_unmeth_dam), 1)

        # Dam methylated: clean site cuts, overlapping site blocked
        res_meth_clean = find_restriction_sites(seq_clai_clean, ["ClaI"], dam_methylated=True)["ClaI"]
        res_meth_dam = find_restriction_sites(seq_clai_dam, ["ClaI"], dam_methylated=True)["ClaI"]
        self.assertEqual(len(res_meth_clean), 1)
        self.assertEqual(len(res_meth_dam), 0)

        # 2. XbaI blocked by Dam methylation when overlapping GATC
        seq_xbai_dam = "CCCTCTAGATCCCC"  # TCTAGATC: overlaps GATC
        self.assertEqual(len(find_restriction_sites(seq_xbai_dam, ["XbaI"], dam_methylated=False)["XbaI"]), 1)
        self.assertEqual(len(find_restriction_sites(seq_xbai_dam, ["XbaI"], dam_methylated=True)["XbaI"]), 0)

        # 3. DpnI requires Dam methylation
        seq_dpni = "CCCGATCCCC"
        self.assertEqual(len(find_restriction_sites(seq_dpni, ["DpnI"], dam_methylated=False)["DpnI"]), 0)
        self.assertEqual(len(find_restriction_sites(seq_dpni, ["DpnI"], dam_methylated=True)["DpnI"]), 1)

        # 4. NotI blocked by CpG methylation
        seq_noti = "CCCGCGGCCGCCCC"
        self.assertEqual(len(find_restriction_sites(seq_noti, ["NotI"], cpg_methylated=False)["NotI"]), 1)
        self.assertEqual(len(find_restriction_sites(seq_noti, ["NotI"], cpg_methylated=True)["NotI"]), 0)

    def test_uncut_circular_plasmid_conformations(self):
        # NotI does not cut pUC19
        pred = predict_restriction_digest(PUC19_SEQ, ["NotI"], circular=True)
        self.assertEqual(pred.fragment_count, 1)
        self.assertEqual(len(pred.cut_sites), 0)

        # Conformations: supercoiled (~0.72*L), relaxed_circle (1.0*L), nicked_open_circular (~1.25*L)
        self.assertIn("supercoiled", pred.uncut_conformations)
        self.assertIn("relaxed_circle", pred.uncut_conformations)
        self.assertIn("nicked_open_circular", pred.uncut_conformations)

        self.assertEqual(pred.uncut_conformations["supercoiled"], round(0.72 * 2686))
        self.assertEqual(pred.uncut_conformations["relaxed_circle"], 2686)
        self.assertEqual(pred.uncut_conformations["nicked_open_circular"], round(1.25 * 2686))

        # Check virtual gel simulation contains bands for conformations
        self.assertEqual(len(pred.gel_bands), 3)

    def test_enzyme_screening_puc19(self):
        plasmid = PlasmidRecord(
            name="pUC19",
            sequence=PUC19_SEQ,
            circular=True,
            features=(
                PlasmidFeature(name="MCS", start=396, end=452, feature_type="mcs"),
                PlasmidFeature(name="ampR", start=1626, end=2486, feature_type="CDS"),
                PlasmidFeature(name="ori", start=2500, end=2686, feature_type="rep_origin"),
            ),
        )

        screen = screen_restriction_enzymes(plasmid)
        self.assertEqual(screen.plasmid_name, "pUC19")

        # Classic 10 single cutters in pUC19 MCS
        expected_mcs_cutters = {
            "BamHI", "EcoRI", "HindIII", "KpnI", "PstI",
            "SacI", "SalI", "SmaI", "SphI", "XbaI",
        }
        self.assertTrue(expected_mcs_cutters.issubset(set(screen.single_cutters)))
        self.assertEqual(set(screen.mcs_unique_cutters), expected_mcs_cutters)

        # Non-cutters include rare 8-base cutters
        self.assertIn("NotI", screen.non_cutters)
        self.assertIn("PacI", screen.non_cutters)
        self.assertIn("AscI", screen.non_cutters)

        # Double cutters in pUC19
        self.assertIn("PvuI", screen.double_cutters)
        self.assertIn("PvuII", screen.double_cutters)

    def test_linear_dna_digestion(self):
        seq = "A" * 200 + "GAATTC" + "A" * 300 + "GAATTC" + "A" * 100
        # Length: 200 + 6 + 300 + 6 + 100 = 612 bp
        self.assertEqual(len(seq), 612)

        pred = predict_restriction_digest(seq, ["EcoRI"], circular=False)
        self.assertEqual(pred.topology, "linear")
        self.assertEqual(len(pred.cut_sites), 2)
        # Linear DNA with 2 cuts produces exactly 3 fragments
        self.assertEqual(pred.fragment_count, 3)
        self.assertEqual(sum(f.length_bp for f in pred.fragments), 612)

        # First fragment ends at cut 1, last fragment starts at cut 2
        self.assertEqual(pred.fragments[0].left_enzyme, "none")
        self.assertEqual(pred.fragments[0].right_enzyme, "EcoRI")
        self.assertEqual(pred.fragments[2].left_enzyme, "EcoRI")
        self.assertEqual(pred.fragments[2].right_enzyme, "none")

    def test_contained_features_tracking(self):
        plasmid = PlasmidRecord(
            name="pUC19",
            sequence=PUC19_SEQ,
            circular=True,
            features=(
                PlasmidFeature(name="ampR", start=1626, end=2486, feature_type="CDS"),
            ),
        )

        pred = predict_restriction_digest(plasmid, ["EcoRI", "HindIII"], circular=True)
        # Fragment 1 (51 bp, 397-447) does not contain ampR
        self.assertEqual(pred.fragments[0].contained_features, ())
        # Fragment 2 (2635 bp, 448-396 wrapping origin) completely contains ampR (1626-2486)
        self.assertIn("ampR", pred.fragments[1].contained_features)


if __name__ == '__main__':
    unittest.main()
