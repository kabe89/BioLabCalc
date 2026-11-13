"""Unit tests for sequence utilities and molecular weight QoL enhancements."""

from __future__ import annotations
import os
import sys
import tempfile
import unittest

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.molecular_weight import (
    calculate_dna_mw,
    calculate_rna_mw,
    calculate_protein_mw,
    DNA_RESIDUE_MW,
    RNA_RESIDUE_MW,
    DNA_RESIDUE_MONOISOTOPIC,
    RNA_RESIDUE_MONOISOTOPIC,
    AMINO_ACID_MW,
    AMINO_ACID_MONOISOTOPIC,
)
from biolabcalc.seq_utils import (
    clean_sequence,
    validate_sequence,
    reverse_complement,
    calculate_gc_content,
    translate_dna,
    transcribe,
    reverse_transcribe,
    six_frame_translation,
    ORF,
    find_orfs,
    parse_fasta,
    format_fasta,
)
from biolabcalc import easy


class TestSeqUtilsQoL(unittest.TestCase):
    """Test suite covering degenerate base MW, Sec/Pyl, sequence translation/transcription, ORF finding, and FASTA I/O."""

    def test_degenerate_nucleotide_weights(self):
        """Test IUPAC degenerate nucleotide molecular weights for DNA and RNA."""
        # Check expected average DNA residue weights
        self.assertAlmostEqual(DNA_RESIDUE_MW["R"], 321.21, places=2)
        self.assertAlmostEqual(DNA_RESIDUE_MW["Y"], 296.69, places=2)
        self.assertAlmostEqual(DNA_RESIDUE_MW["S"], 309.20, places=2)
        self.assertAlmostEqual(DNA_RESIDUE_MW["W"], 308.71, places=2)
        self.assertAlmostEqual(DNA_RESIDUE_MW["K"], 316.71, places=2)
        self.assertAlmostEqual(DNA_RESIDUE_MW["M"], 301.20, places=2)
        self.assertAlmostEqual(DNA_RESIDUE_MW["B"], 307.53, places=2)
        self.assertAlmostEqual(DNA_RESIDUE_MW["D"], 315.54, places=2)
        self.assertAlmostEqual(DNA_RESIDUE_MW["H"], 302.20, places=2)
        self.assertAlmostEqual(DNA_RESIDUE_MW["V"], 310.53, places=2)
        self.assertAlmostEqual(DNA_RESIDUE_MW["N"], 308.95, places=2)

        # Check monoisotopic DNA residue weights
        self.assertAlmostEqual(DNA_RESIDUE_MONOISOTOPIC["R"], 321.0551, places=3)
        self.assertAlmostEqual(DNA_RESIDUE_MONOISOTOPIC["Y"], 296.5462, places=3)
        self.assertAlmostEqual(DNA_RESIDUE_MONOISOTOPIC["S"], 309.0495, places=3)
        self.assertAlmostEqual(DNA_RESIDUE_MONOISOTOPIC["W"], 308.5518, places=3)
        self.assertAlmostEqual(DNA_RESIDUE_MONOISOTOPIC["N"], 308.8006, places=3)

        # Check RNA degenerate values
        self.assertAlmostEqual(RNA_RESIDUE_MW["R"], 337.21, places=2)
        self.assertAlmostEqual(RNA_RESIDUE_MW["Y"], 305.68, places=2)
        self.assertAlmostEqual(RNA_RESIDUE_MW["S"], 325.20, places=2)
        self.assertAlmostEqual(RNA_RESIDUE_MW["W"], 317.69, places=2)
        self.assertAlmostEqual(RNA_RESIDUE_MW["K"], 325.69, places=2)
        self.assertAlmostEqual(RNA_RESIDUE_MW["M"], 317.20, places=2)
        self.assertAlmostEqual(RNA_RESIDUE_MW["B"], 318.85, places=2)
        self.assertAlmostEqual(RNA_RESIDUE_MW["D"], 326.86, places=2)
        self.assertAlmostEqual(RNA_RESIDUE_MW["H"], 313.52, places=2)
        self.assertAlmostEqual(RNA_RESIDUE_MW["V"], 326.53, places=2)
        self.assertAlmostEqual(RNA_RESIDUE_MW["N"], 321.44, places=2)

        # ssDNA MW calculation with degenerate bases
        res_dna = calculate_dna_mw("RYSWKMBDHVN", double_stranded=False)
        self.assertEqual(res_dna.length, 11)
        expected_avg = sum(DNA_RESIDUE_MW[b] for b in "RYSWKMBDHVN") - 61.96
        self.assertAlmostEqual(res_dna.average_mw, expected_avg, places=1)

        # dsDNA MW calculation with degenerate bases
        res_ds = calculate_dna_mw("RYSWKMBDHVN", double_stranded=True)
        self.assertEqual(res_ds.seq_type, "dsDNA")
        self.assertGreater(res_ds.average_mw, res_dna.average_mw * 1.9)

        # RNA MW calculation with degenerate bases
        res_rna = calculate_rna_mw("RYSWKMBDHVN")
        self.assertEqual(res_rna.length, 11)
        expected_rna_avg = sum(RNA_RESIDUE_MW[b] for b in "RYSWKMBDHVN") - 61.96 + 239.94
        self.assertAlmostEqual(res_rna.average_mw, expected_rna_avg, places=1)

    def test_non_canonical_amino_acids_mw(self):
        """Test Selenocysteine ('U') and Pyrrolysine ('O') molecular weights."""
        self.assertAlmostEqual(AMINO_ACID_MW["U"], 150.04, places=2)
        self.assertAlmostEqual(AMINO_ACID_MONOISOTOPIC["U"], 150.9536, places=4)
        self.assertAlmostEqual(AMINO_ACID_MW["O"], 237.30, places=2)
        self.assertAlmostEqual(AMINO_ACID_MONOISOTOPIC["O"], 237.1477, places=4)

        # Test single-residue peptide MW: residue MW + H2O (18.015)
        res_u = calculate_protein_mw("U")
        self.assertAlmostEqual(res_u.average_mw, 150.04 + 18.015, places=2)
        self.assertAlmostEqual(res_u.monoisotopic_mw, 150.9536 + 18.01056, places=3)

        res_o = calculate_protein_mw("O")
        self.assertAlmostEqual(res_o.average_mw, 237.30 + 18.015, places=2)
        self.assertAlmostEqual(res_o.monoisotopic_mw, 237.1477 + 18.01056, places=3)

        # Test peptide containing U and O
        peptide = "ACDEFGUO"
        res_pep = calculate_protein_mw(peptide)
        self.assertEqual(res_pep.length, 8)
        self.assertTrue(validate_sequence(peptide, "protein"))

    def test_transcribe_and_reverse_transcribe(self):
        """Test transcribe and reverse_transcribe utilities."""
        dna = "ATGCGTACGTTAGC"
        rna = "AUGCGUACGUUAGC"

        # Direct conversions
        self.assertEqual(transcribe(dna), rna)
        self.assertEqual(reverse_transcribe(rna), dna)

        # Case-insensitivity and cleaning
        self.assertEqual(transcribe("atg cgt acg tta gc"), rna)
        self.assertEqual(reverse_transcribe("aug cgu acg uua gc"), dna)

        # Round-trip
        self.assertEqual(reverse_transcribe(transcribe(dna)), dna)
        self.assertEqual(transcribe(reverse_transcribe(rna)), rna)

        # Empty inputs
        self.assertEqual(transcribe(""), "")
        self.assertEqual(reverse_transcribe(""), "")

    def test_six_frame_translation(self):
        """Test 6-frame translation (+1, +2, +3, -1, -2, -3)."""
        # Sequence: ATGAAGTAACCC
        # Forward:
        # Frame 1: ATG AAG TAA CCC -> M K * P
        # Frame 2: TGA AGT AAC CC  -> * S N
        # Frame 3: GAA GTA ACC C   -> E V T
        # Reverse complement of ATGAAGTAACCC:
        # GGG TTA CTT CAT
        # Frame -1: GGG TTA CTT CAT -> G L L H
        # Frame -2: GGT TAC TTC AT  -> G Y F
        # Frame -3: GTT ACT TCA T   -> V T S
        seq = "ATGAAGTAACCC"
        frames = six_frame_translation(seq, to_stop=False)
        self.assertEqual(set(frames.keys()), {1, 2, 3, -1, -2, -3})
        self.assertEqual(frames[1], "MK*P")
        self.assertEqual(frames[2], "*SN")
        self.assertEqual(frames[3], "EVT")
        self.assertEqual(frames[-1], "GLLH")
        self.assertEqual(frames[-2], "GYF")
        self.assertEqual(frames[-3], "VTS")

        # Translation with to_stop=True
        frames_stopped = six_frame_translation(seq, to_stop=True)
        self.assertEqual(frames_stopped[1], "MK")
        self.assertEqual(frames_stopped[2], "")
        self.assertEqual(frames_stopped[3], "EVT")
        self.assertEqual(frames_stopped[-1], "GLLH")

    def test_find_orfs_known_sequence(self):
        """Test find_orfs with a known ORF sequence."""
        # Construct an artificial sequence with a known 37-aa ORF in frame +1
        # Prefix (9 nt): CCGGTTAAC (0 mod 3 -> frame 1)
        # ORF: ATG (M) + (GATTACAGATTAGACTTA * 6) + TAA (*) -> 114 nt, 37 aa
        # Suffix: GGCCTT
        prefix = "CCGGTTAAC"
        coding = "ATG" + ("GATTACAGATTAGACTTA" * 6) + "TAA"
        suffix = "GGCCTT"
        full_seq = prefix + coding + suffix

        orfs = find_orfs(full_seq, min_length_aa=30)
        self.assertEqual(len(orfs), 1)

        orf = orfs[0]
        self.assertEqual(orf.frame, 1)
        # 1-based start: len(prefix) + 1 = 10
        self.assertEqual(orf.start_nt, 10)
        self.assertEqual(orf.end_nt, 10 + len(coding) - 1)
        self.assertEqual(orf.length_nt, len(coding))
        self.assertEqual(orf.length_aa, 37)
        self.assertEqual(orf.dna_sequence, coding)
        self.assertEqual(orf.protein_sequence, "M" + ("DYRLDL" * 6))

        # Check that shorter ORFs are excluded when min_length_aa is higher
        orfs_strict = find_orfs(full_seq, min_length_aa=40)
        self.assertEqual(len(orfs_strict), 0)

        # Check that min_length_aa lower threshold finds smaller ORFs
        short_seq = "ATG" + ("GCA" * 10) + "TGA"  # 11 aa
        self.assertEqual(len(find_orfs(short_seq, min_length_aa=30)), 0)
        self.assertEqual(len(find_orfs(short_seq, min_length_aa=10)), 1)

        # Check negative frame ORF detection
        rc_seq = reverse_complement(full_seq, seq_type="dna")
        orfs_rc = find_orfs(rc_seq, min_length_aa=30)
        self.assertEqual(len(orfs_rc), 1)
        self.assertEqual(orfs_rc[0].frame, -1)
        self.assertEqual(orfs_rc[0].length_aa, 37)
        self.assertEqual(orfs_rc[0].protein_sequence, "M" + ("DYRLDL" * 6))

    def test_parse_and_format_fasta(self):
        """Test parse_fasta and format_fasta string and file handling."""
        header = "sample_gene | Homo sapiens"
        seq = "ATGCGTAC" * 15  # 120 nt

        # Formatting
        fasta_str = format_fasta(header, seq, line_length=50)
        lines = fasta_str.strip().splitlines()
        self.assertEqual(lines[0], f">{header}")
        self.assertEqual(len(lines[1]), 50)
        self.assertEqual(len(lines[2]), 50)
        self.assertEqual(len(lines[3]), 20)

        # Format with header that already has '>'
        fasta_with_gt = format_fasta(f">{header}", seq, line_length=60)
        self.assertTrue(fasta_with_gt.startswith(f">{header}\n"))
        self.assertFalse(fasta_with_gt.startswith(">>"))

        # Parsing from string
        parsed = parse_fasta(fasta_str)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0][0], header)
        self.assertEqual(parsed[0][1], seq)

        # Parsing multi-record FASTA string
        multi_fasta = ">seq1\nATGC\n>seq2\nGGCCAA\nTT\n"
        records = parse_fasta(multi_fasta)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0], ("seq1", "ATGC"))
        self.assertEqual(records[1], ("seq2", "GGCCAATT"))

        # Parsing from temporary file
        with tempfile.NamedTemporaryFile("w", suffix=".fasta", delete=False) as tf:
            tf.write(multi_fasta)
            tf_path = tf.name

        try:
            file_records = parse_fasta(tf_path)
            self.assertEqual(file_records, records)
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

        # Empty string handling
        self.assertEqual(parse_fasta(""), [])

    def test_easy_sequence_shortcuts(self):
        """Test easy API shortcuts: rc, translate, gc, transcribe, reverse_transcribe, find_orfs."""
        seq = "ATGCGTAC"

        # easy.rc
        self.assertEqual(easy.rc(seq), reverse_complement(seq))
        self.assertEqual(easy.rc("AUGC", seq_type="rna"), "GCAU")

        # easy.translate
        self.assertEqual(easy.translate("ATGAAGTAA"), "MK*")
        self.assertEqual(easy.translate("ATGAAGTAA", to_stop=True), "MK")

        # easy.gc
        self.assertEqual(easy.gc("GGCC"), 100.0)
        self.assertEqual(easy.gc("AATT"), 0.0)
        self.assertEqual(easy.gc("ATGC"), 50.0)

        # easy.transcribe and easy.reverse_transcribe
        self.assertEqual(easy.transcribe("ATGC"), "AUGC")
        self.assertEqual(easy.reverse_transcribe("AUGC"), "ATGC")

        # easy.find_orfs
        orf_seq = "ATG" + ("GCA" * 35) + "TAA"
        orfs = easy.find_orfs(orf_seq, min_aa=30)
        self.assertEqual(len(orfs), 1)
        self.assertEqual(orfs[0].length_aa, 36)
        self.assertEqual(orfs[0].protein_sequence, "M" + ("A" * 35))


if __name__ == "__main__":
    unittest.main()
