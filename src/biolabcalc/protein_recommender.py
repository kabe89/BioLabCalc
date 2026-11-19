"""Application-Specific Protein Expression and Purification Strategy Recommender.

Provides deterministic biophysical profiling (MW, pI, GRAVY, Cys/disulfides,
N-glycosylation motifs) and recommends optimal expression host systems, affinity
and solubility tags, protease cleavage sites, and lysis/SEC buffer pH conditions
tailored to specific downstream applications:
- cryo_em
- xray_crystallography
- electrophysiology
- enzymatic_assay
- antibody_antigen
- pull_down
- therapeutic_grade
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .molecular_weight import calculate_protein_mw
from .seq_utils import clean_sequence


# ---------------------------------------------------------------------------
# Kyte-Doolittle Hydropathy Scale for GRAVY Calculation
# ---------------------------------------------------------------------------

KYTE_DOOLITTLE: Dict[str, float] = {
    "A": 1.8,
    "R": -4.5,
    "N": -3.5,
    "D": -3.5,
    "C": 2.5,
    "Q": -3.5,
    "E": -3.5,
    "G": -0.4,
    "H": -3.2,
    "I": 4.5,
    "L": 3.8,
    "K": -3.9,
    "M": 1.9,
    "F": 2.8,
    "P": -1.6,
    "S": -0.8,
    "T": -0.7,
    "W": -0.9,
    "Y": -1.3,
    "V": 4.2,
}


# ---------------------------------------------------------------------------
# Bjellqvist pKa Values for Isoelectric Point (pI) Calculation
# ---------------------------------------------------------------------------

PKA_VALUES: Dict[str, float] = {
    "N_term": 8.6,
    "C_term": 3.6,
    "C": 8.5,
    "D": 3.9,
    "E": 4.1,
    "H": 6.5,
    "K": 10.8,
    "R": 12.5,
    "Y": 10.1,
}


def calculate_gravy(sequence: str) -> float:
    """Calculate Grand Average of Hydropathy (GRAVY) using the Kyte-Doolittle scale.

    Positive values indicate hydrophobic / membrane-spanning proteins.
    Negative values indicate hydrophilic / soluble globular proteins.
    """
    clean = clean_sequence(sequence).upper()
    if not clean:
        return 0.0
    total = sum(KYTE_DOOLITTLE.get(aa, 0.0) for aa in clean)
    return round(total / len(clean), 3)


def calculate_isoelectric_point(sequence: str) -> float:
    """Calculate the isoelectric point (pI) using Bjellqvist pKa values and bisection search."""
    clean = clean_sequence(sequence).upper()
    if not clean:
        return 7.0

    counts: Dict[str, int] = {}
    for aa in clean:
        counts[aa] = counts.get(aa, 0) + 1

    def _net_charge(ph: float) -> float:
        # Positively charged groups at low pH
        pos = 1.0 / (1.0 + 10.0 ** (ph - PKA_VALUES["N_term"]))
        pos += counts.get("H", 0) / (1.0 + 10.0 ** (ph - PKA_VALUES["H"]))
        pos += counts.get("K", 0) / (1.0 + 10.0 ** (ph - PKA_VALUES["K"]))
        pos += counts.get("R", 0) / (1.0 + 10.0 ** (ph - PKA_VALUES["R"]))

        # Negatively charged groups at high pH
        neg = 1.0 / (1.0 + 10.0 ** (PKA_VALUES["C_term"] - ph))
        neg += counts.get("D", 0) / (1.0 + 10.0 ** (PKA_VALUES["D"] - ph))
        neg += counts.get("E", 0) / (1.0 + 10.0 ** (PKA_VALUES["E"] - ph))
        neg += counts.get("C", 0) / (1.0 + 10.0 ** (PKA_VALUES["C"] - ph))
        neg += counts.get("Y", 0) / (1.0 + 10.0 ** (PKA_VALUES["Y"] - ph))

        return pos - neg

    low = 0.0
    high = 14.0
    for _ in range(40):
        mid = (low + high) / 2.0
        charge = _net_charge(mid)
        if charge > 0:
            low = mid
        else:
            high = mid

    return round((low + high) / 2.0, 2)


def find_n_glycosylation_sites(sequence: str) -> Tuple[int, ...]:
    """Find 1-based positions of Asn in canonical N-X-[S/T] (where X != P) sequons."""
    clean = clean_sequence(sequence).upper()
    sites: List[int] = []
    # Sequon: Asn followed by any residue except Pro, followed by Ser or Thr, followed by non-Pro
    for i in range(len(clean) - 2):
        if clean[i] == "N" and clean[i + 1] != "P" and clean[i + 2] in ("S", "T"):
            # Check 4th residue if present (proline at +3 strongly inhibits oligosaccharyltransferase)
            if i + 3 < len(clean) and clean[i + 3] == "P":
                continue
            sites.append(i + 1)
    return tuple(sites)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProteinBiophysicalProfile:
    """Biophysical metrics computed from primary amino acid sequence."""
    sequence: str
    length: int
    molecular_weight_da: float
    isoelectric_point: float
    gravy_index: float
    cysteine_count: int
    predicted_disulfide_bonds: int
    has_odd_cysteines: bool
    n_glycosylation_sites: Tuple[int, ...]
    is_membrane_predicted: bool

    def __post_init__(self) -> None:
        if not isinstance(self.n_glycosylation_sites, tuple):
            object.__setattr__(self, "n_glycosylation_sites", tuple(self.n_glycosylation_sites))


@dataclass(frozen=True)
class ProteinRecommendationResult:
    """Comprehensive, ranked expression and purification recommendation."""
    target_name: str
    application: str
    biophysical_profile: ProteinBiophysicalProfile
    recommended_hosts: Tuple[Tuple[str, str, int], ...]  # (host, rationale, score)
    recommended_tags: Tuple[Tuple[str, str], ...]  # (tag, rationale)
    recommended_cleavage_proteases: Tuple[Tuple[str, str], ...]  # (protease, rationale)
    recommended_lysis_buffer_ph: float
    recommended_sec_buffer_ph: float
    buffer_rationale: str
    detergent_or_additive_guidance: Tuple[str, ...]
    warnings: Tuple[str, ...]

    def __post_init__(self) -> None:
        for f in (
            "recommended_hosts",
            "recommended_tags",
            "recommended_cleavage_proteases",
            "detergent_or_additive_guidance",
            "warnings",
        ):
            val = getattr(self, f, ())
            if not isinstance(val, tuple):
                object.__setattr__(self, f, tuple(val))

    def _repr_html_(self) -> str:
        """Render clean minimalist HTML for Jupyter notebooks and web view."""
        import html
        prof = self.biophysical_profile
        hosts_rows = "".join(
            f"<tr><td style='padding:4px 8px;font-weight:600;'>{html.escape(h[0])}</td>"
            f"<td style='padding:4px 8px;'>{html.escape(h[1])}</td>"
            f"<td style='padding:4px 8px;text-align:right;'>{h[2]}/100</td></tr>"
            for h in self.recommended_hosts
        )
        tags_rows = "".join(
            f"<tr><td style='padding:4px 8px;font-weight:600;'>{html.escape(t[0])}</td>"
            f"<td style='padding:4px 8px;'>{html.escape(t[1])}</td></tr>"
            for t in self.recommended_tags
        )
        return (
            f"<div style='font-family:system-ui,sans-serif;border:1px solid #E2E8F0;border-radius:8px;padding:16px;max-width:680px;background:#FFF;'>"
            f"<h3 style='margin:0 0 8px 0;font-size:16px;'>Protein Expression Strategy: {html.escape(self.target_name)}</h3>"
            f"<p style='color:#64748B;font-size:13px;margin:0 0 12px 0;'>Application: <b>{html.escape(self.application)}</b> | Length: {prof.length} aa | MW: {prof.molecular_weight_da:,.1f} Da | pI: {prof.isoelectric_point} | GRAVY: {prof.gravy_index:+.2f}</p>"
            f"<h4 style='font-size:13px;margin:10px 0 4px 0;'>Recommended Expression Hosts</h4>"
            f"<table style='width:100%;font-size:12.5px;border-collapse:collapse;border:1px solid #E2E8F0;margin-bottom:12px;'>"
            f"<tr style='background:#F8FAFC;'><th style='padding:4px 8px;text-align:left;'>Host</th><th style='padding:4px 8px;text-align:left;'>Rationale</th><th style='padding:4px 8px;text-align:right;'>Score</th></tr>"
            f"{hosts_rows}</table>"
            f"<h4 style='font-size:13px;margin:10px 0 4px 0;'>Recommended Affinity & Solubility Tags</h4>"
            f"<table style='width:100%;font-size:12.5px;border-collapse:collapse;border:1px solid #E2E8F0;margin-bottom:12px;'>"
            f"{tags_rows}</table>"
            f"<p style='font-size:12.5px;margin:4px 0;'><b>Buffer pH Guidance:</b> Lysis pH {self.recommended_lysis_buffer_ph:.1f}, SEC pH {self.recommended_sec_buffer_ph:.1f}. {html.escape(self.buffer_rationale)}</p>"
            f"</div>"
        )


def analyze_protein_profile(sequence: str, is_membrane: bool = False) -> ProteinBiophysicalProfile:
    """Analyze primary amino acid sequence for key biophysical properties."""
    clean = clean_sequence(sequence).upper()
    if not clean:
        raise ValueError("Protein sequence cannot be empty.")

    L = len(clean)
    mw_res = calculate_protein_mw(clean)
    mw = mw_res.molecular_weight
    pi = calculate_isoelectric_point(clean)
    gravy = calculate_gravy(clean)
    cys_count = clean.count("C")
    disulfides = cys_count // 2
    odd_cys = bool(cys_count % 2 != 0)
    glyc_sites = find_n_glycosylation_sites(clean)
    membrane = is_membrane or (gravy > 0.35)

    return ProteinBiophysicalProfile(
        sequence=clean,
        length=L,
        molecular_weight_da=mw,
        isoelectric_point=pi,
        gravy_index=gravy,
        cysteine_count=cys_count,
        predicted_disulfide_bonds=disulfides,
        has_odd_cysteines=odd_cys,
        n_glycosylation_sites=glyc_sites,
        is_membrane_predicted=membrane,
    )


def recommend_protein_strategy(
    sequence: str,
    application: str = "xray_crystallography",
    is_membrane: bool = False,
    target_name: str = "Target_Protein",
) -> ProteinRecommendationResult:
    """Generate ranked expression, tag, protease, and buffer recommendations.

    Parameters
    ----------
    sequence : str
        Target protein amino acid sequence (single-letter code).
    application : str
        Target biochemical application. Choices:
        - 'cryo_em'
        - 'xray_crystallography'
        - 'electrophysiology'
        - 'enzymatic_assay'
        - 'antibody_antigen'
        - 'pull_down'
        - 'therapeutic_grade'
    is_membrane : bool
        Whether the target is known to be a membrane protein.
    target_name : str
        Descriptive identifier for the target.
    """
    profile = analyze_protein_profile(sequence, is_membrane=is_membrane)
    app = application.lower().strip()

    valid_apps = {
        "cryo_em",
        "xray_crystallography",
        "electrophysiology",
        "enzymatic_assay",
        "antibody_antigen",
        "pull_down",
        "therapeutic_grade",
    }
    if app not in valid_apps:
        app = "xray_crystallography"

    hosts: List[Tuple[str, str, int]] = []
    tags: List[Tuple[str, str]] = []
    proteases: List[Tuple[str, str]] = []
    guidance: List[str] = []
    warnings: List[str] = []

    # 1. Cysteine / Disulfide Analysis
    if profile.has_odd_cysteines:
        warnings.append(
            f"Odd number of cysteines ({profile.cysteine_count}) detected. Unpaired free thiol presents risk of non-specific intermolecular disulfide aggregation. Include 0.5–2 mM TCEP/DTT in purification buffers."
        )

    # 2. Application-Specific Host & Tag Strategy
    if app == "cryo_em":
        if profile.is_membrane_predicted or len(profile.n_glycosylation_sites) > 0:
            hosts.append(("Expi293F (Mammalian)", "Optimal for complex multi-pass membrane proteins with post-translational modifications and native fold", 95))
            hosts.append(("Sf9 / High Five (Baculovirus)", "High-yield insect expression for large multi-protein eukaryotic complexes", 88))
        else:
            hosts.append(("E. coli BL21(DE3)", "Cost-effective, rapid high-yield expression for rigid globular complexes lacking complex PTMs", 90))
            hosts.append(("Expi293F (Mammalian)", "High conformational homogeneity and native chaperone environment", 85))
        tags.append(("Twin-Strep (N- or C-term)", "High affinity (pM Kd) with Strep-Tactin XT; elutes under gentle native conditions (biotin) preserving cryo-EM grid particle integrity"))
        tags.append(("His6-TEV", "Standard compact affinity tag; cleavable with TEV protease to prevent flexible tag-induced orientation bias on EM grids"))
        proteases.append(("TEV Protease", "High specificity cleavage; removes flexible tags to improve angular particle alignment in single-particle analysis"))
        proteases.append(("HRV 3C (PreScission)", "Active at 4°C for temperature-sensitive cryo-EM targets"))

    elif app == "xray_crystallography":
        if profile.is_membrane_predicted:
            hosts.append(("Sf9 Baculovirus", "Proven host for GPCR and transporter crystal structures", 92))
            hosts.append(("HEK293S GnTI- (Mammalian)", "Produces uniform, truncated Man5GlcNAc2 high-mannose glycans essential for crystal lattice packing", 88))
        elif profile.predicted_disulfide_bonds > 1:
            hosts.append(("E. coli SHuffle T7 Express", "Engineered trxB/gor deletion cytoplasm allows oxidative disulfide bond formation in E. coli", 94))
            hosts.append(("E. coli BL21(DE3)", "Standard bacterial expression; target may require periplasmic targeting (pelB/ompA) or in vitro refolding", 80))
        else:
            hosts.append(("E. coli BL21(DE3)", "Industry standard for structural biology; high yield, fast doubling, rigid monodisperse protein", 95))
            hosts.append(("E. coli Rosetta 2(DE3)", "Supplies rare tRNAs (AUA, AGG, AGA, CUA, CCC, GGA) for eukaryotic targets", 90))
        tags.append(("His6-TEV", "Minimal 6xHis tag; cleanly cleaved by TEV leaving only a single Gly scar for tight crystal packing"))
        tags.append(("His8-TEV", "Extended 8xHis tag providing stronger Ni-NTA binding during stringent salt washes"))
        if profile.gravy_index > 0.0:
            tags.append(("MBP-TEV", "Maltose-binding protein solubility chaperone; prevents aggregation and can promote crystallization via rigid fusion"))
        proteases.append(("TEV Protease", "Rigorous sequence specificity; leaves minimal N-terminal scar"))
        proteases.append(("Ulp1 (SUMO Protease)", "Scarless cleavage at SUMO C-terminus; generates native N-terminus for crystallography"))

    elif app == "electrophysiology":
        hosts.append(("HEK293 / Expi293F (Mammalian)", "Native mammalian membrane lipid bilayer composition for patch-clamp and automated planar electrophysiology", 96))
        hosts.append(("Xenopus laevis Oocytes", "Two-electrode voltage clamp (TEVC) expression via cRNA microinjection", 90))
        tags.append(("Twin-Strep-tag", "Ultra-high affinity enables microgram-scale clean isolation from detergent-solubilized membrane fractions"))
        tags.append(("1D4 / C-terminal Rhodopsin tag", "Gentle elution with peptide for intact, functionally active ion channels"))
        proteases.append(("HRV 3C", "Reliable low-temperature cleavage in detergent micelles"))

    elif app == "enzymatic_assay":
        if profile.predicted_disulfide_bonds > 0:
            hosts.append(("E. coli SHuffle T7", "Permits cytoplasmic disulfide formation to sustain catalytic disulfide bridges", 92))
            hosts.append(("Pichia pastoris", "Eukaryotic secretor; yields folded active extracellular enzymes", 85))
        else:
            hosts.append(("E. coli BL21(DE3)", "High-yield, robust production of recombinant enzymes", 95))
        tags.append(("His6-TEV", "Compact tag; minimal steric hindrance on catalytic active sites"))
        tags.append(("FLAG-tag (DYKDDDDK)", "Highly hydrophilic octapeptide; low interference with enzyme kinetics"))
        proteases.append(("TEV Protease", "High cleavage efficiency leaving active catalytic domain"))

    elif app == "antibody_antigen":
        hosts.append(("Expi293F / CHO (Mammalian)", "Mandatory for authentic human/mammalian epitope conformation and native complex N-linked glycosylation", 98))
        hosts.append(("Sf9 Insect Cells", "High yield with core paucimannose glycosylation suitable for structural immunology", 84))
        tags.append(("AviTag (BirA Biotinylation)", "Site-specific enzymatic biotinylation for SPR (Biacore), BLI (Octet), and ELISA surfaces"))
        tags.append(("Twin-Strep-tag", "High-affinity immobilization without antibody inactivation"))
        proteases.append(("HRV 3C", "Clean cleavage to release monomeric or Fab-like antigens"))

    elif app == "pull_down":
        hosts.append(("E. coli BL21(DE3)", "Rapid high-yield bait protein production", 94))
        hosts.append(("HEK293T", "Co-immunoprecipitation host for native protein-protein interactome discovery", 90))
        tags.append(("GST (Glutathione S-transferase)", "High-capacity glutathione resin capture; gold standard for GST pull-down interactomics"))
        tags.append(("Twin-Strep-tag", "Strep-Tactin XT pull-down with nanomolar to picomolar retention and gentle competitive elution"))
        tags.append(("MBP (Maltose-binding protein)", "Solubilizes difficult aggregation-prone interactome targets"))
        proteases.append(("Thrombin", "Standard cleavage to release pulled-down prey complexes from glutathione beads"))
        proteases.append(("TEV Protease", "High specificity bait-prey separation"))

    elif app == "therapeutic_grade":
        hosts.append(("CHO-K1 / ExpiCHO (Mammalian)", "Regulatory gold-standard host for biopharmaceutical manufacturing (mAb, Fc-fusions, cytokines)", 98))
        hosts.append(("Expi293F (Mammalian)", "Rapid transient biotherapeutic candidate screening with human glycoforms", 90))
        if not profile.is_membrane_predicted and len(profile.n_glycosylation_sites) == 0:
            hosts.append(("ClearColi BL21(DE3)", "Genetically modified E. coli producing non-pyrogenic lipid IVA; eliminates endotoxin contamination", 86))
        tags.append(("Tag-Free / Untagged", "Regulatory preferred for clinical translation; purified via ion-exchange, hydrophobic interaction, and multimodal chromatography"))
        tags.append(("His6-TEV (Research Grade Only)", "For preclinical discovery stages; must be completely cleaved prior to in-vivo dosing"))
        proteases.append(("TEV Protease", "Stringent protease with virtually zero non-specific off-target clipping"))

    # 3. Buffer pH & Formulation Strategy
    # Principle: buffer pH must be at least 1.0 pH unit away from pI to maximize net charge and avoid isoelectric aggregation
    pI = profile.isoelectric_point
    if pI <= 6.2:
        lysis_ph = 8.0
        sec_ph = 7.5
        rationale = f"pI is acidic ({pI:.2f}). Operating at pH 7.5–8.0 imparts net negative surface charge, ensuring colloidal solubility in Tris-HCl or HEPES buffers."
    elif pI >= 7.8:
        lysis_ph = 6.8
        sec_ph = 6.8
        rationale = f"pI is basic ({pI:.2f}). Operating at pH 6.5–7.0 imparts net positive surface charge, preventing precipitation in Bis-Tris, MES, or HEPES buffers."
    else:
        # Near neutral pI (6.3 - 7.7) -> high risk at physiological pH
        lysis_ph = 8.5
        sec_ph = 8.2
        rationale = f"pI is near neutral ({pI:.2f}). To avoid isoelectric aggregation at physiological pH 7.0–7.4, buffer pH is offset to {sec_ph:.1f} (Tris-HCl) to maintain net charge repulsion."
        warnings.append(
            f"Protein pI ({pI:.2f}) is near physiological pH. Avoid buffers between pH 6.6 and 7.4 during concentration steps to prevent isoelectric precipitation."
        )

    # 4. Detergent / Chaperone Additive Guidance
    if profile.is_membrane_predicted or profile.gravy_index > 0.3:
        guidance.append("Target is highly hydrophobic/membrane-spanning. Screen non-ionic detergents: 0.05% DDM/0.01% CHS or 0.005% LMNG/CHS for extraction and SEC.")
        guidance.append("Maintain 150–300 mM NaCl in all purification steps to suppress non-specific hydrophobic aggregation.")
    if profile.cysteine_count > 0:
        guidance.append("Include 0.5–1.0 mM TCEP in lysis and SEC buffers to protect against cysteine oxidation during purification.")
    if len(profile.n_glycosylation_sites) > 0:
        guidance.append(f"Contains {len(profile.n_glycosylation_sites)} canonical N-glycosylation site(s) at position(s): {', '.join(str(s) for s in profile.n_glycosylation_sites)}. Treatment with PNGase F will yield uniform deglycosylated mass.")

    return ProteinRecommendationResult(
        target_name=target_name,
        application=app,
        biophysical_profile=profile,
        recommended_hosts=tuple(hosts),
        recommended_tags=tuple(tags),
        recommended_cleavage_proteases=tuple(proteases),
        recommended_lysis_buffer_ph=round(lysis_ph, 2),
        recommended_sec_buffer_ph=round(sec_ph, 2),
        buffer_rationale=rationale,
        detergent_or_additive_guidance=tuple(guidance),
        warnings=tuple(warnings),
    )
