"""In-silico restriction digestion predictions, restriction site mapping, and virtual gel simulation engine."""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from .cloning import ENZYME_DATABASE, RestrictionEnzyme, get_restriction_enzyme, plan_restriction_digest
from .gels import simulate_gel
from .molecular_weight import calculate_dna_mw
from .seq_utils import clean_sequence


# IUPAC Degenerate Motif-to-Regex Map
IUPAC_REGEX_MAP: Dict[str, str] = {
    "A": "A",
    "C": "C",
    "G": "G",
    "T": "T",
    "R": "[AG]",
    "Y": "[CT]",
    "S": "[GC]",
    "W": "[AT]",
    "K": "[GT]",
    "M": "[AC]",
    "B": "[CGT]",
    "D": "[AGT]",
    "H": "[ACT]",
    "V": "[ACG]",
    "N": "[ACGT]",
}

IUPAC_COMPLEMENT: Dict[str, str] = {
    "A": "T", "T": "A", "C": "G", "G": "C",
    "R": "Y", "Y": "R", "S": "S", "W": "W",
    "K": "M", "M": "K", "B": "V", "D": "H",
    "H": "D", "V": "B", "N": "N",
}


def reverse_complement_iupac(seq: str) -> str:
    """Compute reverse complement of a nucleotide sequence supporting IUPAC ambiguity codes."""
    return "".join(IUPAC_COMPLEMENT.get(c, c) for c in reversed(seq.upper()))


def compile_recognition_regex(motif: str) -> re.Pattern:
    """Compile an IUPAC degenerate nucleotide recognition sequence into a lookahead regular expression."""
    clean_motif = "".join(c for c in motif.upper() if c.isalpha())
    pattern = "".join(IUPAC_REGEX_MAP.get(c, c) for c in clean_motif)
    return re.compile(f"(?=({pattern}))")


@dataclass(frozen=True)
class PlasmidFeature:
    name: str
    start: int  # 1-based inclusive
    end: int  # 1-based inclusive
    feature_type: str = "misc_feature"
    strand: int = 1


@dataclass(frozen=True)
class PlasmidRecord:
    name: str
    sequence: str
    circular: bool = True
    topology: str = "circular"
    features: Tuple[PlasmidFeature, ...] = ()


@dataclass(frozen=True)
class RestrictionCutSite:
    enzyme: str
    cut_pos_top: int  # 1-based coordinate of top strand cut
    cut_pos_bottom: int  # 1-based coordinate of bottom strand cut
    recognition_start: int  # 1-based start of recognition sequence
    recognition_end: int  # 1-based end of recognition sequence
    strand: int = 1  # 1 for forward, -1 for reverse
    overhang_type: str = "5' overhang"  # "5' overhang", "3' overhang", "blunt"
    overhang_seq: str = ""  # sequence of the overhang on the protruding strand


@dataclass(frozen=True)
class DigestedFragment:
    fragment_id: int
    start_1based: int
    end_1based: int
    length_bp: int
    molecular_weight_da: float
    mass_ng: float = 0.0
    relative_intensity: float = 0.0
    left_enzyme: str = ""
    right_enzyme: str = ""
    left_overhang_type: str = "blunt"
    right_overhang_type: str = "blunt"
    left_overhang_seq: str = ""
    right_overhang_seq: str = ""
    wraps_origin: bool = False
    contained_features: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RestrictionDigestPrediction:
    plasmid_name: str
    total_length_bp: int
    topology: str
    enzymes: Tuple[str, ...]
    cut_sites: Tuple[RestrictionCutSite, ...]
    fragments: Tuple[DigestedFragment, ...]
    fragment_count: int
    uncut_conformations: Dict[str, int] = field(default_factory=dict)
    gel_bands: Tuple[Dict[str, Any], ...] = ()
    pipetting_plan: Optional[Any] = None


@dataclass(frozen=True)
class EnzymeScreenResult:
    plasmid_name: str
    non_cutters: Tuple[str, ...]
    single_cutters: Tuple[str, ...]
    double_cutters: Tuple[str, ...]
    multi_cutters: Tuple[Tuple[str, int], ...]
    mcs_unique_cutters: Tuple[str, ...]


def _extract_plasmid_data(
    seq_or_plasmid: Any,
    circular: Optional[bool] = None,
) -> Tuple[str, str, bool, Tuple[PlasmidFeature, ...]]:
    """Extract sequence, name, circularity, and features from input str or PlasmidRecord."""
    if isinstance(seq_or_plasmid, str):
        seq = clean_sequence(seq_or_plasmid).upper()
        name = "unnamed"
        is_circ = True if circular is None else bool(circular)
        features: Tuple[PlasmidFeature, ...] = ()
    else:
        seq = clean_sequence(getattr(seq_or_plasmid, "sequence", getattr(seq_or_plasmid, "seq", ""))).upper()
        name = getattr(seq_or_plasmid, "name", "plasmid")
        if circular is not None:
            is_circ = bool(circular)
        elif hasattr(seq_or_plasmid, "circular"):
            is_circ = bool(seq_or_plasmid.circular)
        elif hasattr(seq_or_plasmid, "topology"):
            is_circ = str(seq_or_plasmid.topology).lower() in ("circular", "circ")
        else:
            is_circ = True

        raw_feats = getattr(seq_or_plasmid, "features", ())
        parsed_feats: List[PlasmidFeature] = []
        for f in raw_feats:
            if isinstance(f, PlasmidFeature):
                parsed_feats.append(f)
            elif isinstance(f, dict):
                parsed_feats.append(PlasmidFeature(
                    name=f.get("name", "feature"),
                    start=f.get("start", 1),
                    end=f.get("end", 1),
                    feature_type=f.get("feature_type", f.get("type", "misc_feature")),
                    strand=f.get("strand", 1),
                ))
            else:
                f_name = getattr(f, "name", getattr(f, "label", "feature"))
                f_start = getattr(f, "start", 1)
                f_end = getattr(f, "end", 1)
                f_type = getattr(f, "feature_type", getattr(f, "type", "misc_feature"))
                f_strand = getattr(f, "strand", 1)
                parsed_feats.append(PlasmidFeature(
                    name=f_name, start=f_start, end=f_end, feature_type=f_type, strand=f_strand
                ))
        features = tuple(parsed_feats)

    return seq, name, is_circ, features


def _circular_slice(seq: str, start_0based: int, length: int) -> str:
    """Extract a circular slice of sequence given 0-based start and length."""
    L = len(seq)
    if L == 0 or length <= 0:
        return ""
    return "".join(seq[(start_0based + k) % L] for k in range(length))


def find_restriction_sites(
    seq_or_plasmid: Any,
    enzymes: Optional[List[str]] = None,
    circular: Optional[bool] = None,
    dam_methylated: bool = False,
    dcm_methylated: bool = False,
    cpg_methylated: bool = False,
) -> Dict[str, List[RestrictionCutSite]]:
    """Map restriction cleavage sites on DNA sequence or plasmid construct with methylation filtering."""
    seq, _, is_circ, _ = _extract_plasmid_data(seq_or_plasmid, circular)
    L = len(seq)
    if L == 0:
        return {}

    target_enzymes: List[RestrictionEnzyme] = []
    if enzymes is None:
        seen = set()
        for e in ENZYME_DATABASE.values():
            if e.name not in seen:
                seen.add(e.name)
                target_enzymes.append(e)
    else:
        for name in enzymes:
            target_enzymes.append(get_restriction_enzyme(name))

    # Pre-index methylation sites in sequence (with wrap-around)
    dam_sites_0based = set()  # GATC
    dcm_sites_0based = set()  # CC[AT]GG
    cpg_sites_0based = set()  # CG

    max_reach = 100
    search_buf = seq + (seq[:max_reach] if is_circ else "")

    for m in re.finditer(r"(?=(GATC))", search_buf):
        idx = m.start()
        if idx < L:
            for offset in range(4):
                dam_sites_0based.add((idx + offset) % L)

    for m in re.finditer(r"(?=(CC[AT]GG))", search_buf):
        idx = m.start()
        if idx < L:
            for offset in range(5):
                dcm_sites_0based.add((idx + offset) % L)

    for m in re.finditer(r"(?=(CG))", search_buf):
        idx = m.start()
        if idx < L:
            for offset in range(2):
                cpg_sites_0based.add((idx + offset) % L)

    results: Dict[str, List[RestrictionCutSite]] = {}

    for enzyme in target_enzymes:
        cut_sites: List[RestrictionCutSite] = []
        motif = enzyme.recognition_seq_clean or "".join(c for c in enzyme.recognition_site.upper() if c.isalpha())
        if not motif:
            continue

        motif_len = len(motif)
        o_top = enzyme.cut_offset_top
        o_bot = enzyme.cut_offset_bottom
        is_palindromic = (motif == reverse_complement_iupac(motif))

        # Check Forward Strand
        regex_fwd = compile_recognition_regex(motif)
        for match in regex_fwd.finditer(search_buf):
            start_0 = match.start()
            if start_0 >= L:
                continue

            end_0 = start_0 + motif_len - 1
            rec_indices = set((start_0 + k) % L for k in range(motif_len))

            # Methylation blocking check
            is_blocked = False

            # DpnI requires Dam methylation
            if enzyme.name.upper() == "DPNI":
                if not dam_methylated:
                    is_blocked = True
            elif dam_methylated:
                dam_sensitive = ("dam" in enzyme.methylation_sensitivity.lower() or
                                 enzyme.name in ("ClaI", "XbaI", "MboI", "BspEI", "BglII"))
                if dam_sensitive and rec_indices.intersection(dam_sites_0based):
                    is_blocked = True

            if dcm_methylated and not is_blocked:
                dcm_sensitive = ("dcm" in enzyme.methylation_sensitivity.lower() or
                                 enzyme.name in ("StuI", "Esp3I", "EcoRII"))
                if dcm_sensitive and rec_indices.intersection(dcm_sites_0based):
                    is_blocked = True

            if cpg_methylated and not is_blocked:
                cpg_sensitive = ("cpg" in enzyme.methylation_sensitivity.lower() or
                                 enzyme.name in ("NotI", "SalI", "SmaI", "PvuI", "AscI", "FseI", "AgeI", "SapI"))
                if cpg_sensitive and rec_indices.intersection(cpg_sites_0based):
                    is_blocked = True

            if is_blocked:
                continue

            # Calculate cut coordinates and overhang
            if not is_circ:
                top_cut_idx = start_0 + o_top
                bot_cut_idx = start_0 + o_bot
                if top_cut_idx < 0 or top_cut_idx > L or bot_cut_idx < 0 or bot_cut_idx > L:
                    continue

            top_cut_1based = ((start_0 + o_top - 1) % L) + 1
            bot_cut_1based = ((start_0 + o_bot - 1) % L) + 1
            rec_start_1based = (start_0 % L) + 1
            rec_end_1based = (end_0 % L) + 1

            if o_top < o_bot:
                oh_type = "5' overhang"
                oh_len = o_bot - o_top
                oh_seq = _circular_slice(seq, start_0 + o_top, oh_len) if is_circ else seq[start_0 + o_top : start_0 + o_bot]
            elif o_top > o_bot:
                oh_type = "3' overhang"
                oh_len = o_top - o_bot
                oh_seq = _circular_slice(seq, start_0 + o_bot, oh_len) if is_circ else seq[start_0 + o_bot : start_0 + o_top]
            else:
                oh_type = "blunt"
                oh_seq = ""

            cut_sites.append(RestrictionCutSite(
                enzyme=enzyme.name,
                cut_pos_top=top_cut_1based,
                cut_pos_bottom=bot_cut_1based,
                recognition_start=rec_start_1based,
                recognition_end=rec_end_1based,
                strand=1,
                overhang_type=oh_type,
                overhang_seq=oh_seq,
            ))

        # Check Reverse Strand for non-palindromic / Type IIS enzymes
        if not is_palindromic:
            motif_rc = reverse_complement_iupac(motif)
            regex_rev = compile_recognition_regex(motif_rc)
            for match in regex_rev.finditer(search_buf):
                start_0 = match.start()
                if start_0 >= L:
                    continue

                end_0 = start_0 + motif_len - 1
                rec_indices = set((start_0 + k) % L for k in range(motif_len))

                is_blocked = False
                if enzyme.name.upper() == "DPNI":
                    if not dam_methylated:
                        is_blocked = True
                elif dam_methylated:
                    dam_sensitive = ("dam" in enzyme.methylation_sensitivity.lower() or
                                     enzyme.name in ("ClaI", "XbaI", "MboI", "BspEI", "BglII"))
                    if dam_sensitive and rec_indices.intersection(dam_sites_0based):
                        is_blocked = True

                if dcm_methylated and not is_blocked:
                    dcm_sensitive = ("dcm" in enzyme.methylation_sensitivity.lower() or
                                     enzyme.name in ("StuI", "Esp3I", "EcoRII"))
                    if dcm_sensitive and rec_indices.intersection(dcm_sites_0based):
                        is_blocked = True

                if cpg_methylated and not is_blocked:
                    cpg_sensitive = ("cpg" in enzyme.methylation_sensitivity.lower() or
                                     enzyme.name in ("NotI", "SalI", "SmaI", "PvuI", "AscI", "FseI", "AgeI", "SapI"))
                    if cpg_sensitive and rec_indices.intersection(cpg_sites_0based):
                        is_blocked = True

                if is_blocked:
                    continue

                # On reverse strand, cleavage occurs downstream towards decreasing top-strand index
                # Top strand cut offset = -(o_bot - motif_len)
                # Bottom strand cut offset = -(o_top - motif_len)
                d_top = o_bot - motif_len
                d_bot = o_top - motif_len

                if not is_circ:
                    top_cut_idx = start_0 - d_top
                    bot_cut_idx = start_0 - d_bot
                    if top_cut_idx < 0 or top_cut_idx > L or bot_cut_idx < 0 or bot_cut_idx > L:
                        continue

                top_cut_1based = ((start_0 - d_top - 1) % L) + 1
                bot_cut_1based = ((start_0 - d_bot - 1) % L) + 1
                rec_start_1based = (start_0 % L) + 1
                rec_end_1based = (end_0 % L) + 1

                if o_top < o_bot:
                    oh_type = "5' overhang"
                    oh_len = o_bot - o_top
                    oh_seq = _circular_slice(seq, start_0 - d_top, oh_len) if is_circ else seq[start_0 - d_top : start_0 - d_bot]
                elif o_top > o_bot:
                    oh_type = "3' overhang"
                    oh_len = o_top - o_bot
                    oh_seq = _circular_slice(seq, start_0 - d_bot, oh_len) if is_circ else seq[start_0 - d_bot : start_0 - d_top]
                else:
                    oh_type = "blunt"
                    oh_seq = ""

                cut_sites.append(RestrictionCutSite(
                    enzyme=enzyme.name,
                    cut_pos_top=top_cut_1based,
                    cut_pos_bottom=bot_cut_1based,
                    recognition_start=rec_start_1based,
                    recognition_end=rec_end_1based,
                    strand=-1,
                    overhang_type=oh_type,
                    overhang_seq=oh_seq,
                ))

        cut_sites.sort(key=lambda s: s.cut_pos_top)
        results[enzyme.name] = cut_sites

    return results


def _is_feature_contained(
    f: PlasmidFeature,
    start_pos: int,
    end_pos: int,
    wraps: bool,
    L: int,
) -> bool:
    """Check if a plasmid feature is completely contained within fragment boundaries."""
    f_start = f.start
    f_end = f.end

    if not wraps:
        # Fragment spans [start_pos, end_pos] without wrapping origin
        if f_start <= f_end:
            return start_pos <= f_start and f_end <= end_pos
        return False
    else:
        # Fragment wraps origin: spans [start_pos, L] and [1, end_pos]
        if f_start <= f_end:
            # Contained if entirely in [start_pos, L] OR entirely in [1, end_pos]
            in_tail = (start_pos <= f_start <= L) and (start_pos <= f_end <= L)
            in_head = (1 <= f_start <= end_pos) and (1 <= f_end <= end_pos)
            return in_tail or in_head
        else:
            # Feature also wraps origin
            return f_start >= start_pos and f_end <= end_pos


def predict_restriction_digest(
    seq_or_plasmid: Any,
    enzymes: List[str],
    circular: Optional[bool] = None,
    dna_mass_ug: float = 1.0,
    reaction_volume_ul: float = 50.0,
    dam_methylated: bool = False,
    ladder_key: str = "1kb_dna",
) -> RestrictionDigestPrediction:
    """Simulate in-silico restriction digestion, fragment generation, gel migration, and pipetting recipe."""
    seq, name, is_circ, features = _extract_plasmid_data(seq_or_plasmid, circular)
    L = len(seq)
    if L == 0:
        raise ValueError("Sequence length must be strictly positive.")

    # Find cut sites for all requested enzymes
    site_dict = find_restriction_sites(
        seq_or_plasmid=seq,
        enzymes=enzymes,
        circular=is_circ,
        dam_methylated=dam_methylated,
    )

    all_cut_sites: List[RestrictionCutSite] = []
    for enz_name in enzymes:
        resolved_name = get_restriction_enzyme(enz_name).name
        all_cut_sites.extend(site_dict.get(resolved_name, []))

    # Sort cut sites by top strand cut position
    all_cut_sites.sort(key=lambda s: s.cut_pos_top)
    total_dna_ng = dna_mass_ug * 1000.0

    fragments: List[DigestedFragment] = []
    uncut_conformations: Dict[str, int] = {}
    K = len(all_cut_sites)

    if is_circ:
        if K == 0:
            uncut_conformations = {
                "supercoiled": round(0.72 * L),
                "relaxed_circle": round(1.0 * L),
                "nicked_open_circular": round(1.25 * L),
            }
            mw = calculate_dna_mw(length=L, double_stranded=True).average_mw
            contained = tuple(f.name for f in features)
            fragments.append(DigestedFragment(
                fragment_id=1,
                start_1based=1,
                end_1based=L,
                length_bp=L,
                molecular_weight_da=mw,
                mass_ng=round(total_dna_ng, 2),
                relative_intensity=1.0,
                left_enzyme="uncut",
                right_enzyme="uncut",
                left_overhang_type="blunt",
                right_overhang_type="blunt",
                left_overhang_seq="",
                right_overhang_seq="",
                wraps_origin=False,
                contained_features=contained,
            ))
        elif K == 1:
            cut = all_cut_sites[0]
            start_pos = (cut.cut_pos_top % L) + 1
            end_pos = cut.cut_pos_top
            mw = calculate_dna_mw(length=L, double_stranded=True).average_mw
            contained = tuple(f.name for f in features)
            fragments.append(DigestedFragment(
                fragment_id=1,
                start_1based=start_pos,
                end_1based=end_pos,
                length_bp=L,
                molecular_weight_da=mw,
                mass_ng=round(total_dna_ng, 2),
                relative_intensity=1.0,
                left_enzyme=cut.enzyme,
                right_enzyme=cut.enzyme,
                left_overhang_type=cut.overhang_type,
                right_overhang_type=cut.overhang_type,
                left_overhang_seq=cut.overhang_seq,
                right_overhang_seq=cut.overhang_seq,
                wraps_origin=True,
                contained_features=contained,
            ))
        else:
            # K >= 2 circular cuts
            for k in range(K - 1):
                c_left = all_cut_sites[k]
                c_right = all_cut_sites[k + 1]
                frag_len = c_right.cut_pos_top - c_left.cut_pos_top
                start_pos = (c_left.cut_pos_top % L) + 1
                end_pos = c_right.cut_pos_top
                mw = calculate_dna_mw(length=frag_len, double_stranded=True).average_mw
                mass = total_dna_ng * (frag_len / L)
                contained = tuple(
                    f.name for f in features if _is_feature_contained(f, start_pos, end_pos, wraps=False, L=L)
                )
                fragments.append(DigestedFragment(
                    fragment_id=k + 1,
                    start_1based=start_pos,
                    end_1based=end_pos,
                    length_bp=frag_len,
                    molecular_weight_da=mw,
                    mass_ng=round(mass, 2),
                    relative_intensity=round(frag_len / L, 4),
                    left_enzyme=c_left.enzyme,
                    right_enzyme=c_right.enzyme,
                    left_overhang_type=c_left.overhang_type,
                    right_overhang_type=c_right.overhang_type,
                    left_overhang_seq=c_left.overhang_seq,
                    right_overhang_seq=c_right.overhang_seq,
                    wraps_origin=False,
                    contained_features=contained,
                ))

            # Terminal origin-wrapping fragment from cut[K-1] to cut[0]
            c_last = all_cut_sites[K - 1]
            c_first = all_cut_sites[0]
            frag_len = (L - c_last.cut_pos_top) + c_first.cut_pos_top
            start_pos = (c_last.cut_pos_top % L) + 1
            end_pos = c_first.cut_pos_top
            mw = calculate_dna_mw(length=frag_len, double_stranded=True).average_mw
            mass = total_dna_ng * (frag_len / L)
            contained = tuple(
                f.name for f in features if _is_feature_contained(f, start_pos, end_pos, wraps=True, L=L)
            )
            fragments.append(DigestedFragment(
                fragment_id=K,
                start_1based=start_pos,
                end_1based=end_pos,
                length_bp=frag_len,
                molecular_weight_da=mw,
                mass_ng=round(mass, 2),
                relative_intensity=round(frag_len / L, 4),
                left_enzyme=c_last.enzyme,
                right_enzyme=c_first.enzyme,
                left_overhang_type=c_last.overhang_type,
                right_overhang_type=c_first.overhang_type,
                left_overhang_seq=c_last.overhang_seq,
                right_overhang_seq=c_first.overhang_seq,
                wraps_origin=True,
                contained_features=contained,
            ))
    else:
        # Linear DNA
        if K == 0:
            mw = calculate_dna_mw(length=L, double_stranded=True).average_mw
            contained = tuple(f.name for f in features)
            fragments.append(DigestedFragment(
                fragment_id=1,
                start_1based=1,
                end_1based=L,
                length_bp=L,
                molecular_weight_da=mw,
                mass_ng=round(total_dna_ng, 2),
                relative_intensity=1.0,
                left_enzyme="none",
                right_enzyme="none",
                left_overhang_type="blunt",
                right_overhang_type="blunt",
                left_overhang_seq="",
                right_overhang_seq="",
                wraps_origin=False,
                contained_features=contained,
            ))
        else:
            # First fragment: 1 to cut[0]
            c_first = all_cut_sites[0]
            frag_len = c_first.cut_pos_top
            mw = calculate_dna_mw(length=frag_len, double_stranded=True).average_mw
            mass = total_dna_ng * (frag_len / L)
            contained = tuple(
                f.name for f in features if _is_feature_contained(f, 1, c_first.cut_pos_top, wraps=False, L=L)
            )
            fragments.append(DigestedFragment(
                fragment_id=1,
                start_1based=1,
                end_1based=c_first.cut_pos_top,
                length_bp=frag_len,
                molecular_weight_da=mw,
                mass_ng=round(mass, 2),
                relative_intensity=round(frag_len / L, 4),
                left_enzyme="none",
                right_enzyme=c_first.enzyme,
                left_overhang_type="blunt",
                right_overhang_type=c_first.overhang_type,
                left_overhang_seq="",
                right_overhang_seq=c_first.overhang_seq,
                wraps_origin=False,
                contained_features=contained,
            ))

            # Intermediate fragments
            for k in range(K - 1):
                c_left = all_cut_sites[k]
                c_right = all_cut_sites[k + 1]
                frag_len = c_right.cut_pos_top - c_left.cut_pos_top
                start_pos = c_left.cut_pos_top + 1
                end_pos = c_right.cut_pos_top
                mw = calculate_dna_mw(length=frag_len, double_stranded=True).average_mw
                mass = total_dna_ng * (frag_len / L)
                contained = tuple(
                    f.name for f in features if _is_feature_contained(f, start_pos, end_pos, wraps=False, L=L)
                )
                fragments.append(DigestedFragment(
                    fragment_id=k + 2,
                    start_1based=start_pos,
                    end_1based=end_pos,
                    length_bp=frag_len,
                    molecular_weight_da=mw,
                    mass_ng=round(mass, 2),
                    relative_intensity=round(frag_len / L, 4),
                    left_enzyme=c_left.enzyme,
                    right_enzyme=c_right.enzyme,
                    left_overhang_type=c_left.overhang_type,
                    right_overhang_type=c_right.overhang_type,
                    left_overhang_seq=c_left.overhang_seq,
                    right_overhang_seq=c_right.overhang_seq,
                    wraps_origin=False,
                    contained_features=contained,
                ))

            # Last fragment: cut[K-1] to L
            c_last = all_cut_sites[K - 1]
            frag_len = L - c_last.cut_pos_top
            start_pos = c_last.cut_pos_top + 1
            end_pos = L
            mw = calculate_dna_mw(length=frag_len, double_stranded=True).average_mw
            mass = total_dna_ng * (frag_len / L)
            contained = tuple(
                f.name for f in features if _is_feature_contained(f, start_pos, end_pos, wraps=False, L=L)
            )
            fragments.append(DigestedFragment(
                fragment_id=K + 1,
                start_1based=start_pos,
                end_1based=end_pos,
                length_bp=frag_len,
                molecular_weight_da=mw,
                mass_ng=round(mass, 2),
                relative_intensity=round(frag_len / L, 4),
                left_enzyme=c_last.enzyme,
                right_enzyme="none",
                left_overhang_type=c_last.overhang_type,
                right_overhang_type="blunt",
                left_overhang_seq=c_last.overhang_seq,
                right_overhang_seq="",
                wraps_origin=False,
                contained_features=contained,
            ))

    # Virtual gel simulation
    if is_circ and K == 0:
        gel_sample_sizes = [
            float(uncut_conformations["supercoiled"]),
            float(uncut_conformations["relaxed_circle"]),
            float(uncut_conformations["nicked_open_circular"]),
        ]
    else:
        gel_sample_sizes = [float(f.length_bp) for f in fragments]

    sim = simulate_gel(sample_sizes=gel_sample_sizes, ladder_key=ladder_key)
    gel_bands: List[Dict[str, Any]] = []
    for sb in sim.sample_bands:
        gel_bands.append({
            "size_bp": sb.size,
            "relative_migration_rf": sb.relative_migration_rf,
            "label": sb.label,
            "is_reference": sb.is_reference,
        })

    # Pipetting plan
    pipetting_plan = None
    if len(enzymes) == 1:
        pipetting_plan = plan_restriction_digest(
            dna_mass_ug=dna_mass_ug,
            reaction_volume_ul=reaction_volume_ul,
            enzyme_1=enzymes[0],
        )
    elif len(enzymes) >= 2:
        pipetting_plan = plan_restriction_digest(
            dna_mass_ug=dna_mass_ug,
            reaction_volume_ul=reaction_volume_ul,
            enzyme_1=enzymes[0],
            enzyme_2=enzymes[1],
        )

    return RestrictionDigestPrediction(
        plasmid_name=name,
        total_length_bp=L,
        topology="circular" if is_circ else "linear",
        enzymes=tuple(enzymes),
        cut_sites=tuple(all_cut_sites),
        fragments=tuple(fragments),
        fragment_count=len(fragments),
        uncut_conformations=uncut_conformations,
        gel_bands=tuple(gel_bands),
        pipetting_plan=pipetting_plan,
    )


def screen_restriction_enzymes(
    seq_or_plasmid: Any,
    candidate_enzymes: Optional[List[str]] = None,
) -> EnzymeScreenResult:
    """Screen candidate restriction endonucleases into non-cutters, single cutters, double cutters, and MCS unique cutters."""
    seq, name, is_circ, features = _extract_plasmid_data(seq_or_plasmid)

    if candidate_enzymes is None:
        seen = set()
        cands: List[str] = []
        for e in ENZYME_DATABASE.values():
            if e.name not in seen:
                seen.add(e.name)
                cands.append(e.name)
    else:
        cands = list(candidate_enzymes)

    site_map = find_restriction_sites(seq_or_plasmid=seq, enzymes=cands, circular=is_circ)

    # Locate MCS feature if present
    mcs_features = [
        f for f in features
        if "mcs" in f.name.lower() or "multiple cloning site" in f.name.lower() or "polylinker" in f.name.lower()
        or "mcs" in f.feature_type.lower()
    ]

    non_cutters: List[str] = []
    single_cutters: List[str] = []
    double_cutters: List[str] = []
    multi_cutters: List[Tuple[str, int]] = []
    mcs_unique_cutters: List[str] = []

    for enz_name in cands:
        resolved = get_restriction_enzyme(enz_name).name
        sites = site_map.get(resolved, [])
        count = len(sites)

        if count == 0:
            non_cutters.append(resolved)
        elif count == 1:
            single_cutters.append(resolved)
            site = sites[0]
            # Check if cut site falls within any MCS feature
            for mcs in mcs_features:
                if mcs.start <= site.cut_pos_top <= mcs.end:
                    mcs_unique_cutters.append(resolved)
                    break
        elif count == 2:
            double_cutters.append(resolved)
        else:
            multi_cutters.append((resolved, count))

    return EnzymeScreenResult(
        plasmid_name=name,
        non_cutters=tuple(sorted(set(non_cutters))),
        single_cutters=tuple(sorted(set(single_cutters))),
        double_cutters=tuple(sorted(set(double_cutters))),
        multi_cutters=tuple(sorted(set(multi_cutters), key=lambda x: x[0])),
        mcs_unique_cutters=tuple(sorted(set(mcs_unique_cutters))),
    )
