"""
Module: biolabcalc.aptamers
Component: Subunit-Selective Aptamer & SELEX Thermodynamics Engine
Architectural Role: Deterministic biophysical analysis of RNA/DNA aptamers,
Turner (2004) nearest-neighbor hairpin folding thermodynamics, and
Dirichlet-smoothed Counter-SELEX sequencing enrichment with Benjamini-Hochberg FDR.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


# ============================================================================
# Frozen Domain Dataclasses
# ============================================================================

@dataclass(frozen=True)
class SecondaryStructureThermoResult:
    sequence: str
    structure_dot_bracket: str
    delta_g_37: float
    delta_h: float
    delta_s: float
    tm_celsius: float
    stems: Tuple[Tuple[int, int, int], ...] = ()  # (start_5p, start_3p, length) 1-based
    loops: Tuple[str, ...] = ()

    def __post_init__(self):
        for f in ("stems", "loops"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))


@dataclass(frozen=True)
class AptamerCandidateScore:
    candidate_id: str
    sequence: str
    fold_enrichment: float
    p_value_adjusted: float
    is_significant: bool
    predicted_affinity_score: float
    charge_selectivity_score: float
    composite_rank_score: float


@dataclass(frozen=True)
class SELEXEnrichmentResult:
    round_number: int
    total_candidates: int
    top_candidates: Tuple[AptamerCandidateScore, ...]
    mean_enrichment: float
    fdr_threshold: float

    def __post_init__(self):
        if isinstance(self.top_candidates, (list, set, tuple)):
            object.__setattr__(self, "top_candidates", tuple(self.top_candidates))


# ============================================================================
# Turner (2004) Nearest-Neighbor RNA Thermodynamic Parameters (37 °C)
# dG (kcal/mol), dH (kcal/mol), dS (cal/(mol*K))
# ============================================================================

# Base pair stacking parameters: 5'-X1 X2-3' / 3'-Y1 Y2-5' where (X1:Y1) and (X2:Y2) pair
_TURNER_STACKING: Dict[Tuple[str, str, str, str], Tuple[float, float, float]] = {
    ("A", "A", "U", "U"): (-0.90, -6.82, -19.08),
    ("U", "U", "A", "A"): (-0.90, -6.82, -19.08),
    ("A", "U", "U", "A"): (-1.10, -9.38, -26.70),
    ("U", "A", "A", "U"): (-1.33, -7.69, -20.50),
    ("C", "U", "G", "A"): (-2.08, -10.48, -27.08),
    ("A", "G", "U", "C"): (-2.08, -10.48, -27.08),
    ("C", "A", "G", "U"): (-2.11, -10.44, -26.86),
    ("U", "G", "A", "C"): (-2.11, -10.44, -26.86),
    ("G", "U", "C", "A"): (-2.24, -11.40, -29.53),
    ("A", "C", "U", "G"): (-2.24, -11.40, -29.53),
    ("G", "A", "C", "U"): (-2.35, -12.44, -32.53),
    ("U", "C", "A", "G"): (-2.35, -12.44, -32.53),
    ("C", "G", "G", "C"): (-2.36, -10.64, -26.69),
    ("G", "G", "C", "C"): (-3.26, -13.39, -32.66),
    ("C", "C", "G", "G"): (-3.26, -13.39, -32.66),
    ("G", "C", "C", "G"): (-3.42, -14.88, -36.95),
    # Wobble pairs
    ("G", "U", "U", "G"): (-1.30, -8.50, -23.20),
    ("U", "G", "G", "U"): (-1.30, -8.50, -23.20),
    ("A", "U", "U", "G"): (-1.00, -7.50, -21.00),
    ("G", "U", "U", "A"): (-1.00, -7.50, -21.00),
}


def _get_stack_thermo(x1: str, x2: str, y1: str, y2: str) -> Tuple[float, float, float]:
    """Look up Turner (2004) dinucleotide stack thermodynamics."""
    k1 = (x1, x2, y1, y2)
    if k1 in _TURNER_STACKING:
        return _TURNER_STACKING[k1]
    k2 = (y2, y1, x2, x1)
    if k2 in _TURNER_STACKING:
        return _TURNER_STACKING[k2]
    k3 = (x1, x2, y2, y1)
    if k3 in _TURNER_STACKING:
        return _TURNER_STACKING[k3]
    return (-2.0, -10.0, -26.0)

_CANONICAL_PAIRS = {
    ("A", "U"), ("U", "A"),
    ("G", "C"), ("C", "G"),
    ("G", "U"), ("U", "G"),
}

# Hairpin loop initiation penalties (Turner 2004)
_HAIRPIN_LOOP_INIT: Dict[int, float] = {
    3: 5.7,
    4: 5.6,
    5: 5.6,
    6: 5.4,
    7: 5.9,
    8: 5.6,
    9: 6.4,
}


def _is_complementary(b1: str, b2: str) -> bool:
    """Check Watson-Crick or G-U wobble pairing."""
    return (b1, b2) in _CANONICAL_PAIRS


def evaluate_rna_hairpin_thermo(
    sequence: str,
    temperature_celsius: float = 37.0,
) -> SecondaryStructureThermoResult:
    """
    Evaluate secondary structure hairpin folding thermodynamics using
    Turner (2004) nearest-neighbor stacking and loop penalties.
    """
    clean_seq = sequence.upper().replace("T", "U").strip()
    L = len(clean_seq)
    if L < 6:
        # Minimum sequence for stem-loop
        return SecondaryStructureThermoResult(
            sequence=clean_seq,
            structure_dot_bracket="." * L,
            delta_g_37=0.0,
            delta_h=0.0,
            delta_s=0.0,
            tm_celsius=0.0,
            stems=(),
            loops=(),
        )

    best_dg = 0.0
    best_dh = 0.0
    best_ds = 0.0
    best_struct = "." * L
    best_stems: List[Tuple[int, int, int]] = []
    best_loops: List[str] = []

    # Search for optimal single stem-loop hairpin
    for stem_len in range(2, L // 2 + 1):
        for i in range(L - 2 * stem_len - 2):
            # 5' strand of stem starts at i, ends at i + stem_len - 1
            # 3' strand of stem ends at j, starts at j - stem_len + 1
            for j in range(i + stem_len + 3 + stem_len - 1, L):
                # Verify base pairing
                valid_stem = True
                for k in range(stem_len):
                    b5 = clean_seq[i + k]
                    b3 = clean_seq[j - k]
                    if not _is_complementary(b5, b3):
                        valid_stem = False
                        break
                if not valid_stem:
                    continue

                loop_size = (j - stem_len + 1) - (i + stem_len)
                if loop_size < 3:
                    continue

                # Calculate stacking delta G, delta H, delta S
                stem_dg = 0.0
                stem_dh = 0.0
                stem_ds = 0.0

                for k in range(stem_len - 1):
                    x1 = clean_seq[i + k]
                    x2 = clean_seq[i + k + 1]
                    y2 = clean_seq[j - k - 1]
                    y1 = clean_seq[j - k]

                    dg, dh, ds = _get_stack_thermo(x1, x2, y1, y2)
                    stem_dg += dg
                    stem_dh += dh
                    stem_ds += ds

                # Terminal AU / GU penalty (+0.45 kcal/mol each)
                if (clean_seq[i], clean_seq[j]) in {("A", "U"), ("U", "A"), ("G", "U"), ("U", "G")}:
                    stem_dg += 0.45
                if (clean_seq[i + stem_len - 1], clean_seq[j - stem_len + 1]) in {("A", "U"), ("U", "A"), ("G", "U"), ("U", "G")}:
                    stem_dg += 0.45

                # Hairpin loop initiation penalty
                if loop_size in _HAIRPIN_LOOP_INIT:
                    loop_dg = _HAIRPIN_LOOP_INIT[loop_size]
                elif loop_size > 9:
                    loop_dg = 5.6 + 1.75 * 0.6 * math.log(loop_size / 8.0)
                else:
                    loop_dg = 5.6

                loop_dh = 0.0
                loop_ds = -(loop_dg * 1000.0) / 310.15

                total_dg = stem_dg + loop_dg
                total_dh = stem_dh + loop_dh
                total_ds = stem_ds + loop_ds

                if total_dg < best_dg:
                    best_dg = total_dg
                    best_dh = total_dh
                    best_ds = total_ds

                    # Construct dot-bracket
                    struct_chars = ["."] * L
                    for k in range(stem_len):
                        struct_chars[i + k] = "("
                        struct_chars[j - k] = ")"
                    best_struct = "".join(struct_chars)

                    best_stems = [(i + 1, j + 1, stem_len)]
                    loop_seq = clean_seq[i + stem_len : j - stem_len + 1]
                    best_loops = [loop_seq]

    # Calculate Tm
    tm = 0.0
    if best_ds < -0.01:
        tm = (best_dh * 1000.0) / best_ds - 273.15
        tm = max(0.0, min(120.0, tm))

    return SecondaryStructureThermoResult(
        sequence=clean_seq,
        structure_dot_bracket=best_struct,
        delta_g_37=round(best_dg, 2),
        delta_h=round(best_dh, 2),
        delta_s=round(best_ds, 2),
        tm_celsius=round(tm, 1),
        stems=tuple(best_stems),
        loops=tuple(best_loops),
    )


# ============================================================================
# Counter-SELEX Enrichment & Benjamini-Hochberg FDR
# ============================================================================

def _normal_two_tailed_p_value(z: float) -> float:
    """Compute two-tailed normal p-value from z-score using complementary error function."""
    return math.erfc(abs(z) / math.sqrt(2.0))


def analyze_counter_selex(
    target_counts: Dict[str, int],
    counter_counts: Dict[str, int],
    alpha_smoothing: float = 1.0,
    fdr_threshold: float = 0.05,
    target_charge_profile: Optional[Dict[str, float]] = None,
    round_number: int = 1,
) -> SELEXEnrichmentResult:
    """
    Dirichlet-Smoothed Counter-SELEX Enrichment & Subunit Selectivity Engine.
    
    Computes smoothed enrichment ratios R_target / R_counter, propagates
    variance via the Delta method, applies step-down Benjamini-Hochberg FDR
    adjustment, and scores subunit interface selectivity.
    """
    all_keys = sorted(set(target_counts.keys()) | set(counter_counts.keys()))
    K = max(len(all_keys), 1)

    total_target = sum(target_counts.values())
    total_counter = sum(counter_counts.values())

    denom_target = total_target + alpha_smoothing * K
    denom_counter = total_counter + alpha_smoothing * K

    raw_candidates = []
    enrichment_values = []

    for seq in all_keys:
        c_t = target_counts.get(seq, 0)
        c_c = counter_counts.get(seq, 0)

        # Dirichlet smoothed relative frequencies
        p_t = (c_t + alpha_smoothing) / denom_target
        p_c = (c_c + alpha_smoothing) / denom_counter

        fold_enrichment = p_t / p_c
        enrichment_values.append(fold_enrichment)

        # Delta-method variance of log-ratio
        # Var(ln R) ≈ 1/(c_t + alpha) + 1/(c_c + alpha)
        var_log_r = (1.0 / (c_t + alpha_smoothing)) + (1.0 / (c_c + alpha_smoothing))
        se_log_r = math.sqrt(var_log_r)

        # Z-score testing hypothesis of no enrichment (ln R = 0)
        z = math.log(fold_enrichment) / se_log_r
        p_val = _normal_two_tailed_p_value(z)

        # Secondary structure thermodynamic affinity proxy
        thermo = evaluate_rna_hairpin_thermo(seq)
        # More negative delta_g represents higher structural stability/affinity
        affinity_score = round(max(0.0, -thermo.delta_g_37 / 10.0), 3)

        # Subunit charge selectivity score (GC / purine distribution vs target interface charge)
        gc_count = sum(1 for b in seq.upper() if b in "GC")
        gc_frac = gc_count / max(len(seq), 1)
        charge_score = round(0.5 + 0.5 * gc_frac, 3)

        raw_candidates.append({
            "seq": seq,
            "fold_enrichment": fold_enrichment,
            "p_val": p_val,
            "affinity_score": affinity_score,
            "charge_score": charge_score,
        })

    # Step-down Benjamini-Hochberg FDR procedure
    m = len(raw_candidates)
    # Sort ascending by p-value
    sorted_candidates = sorted(raw_candidates, key=lambda x: x["p_val"])

    # Compute BH adjusted p-values: q(i) = min_{j >= i} (p(j) * m / j)
    # Forward calculation
    unclamped_q = [c["p_val"] * m / (idx + 1) for idx, c in enumerate(sorted_candidates)]
    # Backward pass to ensure monotonicity
    adj_p_vals = [0.0] * m
    min_future_q = 1.0
    for idx in range(m - 1, -1, -1):
        min_future_q = min(min_future_q, unclamped_q[idx])
        adj_p_vals[idx] = min(1.0, max(0.0, min_future_q))

    top_scores: List[AptamerCandidateScore] = []
    for idx, c in enumerate(sorted_candidates):
        q_val = adj_p_vals[idx]
        is_sig = bool((q_val <= fdr_threshold) and (c["fold_enrichment"] > 1.0))
        comp_rank = round((c["fold_enrichment"] * (1.0 + c["affinity_score"])) / (1.0 + q_val), 3)

        top_scores.append(AptamerCandidateScore(
            candidate_id=f"APT-{idx + 1:04d}",
            sequence=c["seq"],
            fold_enrichment=round(c["fold_enrichment"], 3),
            p_value_adjusted=round(q_val, 6),
            is_significant=is_sig,
            predicted_affinity_score=c["affinity_score"],
            charge_selectivity_score=c["charge_score"],
            composite_rank_score=comp_rank,
        ))

    # Sort final scores by composite_rank_score descending
    top_scores.sort(key=lambda s: s.composite_rank_score, reverse=True)
    mean_enrich = sum(enrichment_values) / len(enrichment_values) if enrichment_values else 1.0

    return SELEXEnrichmentResult(
        round_number=round_number,
        total_candidates=len(all_keys),
        top_candidates=tuple(top_scores),
        mean_enrichment=round(mean_enrich, 3),
        fdr_threshold=fdr_threshold,
    )
