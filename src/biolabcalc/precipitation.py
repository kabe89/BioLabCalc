"""Ethanol and isopropanol nucleic acid precipitation, desalting, and carrier calculation."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass(frozen=True)
class PrecipitationProtocol:
    sample_volume_ul: float
    nucleic_acid_type: str
    alcohol_type: str
    salt_type: str
    salt_volume_ul: float
    alcohol_volume_ul: float
    carrier_added: str
    carrier_volume_ul: float
    incubation_temp: str
    centrifugation_speed: str
    centrifugation_time_min: int
    wash_volume_70pct_ethanol_ul: float
    drying_instructions: str
    resuspension_guidelines: str
    reagent_summary: Dict[str, float]
    vessel_warning: Optional[str] = None

def calculate_precipitation(
    sample_volume_ul: float,
    nucleic_acid: str = "dna",
    alcohol: str = "ethanol",
    salt: str = "naoac",
    low_concentration_carrier: bool = True,
    target_resuspension_conc_ng_ul: Optional[float] = None,
    estimated_total_ng: Optional[float] = None,
) -> PrecipitationProtocol:
    """Calculate exact pipetting volumes and protocol for ethanol or isopropanol nucleic acid precipitation."""
    if sample_volume_ul <= 0:
        raise ValueError("Sample volume must be positive.")

    na_type = nucleic_acid.lower()
    alc_type = alcohol.lower()
    s_type = salt.lower().replace("-", "").replace(" ", "")

    # Salt volume multiplier
    if "nh4" in s_type:
        salt_name = "5 M Ammonium Acetate (pH 7.0)"
        salt_ratio = 0.50
        salt_notes = "Reduces dNTP co-precipitation. Avoid if downstream T4 PNK phosphorylation is needed."
    elif "li" in s_type:
        salt_name = "8 M Lithium Chloride"
        salt_ratio = 0.50
        salt_notes = "Precipitates large RNA (>200 nt); leaves dNTPs and tRNAs in solution."
    elif "nacl" in s_type:
        salt_name = "5 M Sodium Chloride"
        salt_ratio = 0.20
        salt_notes = "Preferred when sample contains SDS or detergents."
    else:  # Standard NaOAc
        salt_name = "3 M Sodium Acetate (pH 5.2)"
        salt_ratio = 0.10
        salt_notes = "Standard general-purpose salt for DNA/RNA precipitation."

    salt_vol = round(sample_volume_ul * salt_ratio, 1)

    # Carrier (Glycogen or GlycoBlue)
    carrier_vol = 1.0 if low_concentration_carrier else 0.0
    carrier_desc = "1.0 µL of GlycoBlue or Glycogen (20 mg/mL)" if low_concentration_carrier else "None (visible pellet expected for >5 µg)"

    is_licl = "li" in s_type
    pre_alc_vol = sample_volume_ul + salt_vol

    if is_licl:
        alc_name = "None (LiCl does not use alcohol)"
        alc_vol = 0.0
        incubation = "Incubate at -20°C for ≥30 minutes (or overnight at 4°C/-20°C for dilute RNA). Do not add alcohol (alcohol causes unincorporated NTPs and salts to co-precipitate)."
    elif "iso" in alc_type:
        alc_name = "100% Isopropanol (room temperature)"
        alc_ratio = 0.70 if "dna" in na_type else 1.00
        incubation = "Incubate at room temperature or -20°C for 15-30 minutes (do not chill below -20°C to avoid salt precipitation)."
        alc_vol = round(pre_alc_vol * alc_ratio, 1)
    else:  # Ethanol
        alc_name = "100% Ethanol (ice-cold, -20°C)"
        alc_ratio = 3.00 if "rna" in na_type else 2.50
        incubation = "Incubate at -20°C for ≥30 minutes (or -80°C for 15-30 minutes)."
        alc_vol = round(pre_alc_vol * alc_ratio, 1)
    wash_vol = max(200.0, round(sample_volume_ul * 2.0, 1))

    # Centrifugation
    centrifuge_speed = "≥ 14,000 × g (or max speed ~16,000 × g)"
    centrifuge_time = 20 if "rna" in na_type else 15

    # Resuspension volume
    if target_resuspension_conc_ng_ul and estimated_total_ng and target_resuspension_conc_ng_ul > 0:
        resusp_vol = round(estimated_total_ng / target_resuspension_conc_ng_ul, 1)
        resusp_guide = f"Resuspend pellet in {resusp_vol} µL of 1X TE buffer or sterile water to achieve ~{target_resuspension_conc_ng_ul} ng/µL."
    else:
        resusp_guide = "Resuspend pellet in 20-50 µL of 1X TE buffer (pH 8.0) or nuclease-free water."

    reagents = {
        "Initial Sample": sample_volume_ul,
        salt_name: salt_vol,
        alc_name: alc_vol,
        "70% Ethanol (Wash)": wash_vol,
    }
    if low_concentration_carrier:
        reagents["GlycoBlue / Glycogen Carrier"] = carrier_vol

    tot_vol = pre_alc_vol + alc_vol
    vessel_warn = None
    if tot_vol > 1500.0:
        vessel_warn = (
            f"Total volume ({tot_vol:.1f} µL) exceeds standard 1.5 mL microcentrifuge tubes. "
            f"Use a 2.0 mL tube, split across multiple tubes, or switch to isopropanol ({pre_alc_vol * 1.7:.1f} µL total)."
        )

    return PrecipitationProtocol(
        sample_volume_ul=sample_volume_ul,
        nucleic_acid_type=nucleic_acid.upper(),
        alcohol_type=alc_name,
        salt_type=salt_name,
        salt_volume_ul=salt_vol,
        alcohol_volume_ul=alc_vol,
        carrier_added=carrier_desc,
        carrier_volume_ul=carrier_vol,
        incubation_temp=incubation,
        centrifugation_speed=centrifuge_speed,
        centrifugation_time_min=centrifuge_time,
        wash_volume_70pct_ethanol_ul=wash_vol,
        drying_instructions="Air dry pellet for 5-10 minutes with tube open. Do not overdry (translucent pellet becomes difficult to dissolve).",
        resuspension_guidelines=resusp_guide,
        reagent_summary=reagents,
        vessel_warning=vessel_warn,
    )


@dataclass(frozen=True)
class PhenolChloroformProtocol:
    sample_volume_ul: float
    phenol_type: str
    target_nucleic_acid: str
    pci_volume_ul: float
    chloroform_volume_ul: float
    aqueous_phase_layer: str
    protocol_steps: List[str]
    safety_notes: List[str]
    reagent_volumes: Dict[str, float]


def calculate_phenol_chloroform_extraction(
    sample_volume_ul: float,
    nucleic_acid: str = "rna",
    phenol_ph: Optional[float] = None,
) -> PhenolChloroformProtocol:
    """Calculate reagent volumes, phase separation mechanics, and protocol for Phenol:Chloroform extraction.

    Parameters
    ----------
    sample_volume_ul : float
        Aqueous sample volume in microliters.
    nucleic_acid : str
        Target nucleic acid ('rna' or 'dna').
    phenol_ph : float, optional
        Phenol pH (default: 4.5 for RNA selective partitioning, 8.0 for DNA).
    """
    if sample_volume_ul <= 0:
        raise ValueError("Sample volume must be positive.")

    na_lower = nucleic_acid.lower()
    is_rna = "rna" in na_lower

    if phenol_ph is None:
        actual_ph = 4.5 if is_rna else 8.0
    else:
        actual_ph = phenol_ph

    if actual_ph < 5.5:
        p_name = f"Acid Phenol:Chloroform:Isoamyl Alcohol 125:24:1 (pH {actual_ph:.1f})"
        phase_desc = "Upper aqueous phase selectively retains RNA. Genomic and plasmid DNA denatures and partitions into the organic phase / interphase."
    else:
        p_name = f"Buffered Phenol:Chloroform:Isoamyl Alcohol 25:24:1 (pH {actual_ph:.1f})"
        phase_desc = "Upper aqueous phase retains BOTH DNA and RNA."

    pci_vol = sample_volume_ul
    chloro_vol = sample_volume_ul

    steps = [
        f"1. In a fume hood, add equal volume of PCI ({pci_vol:.1f} µL) to aqueous sample ({sample_volume_ul:.1f} µL). Vortex vigorously for 15–30 sec.",
        f"2. Centrifuge at ≥ 14,000 × g for 5 minutes at {'4°C' if is_rna else 'room temperature'} to achieve clean phase separation.",
        f"3. Carefully pipette off the upper aqueous phase (~{sample_volume_ul * 0.9:.1f} µL) into a clean tube without disturbing the white proteinaceous interphase.",
        f"4. Back-extraction / Desolvation: Add equal volume of Chloroform:Isoamyl Alcohol (24:1) ({chloro_vol:.1f} µL), vortex 15 sec, and centrifuge at 14,000 × g for 5 min to extract residual dissolved phenol.",
        "5. Collect final upper aqueous phase for downstream ethanol, isopropanol, or LiCl precipitation.",
    ]

    safety = [
        "DANGER: Phenol causes severe, rapid chemical burns and temporary local anesthesia. Work strictly inside a certified chemical fume hood.",
        "Wear chemical-resistant nitrile gloves, lab coat, and protective eye goggles.",
        "Keep a dedicated chemical waste container for phenol-containing tips and organic waste.",
    ]

    reagents = {
        "Initial Sample": sample_volume_ul,
        p_name: pci_vol,
        "Chloroform:Isoamyl Alcohol (24:1)": chloro_vol,
    }

    return PhenolChloroformProtocol(
        sample_volume_ul=sample_volume_ul,
        phenol_type=p_name,
        target_nucleic_acid=nucleic_acid.upper(),
        pci_volume_ul=pci_vol,
        chloroform_volume_ul=chloro_vol,
        aqueous_phase_layer=phase_desc,
        protocol_steps=steps,
        safety_notes=safety,
        reagent_volumes=reagents,
    )
