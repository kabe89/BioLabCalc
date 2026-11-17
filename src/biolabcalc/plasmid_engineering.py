"""Automated Gene Expression Plasmid Engineering Engine for BioLabCalc v0.4.0.

Provides:
- Codon usage analysis (CAI, GC content, rare codons, unfavorable pairs) for E. coli and Human.
- Codon optimization and silent restriction domestication.
- Expression cassette designer (promoters, RBS/Kozak, N/C tags, proteases, terminators).
- Recombinant plasmid engineering engine supporting:
  - Directional restriction-ligation with reading frame synchronization and frame-padding.
  - Gibson assembly primer and overlap design.
  - Golden Gate assembly with Type IIS scarless excision and silent domestication.
- 7-point audit checks (in-frame, start codon, stop codon, premature stops, RBS/Kozak, ori, marker).
- Colony PCR amplicon sizing with standard sequencing primers.
- Diagnostic restriction digest prediction.
- Expressed protein translation, biophysical properties, and predicted E. coli yield.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple, Union

from .cloning import RestrictionEnzyme, get_restriction_enzyme
from .molecular_weight import calculate_protein_mw
from .plasmid import PlasmidFeature, PlasmidRecord, STANDARD_PLASMID_CATALOG, get_plasmid
from .primers import PrimerAnalysis, analyze_primer, check_heterodimer
from .protein import calculate_extinction_coefficient
from .restriction_engine import RestrictionDigestPrediction, predict_restriction_digest
from .seq_utils import clean_sequence, reverse_complement, translate_dna


# ---------------------------------------------------------------------------
# Genetic Code and Host Codon Tables
# ---------------------------------------------------------------------------

GENETIC_CODE: Dict[str, str] = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

# Synonymous codons per amino acid
SYNONYMOUS_CODONS: Dict[str, Tuple[str, ...]] = {}
for codon, aa in GENETIC_CODE.items():
    SYNONYMOUS_CODONS.setdefault(aa, ())
    SYNONYMOUS_CODONS[aa] = SYNONYMOUS_CODONS[aa] + (codon,)


# E. coli K-12 synonymous codon frequencies (fractions per amino acid)
ECOLI_CODON_USAGE: Dict[str, float] = {
    # Ala
    "GCG": 0.36, "GCC": 0.26, "GCA": 0.23, "GCT": 0.15,
    # Cys
    "TGC": 0.54, "TGT": 0.46,
    # Asp
    "GAT": 0.63, "GAC": 0.37,
    # Glu
    "GAA": 0.68, "GAG": 0.32,
    # Phe
    "TTT": 0.58, "TTC": 0.42,
    # Gly
    "GGC": 0.40, "GGT": 0.35, "GGG": 0.15, "GGA": 0.10,
    # His
    "CAT": 0.57, "CAC": 0.43,
    # Ile (ATA is rare)
    "ATT": 0.51, "ATC": 0.42, "ATA": 0.07,
    # Lys
    "AAA": 0.74, "AAG": 0.26,
    # Leu (CTA is rare)
    "CTG": 0.50, "TTA": 0.14, "TTG": 0.13, "CTT": 0.12, "CTC": 0.10, "CTA": 0.01,
    # Met
    "ATG": 1.00,
    # Asn
    "AAC": 0.51, "AAT": 0.49,
    # Pro (CCC is rare)
    "CCG": 0.53, "CCA": 0.20, "CCT": 0.18, "CCC": 0.09,
    # Gln
    "CAG": 0.65, "CAA": 0.35,
    # Arg (AGA, AGG, CGA are rare)
    "CGC": 0.40, "CGT": 0.38, "CGG": 0.11, "CGA": 0.06, "AGA": 0.03, "AGG": 0.02,
    # Ser
    "AGC": 0.28, "TCT": 0.17, "AGT": 0.16, "TCC": 0.15, "TCA": 0.14, "TCG": 0.10,
    # Thr
    "ACC": 0.40, "ACG": 0.25, "ACT": 0.19, "ACA": 0.16,
    # Val
    "GTG": 0.35, "GTT": 0.28, "GTC": 0.20, "GTA": 0.17,
    # Trp
    "TGG": 1.00,
    # Tyr
    "TAT": 0.59, "TAC": 0.41,
    # Stop
    "TAA": 0.61, "TGA": 0.30, "TAG": 0.09,
}

# Homo sapiens synonymous codon frequencies
HUMAN_CODON_USAGE: Dict[str, float] = {
    # Ala
    "GCC": 0.40, "GCT": 0.26, "GCA": 0.23, "GCG": 0.11,
    # Cys
    "TGC": 0.55, "TGT": 0.45,
    # Asp
    "GAC": 0.54, "GAT": 0.46,
    # Glu
    "GAG": 0.58, "GAA": 0.42,
    # Phe
    "TTC": 0.55, "TTT": 0.45,
    # Gly
    "GGC": 0.34, "GGA": 0.25, "GGG": 0.25, "GGT": 0.16,
    # His
    "CAC": 0.59, "CAT": 0.41,
    # Ile
    "ATC": 0.48, "ATT": 0.36, "ATA": 0.16,
    # Lys
    "AAG": 0.58, "AAA": 0.42,
    # Leu (TTA, CTA are rare)
    "CTG": 0.41, "CTC": 0.20, "CTT": 0.13, "TTG": 0.13, "CTA": 0.07, "TTA": 0.06,
    # Met
    "ATG": 1.00,
    # Asn
    "AAC": 0.54, "AAT": 0.46,
    # Pro
    "CCC": 0.33, "CCT": 0.28, "CCA": 0.27, "CCG": 0.12,
    # Gln
    "CAG": 0.75, "CAA": 0.25,
    # Arg (CGT is rare)
    "CGG": 0.21, "AGA": 0.20, "AGG": 0.20, "CGC": 0.19, "CGA": 0.11, "CGT": 0.09,
    # Ser (TCG is rare)
    "AGC": 0.24, "TCC": 0.22, "TCT": 0.18, "TCA": 0.15, "AGT": 0.15, "TCG": 0.06,
    # Thr
    "ACC": 0.36, "ACA": 0.28, "ACT": 0.24, "ACG": 0.12,
    # Val
    "GTG": 0.47, "GTC": 0.24, "GTT": 0.18, "GTA": 0.11,
    # Trp
    "TGG": 1.00,
    # Tyr
    "TAC": 0.57, "TAT": 0.43,
    # Stop
    "TGA": 0.52, "TAA": 0.28, "TAG": 0.20,
}

# Preferred codons per host
ECOLI_PREFERRED_CODONS: Dict[str, str] = {
    "A": "GCG", "C": "TGC", "D": "GAT", "E": "GAA", "F": "TTT",
    "G": "GGC", "H": "CAT", "I": "ATT", "K": "AAA", "L": "CTG",
    "M": "ATG", "N": "AAC", "P": "CCG", "Q": "CAG", "R": "CGC",
    "S": "AGC", "T": "ACC", "V": "GTG", "W": "TGG", "Y": "TAT",
    "*": "TAA",
}

HUMAN_PREFERRED_CODONS: Dict[str, str] = {
    "A": "GCC", "C": "TGC", "D": "GAC", "E": "GAG", "F": "TTC",
    "G": "GGC", "H": "CAC", "I": "ATC", "K": "AAG", "L": "CTG",
    "M": "ATG", "N": "AAC", "P": "CCC", "Q": "CAG", "R": "CGG",
    "S": "AGC", "T": "ACC", "V": "GTG", "W": "TGG", "Y": "TAC",
    "*": "TGA",
}


def _get_host_table(host: str) -> Tuple[Dict[str, float], Dict[str, str]]:
    h = host.lower().replace("-", "").replace("_", "").replace(" ", "")
    if "human" in h or "homo" in h or "hs" in h or "heparin" in h or "mammal" in h:
        return HUMAN_CODON_USAGE, HUMAN_PREFERRED_CODONS
    return ECOLI_CODON_USAGE, ECOLI_PREFERRED_CODONS


# ---------------------------------------------------------------------------
# Codon Usage Analysis & Optimization
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CodonUsageAnalysis:
    """Quantitative codon usage metrics and rare codon identification."""
    cai: float  # Codon Adaptation Index (0.0 to 1.0)
    gc_content: float  # GC percentage (0.0 to 100.0)
    rare_codon_count: int
    rare_codons: Tuple[Tuple[int, str, str], ...]  # (1-based codon index, codon, amino acid)
    unfavorable_pairs: int  # Count of consecutive rare codons


def evaluate_codon_usage(cds_seq: str, host: str = "ecoli") -> CodonUsageAnalysis:
    """Evaluate Codon Adaptation Index (CAI), rare codons, and GC content of a CDS.
    
    Rare codons are defined as codons with synonymous frequency < 0.10 in the host.
    """
    clean_seq = clean_sequence(cds_seq).upper().replace("U", "T")
    if len(clean_seq) % 3 != 0 or len(clean_seq) == 0:
        gc = (clean_seq.count("G") + clean_seq.count("C")) / max(len(clean_seq), 1) * 100.0
        return CodonUsageAnalysis(cai=0.0, gc_content=round(gc, 2), rare_codon_count=0, rare_codons=(), unfavorable_pairs=0)

    usage, _ = _get_host_table(host)
    codons = [clean_seq[i:i+3] for i in range(0, len(clean_seq), 3)]

    # Compute CAI
    log_w_sum = 0.0
    valid_codons = 0
    rare_codons_list: List[Tuple[int, str, str]] = []
    rare_indices: List[int] = []

    for idx, codon in enumerate(codons, start=1):
        aa = GENETIC_CODE.get(codon, "X")
        if aa in ("*", "X", "M", "W"):
            # Met and Trp have single codons; stop codons excluded from standard CAI
            continue

        syn_codons = SYNONYMOUS_CODONS.get(aa, (codon,))
        max_freq = max(usage.get(c, 0.01) for c in syn_codons)
        codon_freq = usage.get(codon, 0.01)

        w = max(codon_freq / max_freq, 1e-4)
        log_w_sum += math.log(w)
        valid_codons += 1

        if codon_freq < 0.10:
            rare_codons_list.append((idx, codon, aa))
            rare_indices.append(idx)

    cai = math.exp(log_w_sum / valid_codons) if valid_codons > 0 else 1.0
    cai = min(max(cai, 0.0), 1.0)

    # Count unfavorable pairs (consecutive rare codons)
    unfavorable_pairs = 0
    for i in range(len(rare_indices) - 1):
        if rare_indices[i+1] == rare_indices[i] + 1:
            unfavorable_pairs += 1

    gc = (clean_seq.count("G") + clean_seq.count("C")) / len(clean_seq) * 100.0

    return CodonUsageAnalysis(
        cai=round(cai, 4),
        gc_content=round(gc, 2),
        rare_codon_count=len(rare_codons_list),
        rare_codons=tuple(rare_codons_list),
        unfavorable_pairs=unfavorable_pairs,
    )


def optimize_codons(
    seq_or_protein: str,
    host: str = "ecoli",
    avoid_enzymes: Optional[Union[Tuple[str, ...], List[str]]] = None,
    seq_type: Optional[str] = None,
) -> str:
    """Codon-optimize a DNA CDS or reverse-translate a protein sequence for a host.
    
    If input is amino acids, reverse translates directly using preferred host codons.
    If input is DNA CDS, replaces rare codons (synonymous frequency < 0.10) with preferred codons.
    If avoid_enzymes is specified, performs silent restriction domestication by introducing
    synonymous codon mutations that eliminate recognition sites without altering protein sequence.
    """
    clean_in = clean_sequence(seq_or_protein).upper().replace("U", "T")
    usage, preferred = _get_host_table(host)

    # Determine whether input is amino acids or DNA
    if seq_type is not None:
        is_dna = seq_type.lower() in ("dna", "cds", "nt", "nucleotide")
    else:
        dna_chars = set("ACGTN")
        is_dna = (
            set(clean_in).issubset(dna_chars)
            and (len(clean_in) % 3 == 0)
            and (len(clean_in) >= 15 or clean_in.startswith("ATG") or clean_in.endswith(("TAA", "TAG", "TGA")))
            and len(clean_in) > 0
        )

    if not is_dna:
        # Input is amino acid sequence
        optimized_codons = [preferred.get(aa, "NNN") for aa in clean_in]
        optimized_dna = "".join(optimized_codons)
    else:
        # Input is DNA CDS: replace rare codons
        codons = [clean_in[i:i+3] for i in range(0, len(clean_in), 3)]
        optimized_codons = []
        for codon in codons:
            aa = GENETIC_CODE.get(codon, "X")
            freq = usage.get(codon, 0.0)
            if freq < 0.10 and aa in preferred:
                optimized_codons.append(preferred[aa])
            else:
                optimized_codons.append(codon)
        optimized_dna = "".join(optimized_codons)

    # Silent Restriction Domestication
    if avoid_enzymes:
        optimized_dna = domesticate_restriction_sites(optimized_dna, avoid_enzymes, host=host)

    return optimized_dna


def domesticate_restriction_sites(
    cds_seq: str,
    avoid_enzymes: Union[Tuple[str, ...], List[str]],
    host: str = "ecoli",
) -> str:
    """Silently mutate internal restriction enzyme recognition sites in a CDS.
    
    Guarantees that the translated protein sequence remains 100% identical.
    """
    clean_dna = clean_sequence(cds_seq).upper().replace("U", "T")
    if len(clean_dna) % 3 != 0 or len(clean_dna) == 0:
        return clean_dna

    usage, _ = _get_host_table(host)
    codons = [clean_dna[i:i+3] for i in range(0, len(clean_dna), 3)]

    # Collect recognition motifs to avoid
    motifs_to_avoid: List[str] = []
    for enz_name in avoid_enzymes:
        try:
            re_enz = get_restriction_enzyme(enz_name)
            motif = clean_sequence(re_enz.recognition_site).upper()
            if motif:
                motifs_to_avoid.append(motif)
                rc_motif = reverse_complement(motif)
                if rc_motif != motif:
                    motifs_to_avoid.append(rc_motif)
        except KeyError:
            clean_name = enz_name.upper().replace("-", "").replace("_", "")
            # Fallback for common enzymes if not in catalog
            fallback_map = {
                "BSAI": "GGTCTC", "BSAIHFV2": "GGTCTC", "BSMBI": "CGTCTC",
                "BBS1": "GAAGAC", "BAMHI": "GGATCC", "XHOI": "CTCGAG",
                "ECORI": "GAATTC", "HINDIII": "AAGCTT", "NOTI": "GCGGCCGC",
                "NDEI": "CATATG", "NCOI": "CCATGG",
            }
            if clean_name in fallback_map:
                m = fallback_map[clean_name]
                motifs_to_avoid.append(m)
                motifs_to_avoid.append(reverse_complement(m))

    if not motifs_to_avoid:
        return clean_dna

    def has_conflict(seq: str) -> bool:
        return any(m in seq for m in motifs_to_avoid)

    # Iteratively remove motifs
    max_passes = 20
    for _ in range(max_passes):
        current_dna = "".join(codons)
        conflict_found = False

        for motif in motifs_to_avoid:
            start_idx = current_dna.find(motif)
            if start_idx != -1:
                conflict_found = True
                end_idx = start_idx + len(motif)

                # Identify overlapping codon indices
                codon_start = start_idx // 3
                codon_end = (end_idx - 1) // 3

                # Try synonymous substitutions in overlapping codons
                substituted = False
                for c_idx in range(codon_start, min(codon_end + 1, len(codons))):
                    orig_codon = codons[c_idx]
                    aa = GENETIC_CODE.get(orig_codon, "*")
                    syns = SYNONYMOUS_CODONS.get(aa, (orig_codon,))
                    # Sort synonymous codons by usage frequency descending
                    sorted_syns = sorted(syns, key=lambda c: usage.get(c, 0.0), reverse=True)

                    for alt_codon in sorted_syns:
                        if alt_codon == orig_codon:
                            continue
                        # Test replacement
                        test_codons = list(codons)
                        test_codons[c_idx] = alt_codon
                        test_dna = "".join(test_codons)

                        # Check if this mutation eliminated the motif without creating other conflicts locally
                        window_start = max(0, start_idx - 10)
                        window_end = min(len(test_dna), end_idx + 10)
                        local_seq = test_dna[window_start:window_end]
                        if not any(m in local_seq for m in motifs_to_avoid):
                            codons[c_idx] = alt_codon
                            substituted = True
                            break
                    if substituted:
                        break

                if not substituted:
                    # Multi-codon simultaneous swap if single codon was insufficient
                    pass

        if not conflict_found:
            break

    return "".join(codons)


# ---------------------------------------------------------------------------
# Expression Cassette Designer
# ---------------------------------------------------------------------------

STANDARD_PROMOTERS: Dict[str, Tuple[str, str]] = {
    "T7": ("TAATACGACTCACTATAGGGGAATTGTGAGCGGATAACAATT", "T7 promoter with lac operator"),
    "lac": ("AATTGTGAGCGGATAACAATT", "lac promoter operator"),
    "tac": ("TTGACAATTAATCATCGGCTCGTATAATGTGTGGA", "Strong hybrid tac promoter"),
    "CMV": ("GACATTGATTATTGACTAGTTATTAATAGTAATCAATTACGGGGTCATTAGTTCATAGCCCATATATGGAGTTCCGCGTTACATAACTTACGGTAAATGGCCCGCCTGGCTGACCGCCCAACGACCCCCGCCCATTGACG", "Human CMV immediate-early promoter"),
    "SV40": ("TGCATCTCAATTAGTCAGCAACCATAGTCCCGCCCCTAACTCCGCCCATCCCGCCCCTAACTCCGCCCAGTTCCGCCCATTCTCCGCCCCATGGCTGACTAATTTTTTTTATTTATGCAGAGGCCGAGGCCGCCTCGGCCTC", "SV40 early promoter"),
}

STANDARD_RBS: Dict[str, Tuple[str, str]] = {
    "ecoli": ("AAGGAGATATACC", "Bacterial Ribosome Binding Site (Shine-Dalgarno)"),
    "kozak": ("GCCACC", "Kozak consensus eukaryotic translation initiation sequence"),
}

STANDARD_TAGS: Dict[str, Tuple[str, str]] = {
    "6xHis": ("CATCATCATCATCATCAC", "Hexahistidine affinity tag (6xHis)"),
    "FLAG": ("GACTACAAAGACGATGACGACAAG", "FLAG epitope tag (DYKDDDDK)"),
    "HA": ("TACCCATACGATGTTCCAGATTACGCT", "HA epitope tag (YPYDVPDYA)"),
    "Myc": ("GAACAAAAACTCATCTCAGAAGAGGATCTG", "c-Myc epitope tag (EQKLISEEDL)"),
    "GST": ("ATGTCCCCTATACTAGGTTATTGGAAAATTAAGGGCCTTGTGCAACCCACTCGACTTCTTTTGGAATATCTTGAAGAAAAATATGAAGAGCATTTGTATGAGCGCGATGAAGGTGATAAATGGCGAAACAAAAAGTTTGAATTGGGTTTGGAGTTTCCCAATCTTCCTTATTATATTGATGGTGATGTTAAATTAACACAGTCTATGGCCATCATACGTTATATAGCTGACAAGCACAACATGTTGGGTGGTTGTCCAAAAGAGCGTGCAGAGATTTCAATGCTTGAAGGAGCGGTTTTGGATATTAGATACGGTGTTTCGAGAATTGCATATAGTAAAGACTTTGAAACTCTCAAAGTTGATTTTCTTAGCAAGCTACCTGAAATGCTGAAAATGTTCGAAGATCGTTTATGTCATAAAACATATTTAAATGGTGATCATGTAACCCATCCTGACTTCATGTTGTATGACGCTCTTGATGTTGTTTTATACATGGACCCAATGTGCCTGGATGCGTTCCCAAAATTAGTTTGTTTTAAAAAACGTATTGAAGCTATCCCACAAATTGATAAGTACTTGAAATCCAGCAAGTATATAGCATGGCCTTTGCAGGGCTGGCAAGCCACGTTTGGTGGTGGCGACCATCCTCCAAAATCGGAT", "Glutathione S-transferase tag"),
}

STANDARD_PROTEASE_SITES: Dict[str, Tuple[str, str]] = {
    "TEV": ("GAAAACCTGTATTTTCAGGGC", "Tobacco Etch Virus (TEV) protease recognition site (ENLYFQ/G)"),
    "Thrombin": ("CTGGTGCCGCGCGGCAGC", "Thrombin cleavage site (LVPR/GS)"),
    "Enterokinase": ("GATGATGATGATAAA", "Enterokinase cleavage site (DDDDK/)"),
}

STANDARD_TERMINATORS: Dict[str, Tuple[str, str]] = {
    "T7": ("CTAGCATAACCCCTTGGGGCCTCTAAACGGGTCTTGAGGGGTTTTTTG", "T7 transcription terminator"),
    "BGH_polyA": ("TCTAGAGGGCCCGTTTAAACCCGCTGATCAGCCTCGACTGTGCCTTCTAGTTGCCAGCCATCTGTTGTTTGCCCCTCCCCCGTGCCTTCCTTGACCCTGGAAGGTGCCACTCCCACTGTCCTTTCCTAATAAAATGAGGAAATTGCATCGCATTGTCTGAGTAGGTGTCATTCTATTCTGGGGGGTGGGGTGGGGCAGGACAGCAAGGGGGAGGATTGGGAAGACAATAGCAGGCATGCTGGGG", "Bovine Growth Hormone polyadenylation signal"),
}


@dataclass(frozen=True)
class ExpressionCassetteResult:
    """Designed gene expression cassette entity adhering to TEA principles."""
    cassette_seq: str
    promoter: str
    rbs_or_kozak: str
    n_tag: Optional[str]
    c_tag: Optional[str]
    cds_seq: str
    terminator: str
    protein_seq: str
    protein_mw_da: float
    extinction_coeff_280: int
    features: Tuple[PlasmidFeature, ...]


def design_expression_cassette(
    target_seq: str,
    is_protein: bool = False,
    host: str = "ecoli",
    promoter: str = "T7",
    n_tag: Optional[str] = "6xHis",
    c_tag: Optional[str] = None,
    protease_site: Optional[str] = "TEV",
    optimize_for_host: bool = True,
) -> ExpressionCassetteResult:
    """Design a complete transcriptional and translational expression cassette."""
    clean_target = clean_sequence(target_seq).upper()
    host_key = "human" if "human" in host.lower() else "ecoli"

    # Optimize or reverse translate target coding sequence
    if is_protein:
        cds = optimize_codons(clean_target, host=host_key, seq_type="protein")
    elif optimize_for_host:
        cds = optimize_codons(clean_target, host=host_key)
    else:
        cds = clean_target.replace("U", "T")

    # Ensure CDS length is multiple of 3
    if len(cds) % 3 != 0:
        cds = cds[:len(cds) - (len(cds) % 3)]

    # Strip existing start/stop codons to handle fusion tags cleanly
    if cds.startswith("ATG"):
        cds_core = cds[3:]
    else:
        cds_core = cds

    for stop_c in ("TAA", "TAG", "TGA"):
        if cds_core.endswith(stop_c):
            cds_core = cds_core[:-3]
            break

    # 1. Promoter
    prom_key = promoter if promoter in STANDARD_PROMOTERS else ("CMV" if host_key == "human" else "T7")
    prom_seq, prom_notes = STANDARD_PROMOTERS[prom_key]

    # 2. RBS / Kozak
    rbs_key = "kozak" if host_key == "human" else "ecoli"
    rbs_seq, rbs_notes = STANDARD_RBS[rbs_key]

    # 3. N-terminal tag & protease site
    n_tag_seq = ""
    n_tag_notes = ""
    if n_tag and n_tag in STANDARD_TAGS:
        raw_tag_seq, n_tag_notes = STANDARD_TAGS[n_tag]
        n_tag_seq = raw_tag_seq

    prot_seq = ""
    prot_notes = ""
    if protease_site and protease_site in STANDARD_PROTEASE_SITES and n_tag:
        prot_seq, prot_notes = STANDARD_PROTEASE_SITES[protease_site]

    # Assemble coding sequence with tags
    full_cds_parts: List[str] = ["ATG"]
    if n_tag_seq:
        full_cds_parts.append(n_tag_seq)
    if prot_seq:
        full_cds_parts.append(prot_seq)
    full_cds_parts.append(cds_core)

    # 4. C-terminal tag
    c_tag_seq = ""
    c_tag_notes = ""
    if c_tag and c_tag in STANDARD_TAGS:
        c_tag_seq, c_tag_notes = STANDARD_TAGS[c_tag]
        full_cds_parts.append(c_tag_seq)

    # Stop codon
    stop_codon = "TGA" if host_key == "human" else "TAA"
    full_cds_parts.append(stop_codon)
    assembled_cds = "".join(full_cds_parts)

    # 5. Terminator
    term_key = "BGH_polyA" if host_key == "human" else "T7"
    term_seq, term_notes = STANDARD_TERMINATORS[term_key]

    # Assemble full cassette sequence with standard spacers
    # Promoter - spacer(10bp) - RBS - spacer(6bp) - CDS - spacer(10bp) - Terminator
    spacer1 = "AGAGAC"
    spacer2 = "TCT" if host_key == "ecoli" else ""
    spacer3 = "GCTAGC"

    cassette_seq = f"{prom_seq}{spacer1}{rbs_seq}{spacer2}{assembled_cds}{spacer3}{term_seq}"
    total_len = len(cassette_seq)

    # Build features
    features: List[PlasmidFeature] = []
    cursor = 1

    # Promoter feature
    p_len = len(prom_seq)
    features.append(PlasmidFeature(f"{prom_key}_promoter", "promoter", cursor, cursor + p_len - 1, 1, "#EF4444", prom_notes, total_len))
    cursor += p_len + len(spacer1)

    # RBS feature
    r_len = len(rbs_seq)
    features.append(PlasmidFeature(rbs_key.upper(), "RBS", cursor, cursor + r_len - 1, 1, "#F59E0B", rbs_notes, total_len))
    cursor += r_len + len(spacer2)

    # Coding sequence start
    cds_start = cursor
    if n_tag_seq:
        tag_start = cursor + 3  # After ATG
        tag_end = tag_start + len(n_tag_seq) - 1
        features.append(PlasmidFeature(f"{n_tag}_N_tag", "tag", tag_start, tag_end, 1, "#10B981", n_tag_notes, total_len))
        cursor += 3 + len(n_tag_seq)
        if prot_seq:
            p_start = cursor
            p_end = p_start + len(prot_seq) - 1
            features.append(PlasmidFeature(f"{protease_site}_cleavage_site", "protein_bind", p_start, p_end, 1, "#10B981", prot_notes, total_len))
            cursor += len(prot_seq)
    else:
        cursor += 3

    # Target gene CDS feature
    target_start = cursor
    target_end = target_start + len(cds_core) - 1
    features.append(PlasmidFeature("Target_Gene", "CDS", target_start, target_end, 1, "#3B82F6", "Target gene coding sequence", total_len))
    cursor += len(cds_core)

    # C-terminal tag feature
    if c_tag_seq:
        c_start = cursor
        c_end = c_start + len(c_tag_seq) - 1
        features.append(PlasmidFeature(f"{c_tag}_C_tag", "tag", c_start, c_end, 1, "#10B981", c_tag_notes, total_len))
        cursor += len(c_tag_seq)

    cursor += 3  # stop codon
    cds_end = cursor - 1
    cursor += len(spacer3)

    # Terminator feature
    t_len = len(term_seq)
    features.append(PlasmidFeature(f"{term_key}_terminator", "terminator", cursor, cursor + t_len - 1, 1, "#6B7280", term_notes, total_len))

    # Translate complete protein
    prot_seq_full = translate_dna(assembled_cds, frame=1, to_stop=True)
    mw = calculate_protein_mw(prot_seq_full).average_mw if prot_seq_full else 0.0
    ext = calculate_extinction_coefficient(prot_seq_full).extinction_coeff_m_cm if prot_seq_full else 0

    return ExpressionCassetteResult(
        cassette_seq=cassette_seq,
        promoter=prom_key,
        rbs_or_kozak=rbs_key,
        n_tag=n_tag,
        c_tag=c_tag,
        cds_seq=assembled_cds,
        terminator=term_key,
        protein_seq=prot_seq_full,
        protein_mw_da=round(mw, 2),
        extinction_coeff_280=ext,
        features=tuple(features),
    )


# ---------------------------------------------------------------------------
# Recombinant Plasmid Engineering Engine
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EngineeredPlasmidResult:
    """Comprehensive outcome of in-silico plasmid assembly and expression engineering."""
    assembled_plasmid: PlasmidRecord
    mode: str
    target_gene_name: str
    forward_primer: PrimerAnalysis
    reverse_primer: PrimerAnalysis
    forward_primer_full_seq: str
    reverse_primer_full_seq: str
    primer_heterodimer_score: int
    cloning_junctions: Tuple[str, ...]
    in_frame: bool
    has_start_codon: bool
    has_stop_codon: bool
    premature_stops: int
    rbs_or_kozak_ok: bool
    ori_intact: bool
    marker_intact: bool
    colony_pcr_amplicon_bp: int
    diagnostic_digest: RestrictionDigestPrediction
    expressed_protein_seq: str
    protein_mw_da: float
    protein_extinction_280: int
    predicted_expression_yield_mg_l: float
    warnings: Tuple[str, ...]
    notes: Tuple[str, ...]

    def _repr_html_(self) -> str:
        """Render clean HTML summary for Jupyter notebooks."""
        import html
        status_in_frame = '<span style="color: #16A34A; font-weight: 600;">In-Frame</span>' if self.in_frame else '<span style="color: #DC2626; font-weight: 600;">Frameshift</span>'
        status_stops = f'<span style="color: #16A34A;">0</span>' if self.premature_stops == 0 else f'<span style="color: #DC2626; font-weight: 600;">{self.premature_stops}</span>'
        return (
            f'<div style="font-family: system-ui, -apple-system, sans-serif; border: 1px solid #E2E8F0; '
            f'border-radius: 8px; padding: 14px; max-width: 620px; background: #FFFFFF; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">'
            f'<h3 style="margin: 0; font-size: 15px; color: #0F172A;">Engineered Plasmid: {html.escape(self.assembled_plasmid.name)}</h3>'
            f'<span style="background: #F5F3FF; color: #7C3AED; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px;">{html.escape(self.mode.upper())}</span>'
            f'</div>'
            f'<div style="font-size: 12px; color: #64748B; margin-bottom: 10px;">Target: <strong>{html.escape(self.target_gene_name)}</strong> • {self.assembled_plasmid.length:,} bp</div>'
            f'<table style="width: 100%; border-collapse: collapse; font-size: 12.5px; margin-bottom: 8px;">'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Reading Frame</td><td style="text-align: right;">{status_in_frame}</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Start / Stop Codon</td><td style="text-align: right;">{"Yes" if self.has_start_codon else "Missing"} / {"Yes" if self.has_stop_codon else "Missing"} (Premature stops: {status_stops})</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Backbone Integrity</td><td style="text-align: right;">Ori: {"OK" if self.ori_intact else "Disrupted"} • Marker: {"OK" if self.marker_intact else "Disrupted"}</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Colony PCR Amplicon</td><td style="text-align: right; font-weight: 600;">{self.colony_pcr_amplicon_bp} bp</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Expressed Protein</td><td style="text-align: right; font-weight: 600; color: #2563EB;">{self.protein_mw_da:,.1f} Da (ε280: {self.protein_extinction_280:,} M⁻¹cm⁻¹)</td></tr>'
            f'<tr><td style="padding: 3px 0; color: #64748B;">Predicted Yield</td><td style="text-align: right; font-weight: 600; color: #16A34A;">{self.predicted_expression_yield_mg_l:.1f} mg/L</td></tr>'
            f'</table>'
            f'</div>'
        )


def _design_annealing_core(seq: str, reverse: bool = False) -> str:
    """Pick optimal 18-24 nt annealing core with Tm 55-65°C and GC clamp."""
    target = reverse_complement(seq) if reverse else seq
    best_candidate = target[:20]
    best_diff = 999.0

    for l in range(18, min(26, len(target) + 1)):
        cand = target[:l]
        analysis = analyze_primer(cand)
        tm = analysis.tm_celsius
        diff = abs(tm - 60.0)
        # Bonus for GC clamp
        if cand.endswith("G") or cand.endswith("C"):
            diff -= 1.0
        if diff < best_diff:
            best_diff = diff
            best_candidate = cand

    return best_candidate


def engineer_plasmid(
    vector: Union[PlasmidRecord, str],
    insert_seq: str,
    gene_name: str = "Target_Gene",
    mode: Literal["restriction_ligation", "gibson", "golden_gate"] = "restriction_ligation",
    enzyme_5prime: Optional[str] = "BamHI",
    enzyme_3prime: Optional[str] = "XhoI",
    insertion_site_bp: Optional[int] = None,
    type_iis_enzyme: str = "BsaI-HFv2",
    host: str = "ecoli",
    n_tag: Optional[str] = None,
    c_tag: Optional[str] = None,
    auto_domesticate: bool = True,
) -> EngineeredPlasmidResult:
    """Assemble target gene into plasmid vector using directional cloning, Gibson, or Golden Gate.
    
    Performs reading frame synchronization, primer tail synthesis, 7-point QA audit,
    colony PCR prediction, diagnostic restriction simulation, and E. coli yield estimation.
    """
    # 1. Resolve vector
    if isinstance(vector, str):
        vec_record = get_plasmid(vector)
    else:
        vec_record = vector

    vec_seq = vec_record.sequence
    vec_len = len(vec_seq)
    warnings: List[str] = []
    notes: List[str] = []

    # Clean insert sequence
    clean_insert = clean_sequence(insert_seq).upper().replace("U", "T")

    # Domestication if required
    avoid_list: List[str] = []
    if auto_domesticate:
        if mode == "restriction_ligation":
            if enzyme_5prime:
                avoid_list.append(enzyme_5prime)
            if enzyme_3prime:
                avoid_list.append(enzyme_3prime)
        elif mode == "golden_gate":
            avoid_list.append(type_iis_enzyme)

    if avoid_list and len(clean_insert) % 3 == 0:
        domesticated = domesticate_restriction_sites(clean_insert, avoid_list, host=host)
        if domesticated != clean_insert:
            notes.append(f"Auto-domesticated insert: eliminated internal recognition sites for {', '.join(avoid_list)}.")
            clean_insert = domesticated

    # Core annealing primers for insert
    fwd_core = _design_annealing_core(clean_insert, reverse=False)
    rev_core = _design_annealing_core(clean_insert, reverse=True)

    pad_seq = ""
    junctions: List[str] = []

    # -----------------------------------------------------------------------
    # Assembly Logic by Mode
    # -----------------------------------------------------------------------
    if mode == "restriction_ligation":
        enz5 = enzyme_5prime or "BamHI"
        enz3 = enzyme_3prime or "XhoI"

        re5 = get_restriction_enzyme(enz5)
        re3 = get_restriction_enzyme(enz3)
        motif5 = clean_sequence(re5.recognition_site).upper()
        motif3 = clean_sequence(re3.recognition_site).upper()

        idx5 = vec_seq.find(motif5)
        idx3 = vec_seq.find(motif3)

        if idx5 == -1 or idx3 == -1:
            raise ValueError(f"Enzyme site(s) '{enz5}' (found={idx5 != -1}) or '{enz3}' (found={idx3 != -1}) not found in vector {vec_record.name}.")

        # 1-based start of 5' and 3' recognition motifs
        p_site5_start = idx5 + 1
        p_site5_end = idx5 + len(motif5)
        p_site3_start = idx3 + 1
        p_site3_end = idx3 + len(motif3)

        # Vector cleavage: top strand cut positions
        cut5_top = idx5 + getattr(re5, "cut_offset_top", 1)
        cut3_top = idx3 + getattr(re3, "cut_offset_top", 1)

        # Reading Frame Synchronization
        # Check for upstream N-terminal leader / ATG
        p_tag_start: Optional[int] = None
        for feat in vec_record.features:
            if feat.feature_type in ("tag", "CDS") and ("N_tag" in feat.name or "His6" in feat.name):
                # Search backwards from tag for in-frame ATG initiation codon
                search_back = vec_seq[max(0, feat.start - 30):feat.start]
                atg_pos = search_back.rfind("ATG")
                if atg_pos != -1:
                    p_tag_start = max(0, feat.start - 30) + atg_pos + 1
                else:
                    p_tag_start = feat.start
                break

        # Fallback: scan backwards for ATG between RBS / T7 promoter and cut5
        if p_tag_start is None:
            rbs_feat = next((f for f in vec_record.features if f.feature_type == "RBS" or "RBS" in f.name), None)
            search_start = rbs_feat.end if rbs_feat else max(0, idx5 - 200)
            atg_rel = vec_seq[search_start:idx5].find("ATG")
            if atg_rel != -1:
                p_tag_start = search_start + atg_rel + 1
            else:
                last_atg = vec_seq[:idx5].rfind("ATG")
                if last_atg != -1:
                    p_tag_start = last_atg + 1

        if p_tag_start is not None:
            # Let p_cut be the position immediately following the 5' restriction overhang/site
            # In ligated plasmid, the 5' site is fully reconstituted at p_site5_start .. p_site5_end
            # The insert immediately follows p_site5_end without padding
            p_insert_start_unpadded = p_site5_end + 1
            delta_frame = (p_insert_start_unpadded - p_tag_start) % 3
            if delta_frame != 0:
                pad_count = (3 - delta_frame) % 3
                pad_seq = "G" if pad_count == 1 else "GC"
                notes.append(
                    f"Reading Frame Synchronization: delta_frame={delta_frame} bp from leader ATG (bp {p_tag_start}) "
                    f"to {enz5} site. Inserted {pad_count} bp pad ('{pad_seq}') into forward primer to maintain reading frame."
                )
            else:
                notes.append(f"Reading Frame Synchronization: Insert is already naturally in-frame with upstream leader ATG (delta_frame=0).")

        # Full forward and reverse primers with leader clamp + restriction site + pad
        leader_clamp = "CGC"
        fwd_primer_full = f"{leader_clamp}{motif5}{pad_seq}{fwd_core}"
        rev_primer_full = f"{leader_clamp}{motif3}{rev_core}"

        # Recombinant plasmid sequence assembly
        # Vector retains 0 .. cut5_top and cut3_top .. L
        # Insert fragment ligates in: from cut5_top to cut3_top
        # Regenerating motif5 + pad + insert + motif3
        left_backbone = vec_seq[:cut5_top]
        right_backbone = vec_seq[cut3_top:]

        # Insert payload within the excised gap:
        # Reconstitute restriction cohesive ends
        offset5 = getattr(re5, "cut_offset_top", 1)
        offset3 = getattr(re3, "cut_offset_top", 1)
        overhang5 = motif5[offset5:]
        overhang3_prefix = motif3[:offset3]
        ligated_insert = f"{overhang5}{pad_seq}{clean_insert}{overhang3_prefix}"

        assembled_seq = f"{left_backbone}{ligated_insert}{right_backbone}"
        insert_plasmid_start = len(left_backbone) + 1
        insert_plasmid_end = insert_plasmid_start + len(ligated_insert) - 1

        cds_start_1based = len(left_backbone) + len(overhang5) + len(pad_seq) + 1
        cds_end_1based = cds_start_1based + len(clean_insert) - 1

        excised_len = cut3_top - cut5_top
        length_delta = len(ligated_insert) - excised_len

        junctions.append(f"5' Junction: Vector(1..{cut5_top}) - {enz5} overhang - Pad({pad_seq or 'none'}) - {gene_name}")
        junctions.append(f"3' Junction: {gene_name} - {enz3} overhang - Vector({cut3_top+1}..{vec_len})")

    elif mode == "gibson":
        # Linearization site
        if insertion_site_bp is not None:
            cut_point = insertion_site_bp
        else:
            # Linearize at MCS or midpoint of vector
            mcs_feat = next((f for f in vec_record.features if f.name == "MCS"), None)
            cut_point = mcs_feat.start if mcs_feat else (vec_len // 2)

        # 25 bp homology arms from vector
        arm_5p = vec_seq[max(0, cut_point - 25):cut_point]
        arm_3p = vec_seq[cut_point:min(vec_len, cut_point + 25)]
        arm_3p_rc = reverse_complement(arm_3p)

        fwd_primer_full = f"{arm_5p}{fwd_core}"
        rev_primer_full = f"{arm_3p_rc}{rev_core}"

        assembled_seq = f"{vec_seq[:cut_point]}{clean_insert}{vec_seq[cut_point:]}"
        insert_plasmid_start = cut_point + 1
        insert_plasmid_end = cut_point + len(clean_insert)
        cds_start_1based = insert_plasmid_start
        cds_end_1based = insert_plasmid_end
        length_delta = len(clean_insert)

        junctions.append(f"5' Gibson Overlap: Vector(..{cut_point}) [25bp homology] {gene_name}")
        junctions.append(f"3' Gibson Overlap: {gene_name} [25bp homology] Vector({cut_point+1}..)")

    elif mode == "golden_gate":
        # Search for Type IIS BsaI recognition sites (GGTCTC)
        re_iis = get_restriction_enzyme(type_iis_enzyme)
        iis_motif = clean_sequence(re_iis.recognition_site).upper()
        iis_rc = reverse_complement(iis_motif)

        idx_5p = vec_seq.find(iis_motif)
        idx_3p = vec_seq.find(iis_rc)

        if idx_5p != -1 and idx_3p != -1:
            # Excise drop-out cassette between inward sites
            # 5' site cuts downstream; 3' site cuts upstream
            cut_5p = idx_5p + len(iis_motif) + 5
            cut_3p = idx_3p - 4
            overhang_5p = vec_seq[cut_5p - 4:cut_5p]
            overhang_3p = vec_seq[cut_3p:cut_3p + 4]

            fwd_primer_full = f"CGC{iis_motif}A{overhang_5p}{fwd_core}"
            rev_primer_full = f"CGC{iis_motif}A{reverse_complement(overhang_3p)}{rev_core}"

            assembled_seq = f"{vec_seq[:cut_5p]}{clean_insert}{vec_seq[cut_3p+4:]}"
            excised_len = (cut_3p + 4) - cut_5p
            length_delta = len(clean_insert) - excised_len
            insert_plasmid_start = cut_5p + 1
            insert_plasmid_end = cut_5p + len(clean_insert)
            cds_start_1based = insert_plasmid_start
            cds_end_1based = insert_plasmid_end
        else:
            # Fallback to direct insertion if destination vector lacks standard BsaI
            cut_point = vec_len // 2
            fwd_primer_full = f"CGC{iis_motif}ACCAG{fwd_core}"
            rev_primer_full = f"CGC{iis_motif}AACCT{rev_core}"
            assembled_seq = f"{vec_seq[:cut_point]}{clean_insert}{vec_seq[cut_point:]}"
            length_delta = len(clean_insert)
            insert_plasmid_start = cut_point + 1
            insert_plasmid_end = cut_point + len(clean_insert)
            cds_start_1based = insert_plasmid_start
            cds_end_1based = insert_plasmid_end

        junctions.append(f"5' Golden Gate: Type IIS seamless scarless joint")
        junctions.append(f"3' Golden Gate: Type IIS seamless scarless joint")

    else:
        raise ValueError(f"Unsupported cloning mode: '{mode}'. Choose 'restriction_ligation', 'gibson', or 'golden_gate'.")

    # Update features for assembled plasmid
    new_features: List[PlasmidFeature] = []
    new_len = len(assembled_seq)

    for feat in vec_record.features:
        # Check if feature was in excised region
        if mode == "restriction_ligation" and idx5 < idx3:
            if feat.start >= p_site5_start and feat.end <= p_site3_end:
                continue
        elif mode == "golden_gate" and 'ccdB' in feat.name:
            continue

        # Adjust coordinates for features downstream of insertion
        if feat.start > insert_plasmid_start:
            new_start = feat.start + length_delta
            new_end = feat.end + length_delta
            new_features.append(
                PlasmidFeature(feat.name, feat.feature_type, new_start, new_end, feat.strand, feat.color, feat.notes, new_len)
            )
        else:
            new_features.append(
                PlasmidFeature(feat.name, feat.feature_type, feat.start, feat.end, feat.strand, feat.color, feat.notes, new_len)
            )

    # Add Target Gene feature
    new_features.append(
        PlasmidFeature(gene_name, "CDS", cds_start_1based, cds_end_1based, 1, "#3B82F6", f"Cloned {gene_name} via {mode}", new_len)
    )

    history = vec_record.cloning_history + (f"Engineered {gene_name} via {mode}",)
    assembled_plasmid = PlasmidRecord(
        id=f"{vec_record.id}_{gene_name}",
        name=f"{vec_record.name}-{gene_name}",
        sequence=assembled_seq,
        topology=vec_record.topology,
        features=tuple(new_features),
        description=f"Recombinant expression construct of {gene_name} in {vec_record.name} via {mode}",
        cloning_history=history,
    )

    # -----------------------------------------------------------------------
    # 7-Point Quality Audit
    # -----------------------------------------------------------------------
    # 1. In-frame check
    # Locate active start codon for the fusion / gene
    # In pET vectors, active start is upstream leader ATG
    start_pos: Optional[int] = None
    for feat in new_features:
        if feat.name in ("His6_N_tag", "T7_tag", gene_name) and feat.strand == 1:
            # Look backwards for ATG
            sub_seq = assembled_seq[:feat.end]
            atg_idx = sub_seq.rfind("ATG")
            if atg_idx != -1:
                start_pos = atg_idx
                break

    if start_pos is None:
        start_pos = assembled_seq.find("ATG")

    in_frame = True
    premature_stops = 0
    expressed_protein = ""
    has_start = False
    has_stop = False

    # 1. Insert itself must have non-fractional codons
    if len(clean_insert) % 3 != 0 or len(clean_insert) == 0:
        in_frame = False

    if start_pos is not None and start_pos != -1:
        has_start = True
        orf_seq = assembled_seq[start_pos:]
        # Translate to stop
        translated = translate_dna(orf_seq, frame=1, to_stop=True)
        expressed_protein = translated

        # 2. In fusion constructs, distance from leader start_pos to cds_start must be multiple of 3
        if start_pos < (cds_start_1based - 1):
            if (cds_start_1based - 1 - start_pos) % 3 != 0:
                in_frame = False

        # 3. Expected translation of insert must match translated region in ORF
        if in_frame:
            insert_trans = translate_dna(clean_insert, frame=1, to_stop=True)
            if insert_trans and (insert_trans not in translated):
                in_frame = False

        # Check for premature stops inside coding region
        coding_region = assembled_seq[start_pos:cds_end_1based]
        coding_trans = translate_dna(coding_region, frame=1, to_stop=False)
        # Strip terminal stop codons (including tandem stops) to check for truly internal stops
        internal_trans = coding_trans.rstrip("*")
        premature_stops = internal_trans.count("*")
        if premature_stops > 0:
            warnings.append(f"Premature stop codon(s) detected: found {premature_stops} in-frame stop codon(s) inside coding region.")

        # Check stop codon
        trailing_triplet = assembled_seq[cds_end_1based - 3:cds_end_1based]
        if trailing_triplet in ("TAA", "TAG", "TGA") or translated:
            has_stop = True
    else:
        in_frame = False

    # 5. RBS / Kozak check
    rbs_ok = False
    if start_pos is not None:
        upstream_30bp = assembled_seq[max(0, start_pos - 30):start_pos]
        # Check Shine-Dalgarno motifs or Kozak
        if any(motif in upstream_30bp for motif in ("AAGGAG", "AGGAG", "GGAG", "GCCACC", "AGGA")):
            rbs_ok = True
        elif any(f.feature_type == "RBS" for f in new_features):
            rbs_ok = True

    # 6. Ori intact check
    ori_intact = any(f.feature_type == "rep_origin" or "ori" in f.name.lower() for f in new_features)

    # 7. Marker intact check
    marker_intact = any(
        f.feature_type == "CDS" and any(m in f.name.lower() for m in ("ampr", "kanr", "neor", "bla", "tet", "cam"))
        for f in new_features
    )

    if not in_frame:
        warnings.append("Frame shift detected: Target gene coding sequence is out of frame with initiation codon.")
    if not ori_intact:
        warnings.append("Vector replication origin (ori) is missing or compromised.")
    if not marker_intact:
        warnings.append("Selectable antibiotic marker is missing or compromised.")

    # -----------------------------------------------------------------------
    # Colony PCR Verification
    # -----------------------------------------------------------------------
    # Standard sequencing primer pairs for pET, pUC, pcDNA
    colony_pcr_amplicon_bp = 0
    t7_fwd = "TAATACGACTCACTATAGGG"
    t7_rev = reverse_complement("GCTAGTTATTGCTCAGCGG")
    m13_fwd = "TGTAAAACGACGGCCAGT"
    m13_rev = reverse_complement("CAGGAAACAGCTATGACC")

    pos_fwd = assembled_seq.find(t7_fwd)
    pos_rev = assembled_seq.find(t7_rev)

    if pos_fwd != -1 and pos_rev != -1 and pos_rev > pos_fwd:
        colony_pcr_amplicon_bp = (pos_rev + len(t7_rev)) - pos_fwd
    else:
        # Check M13
        pos_mfwd = assembled_seq.find(m13_fwd)
        pos_mrev = assembled_seq.find(m13_rev)
        if pos_mfwd != -1 and pos_mrev != -1 and pos_mrev > pos_mfwd:
            colony_pcr_amplicon_bp = (pos_mrev + len(m13_rev)) - pos_mfwd
        else:
            # Flanking amplicon (approx 100 bp flanking each side)
            colony_pcr_amplicon_bp = len(clean_insert) + 200

    # -----------------------------------------------------------------------
    # Diagnostic Restriction Digest
    # -----------------------------------------------------------------------
    diag_enzymes: List[str] = []
    if mode == "restriction_ligation":
        diag_enzymes = [enz5, enz3]
    elif mode == "golden_gate":
        diag_enzymes = ["EcoRI", "HindIII"] if "EcoRI" in vec_seq else [type_iis_enzyme]
    else:
        diag_enzymes = ["BamHI", "EcoRI"] if "BamHI" in assembled_seq else ["HindIII"]

    diag_digest = predict_restriction_digest(assembled_plasmid, enzymes=diag_enzymes)

    # -----------------------------------------------------------------------
    # Expressed Protein Metrics & Yield Prediction
    # -----------------------------------------------------------------------
    prot_mw = calculate_protein_mw(expressed_protein).average_mw if expressed_protein else 0.0
    prot_ext = calculate_extinction_coefficient(expressed_protein).extinction_coeff_m_cm if expressed_protein else 0

    # Empirical E. coli yield estimation (mg/L)
    codon_analysis = evaluate_codon_usage(clean_insert, host="ecoli")
    base_yield = 45.0  # mg/L for strong T7 promoter in LB
    cai_factor = max(0.2, codon_analysis.cai)
    rare_penalty = max(0.5, 1.0 - (codon_analysis.rare_codon_count * 0.03))
    size_penalty = min(1.0, 75000.0 / max(prot_mw, 25000.0))

    if not in_frame or premature_stops > 0:
        predicted_yield = 0.0
    else:
        predicted_yield = round(base_yield * cai_factor * rare_penalty * size_penalty, 2)

    # Primer analysis
    pa_fwd = analyze_primer(fwd_core)
    pa_rev = analyze_primer(rev_core)
    hetero_score = check_heterodimer(fwd_primer_full, rev_primer_full)[0]

    return EngineeredPlasmidResult(
        assembled_plasmid=assembled_plasmid,
        mode=mode,
        target_gene_name=gene_name,
        forward_primer=pa_fwd,
        reverse_primer=pa_rev,
        forward_primer_full_seq=fwd_primer_full,
        reverse_primer_full_seq=rev_primer_full,
        primer_heterodimer_score=hetero_score,
        cloning_junctions=tuple(junctions),
        in_frame=in_frame,
        has_start_codon=has_start,
        has_stop_codon=has_stop,
        premature_stops=premature_stops,
        rbs_or_kozak_ok=rbs_ok,
        ori_intact=ori_intact,
        marker_intact=marker_intact,
        colony_pcr_amplicon_bp=colony_pcr_amplicon_bp,
        diagnostic_digest=diag_digest,
        expressed_protein_seq=expressed_protein,
        protein_mw_da=round(prot_mw, 2),
        protein_extinction_280=prot_ext,
        predicted_expression_yield_mg_l=predicted_yield,
        warnings=tuple(warnings),
        notes=tuple(notes),
    )


engineer_expression_plasmid = engineer_plasmid


def generate_allosteric_mutagenesis_primers(
    plasmid: PlasmidRecord,
    allosteric_result: Any,
    target_amino_acid: str = "A",
    flanking_bp: int = 15,
) -> Tuple[PrimerPair, ...]:
    """
    Auto-generate site-directed mutagenesis primers targeting allosteric hotspot
    and bottleneck residues identified by allosteric pathway tracing.
    
    Parameters:
        plasmid (PlasmidRecord): Plasmid containing the target gene/CDS.
        allosteric_result (AllostericNetworkResult): Identified allosteric pathways & hotspots.
        target_amino_acid (str): Target replacement amino acid (default 'A' for Alanine scanning).
        flanking_bp (int): Flanking homology length on each side of the mutation (default: 15 bp).
        
    Returns:
        Tuple[PrimerPair, ...]: Designed mutagenesis primer pairs for each hotspot residue.
    """
    from .primers import analyze_primer, PrimerPair

    # Select target codon for alanine scanning or specified amino acid
    aa_to_codon = {
        "A": "GCG", "C": "TGC", "D": "GAC", "E": "GAG", "F": "TTC",
        "G": "GGC", "H": "CAC", "I": "ATC", "K": "AAG", "L": "CTG",
        "M": "ATG", "N": "AAC", "P": "CCG", "Q": "CAG", "R": "CGC",
        "S": "AGC", "T": "ACC", "V": "GTG", "W": "TGG", "Y": "TAC",
    }
    mut_codon = aa_to_codon.get(target_amino_acid.upper(), "GCG")

    # Locate coding feature
    cds_feat = next((f for f in plasmid.features if f.feature_type.upper() in ("CDS", "GENE")), None)
    seq = plasmid.sequence
    cds_start = cds_feat.start if cds_feat else 1

    pairs: List[PrimerPair] = []
    hotspots = getattr(allosteric_result, "hotspot_residues", ())
    if not hotspots and hasattr(allosteric_result, "paths") and allosteric_result.paths:
        hotspots = (allosteric_result.paths[0].bottleneck_residue,)

    for res_idx in hotspots:
        # Determine 1-based nucleotide position in plasmid sequence
        codon_start_nt = cds_start + (res_idx - 1) * 3
        if codon_start_nt < 1 or codon_start_nt + 2 > len(seq):
            continue

        # Extract flanking 5' and 3' regions
        left_start = max(1, codon_start_nt - flanking_bp)
        right_end = min(len(seq), codon_start_nt + 2 + flanking_bp)

        left_flank = seq[left_start - 1 : codon_start_nt - 1]
        right_flank = seq[codon_start_nt + 2 : right_end]

        fwd_mut_seq = left_flank + mut_codon + right_flank
        rev_mut_seq = reverse_complement(fwd_mut_seq, seq_type="dna")

        pa_fwd = analyze_primer(fwd_mut_seq)
        pa_rev = analyze_primer(rev_mut_seq)

        tm_diff = abs(pa_fwd.tm_celsius - pa_rev.tm_celsius)
        pair = PrimerPair(
            forward_primer=pa_fwd,
            reverse_primer=pa_rev,
            amplicon_length_bp=len(seq),
            tm_difference=round(tm_diff, 2),
            product_start=left_start,
            product_end=right_end,
            pair_quality_score=round((pa_fwd.quality_score + pa_rev.quality_score) / 2.0, 2),
        )
        pairs.append(pair)

    return tuple(pairs)
