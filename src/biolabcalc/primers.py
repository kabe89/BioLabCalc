"""Primer design, thermodynamic Tm calculation (SantaLucia 1998), GC clamp, and dimer analysis."""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from .seq_utils import clean_sequence, reverse_complement, calculate_gc_content

# Nearest-neighbor thermodynamic parameters (SantaLucia 1998, PNAS 95:1460-1465)
# dH in kcal/mol, dS in cal/(K*mol)
NN_PARAMS: Dict[str, Tuple[float, float]] = {
    "AA": (-7.6, -21.3), "TT": (-7.6, -21.3),
    "AT": (-7.2, -20.4),
    "TA": (-7.2, -21.3),
    "CA": (-8.5, -22.7), "TG": (-8.5, -22.7),
    "GT": (-8.4, -22.4), "AC": (-8.4, -22.4),
    "CT": (-7.8, -21.0), "AG": (-7.8, -21.0),
    "GA": (-8.2, -22.2), "TC": (-8.2, -22.2),
    "CG": (-10.6, -27.2),
    "GC": (-9.8, -24.4),
    "GG": (-8.0, -19.9), "CC": (-8.0, -19.9),
}

INIT_TERMINAL_AT: Tuple[float, float] = (2.3, 4.1)
INIT_TERMINAL_GC: Tuple[float, float] = (0.1, -2.8)
SYMMETRY_PENALTY: Tuple[float, float] = (0.0, -1.4)
R_GAS_CAL: float = 1.9872  # cal / (mol * K)


@dataclass(frozen=True)
class PrimerAnalysis:
    sequence: str
    length: int
    tm_celsius: float
    gc_percent: float
    gc_clamp_count: int
    has_gc_clamp: bool
    delta_h_kcal: float
    delta_s_cal: float
    delta_g_37_kcal: float
    homopolymer_warning: bool
    dimer_score: int
    hairpin_score: int
    quality_score: float
    self_dimer_dg_kcal: float = 0.0
    hairpin_dg_kcal: float = 0.0
    three_prime_dg_kcal: float = 0.0
    alignment_ascii: str = ""

    def _repr_html_(self) -> str:
        """Render clean HTML summary for Jupyter notebooks."""
        import html
        align_html = f"<pre style='background: #F8FAFC; padding: 6px; border-radius: 4px; font-size: 11px; margin-top: 6px; overflow-x: auto;'>{html.escape(self.alignment_ascii)}</pre>" if self.alignment_ascii else ""
        clamp_str = " (GC Clamp)" if self.has_gc_clamp else ""
        return (
            f'<div style="font-family: system-ui, -apple-system, sans-serif; border: 1px solid #E2E8F0; '
            f'border-radius: 8px; padding: 14px; max-width: 580px; background: #FFFFFF; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">'
            f'<h3 style="margin: 0; font-size: 15px; color: #0F172A;">Primer Analysis</h3>'
            f'<span style="background: #EFF6FF; color: #2563EB; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px;">Score: {self.quality_score:.1f}/100</span>'
            f'</div>'
            f'<div style="font-family: monospace; font-size: 12px; background: #F8FAFC; padding: 6px 10px; border-radius: 4px; color: #334155; margin-bottom: 10px;">{html.escape(self.sequence)}</div>'
            f'<table style="width: 100%; border-collapse: collapse; font-size: 12.5px;">'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Length / GC%</td><td style="text-align: right; font-weight: 600;">{self.length} nt • {self.gc_percent:.1f}% GC{clamp_str}</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Melting Temp (Tm)</td><td style="text-align: right; font-weight: 600; color: #DC2626;">{self.tm_celsius:.1f} °C</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Self-Dimer ΔG</td><td style="text-align: right;">{self.self_dimer_dg_kcal:.2f} kcal/mol</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Hairpin ΔG</td><td style="text-align: right;">{self.hairpin_dg_kcal:.2f} kcal/mol</td></tr>'
            f'<tr><td style="padding: 3px 0; color: #64748B;">3\'-Terminal ΔG</td><td style="text-align: right;">{self.three_prime_dg_kcal:.2f} kcal/mol</td></tr>'
            f'</table>'
            f'{align_html}'
            f'</div>'
        )


@dataclass(frozen=True)
class PrimerPair:
    forward_primer: PrimerAnalysis
    reverse_primer: PrimerAnalysis
    amplicon_length_bp: int
    tm_difference: float
    product_start: int
    product_end: int
    pair_quality_score: float
    heterodimer_score: int = 0
    three_prime_heterodimer_score: int = 0
    heterodimer_warning: bool = False
    heterodimer_dg_kcal: float = 0.0
    three_prime_dg_kcal: float = 0.0
    alignment_ascii: str = ""

    def _repr_html_(self) -> str:
        """Render clean HTML summary for Jupyter notebooks."""
        import html
        return (
            f'<div style="font-family: system-ui, -apple-system, sans-serif; border: 1px solid #E2E8F0; '
            f'border-radius: 8px; padding: 14px; max-width: 620px; background: #FFFFFF; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">'
            f'<h3 style="margin: 0; font-size: 15px; color: #0F172A;">PCR Primer Pair</h3>'
            f'<span style="background: #F0FDF4; color: #16A34A; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px;">Pair Score: {self.pair_quality_score:.1f}/100</span>'
            f'</div>'
            f'<table style="width: 100%; border-collapse: collapse; font-size: 12.5px; margin-bottom: 8px;">'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 4px 0; color: #64748B;">Amplicon Size</td><td style="text-align: right; font-weight: 600;">{self.amplicon_length_bp:,} bp ({self.product_start} .. {self.product_end})</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 4px 0; color: #64748B;">Forward Primer</td><td style="text-align: right; font-family: monospace; font-size: 11.5px;">{html.escape(self.forward_primer.sequence)} ({self.forward_primer.tm_celsius:.1f}°C)</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 4px 0; color: #64748B;">Reverse Primer</td><td style="text-align: right; font-family: monospace; font-size: 11.5px;">{html.escape(self.reverse_primer.sequence)} ({self.reverse_primer.tm_celsius:.1f}°C)</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 4px 0; color: #64748B;">ΔTm</td><td style="text-align: right;">{self.tm_difference:.1f} °C</td></tr>'
            f'<tr><td style="padding: 4px 0; color: #64748B;">Cross-Dimer ΔG</td><td style="text-align: right;">{self.heterodimer_dg_kcal:.2f} kcal/mol</td></tr>'
            f'</table>'
            f'</div>'
        )


def check_self_dimer(seq: str) -> int:
    """Score potential self-dimerization by assessing contiguous self-complementarity across all sliding alignments with its reverse complement."""
    clean = clean_sequence(seq).replace("U", "T")
    len_s = len(clean)
    if len_s < 2:
        return 0
    rc = reverse_complement(clean, seq_type="dna")

    max_matches = 0
    three_p_matches = 0

    # Slide across all possible alignments between primer and its reverse complement
    for shift in range(-len_s + 1, len_s):
        consec = 0
        for i in range(len_s):
            j = i - shift
            if 0 <= j < len_s:
                if clean[i] == rc[j]:
                    consec += 1
                    if consec > max_matches:
                        max_matches = consec
                    if i == len_s - 1 or j == 0:
                        if consec > three_p_matches:
                            three_p_matches = consec
                else:
                    consec = 0

    # Assess 3' terminal tail self-complementarity specifically
    tail_len = min(6, len_s)
    tail = clean[-tail_len:]
    rc_tail = reverse_complement(tail, seq_type="dna")
    for k in range(2, tail_len + 1):
        sub = tail[-k:]
        if sub in rc_tail:
            three_p_matches = max(three_p_matches, k)

    return max(max_matches, three_p_matches)


def check_hairpin(seq: str) -> int:
    """Estimate hairpin loop potential by finding inverted repeats."""
    clean = clean_sequence(seq)
    rc = reverse_complement(clean)
    max_stem = 0
    for stem_len in range(3, min(8, len(clean) // 2)):
        for i in range(len(clean) - stem_len):
            sub = clean[i:i + stem_len]
            # search for sub in rc after a loop of at least 3 nt
            min_pos = i + stem_len + 3
            if min_pos < len(clean):
                target_region = clean[min_pos:]
                if reverse_complement(sub) in target_region:
                    max_stem = max(max_stem, stem_len)
    return max_stem


def calculate_dimer_dg(
    seq1: str,
    seq2: str,
    temp_celsius: float = 37.0,
    na_conc_mm: float = 50.0,
    mg_conc_mm: float = 1.5,
) -> Tuple[float, str, float]:
    """
    Calculate thermodynamic dimer free energy (dG in kcal/mol) using SantaLucia (1998)
    nearest-neighbor parameters across all sliding antiparallel alignments.
    
    Returns:
        (min_dg_kcal, ascii_alignment, three_prime_dg_kcal)
    """
    s1 = clean_sequence(seq1).replace("U", "T")
    s2 = clean_sequence(seq2).replace("U", "T")
    l1, l2 = len(s1), len(s2)
    if l1 < 2 or l2 < 2:
        return 0.0, "No dimer", 0.0

    comp_map = {"A": "T", "T": "A", "C": "G", "G": "C"}
    t_kelvin = temp_celsius + 273.15
    free_mg = max(0.0, mg_conc_mm / 1000.0)
    monovalent = max(0.001, (na_conc_mm / 1000.0) + 3.795 * math.sqrt(free_mg))

    best_dg = 0.0
    best_align = ""
    three_prime_dg = 0.0

    s2_rev = s2[::-1]  # 3' to 5'

    for offset in range(-l2 + 1, l1):
        matches: List[int] = []
        for i in range(l1):
            j = i - offset
            if 0 <= j < l2:
                if comp_map.get(s1[i]) == s2_rev[j]:
                    matches.append(i)

        if not matches:
            continue

        blocks: List[List[int]] = []
        curr_b: List[int] = [matches[0]]
        for m in matches[1:]:
            if m == curr_b[-1] + 1:
                curr_b.append(m)
            else:
                if len(curr_b) >= 2:
                    blocks.append(curr_b)
                curr_b = [m]
        if len(curr_b) >= 2:
            blocks.append(curr_b)

        for b in blocks:
            k = len(b)
            dh = 0.0
            ds = 0.0
            for idx in range(k - 1):
                dinuc = s1[b[idx] : b[idx] + 2]
                if dinuc in NN_PARAMS:
                    h, s = NN_PARAMS[dinuc]
                    dh += h
                    ds += s
                else:
                    dh += -8.0
                    ds += -22.0

            for term in (s1[b[0]], s1[b[-1]]):
                if term in ("A", "T"):
                    dh += INIT_TERMINAL_AT[0]
                    ds += INIT_TERMINAL_AT[1]
                else:
                    dh += INIT_TERMINAL_GC[0]
                    ds += INIT_TERMINAL_GC[1]

            ds_corr = ds + 0.368 * (k - 1) * math.log(monovalent)
            dg = dh - (t_kelvin * ds_corr / 1000.0) + 0.2

            involves_3p = (l1 - 1 in b) or any((i - offset) == l2 - 1 for i in b)

            if dg < best_dg:
                best_dg = dg
                top_str = "5' " + s1 + " 3'"
                pipe_chars = [" "] * len(s1)
                for i_pos in b:
                    pipe_chars[i_pos] = "|"
                mid_str = "   " + "".join(pipe_chars)
                pad_s1 = max(0, offset)
                bot_str = "3' " + (" " * pad_s1) + s2_rev + " 5'"
                best_align = f"{top_str}\n{mid_str}\n{bot_str}"

            if involves_3p and (dg < three_prime_dg or three_prime_dg == 0.0):
                three_prime_dg = dg

    return round(best_dg, 2), best_align, round(three_prime_dg, 2)


def calculate_hairpin_dg(seq: str, temp_celsius: float = 37.0) -> Tuple[float, str]:
    """
    Calculate thermodynamic hairpin free energy (dG in kcal/mol) using SantaLucia (1998)
    nearest-neighbor parameters across all internal stem-loop configurations.
    
    Returns:
        (min_dg_kcal, dot_bracket_structure)
    """
    s = clean_sequence(seq).replace("U", "T")
    L = len(s)
    if L < 7:
        return 0.0, "." * L

    comp_map = {"A": "T", "T": "A", "C": "G", "G": "C"}
    t_kelvin = temp_celsius + 273.15
    best_dg = 0.0
    best_struct = "." * L

    loop_init = {3: 3.5, 4: 3.5, 5: 4.0, 6: 4.3}

    for stem_len in range(2, L // 2 + 1):
        for i in range(L - 2 * stem_len - 2):
            for j in range(i + stem_len + 3 + stem_len - 1, L):
                valid = True
                for k in range(stem_len):
                    if comp_map.get(s[i + k]) != s[j - k]:
                        valid = False
                        break
                if not valid:
                    continue

                loop_size = (j - stem_len + 1) - (i + stem_len)
                if loop_size < 3:
                    continue

                dh = 0.0
                ds = 0.0
                for k in range(stem_len - 1):
                    dinuc = s[i + k : i + k + 2]
                    if dinuc in NN_PARAMS:
                        h, sc = NN_PARAMS[dinuc]
                        dh += h
                        ds += sc
                    else:
                        dh += -8.0
                        ds += -22.0

                l_pen = loop_init.get(loop_size, 4.5 + 1.05 * math.log(max(loop_size / 6.0, 1.0)))
                dg = dh - (t_kelvin * ds / 1000.0) + l_pen

                if dg < best_dg:
                    best_dg = dg
                    chars = ["."] * L
                    for k in range(stem_len):
                        chars[i + k] = "("
                        chars[j - k] = ")"
                    best_struct = "".join(chars)

    return round(best_dg, 2), best_struct


def calculate_tm_santalucia(
    seq: str,
    primer_conc_nm: float = 400.0,
    na_conc_mm: float = 50.0,
    mg_conc_mm: float = 1.5,
    dntp_conc_mm: float = 0.8,
    is_excess_primer: bool = True,
) -> Tuple[float, float, float, float]:
    """Calculate melting temperature (Tm) using SantaLucia (1998, PNAS 95:1460-1465) unified nearest-neighbor parameters.

    Parameters
    ----------
    seq : str
        Oligonucleotide primer sequence (5' -> 3').
    primer_conc_nm : float
        Primer concentration in nM (default 400.0 nM).
    na_conc_mm : float
        Monovalent sodium/potassium ion concentration in mM (default 50.0 mM).
    mg_conc_mm : float
        Divalent magnesium ion concentration in mM (default 1.5 mM).
    dntp_conc_mm : float
        Total dNTP concentration in mM (default 0.8 mM).
    is_excess_primer : bool
        True if primer is in vast excess over template (standard PCR, x=1.0),
        False for equimolar hybridization (x=4.0).

    Returns
    -------
    Tuple[float, float, float, float]
        (tm_celsius, dH_kcal, dS_cal, dG_37_kcal)
    """
    if primer_conc_nm <= 0:
        raise ValueError(f"Primer concentration must be strictly positive (got {primer_conc_nm} nM).")
    clean = clean_sequence(seq).replace("U", "T")
    n = len(clean)
    if n < 2:
        return 0.0, 0.0, 0.0, 0.0

    dh_total = 0.0
    ds_total = 0.0

    # Nearest neighbor sum
    for i in range(n - 1):
        dinuc = clean[i:i + 2]
        if dinuc in NN_PARAMS:
            h, s = NN_PARAMS[dinuc]
            dh_total += h
            ds_total += s

    # Terminal initiation
    for term in (clean[0], clean[-1]):
        if term in ("A", "T"):
            dh_total += INIT_TERMINAL_AT[0]
            ds_total += INIT_TERMINAL_AT[1]
        else:
            dh_total += INIT_TERMINAL_GC[0]
            ds_total += INIT_TERMINAL_GC[1]

    # Symmetry check
    rc = reverse_complement(clean)
    is_symmetric = (clean == rc)
    if is_symmetric:
        ds_total += SYMMETRY_PENALTY[1]

    # Salt correction (SantaLucia 1998 / Owczarzy 2008 approx)
    # Monovalent equivalent: [Na+] + 3.795 * sqrt([Mg2+] - [dNTP])
    free_mg = max(0.0, (mg_conc_mm - dntp_conc_mm) / 1000.0)
    monovalent = (na_conc_mm / 1000.0) + 3.795 * math.sqrt(free_mg) if free_mg > 0 else (na_conc_mm / 1000.0)
    monovalent = max(0.001, monovalent)

    ds_salt_corrected = ds_total + 0.368 * (n - 1) * math.log(monovalent)

    # Primer molar concentration
    c_t = primer_conc_nm * 1e-9
    # In PCR with vast primer excess, x=1.0. For equimolar complementary strands, x=4.0.
    if is_symmetric or is_excess_primer:
        x = 1.0
    else:
        x = 4.0

    # Tm in Kelvin: dH / (dS + R * ln(Ct / x))
    tm_kelvin = (dh_total * 1000.0) / (ds_salt_corrected + R_GAS_CAL * math.log(c_t / x))
    tm_celsius = tm_kelvin - 273.15

    # dG at 37 C (310.15 K) in kcal/mol
    dg_37 = dh_total - (310.15 * ds_salt_corrected / 1000.0)

    return round(tm_celsius, 2), round(dh_total, 2), round(ds_salt_corrected, 2), round(dg_37, 2)


def calculate_tm_santaluicia(
    seq: str,
    primer_conc_nm: float = 400.0,
    na_conc_mm: float = 50.0,
    mg_conc_mm: float = 1.5,
    dntp_conc_mm: float = 0.8,
    is_excess_primer: bool = True,
) -> Tuple[float, float, float, float]:
    """Calculate melting temperature (Tm) using SantaLucia (1998) parameters.

    Deprecated alias for calculate_tm_santalucia (retained for backward compatibility).
    """
    return calculate_tm_santalucia(
        seq=seq,
        primer_conc_nm=primer_conc_nm,
        na_conc_mm=na_conc_mm,
        mg_conc_mm=mg_conc_mm,
        dntp_conc_mm=dntp_conc_mm,
        is_excess_primer=is_excess_primer,
    )


def analyze_primer(
    seq: str,
    primer_conc_nm: float = 400.0,
    na_conc_mm: float = 50.0,
    mg_conc_mm: float = 1.5,
    dntp_conc_mm: float = 0.8,
    is_excess_primer: bool = True,
) -> PrimerAnalysis:
    """Perform comprehensive thermodynamic and quality analysis on a candidate primer."""
    clean = clean_sequence(seq)
    length = len(clean)
    tm, dh, ds, dg = calculate_tm_santalucia(
        clean,
        primer_conc_nm=primer_conc_nm,
        na_conc_mm=na_conc_mm,
        mg_conc_mm=mg_conc_mm,
        dntp_conc_mm=dntp_conc_mm,
        is_excess_primer=is_excess_primer,
    )
    gc = calculate_gc_content(clean)

    # 3' GC clamp: count of G or C in last 5 bases
    tail = clean[-5:] if length >= 5 else clean
    gc_clamp_count = tail.count("G") + tail.count("C")
    has_gc_clamp = 1 <= gc_clamp_count <= 3

    # Homopolymers (run of 4 or more identical bases)
    has_homopolymer = any(base * 4 in clean for base in "ACGT")

    dimer = check_self_dimer(clean)
    hairpin = check_hairpin(clean)
    self_dg, self_align, tp_self_dg = calculate_dimer_dg(clean, clean, na_conc_mm=na_conc_mm, mg_conc_mm=mg_conc_mm)
    hp_dg, hp_struct = calculate_hairpin_dg(clean)

    # Quality score: 100 max, penalized for bad GC, homopolymer, extreme Tm, dimers
    score = 100.0
    if gc < 40.0:
        score -= (40.0 - gc) * 1.5
    elif gc > 60.0:
        score -= (gc - 60.0) * 1.5

    if not has_gc_clamp:
        score -= 10.0
    if has_homopolymer:
        score -= 15.0
    score -= dimer * 5.0
    score -= hairpin * 8.0

    return PrimerAnalysis(
        sequence=clean,
        length=length,
        tm_celsius=tm,
        gc_percent=gc,
        gc_clamp_count=gc_clamp_count,
        has_gc_clamp=has_gc_clamp,
        delta_h_kcal=dh,
        delta_s_cal=ds,
        delta_g_37_kcal=dg,
        homopolymer_warning=has_homopolymer,
        dimer_score=dimer,
        hairpin_score=hairpin,
        quality_score=round(max(0.0, score), 1),
        self_dimer_dg_kcal=self_dg,
        hairpin_dg_kcal=hp_dg,
        three_prime_dg_kcal=tp_self_dg,
        alignment_ascii=self_align,
    )


def check_heterodimer(fwd_seq: str, rev_seq: str) -> Tuple[int, int, str]:
    """Score potential heterodimerization (cross-dimer) between forward and reverse primers.

    Returns
    -------
    Tuple of (max_consecutive_matches, three_prime_cross_matches, description)
    """
    fwd = clean_sequence(fwd_seq).replace("U", "T")
    rev = clean_sequence(rev_seq).replace("U", "T")
    rc_rev = reverse_complement(rev, seq_type="dna")

    len_f = len(fwd)
    len_r = len(rev)

    max_matches = 0
    for shift in range(-len_r + 4, len_f - 3):
        consec = 0
        max_consec = 0
        for i in range(len_f):
            j = i - shift
            if 0 <= j < len_r:
                if fwd[i] == rc_rev[j]:
                    consec += 1
                    max_consec = max(max_consec, consec)
                else:
                    consec = 0
        max_matches = max(max_matches, max_consec)

    three_p_matches = 0
    tail_f = fwd[-6:]
    rc_rev_tail = reverse_complement(rev[-6:], seq_type="dna")
    for k in range(3, min(7, len(tail_f) + 1)):
        sub = tail_f[-k:]
        if sub in rc_rev_tail:
            three_p_matches = max(three_p_matches, k)

    desc = "Low heterodimer risk"
    if three_p_matches >= 4 or max_matches >= 6:
        desc = "Severe heterodimer risk (strong 3' or internal cross-annealing)"
    elif three_p_matches >= 3 or max_matches >= 5:
        desc = "Moderate heterodimer risk"

    return max_matches, three_p_matches, desc


def design_primers(
    template_seq: str,
    target_tm: float = 60.0,
    min_tm: float = 57.0,
    max_tm: float = 64.0,
    min_length: int = 18,
    max_length: int = 25,
    min_amplicon_bp: int = 100,
    max_amplicon_bp: int = 1000,
    max_pairs: int = 5,
    primer_conc_nm: float = 400.0,
) -> List[PrimerPair]:
    """Scan a target sequence and design optimal forward and reverse primer pairs."""
    clean_template = clean_sequence(template_seq).replace("U", "T")
    n = len(clean_template)
    if n < min_amplicon_bp:
        raise ValueError(f"Template sequence ({n} bp) is shorter than minimum amplicon size ({min_amplicon_bp} bp).")

    # Generate candidate forward primers from beginning region
    fwd_candidates: List[Tuple[int, PrimerAnalysis]] = []
    # Search first 200 bp or half of template
    fwd_search_bound = min(250, n - min_amplicon_bp)
    for start in range(0, fwd_search_bound, 2):
        for plen in range(min_length, max_length + 1):
            if start + plen <= n:
                cand_seq = clean_template[start:start + plen]
                p_analysis = analyze_primer(cand_seq, primer_conc_nm=primer_conc_nm)
                if min_tm <= p_analysis.tm_celsius <= max_tm and 35.0 <= p_analysis.gc_percent <= 65.0:
                    fwd_candidates.append((start, p_analysis))

    # Generate candidate reverse primers from downstream region
    rev_candidates: List[Tuple[int, PrimerAnalysis]] = []
    rev_search_start = min_amplicon_bp
    for end in range(rev_search_start, n, 2):
        for plen in range(min_length, max_length + 1):
            start = end - plen
            if start >= 0:
                # Sense strand region: reverse primer is reverse complement!
                sense_region = clean_template[start:end]
                rev_seq = reverse_complement(sense_region)
                p_analysis = analyze_primer(rev_seq, primer_conc_nm=primer_conc_nm)
                if min_tm <= p_analysis.tm_celsius <= max_tm and 35.0 <= p_analysis.gc_percent <= 65.0:
                    rev_candidates.append((end, p_analysis))

    # Pair matching
    pairs: List[PrimerPair] = []
    for f_start, f_prim in fwd_candidates:
        f_end = f_start + f_prim.length
        for r_end, r_prim in rev_candidates:
            amp_len = r_end - f_start
            if min_amplicon_bp <= amp_len <= max_amplicon_bp:
                delta_tm = abs(f_prim.tm_celsius - r_prim.tm_celsius)
                if delta_tm <= 3.0:
                    # Score pair and check heterodimerization
                    max_het, tp_het, het_desc = check_heterodimer(f_prim.sequence, r_prim.sequence)
                    het_warn = tp_het >= 3 or max_het >= 5
                    het_penalty = (tp_het * 5.0) + (max_het * 2.0)

                    tm_penalty = abs(f_prim.tm_celsius - target_tm) + abs(r_prim.tm_celsius - target_tm)
                    pair_score = (f_prim.quality_score + r_prim.quality_score) / 2.0 - (delta_tm * 5.0) - (tm_penalty * 2.0) - het_penalty
                    het_dg, het_align, het_tp_dg = calculate_dimer_dg(f_prim.sequence, r_prim.sequence)
                    pairs.append(PrimerPair(
                        forward_primer=f_prim,
                        reverse_primer=r_prim,
                        amplicon_length_bp=amp_len,
                        tm_difference=round(delta_tm, 2),
                        product_start=f_start + 1,
                        product_end=r_end,
                        pair_quality_score=round(max(0.0, pair_score), 1),
                        heterodimer_score=max_het,
                        three_prime_heterodimer_score=tp_het,
                        heterodimer_warning=het_warn,
                        heterodimer_dg_kcal=het_dg,
                        three_prime_dg_kcal=het_tp_dg,
                        alignment_ascii=het_align,
                    ))

    # Sort by quality score descending
    pairs.sort(key=lambda p: p.pair_quality_score, reverse=True)
    return pairs[:max_pairs]


__all__ = [
    "calculate_tm_santalucia",
    "calculate_tm_santaluicia",
    "calculate_dimer_dg",
    "calculate_hairpin_dg",
    "analyze_primer",
    "design_primers",
    "check_self_dimer",
    "check_hairpin",
    "check_heterodimer",
    "PrimerAnalysis",
    "PrimerPair",
    "NN_PARAMS",
]
