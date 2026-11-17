"""Common laboratory buffer and stock solution recipes with dynamic volume scaling and bench preparation notes."""

from __future__ import annotations
import os
import json
import tempfile
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple, Literal, Union

@dataclass(frozen=True)
class BufferComponent:
    name: str
    amount: float
    unit: str  # "g" or "mL"
    molar_concentration: str
    cas_or_mw: Optional[str] = None

@dataclass(frozen=True)
class BufferRecipeResult:
    buffer_id: str
    name: str
    target_volume_ml: float
    components: Tuple[BufferComponent, ...]
    ph_specification: str
    preparation_steps: Tuple[str, ...]
    storage_conditions: str
    safety_notes: Optional[str] = None

    def __post_init__(self):
        for f in ("components", "preparation_steps"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))

    def _repr_html_(self) -> str:
        """Render clean HTML summary for Jupyter notebooks."""
        import html
        comp_rows = "".join(
            f"<tr style='border-bottom: 1px solid #F1F5F9;'>"
            f"<td style='padding: 3px 6px;'>{html.escape(c.name)}</td>"
            f"<td style='padding: 3px 6px;'>{html.escape(c.molar_concentration)}</td>"
            f"<td style='padding: 3px 6px; text-align: right; font-weight: 600;'>{c.amount:.3g} {html.escape(c.unit)}</td>"
            f"</tr>"
            for c in self.components
        )
        return (
            f'<div style="font-family: system-ui, -apple-system, sans-serif; border: 1px solid #E2E8F0; '
            f'border-radius: 8px; padding: 14px; max-width: 580px; background: #FFFFFF; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">'
            f'<h3 style="margin: 0; font-size: 15px; color: #0F172A;">{html.escape(self.name)}</h3>'
            f'<span style="background: #EFF6FF; color: #2563EB; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px;">{self.target_volume_ml:g} mL</span>'
            f'</div>'
            f'<div style="font-size: 12px; color: #64748B; margin-bottom: 10px;">pH Spec: {html.escape(self.ph_specification)} • Storage: {html.escape(self.storage_conditions)}</div>'
            f'<table style="width: 100%; border-collapse: collapse; font-size: 12px; background: #F8FAFC; border-radius: 4px; margin-bottom: 8px;">'
            f'<tr style="color: #64748B; border-bottom: 1px solid #E2E8F0;"><th style="padding: 4px 6px; text-align: left;">Component</th><th style="padding: 4px 6px; text-align: left;">Target Conc</th><th style="padding: 4px 6px; text-align: right;">Amount</th></tr>'
            f'{comp_rows}'
            f'</table>'
            f'</div>'
        )


@dataclass(frozen=True)
class EquilibriumComponent:
    name: str
    total_conc_m: float
    pka_values: Tuple[float, ...] = ()
    charge_states: Tuple[int, ...] = ()
    dpka_dt: float = 0.0

    def __post_init__(self):
        for f in ("pka_values", "charge_states"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))


@dataclass(frozen=True)
class SpeciesConcentration:
    name: str
    concentration_m: float
    fraction_of_total: float
    charge: int


@dataclass(frozen=True)
class PrecipitationCheck:
    salt_name: str
    ion_product: float
    ksp: float
    saturation_index: float
    will_precipitate: bool


@dataclass(frozen=True)
class BufferEquilibriumResult:
    target_ph: float
    actual_ph: float
    ionic_strength_m: float
    temperature_celsius: float
    free_mg_conc_m: float
    free_ca_conc_m: float
    free_atp_conc_m: float
    species: Tuple[SpeciesConcentration, ...]
    precipitation_risks: Tuple[PrecipitationCheck, ...]
    buffer_capacity_beta: float = 0.0
    components: Tuple[EquilibriumComponent, ...] = ()

    def __post_init__(self):
        for f in ("species", "precipitation_risks", "components"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))

    def _repr_html_(self) -> str:
        """Render clean HTML summary for Jupyter notebooks."""
        import html
        precip_rows = "".join(
            f"<tr style='border-bottom: 1px solid #F1F5F9; color: {'#DC2626' if p.will_precipitate else '#16A34A'};'>"
            f"<td style='padding: 2px 6px;'>{html.escape(p.salt_name)}</td>"
            f"<td style='padding: 2px 6px; text-align: right;'>SI={p.saturation_index:+.2f} ({'RISK' if p.will_precipitate else 'Soluble'})</td>"
            f"</tr>"
            for p in self.precipitation_risks
        )
        return (
            f'<div style="font-family: system-ui, -apple-system, sans-serif; border: 1px solid #E2E8F0; '
            f'border-radius: 8px; padding: 14px; max-width: 600px; background: #FFFFFF; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">'
            f'<h3 style="margin: 0; font-size: 15px; color: #0F172A;">Multi-Metal Buffer Speciation</h3>'
            f'<span style="background: #F0FDF4; color: #16A34A; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px;">pH {self.actual_ph:.2f} @ {self.temperature_celsius:g}°C</span>'
            f'</div>'
            f'<table style="width: 100%; border-collapse: collapse; font-size: 12.5px; margin-bottom: 8px;">'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Ionic Strength (I)</td><td style="text-align: right; font-weight: 600;">{self.ionic_strength_m:.4f} M</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Buffer Capacity (β)</td><td style="text-align: right; font-weight: 600;">{self.buffer_capacity_beta:.4f} M/pH</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Free [Mg²⁺]</td><td style="text-align: right; font-weight: 600; color: #2563EB;">{self.free_mg_conc_m * 1000.0:.3f} mM</td></tr>'
            f'<tr style="border-bottom: 1px solid #F1F5F9;"><td style="padding: 3px 0; color: #64748B;">Free [Ca²⁺]</td><td style="text-align: right; font-weight: 600; color: #2563EB;">{self.free_ca_conc_m * 1000.0:.3f} mM</td></tr>'
            f'<tr><td style="padding: 3px 0; color: #64748B;">Free [ATP]</td><td style="text-align: right; font-weight: 600;">{self.free_atp_conc_m * 1000.0:.3f} mM</td></tr>'
            f'</table>'
            f'{"<table style=\'width: 100%; border-collapse: collapse; font-size: 11.5px; background: #F8FAFC; border-radius: 4px;\'>" + precip_rows + "</table>" if precip_rows else ""}'
            f'</div>'
        )

# Baseline recipes normalized to 1000 mL (1.0 L)
BUFFER_CATALOG: Dict[str, Dict[str, Any]] = {
    "50X_TAE": {
        "name": "50X TAE Buffer (Tris-Acetate-EDTA)",
        "ph": "Approx. 8.3 (do not adjust)",
        "storage": "Room temperature (stable for >1 year)",
        "safety": "Glacial acetic acid is corrosive. Handle in fume hood.",
        "components": [
            ("Tris base", 242.0, "g", "2.0 M", "MW 121.14"),
            ("Glacial acetic acid", 57.1, "mL", "1.0 M", "17.4 M pure stock"),
            ("0.5 M EDTA (pH 8.0)", 100.0, "mL", "50 mM", "-"),
        ],
        "steps": [
            "Dissolve Tris base in ~700 mL deionized water.",
            "Carefully add 57.1 mL glacial acetic acid and 100 mL 0.5 M EDTA (pH 8.0).",
            "Bring final volume to 1000 mL with deionized water.",
            "Dilute 1:50 with water to prepare 1X working buffer for agarose gels (40 mM Tris, 20 mM Acetic acid, 1 mM EDTA)."
        ]
    },
    "10X_TBE": {
        "name": "10X TBE Buffer (Tris-Borate-EDTA)",
        "ph": "Approx. 8.3 (do not adjust)",
        "storage": "Room temperature (discard if white borate precipitate forms)",
        "safety": "Boric acid is a reproductive toxicant. Weigh with caution.",
        "components": [
            ("Tris base", 108.0, "g", "890 mM", "MW 121.14"),
            ("Boric acid", 55.0, "g", "890 mM", "MW 61.83"),
            ("0.5 M EDTA (pH 8.0)", 40.0, "mL", "20 mM", "-"),
        ],
        "steps": [
            "Dissolve Tris base and Boric acid in ~800 mL deionized water with magnetic stirring.",
            "Add 40 mL 0.5 M EDTA (pH 8.0).",
            "Bring final volume to 1000 mL with deionized water.",
            "Dilute 1:10 with water to prepare 1X working buffer for PAGE or high-voltage agarose runs."
        ]
    },
    "10X_PBS": {
        "name": "10X Phosphate-Buffered Saline (PBS)",
        "ph": "7.4 ± 0.1 (adjust with HCl/NaOH if needed)",
        "storage": "Room temperature or 4°C (autoclave for cell culture sterility)",
        "safety": "Standard laboratory safety practices.",
        "components": [
            ("NaCl", 80.0, "g", "1.37 M", "MW 58.44"),
            ("KCl", 2.0, "g", "27 mM", "MW 74.55"),
            ("Na2HPO4 (anhydrous)", 14.4, "g", "100 mM", "MW 141.96"),
            ("KH2PO4", 2.4, "g", "18 mM", "MW 136.09"),
        ],
        "steps": [
            "Dissolve all salts in ~800 mL deionized water.",
            "Adjust pH to 7.4 using concentrated HCl (approx. 2-3 mL).",
            "Bring final volume to 1000 mL with deionized water.",
            "Dilute 1:10 with water to obtain 1X PBS (137 mM NaCl, 2.7 mM KCl, 10 mM Na2HPO4, 1.8 mM KH2PO4, pH 7.4)."
        ]
    },
    "1M_TRIS": {
        "name": "1 M Tris-HCl Stock Solution (pH 8.0 or 7.5)",
        "ph": "8.0 (or user-desired 7.5)",
        "storage": "Room temperature (autoclaved)",
        "safety": "Exothermic upon concentrated HCl addition; handle in fume hood.",
        "components": [
            ("Tris base", 121.14, "g", "1.0 M", "MW 121.14"),
            ("Concentrated HCl (~37%)", 42.0, "mL", "pH adjustment", "~12 M stock"),
        ],
        "steps": [
            "Dissolve 121.14 g Tris base in ~800 mL deionized water.",
            "Allow temperature to equilibrate to 25°C (Tris pH is temperature dependent, ~ -0.03 pH units/°C).",
            "Adjust pH to 8.0 by slowly adding concentrated HCl (~42 mL for pH 8.0; ~65 mL for pH 7.5).",
            "Bring final volume to 1000 mL with deionized water and autoclave."
        ]
    },
    "0.5M_EDTA": {
        "name": "0.5 M EDTA Stock Solution (pH 8.0)",
        "ph": "8.0 (strictly required for dissolution)",
        "storage": "Room temperature",
        "safety": "NaOH addition produces heat. Wear eye protection.",
        "components": [
            ("Disodium EDTA·2H2O", 186.1, "g", "0.5 M", "MW 372.24"),
            ("NaOH pellets", 20.0, "g", "pH adjustment", "~500 mM"),
        ],
        "steps": [
            "Add 186.1 g Na2EDTA·2H2O to ~700 mL deionized water on a magnetic stirrer.",
            "NOTE: EDTA will NOT dissolve until pH approaches 8.0!",
            "Add ~18-20 g NaOH pellets slowly; as pH rises above 7.5, EDTA will rapidly dissolve.",
            "Fine-tune pH to 8.0 with 5 M NaOH solution.",
            "Bring final volume to 1000 mL with water and autoclave."
        ]
    },
    "1X_TE": {
        "name": "1X TE Buffer (10 mM Tris, 1 mM EDTA, pH 8.0)",
        "ph": "8.0",
        "storage": "Room temperature or 4°C",
        "safety": "Non-hazardous.",
        "components": [
            ("1 M Tris-HCl (pH 8.0)", 10.0, "mL", "10 mM", "Stock"),
            ("0.5 M EDTA (pH 8.0)", 2.0, "mL", "1 mM", "Stock"),
        ],
        "steps": [
            "Add 10 mL 1 M Tris-HCl (pH 8.0) and 2 mL 0.5 M EDTA (pH 8.0) to ~900 mL water.",
            "Bring volume to 1000 mL with deionized water.",
            "Autoclave or filter sterilize (0.22 µm)."
        ]
    },
    "6X_LOADING_DYE": {
        "name": "6X DNA Loading Dye (Bromophenol Blue / Xylene Cyanol)",
        "ph": "Neutral",
        "storage": "4°C or -20°C",
        "safety": "Powder dye can stain clothing and skin.",
        "components": [
            ("Bromophenol blue", 2.5, "g", "0.25% w/v", "Migrates ~300 bp in 1% agarose"),
            ("Xylene cyanol FF", 2.5, "g", "0.25% w/v", "Migrates ~4000 bp in 1% agarose"),
            ("Glycerol (100%)", 300.0, "mL", "30% v/v", "Density agent"),
        ],
        "steps": [
            "Dissolve dyes in ~500 mL deionized water.",
            "Add 300 mL glycerol.",
            "Bring volume to 1000 mL with deionized water.",
            "Aliquot into 1.5 mL tubes and store at -20°C."
        ]
    },
    "LB_BROTH": {
        "name": "LB Broth (Lennox / Miller Formulation)",
        "ph": "7.0 ± 0.2",
        "storage": "Room temperature (autoclaved)",
        "safety": "Autoclave safety rules apply.",
        "components": [
            ("Tryptone", 10.0, "g", "1% w/v", "Peptide source"),
            ("Yeast Extract", 5.0, "g", "0.5% w/v", "Vitamins & cofactors"),
            ("NaCl", 10.0, "g", "170 mM", "Miller = 10 g/L, Lennox = 5 g/L"),
        ],
        "steps": [
            "Dissolve tryptone, yeast extract, and NaCl in ~900 mL deionized water.",
            "Adjust pH to 7.0 with 1 M NaOH if needed.",
            "Bring volume to 1000 mL with water.",
            "Autoclave at 121°C (15 psi) for 20 minutes with loosened cap."
        ]
    },
    "10X_HEPES_IVT": {
        "name": "10X HEPES-KOH IVT Reaction Buffer (pH 7.5 at 37°C)",
        "ph": "7.67 at 25°C (compensates to pH 7.50 at 37°C with KOH)",
        "storage": "-20°C in single-use aliquots (protect DTT from oxidation)",
        "safety": "KOH is caustic. Wear gloves and eye protection.",
        "components": [
            ("HEPES free acid", 95.32, "g", "400 mM", "MW 238.30"),
            ("5 M KOH solution", 45.5, "mL", "~227 mM", "Titrate to pH 7.67 at 25°C"),
            ("DTT (Dithiothreitol)", 15.42, "g", "100 mM", "MW 154.25"),
            ("Spermidine trihydrochloride", 5.09, "g", "20 mM", "MW 254.63"),
            ("Triton X-100", 1.0, "mL", "0.1% (v/v)", "Surfactant to prevent wall loss"),
        ],
        "steps": [
            "Dissolve HEPES free acid in ~700 mL nuclease-free water.",
            "Titrate with ~45 mL 5 M KOH at room temperature (25°C) to exactly pH 7.67 (drops to pH 7.50 at 37°C).",
            "Add DTT, spermidine-3HCl, and Triton X-100; mix until completely dissolved.",
            "Bring to 1000 mL with nuclease-free water.",
            "Filter sterilize through 0.22 µm PES membrane, aliquot into 1.5 mL tubes, and store at -20°C.",
        ]
    }
}

def calculate_buffer_recipe(
    buffer_key: str,
    target_volume_ml: float = 1000.0,
) -> BufferRecipeResult:
    """Calculate scaled chemical masses and stock volumes to prepare any laboratory buffer."""
    if target_volume_ml <= 0:
        raise ValueError("Target volume must be positive.")

    b_key = buffer_key.upper().replace("-", "_").replace(" ", "_")
    matched = None
    for k, v in BUFFER_CATALOG.items():
        if k == b_key or b_key in k:
            matched = (k, v)
            break

    if not matched:
        available = list(BUFFER_CATALOG.keys())
        raise KeyError(f"Buffer '{buffer_key}' not found. Available: {available}")

    k_id, data = matched
    scale = target_volume_ml / 1000.0

    scaled_components: List[BufferComponent] = []
    for name, base_amt, unit, molarity, cas in data["components"]:
        scaled_amt = round(base_amt * scale, 3 if unit == "g" and base_amt * scale < 1.0 else 2)
        scaled_components.append(BufferComponent(
            name=name,
            amount=scaled_amt,
            unit=unit,
            molar_concentration=molarity,
            cas_or_mw=cas,
        ))

    # Scale steps text
    scaled_steps = []
    for step in data["steps"]:
        # If step mentions 1000 mL or specific baseline amounts, add note
        scaled_steps.append(step)

    return BufferRecipeResult(
        buffer_id=k_id,
        name=data["name"],
        target_volume_ml=target_volume_ml,
        components=scaled_components,
        ph_specification=data["ph"],
        preparation_steps=scaled_steps,
        storage_conditions=data["storage"],
        safety_notes=data.get("safety"),
    )


@dataclass(frozen=True)
class NTPNeutralizationResult:
    initial_volume_ml: float
    initial_conc_mm: float
    target_volume_ml: float
    target_conc_mm: float
    target_ph: float
    ntp_species: str
    starting_form: str
    total_ntp_mmol: float
    naoh_equivalents: float
    naoh_mmol: float
    naoh_volume_ul: Dict[str, float]
    water_volume_ml: float
    warnings: Tuple[str, ...]
    logic_checks: Tuple[str, ...]
    preparation_steps: Tuple[str, ...]

    def __post_init__(self):
        for f in ("warnings", "logic_checks", "preparation_steps"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))


def calculate_ntp_ph_adjustment(
    initial_volume_ml: float = 4.0,
    initial_conc_mm: float = 100.0,
    target_volume_ml: float = 16.0,
    target_conc_mm: Optional[float] = 25.0,
    target_ph: float = 7.5,
    starting_form: str = "disodium_salt",
    ntp_species: str = "equimolar_mix",
    naoh_stock_m: float = 5.0,
) -> NTPNeutralizationResult:
    """Calculate the required NaOH volume, water diluent, and wet-lab bench protocol for adjusting NTP solutions to target pH.

    Parameters
    ----------
    initial_volume_ml : float
        Starting volume of NTP stock in mL (e.g. 4.0 mL).
    initial_conc_mm : float
        Starting molar concentration of NTP stock in mM (e.g. 100.0 mM).
    target_volume_ml : float
        Desired final volume in mL (e.g. 16.0 mL).
    target_conc_mm : float, optional
        Desired final concentration in mM (default: 25.0 mM).
    target_ph : float
        Desired target pH (default: 7.5).
    starting_form : str
        Form of starting material: 'pre_neutralized', 'disodium_salt', or 'free_acid'.
    ntp_species : str
        Nucleotide type: 'equimolar_mix', 'ATP', 'CTP', 'GTP', 'UTP'.
    naoh_stock_m : float
        Concentration of NaOH stock in M (default: 5.0 M).
    """
    if initial_volume_ml <= 0 or initial_conc_mm <= 0 or target_volume_ml <= 0:
        raise ValueError("Volumes and concentrations must be strictly positive.")
    if target_volume_ml < initial_volume_ml:
        raise ValueError(f"Target volume ({target_volume_ml} mL) cannot be less than initial volume ({initial_volume_ml} mL) for dilution.")
    if target_ph < 3.0 or target_ph > 11.0:
        raise ValueError("Target pH must be between 3.0 and 11.0.")

    expected_target_conc = (initial_volume_ml * initial_conc_mm) / target_volume_ml
    if target_conc_mm is not None:
        if abs(expected_target_conc - target_conc_mm) / expected_target_conc > 0.01:
            raise ValueError(
                f"Mass balance inconsistency: {initial_volume_ml} mL of {initial_conc_mm} mM dilutes to "
                f"{expected_target_conc:.2f} mM in {target_volume_ml} mL, but requested {target_conc_mm} mM."
            )
    else:
        target_conc_mm = expected_target_conc

    total_ntp_mmol = (initial_volume_ml * initial_conc_mm) / 1000.0

    valid_forms = {"pre_neutralized", "neutralized", "disodium_salt", "sodium_salt", "free_acid"}
    norm_form = starting_form.lower().strip()
    if norm_form not in valid_forms:
        raise ValueError(f"Unknown starting form '{starting_form}'. Must be one of: {sorted(list(valid_forms))}")

    norm_species = ntp_species.strip()
    valid_species = {"equimolar_mix", "ATP", "CTP", "GTP", "UTP"}
    if norm_species not in valid_species:
        raise ValueError(f"Unknown NTP species '{ntp_species}'. Must be one of: {sorted(list(valid_species))}")

    # Gamma phosphate deprotonation fraction: pKa ~ 6.65
    alpha_gamma = 10.0 ** (target_ph - 6.65) / (1.0 + 10.0 ** (target_ph - 6.65))

    if norm_form in ("pre_neutralized", "neutralized"):
        eq = 0.0
    elif norm_form in ("disodium_salt", "sodium_salt"):
        eq_map = {
            "ATP": alpha_gamma + 0.88,
            "CTP": alpha_gamma + 0.95,
            "GTP": alpha_gamma + 0.07,
            "UTP": alpha_gamma + 0.02,
            "equimolar_mix": alpha_gamma + (0.88 + 0.95 + 0.07 + 0.02) / 4.0,
        }
        eq = eq_map[norm_species]
    else:  # free_acid
        eq = 3.0 + alpha_gamma

    naoh_mmol = total_ntp_mmol * eq

    naoh_volume_ul = {
        "10M": round((naoh_mmol / 10.0) * 1000.0, 1),
        "5M": round((naoh_mmol / 5.0) * 1000.0, 1),
        "1M": round((naoh_mmol / 1.0) * 1000.0, 1),
        "0.5M": round((naoh_mmol / 0.5) * 1000.0, 1),
    }

    used_naoh_vol_ml = (naoh_mmol / naoh_stock_m) if naoh_stock_m > 0 else 0.0
    max_diluent_avail_ml = target_volume_ml - initial_volume_ml
    water_vol_ml = max(0.0, max_diluent_avail_ml - used_naoh_vol_ml)

    warnings: List[str] = []
    logic_checks: List[str] = []

    if norm_form in ("pre_neutralized", "neutralized"):
        logic_checks.append(
            "COMMERCIAL PRE-NEUTRALIZED STOCK: Most commercial 100 mM NTPs (e.g., NEB, Promega, ThermoFisher) "
            "are already supplied at pH 7.0–7.5. Diluting with water preserves the conjugate base/acid ratio; "
            "therefore, 0 µL NaOH should be added."
        )
        warnings.append(
            "CRITICAL: Do NOT add NaOH to pre-neutralized commercial NTPs. Adding NaOH will cause over-alkalization (pH > 9.0), "
            "leading to rapid CTP deamination and alkaline phosphodiester cleavage."
        )
    else:
        logic_checks.append(
            f"STARTING STOCK STATE: Stock form is '{norm_form}' (initial pH ~{'3.0-3.5' if 'disodium' in norm_form else '1.5-2.0'}). "
            f"Titration requires {eq:.3f} equivalents of OH- per mole of NTP ({naoh_mmol:.3f} mmol total OH-)."
        )

    if used_naoh_vol_ml >= max_diluent_avail_ml:
        warnings.append(
            f"VOLUME OVERSHOOT WARNING: The volume of {naoh_stock_m} M NaOH ({used_naoh_vol_ml:.2f} mL) exceeds the available "
            f"diluent budget ({max_diluent_avail_ml:.2f} mL). Use a more concentrated NaOH stock (e.g., 5 M or 10 M)."
        )
    else:
        logic_checks.append(
            f"VOLUME BALANCE CHECK: Initial NTP ({initial_volume_ml} mL) + NaOH ({used_naoh_vol_ml:.3f} mL using {naoh_stock_m} M) + "
            f"Water ({water_vol_ml:.3f} mL) = {target_volume_ml} mL final volume."
        )

    logic_checks.append(
        "ORDER OF PIPETTING: Never add the full 12.0 mL of water before pH adjustment. Adding 12.0 mL of water immediately brings "
        "the volume to 16.0 mL; subsequent addition of NaOH (or HCl for back-titration) will cause volume overshooting and dilute "
        "the NTPs below 25.0 mM."
    )

    if norm_form not in ("pre_neutralized", "neutralized"):
        logic_checks.append(
            f"TITRATION DYNAMICS: Near pH 7.5, buffer capacity of the gamma-phosphate (pKa ~ 6.65) is decreasing. "
            f"Add ~80% of theoretical base ({naoh_volume_ul['5M'] * 0.8:.1f} µL of 5 M NaOH), then titrate dropwise with dilute "
            f"0.5 M or 1 M NaOH under micro-electrode monitoring to avoid overshooting."
        )

    if target_ph > 8.0:
        warnings.append(
            f"HIGH pH WARNING: Target pH {target_ph} exceeds 8.0. Elevated pH accelerates CTP deamination to UTP and base-catalyzed "
            "hydrolysis of triphosphate bonds."
        )
    elif target_ph < 6.8:
        warnings.append(
            f"LOW pH WARNING: Target pH {target_ph} is below 6.8. Low pH risks apurinic cleavage and reduces T7 RNA polymerase activity."
        )

    steps = [
        f"1. Measure {initial_volume_ml:.2f} mL of 100 mM {norm_species} stock into a sterile 50 mL polypropylene tube or beaker.",
    ]
    if norm_form in ("pre_neutralized", "neutralized"):
        steps.extend([
            f"2. Add exactly {max_diluent_avail_ml:.2f} mL of nuclease-free water.",
            "3. Mix thoroughly by gentle inversion or pipetting.",
            f"4. Verify final volume is {target_volume_ml:.2f} mL and check pH is 7.5 ± 0.1 using a calibrated micro-pH probe.",
            "5. Aliquot into single-use microcentrifuge tubes and store at -20°C or -80°C."
        ])
    else:
        steps.extend([
            f"2. Add ~8.0–10.0 mL of nuclease-free water (reserving ~2–4 mL for titration and final QS).",
            f"3. Add ~80% of estimated 5 M NaOH ({naoh_volume_ul['5M'] * 0.8:.1f} µL) while stirring.",
            "4. Insert a calibrated micro-pH probe (calibrated at pH 4.0, 7.0, and 10.0).",
            "5. Slowly titrate dropwise using 0.5 M or 1.0 M NaOH until pH reaches exactly 7.50 ± 0.05.",
            f"6. Carefully bring final volume to exactly {target_volume_ml:.2f} mL with nuclease-free water in a volumetric flask or graduated cylinder.",
            "7. Aliquot into nuclease-free tubes and flash-freeze for storage at -20°C or -80°C."
        ])

    return NTPNeutralizationResult(
        initial_volume_ml=initial_volume_ml,
        initial_conc_mm=initial_conc_mm,
        target_volume_ml=target_volume_ml,
        target_conc_mm=target_conc_mm,
        target_ph=target_ph,
        ntp_species=norm_species,
        starting_form=norm_form,
        total_ntp_mmol=round(total_ntp_mmol, 4),
        naoh_equivalents=round(eq, 3),
        naoh_mmol=round(naoh_mmol, 4),
        naoh_volume_ul=naoh_volume_ul,
        water_volume_ml=round(water_vol_ml, 3),
        warnings=warnings,
        logic_checks=logic_checks,
        preparation_steps=steps,
    )


def calculate_tris_temperature_shift(
    measured_ph: float,
    target_temp_c: float,
    measured_temp_c: float = 25.0,
    dpka_dt: float = -0.030,
) -> float:
    """Calculate expected pH shift for Tris buffers across temperatures.

    Parameters
    ----------
    measured_ph : float
        pH measured at reference temperature (e.g. 8.00).
    target_temp_c : float
        Operating temperature in Celsius (e.g. 4.0°C for cold-room, 37.0°C for incubation).
    measured_temp_c : float, optional
        Temperature in Celsius at measurement (default is 25.0°C).
    dpka_dt : float, optional
        Temperature coefficient of Tris pKa (typically -0.028 to -0.031 pH units / °C, default -0.030).

    Returns
    -------
    float
        Expected shifted pH at target temperature.
    """
    delta_t = target_temp_c - measured_temp_c
    shifted = measured_ph + (dpka_dt * delta_t)
    return round(shifted, 2)


def register_custom_buffer(buffer_key: str, recipe_data: Dict[str, Any]) -> None:
    """Register a custom or proprietary laboratory buffer recipe into the global catalog."""
    key = buffer_key.upper().replace("-", "_").replace(" ", "_")
    required_keys = {"name", "ph", "storage", "components", "steps"}
    missing = required_keys - set(recipe_data.keys())
    if missing:
        raise ValueError(f"Custom buffer recipe missing required fields: {missing}")
    BUFFER_CATALOG[key] = recipe_data


@dataclass(frozen=True)
class HepesIVTBufferResult:
    target_volume_ml: float
    stock_multiplier: int
    hepes_conc_mm: float
    target_ph_37c: float
    preparation_ph_25c: float
    components: Tuple[BufferComponent, ...]
    reagent_masses_and_volumes: Dict[str, float]
    buffering_capacity_comparison: str
    preparation_steps: Tuple[str, ...]

    def __post_init__(self):
        for f in ("components", "preparation_steps"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))


def calculate_hepes_ivt_buffer(
    target_volume_ml: float = 50.0,
    stock_multiplier: int = 10,
    target_ph_37c: float = 7.50,
    koh_stock_m: float = 5.0,
) -> HepesIVTBufferResult:
    """Calculate preparation recipe for 10X (or 5X) HEPES-KOH in vitro transcription reaction buffer.

    Compensates for the temperature shift of HEPES (dpKa/dT = -0.014 pH/°C) so the buffer reaches
    exactly target pH at 37°C reaction temperature.

    Parameters
    ----------
    target_volume_ml : float
        Final volume of buffer stock to prepare in mL (default: 50.0 mL).
    stock_multiplier : int
        Concentration multiplier (default: 10 for 10X stock, i.e., 400 mM HEPES / 40 mM 1X).
    target_ph_37c : float
        Desired pH at 37°C reaction temperature (default: 7.50).
    koh_stock_m : float
        Molarity of KOH stock used for titrating pH (default: 5.0 M KOH).
    """
    if target_volume_ml <= 0:
        raise ValueError("Target volume must be positive.")
    if stock_multiplier <= 0:
        raise ValueError("Stock multiplier must be positive.")

    vol_l = target_volume_ml / 1000.0

    # 1X concentrations: 40 mM HEPES, 10 mM DTT, 2 mM Spermidine, 0.01% Triton X-100
    hepes_mm = 40.0 * stock_multiplier
    dtt_mm = 10.0 * stock_multiplier
    sperm_mm = 2.0 * stock_multiplier
    triton_pct = 0.01 * stock_multiplier

    mass_hepes = round(vol_l * (hepes_mm * 1e-3) * 238.30, 3)
    mass_dtt = round(vol_l * (dtt_mm * 1e-3) * 154.25, 3)
    mass_sperm = round(vol_l * (sperm_mm * 1e-3) * 254.63, 3)
    vol_triton_ul = round((triton_pct / 100.0) * target_volume_ml * 1000.0, 1)

    # Temperature shift: HEPES dpKa/dT = -0.014 / °C
    # Target at 37°C -> prepare at 25°C:
    # pH(25°C) = pH(37°C) - (-0.014 * (25 - 37)) = pH(37°C) + 0.168
    ph_25c = round(target_ph_37c + (0.014 * 12.0), 2)

    # KOH titration estimation (HEPES pKa at 25°C = 7.55)
    import math
    ratio = 10 ** (ph_25c - 7.55)
    alpha = ratio / (1.0 + ratio)
    moles_hepes = vol_l * (hepes_mm * 1e-3)
    moles_koh = alpha * moles_hepes
    vol_koh_ml = round((moles_koh / koh_stock_m) * 1000.0, 2)

    components = [
        BufferComponent("HEPES (free acid)", mass_hepes, "g", f"{hepes_mm:.0f} mM", "MW 238.30"),
        BufferComponent(f"{koh_stock_m:.1f} M KOH", vol_koh_ml, "mL", f"~{moles_koh/vol_l*1000:.0f} mM", f"Titrate to pH {ph_25c:.2f} at 25°C"),
        BufferComponent("DTT", mass_dtt, "g", f"{dtt_mm:.0f} mM", "MW 154.25"),
        BufferComponent("Spermidine-3HCl", mass_sperm, "g", f"{sperm_mm:.0f} mM", "MW 254.63"),
        BufferComponent("Triton X-100", vol_triton_ul, "µL", f"{triton_pct:.2f}%", "Surfactant"),
    ]

    reagents = {
        "HEPES (free acid)": mass_hepes,
        f"{koh_stock_m:.1f} M KOH": vol_koh_ml,
        "DTT": mass_dtt,
        "Spermidine-3HCl": mass_sperm,
        "Triton X-100": vol_triton_ul,
        "Nuclease-Free Water": round(target_volume_ml - vol_koh_ml, 2),
    }

    comparison = (
        "HEPES vs Tris Advantage in IVT: Tris-HCl buffer drops ~0.34 pH units when warmed from 25°C to 37°C "
        "(dpKa/dT = -0.028/°C) and lacks buffering capacity below pH 7.5. HEPES has half the temperature sensitivity "
        "(dpKa/dT = -0.014/°C) and peaks in buffer capacity at pH 7.3–7.5, maintaining enzyme activity as H+ is released during synthesis. "
        "KOH provides potassium counterions which stimulate T7 RNAP elongation (unlike inhibitory sodium)."
    )

    steps = [
        f"1. Weigh out {mass_hepes:.3f} g HEPES free acid and dissolve in ~{target_volume_ml * 0.7:.1f} mL nuclease-free water.",
        f"2. Calibrate pH meter at 25°C. Slowly add ~{vol_koh_ml:.2f} mL {koh_stock_m:.1f} M KOH while stirring until pH reaches exactly {ph_25c:.2f} (which will shift to pH {target_ph_37c:.2f} at 37°C).",
        f"3. Add {mass_dtt:.3f} g DTT, {mass_sperm:.3f} g Spermidine-3HCl, and {vol_triton_ul:.1f} µL Triton X-100. Stir until completely dissolved.",
        f"4. Bring final volume to {target_volume_ml:.1f} mL with nuclease-free water in a volumetric flask or graduated cylinder.",
        f"5. Filter sterilize through a 0.22 µm PES membrane filter. Aliquot into 1.0–1.5 mL tubes and store at -20°C (stable for >1 year; avoid freeze-thaw cycles).",
    ]

    return HepesIVTBufferResult(
        target_volume_ml=target_volume_ml,
        stock_multiplier=stock_multiplier,
        hepes_conc_mm=hepes_mm,
        target_ph_37c=target_ph_37c,
        preparation_ph_25c=ph_25c,
        components=components,
        reagent_masses_and_volumes=reagents,
        buffering_capacity_comparison=comparison,
        preparation_steps=steps,
    )


def get_custom_buffers_path() -> str:
    env_path = os.environ.get("BIOLABCALC_BUFFER_PATH")
    if env_path:
        return env_path
    try:
        home_path = os.path.expanduser("~/.biolabcalc/custom_buffers.json")
        os.makedirs(os.path.dirname(home_path), exist_ok=True)
        return home_path
    except (PermissionError, OSError):
        import tempfile
        tmp_dir = os.path.join(tempfile.gettempdir(), ".biolabcalc")
        os.makedirs(tmp_dir, exist_ok=True)
        return os.path.join(tmp_dir, "custom_buffers.json")


CUSTOM_BUFFERS_PATH = get_custom_buffers_path()


@dataclass(frozen=True)
class CustomBufferComponent:
    name: str
    comp_type: Literal["solid", "stock", "percent_w_v", "percent_v_v"]
    target_concentration_mm: Optional[float] = None
    mw_g_mol: Optional[float] = None
    stock_concentration_mm: Optional[float] = None
    target_percent: Optional[float] = None
    cas_or_notes: str = ""

    def calculate_for_1000ml(self) -> Tuple[str, float, str, str, str]:
        """Compute the baseline amount for 1000 mL and return the standard catalog tuple."""
        if self.comp_type == "solid":
            if self.mw_g_mol is None or self.target_concentration_mm is None:
                raise ValueError(f"Solid component '{self.name}' requires target_concentration_mm and mw_g_mol.")
            grams = round((self.target_concentration_mm * 1e-3) * 1.0 * self.mw_g_mol, 3)
            molar_str = f"{self.target_concentration_mm:g} mM" if self.target_concentration_mm < 1000 else f"{self.target_concentration_mm/1000:g} M"
            mw_str = f"MW {self.mw_g_mol:g}" + (f" ({self.cas_or_notes})" if self.cas_or_notes else "")
            return (self.name, grams, "g", molar_str, mw_str)

        elif self.comp_type == "stock":
            if self.stock_concentration_mm is None or self.target_concentration_mm is None:
                raise ValueError(f"Stock component '{self.name}' requires target_concentration_mm and stock_concentration_mm.")
            vol_ml = round((self.target_concentration_mm * 1000.0) / self.stock_concentration_mm, 3)
            molar_str = f"{self.target_concentration_mm:g} mM" if self.target_concentration_mm < 1000 else f"{self.target_concentration_mm/1000:g} M"
            stock_str = f"From {self.stock_concentration_mm:g} mM stock" if self.stock_concentration_mm < 1000 else f"From {self.stock_concentration_mm/1000:g} M stock"
            if self.cas_or_notes:
                stock_str += f" ({self.cas_or_notes})"
            return (self.name, vol_ml, "mL", molar_str, stock_str)

        elif self.comp_type == "percent_w_v":
            if self.target_percent is None:
                raise ValueError(f"Percent component '{self.name}' requires target_percent.")
            grams = round(self.target_percent * 10.0, 3)
            pct_str = f"{self.target_percent:g}% w/v"
            return (self.name, grams, "g", pct_str, self.cas_or_notes or "Solid dissolved w/v")

        elif self.comp_type == "percent_v_v":
            if self.target_percent is None:
                raise ValueError(f"Percent component '{self.name}' requires target_percent.")
            vol_ml = round(self.target_percent * 10.0, 3)
            pct_str = f"{self.target_percent:g}% v/v"
            return (self.name, vol_ml, "mL", pct_str, self.cas_or_notes or "Liquid stock v/v")

        else:
            raise ValueError(f"Unknown component type '{self.comp_type}'.")


class CustomBufferBuilder:
    """Fluent, user-friendly builder for constructing, scaling, and registering custom laboratory buffers."""

    def __init__(
        self,
        name: str,
        ph: str = "7.5",
        storage: str = "Room temperature or 4°C",
        safety: Optional[str] = None,
    ):
        self.name = name.strip()
        self.ph = ph.strip()
        self.storage = storage.strip()
        self.safety = safety or "Standard laboratory chemical safety."
        self.components: List[CustomBufferComponent] = []
        self.steps: List[str] = []

    def add_solid(self, name: str, target_conc_mm: float, mw_g_mol: float, cas_or_notes: str = "") -> CustomBufferBuilder:
        """Add a solid chemical component defined by molecular weight (g/mol) and desired mM."""
        self.components.append(CustomBufferComponent(
            name=name.strip(),
            comp_type="solid",
            target_concentration_mm=float(target_conc_mm),
            mw_g_mol=float(mw_g_mol),
            cas_or_notes=cas_or_notes.strip(),
        ))
        return self

    def add_liquid_stock(self, name: str, target_conc_mm: float, stock_conc_mm: float, notes: str = "") -> CustomBufferBuilder:
        """Add a component prepared by diluting a concentrated liquid stock (e.g. 5 M NaCl, 1 M Tris)."""
        self.components.append(CustomBufferComponent(
            name=name.strip(),
            comp_type="stock",
            target_concentration_mm=float(target_conc_mm),
            stock_concentration_mm=float(stock_conc_mm),
            cas_or_notes=notes.strip(),
        ))
        return self

    def add_percent(self, name: str, target_percent: float, is_volume: bool = True, notes: str = "") -> CustomBufferBuilder:
        """Add a percentage component (e.g. 0.1% v/v Triton X-100 or 1% w/v BSA)."""
        self.components.append(CustomBufferComponent(
            name=name.strip(),
            comp_type="percent_v_v" if is_volume else "percent_w_v",
            target_percent=float(target_percent),
            cas_or_notes=notes.strip(),
        ))
        return self

    def add_step(self, step: str) -> CustomBufferBuilder:
        """Add a step-by-step preparation instruction."""
        if step.strip():
            self.steps.append(step.strip())
        return self

    def to_catalog_entry(self) -> Dict[str, Any]:
        """Convert custom buffer definition into standard BUFFER_CATALOG entry."""
        if not self.components:
            raise ValueError(f"Custom buffer '{self.name}' must have at least one component.")

        cat_components = [c.calculate_for_1000ml() for c in self.components]

        steps = list(self.steps)
        if not steps:
            steps = [
                f"Dissolve components in ~70% final volume of deionized or nuclease-free water.",
                f"Adjust pH to {self.ph} using appropriate acid/base titrant (e.g. HCl, NaOH, KOH).",
                "Bring to final volume with water.",
                "Filter sterilize (0.22 µm) or autoclave as appropriate for components.",
            ]

        return {
            "name": self.name,
            "ph": self.ph,
            "storage": self.storage,
            "safety": self.safety,
            "components": cat_components,
            "steps": steps,
        }

    def register(self, buffer_key: Optional[str] = None) -> str:
        """Register into global BUFFER_CATALOG so calculate_buffer_recipe works immediately."""
        key = (buffer_key or self.name).upper().replace("-", "_").replace(" ", "_")
        recipe_data = self.to_catalog_entry()
        register_custom_buffer(key, recipe_data)
        return key

    def build(self, target_volume_ml: float = 1000.0) -> BufferRecipeResult:
        """Calculate scaled chemical masses and pipetting recipe for any volume."""
        key = self.register()
        return calculate_buffer_recipe(key, target_volume_ml=target_volume_ml)

    def save(self, filepath: Optional[str] = None) -> str:
        """Save this custom buffer to persistent disk storage."""
        return save_custom_buffer_to_disk(self, filepath=filepath)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ph": self.ph,
            "storage": self.storage,
            "safety": self.safety,
            "components": [asdict(c) for c in self.components],
            "steps": self.steps,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CustomBufferBuilder:
        builder = cls(
            name=data["name"],
            ph=data.get("ph", "7.5"),
            storage=data.get("storage", "Room temperature or 4°C"),
            safety=data.get("safety"),
        )
        for c in data.get("components", []):
            builder.components.append(CustomBufferComponent(**c))
        builder.steps = data.get("steps", [])
        return builder


def save_custom_buffer_to_disk(builder: CustomBufferBuilder, filepath: Optional[str] = None) -> str:
    """Save a custom buffer definition to JSON disk storage with atomic replacement."""
    path = filepath or CUSTOM_BUFFERS_PATH
    dir_name = os.path.dirname(os.path.abspath(path))
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    key = builder.name.upper().replace("-", "_").replace(" ", "_")
    data[key] = builder.to_dict()

    temp_fd, temp_file = tempfile.mkstemp(dir=dir_name, prefix=".tmp_buffer_", suffix=".json")
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, path)
    except Exception:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
        raise

    # Register into runtime catalog
    builder.register(key)
    return path


def load_custom_buffers_from_disk(filepath: Optional[str] = None) -> List[CustomBufferBuilder]:
    """Load and register all persistent custom buffers from disk into the runtime BUFFER_CATALOG."""
    path = filepath or CUSTOM_BUFFERS_PATH
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    loaded: List[CustomBufferBuilder] = []
    for key, b_data in data.items():
        try:
            builder = CustomBufferBuilder.from_dict(b_data)
            builder.register(key)
            loaded.append(builder)
        except Exception:
            continue
    return loaded


def list_custom_buffers(filepath: Optional[str] = None) -> List[str]:
    """Return a list of all registered custom buffer names."""
    path = filepath or CUSTOM_BUFFERS_PATH
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return list(data.keys())
    except Exception:
        return []


def delete_custom_buffer(name_or_key: str, filepath: Optional[str] = None) -> bool:
    """Delete a custom buffer from disk storage and runtime catalog with atomic replacement."""
    key = name_or_key.upper().replace("-", "_").replace(" ", "_")
    path = filepath or CUSTOM_BUFFERS_PATH
    if not os.path.exists(path):
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if key in data:
            del data[key]
            dir_name = os.path.dirname(os.path.abspath(path))
            temp_fd, temp_file = tempfile.mkstemp(dir=dir_name, prefix=".tmp_buffer_", suffix=".json")
            try:
                with open(temp_fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_file, path)
            except Exception:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass
                raise
            if key in BUFFER_CATALOG:
                del BUFFER_CATALOG[key]
            return True
        return False
    except Exception:
        return False


def create_custom_buffer(
    name: str,
    components: List[Dict[str, Any]],
    ph: str = "7.5",
    target_volume_ml: float = 1000.0,
    storage: str = "Room temperature or 4°C",
    safety: Optional[str] = None,
    steps: Optional[List[str]] = None,
    save_to_disk: bool = False,
) -> BufferRecipeResult:
    """One-line helper to create, register, scale, and optionally persist a custom buffer.

    Parameters
    ----------
    name : str
        Buffer name (e.g. 'HEPES-NaCl Lysis Buffer').
    components : List[Dict[str, Any]]
        List of component dictionaries. Each dictionary can specify:
        - name: str (e.g. 'HEPES', 'NaCl', 'Triton X-100')
        - type: 'solid', 'stock', 'percent_w_v', 'percent_v_v'
        - conc_mm or target_percent: float
        - mw: float (required for solid)
        - stock_mm: float (required for stock)
        - notes: str (optional)
    ph : str
        Target pH (e.g. '7.5').
    target_volume_ml : float
        Target volume to scale pipetting recipe to.
    storage : str
        Storage conditions.
    safety : str, optional
        Safety notes.
    steps : List[str], optional
        Custom preparation steps.
    save_to_disk : bool
        If True, persists buffer to ~/.biolabcalc/custom_buffers.json.
    """
    builder = CustomBufferBuilder(name=name, ph=ph, storage=storage, safety=safety)
    for c in components:
        c_type = c.get("type", "solid").lower()
        c_name = c["name"]
        notes = c.get("notes", "")

        if c_type == "solid":
            conc = c.get("conc_mm", c.get("conc", 0.0))
            mw = c.get("mw", c.get("mw_g_mol", 0.0))
            builder.add_solid(c_name, target_conc_mm=conc, mw_g_mol=mw, cas_or_notes=notes)
        elif c_type in ("stock", "liquid"):
            conc = c.get("conc_mm", c.get("conc", 0.0))
            stock_conc = c.get("stock_mm", c.get("stock_conc_mm", 0.0))
            builder.add_liquid_stock(c_name, target_conc_mm=conc, stock_conc_mm=stock_conc, notes=notes)
        elif "percent" in c_type or "%" in c_type:
            pct = c.get("percent", c.get("target_percent", 0.0))
            is_vol = "v" in c_type or c.get("is_volume", True)
            builder.add_percent(c_name, target_percent=pct, is_volume=is_vol, notes=notes)
        else:
            raise ValueError(f"Unknown component type '{c_type}' for '{c_name}'. Use 'solid', 'stock', or 'percent'.")

    if steps:
        for s in steps:
            builder.add_step(s)

    if save_to_disk:
        builder.save()

    return builder.build(target_volume_ml=target_volume_ml)


# Auto-load persistent custom buffers if file exists
try:
    load_custom_buffers_from_disk()
except Exception:
    pass


# ============================================================================
# Multi-Metal Competitive Buffer Speciation Solver
# ============================================================================

def _parse_conc_string(val_str: str) -> float:
    """Parse a concentration string such as '50mM', '5uM', '10µM', '0.1M' into Molar."""
    s = str(val_str).strip()
    s_lower = s.lower()
    if s_lower.endswith("um") or s_lower.endswith("µm"):
        return float(s[:-2].strip()) * 1e-6
    elif s_lower.endswith("mm"):
        return float(s[:-2].strip()) * 1e-3
    elif s_lower.endswith("nm"):
        return float(s[:-2].strip()) * 1e-9
    elif s_lower.endswith("m"):
        return float(s[:-1].strip())
    else:
        try:
            val = float(s)
            # Default interpretation: if val >= 0.5, could be mM or M; standard lab notation without unit is mM if >= 1
            return val * 1e-3 if val >= 0.5 else val
        except ValueError:
            raise ValueError(f"Unable to parse concentration value: '{val_str}'")


# Standard thermodynamic database for buffer components at 25 °C
_BUFFER_PKA_DB: Dict[str, Dict[str, Any]] = {
    "tris": {
        "pka": (8.06,),
        "dpka_dt": -0.028,
        "charges": (1, 0),
        "is_base": True,
    },
    "hepes": {
        "pka": (7.55,),
        "dpka_dt": -0.014,
        "charges": (0, -1),
        "is_base": False,
    },
    "mops": {
        "pka": (7.20,),
        "dpka_dt": -0.011,
        "charges": (0, -1),
        "is_base": False,
    },
    "pipes": {
        "pka": (6.76,),
        "dpka_dt": -0.0085,
        "charges": (-1, -2),
        "is_base": False,
    },
    "mes": {
        "pka": (6.15,),
        "dpka_dt": -0.011,
        "charges": (0, -1),
        "is_base": False,
    },
    "phosphate": {
        "pka": (2.15, 7.20, 12.35),
        "dpka_dt": -0.0028,
        "charges": (0, -1, -2, -3),
        "is_base": False,
    },
    "pbs": {
        "pka": (2.15, 7.20, 12.35),
        "dpka_dt": -0.0028,
        "charges": (0, -1, -2, -3),
        "is_base": False,
    },
    "atp": {
        "pka": (6.5,),
        "dpka_dt": -0.001,
        "charges": (-3, -4),
        "is_base": False,
        "log_k_mg": 4.0,
        "log_k_ca": 3.9,
    },
    "gtp": {
        "pka": (6.5,),
        "dpka_dt": -0.001,
        "charges": (-3, -4),
        "is_base": False,
        "log_k_mg": 4.0,
        "log_k_ca": 3.9,
    },
    "dntp": {
        "pka": (6.5,),
        "dpka_dt": -0.001,
        "charges": (-3, -4),
        "is_base": False,
        "log_k_mg": 4.0,
        "log_k_ca": 3.9,
    },
    "egta": {
        "pka": (2.0, 2.68, 8.85, 9.47),
        "dpka_dt": -0.011,
        "charges": (0, -1, -2, -3, -4),
        "is_base": False,
        "log_k_mg": 5.2,
        "log_k_ca": 11.0,
    },
    "edta": {
        "pka": (2.0, 2.70, 6.16, 10.26),
        "dpka_dt": -0.005,
        "charges": (0, -1, -2, -3, -4),
        "is_base": False,
        "log_k_mg": 8.79,
        "log_k_ca": 10.69,
    },
    "ppi": {
        "pka": (0.83, 2.26, 6.72, 9.46),
        "dpka_dt": -0.002,
        "charges": (0, -1, -2, -3, -4),
        "is_base": False,
        "log_k_mg": 5.4,
        "log_k_ca": 5.0,
    },
}

_KSP_DATABASE = {
    "Mg2P2O7": {"ksp": 2.5e-13, "mg": 2, "ca": 0, "ppi": 1, "po4": 0, "hpo4": 0},
    "Ca3(PO4)2": {"ksp": 2.07e-33, "mg": 0, "ca": 3, "ppi": 0, "po4": 2, "hpo4": 0},
    "MgHPO4": {"ksp": 1.5e-6, "mg": 1, "ca": 0, "ppi": 0, "po4": 0, "hpo4": 1},
    "Mg3(PO4)2": {"ksp": 1.0e-25, "mg": 3, "ca": 0, "ppi": 0, "po4": 2, "hpo4": 0},
}


def _solve_linear_system(A: List[List[float]], b: List[float]) -> List[float]:
    """Pure-Python Gaussian elimination with partial pivoting."""
    n = len(b)
    # Augmented matrix
    M = [A[i][:] + [b[i]] for i in range(n)]

    for i in range(n):
        # Pivot
        max_row = i
        max_val = abs(M[i][i])
        for k in range(i + 1, n):
            if abs(M[k][i]) > max_val:
                max_val = abs(M[k][i])
                max_row = k
        if max_row != i:
            M[i], M[max_row] = M[max_row], M[i]

        pivot = M[i][i]
        if abs(pivot) < 1e-15:
            continue

        for k in range(i + 1, n):
            factor = M[k][i] / pivot
            for j in range(i, n + 1):
                M[k][j] -= factor * M[i][j]

    # Back substitution
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        if abs(M[i][i]) < 1e-15:
            x[i] = 0.0
            continue
        s = sum(M[i][j] * x[j] for j in range(i + 1, n))
        x[i] = (M[i][n] - s) / M[i][i]
    return x


def solve_buffer_equilibrium(
    components: Union[str, Dict[str, Any], Sequence[Union[str, Dict[str, Any], EquilibriumComponent]]],
    target_ph: float = 7.4,
    temperature_celsius: float = 25.0,
    output_temp_celsius: float = 37.0,
    use_davies_correction: bool = True,
) -> BufferEquilibriumResult:
    """
    Multi-Metal Competitive Buffer Speciation Solver.
    
    Solves simultaneous non-linear mass-balance equations for divalent cations (Mg2+, Ca2+)
    and competing chelators/ligands (EGTA, EDTA, ATP, GTP, dNTPs, PPi, phosphate) using
    a damped Newton-Raphson solver in log-concentration space, with temperature drift
    corrections (dpKa/dT) and Davies ionic strength activity adjustments.
    """
    import math

    # 1. Parse components into standard dictionary
    comp_map: Dict[str, float] = {}
    if isinstance(components, str):
        # Format: "Tris=50mM,EGTA=5mM,MgCl2=10mM,ATP=4mM"
        parts = [p.strip() for p in components.replace(";", ",").split(",") if p.strip()]
        for part in parts:
            if "=" in part:
                k, v = part.split("=", 1)
                comp_map[k.strip().lower()] = _parse_conc_string(v.strip())
            elif ":" in part:
                k, v = part.split(":", 1)
                comp_map[k.strip().lower()] = _parse_conc_string(v.strip())
    elif isinstance(components, dict):
        for k, v in components.items():
            conc = _parse_conc_string(v) if isinstance(v, str) else float(v)
            comp_map[k.strip().lower()] = conc
    elif isinstance(components, (list, tuple)):
        for item in components:
            if isinstance(item, EquilibriumComponent):
                comp_map[item.name.strip().lower()] = item.total_conc_m
            elif isinstance(item, dict):
                k = item.get("name") or item.get("id")
                v = item.get("conc_m") or item.get("conc_mm") or item.get("conc") or item.get("total_conc_m")
                if k and v is not None:
                    conc = float(v) * (1e-3 if "mm" in str(item).lower() and "m" not in str(item).lower() else 1.0)
                    comp_map[str(k).strip().lower()] = conc
            elif isinstance(item, str) and "=" in item:
                k, v = item.split("=", 1)
                comp_map[k.strip().lower()] = _parse_conc_string(v.strip())

    temp_eff = output_temp_celsius if output_temp_celsius is not None else temperature_celsius
    dt = temp_eff - 25.0

    # Extract total metals
    total_mg = 0.0
    total_ca = 0.0
    for name, c in comp_map.items():
        if "mg" in name or "magnesium" in name:
            total_mg += c
        elif "ca" in name or "calcium" in name:
            total_ca += c

    # Extract ligands
    ligand_names = ["egta", "edta", "atp", "gtp", "dntp", "ppi", "phosphate", "pbs"]
    present_ligands = [lig for lig in ligand_names if any(lig in k for k in comp_map)]

    # Compute effective deprotonated fraction (alpha) for each ligand at target pH
    alpha_map: Dict[str, float] = {}
    h_conc = 10.0 ** (-target_ph)

    for lig in present_ligands:
        data = _BUFFER_PKA_DB.get(lig, {})
        base_pka = data.get("pka", (7.0,))
        dpka = data.get("dpka_dt", 0.0)
        eff_pka = tuple(pk + dpka * dt for pk in base_pka)

        # Ka values
        ka_vals = [10.0 ** (-pk) for pk in eff_pka]
        n_pka = len(ka_vals)

        # Denominator for polyprotic distribution
        # D = [H]^n + K1 [H]^(n-1) + K1 K2 [H]^(n-2) + ...
        terms = [h_conc ** n_pka]
        prod_k = 1.0
        for i, ka in enumerate(ka_vals):
            prod_k *= ka
            terms.append(prod_k * (h_conc ** (n_pka - 1 - i)))
        d_sum = sum(terms)
        # Fully deprotonated fraction is the last term / d_sum
        alpha_map[lig] = terms[-1] / d_sum if d_sum > 0 else 1.0

    # Initial ionic strength estimate
    i_strength = 0.1  # default initial guess

    # Davies activity correction factor
    def get_davies_gamma(z: int, I: float) -> float:
        if not use_davies_correction or I <= 0.0:
            return 1.0
        A = 0.509 * ((298.15 / (temp_eff + 273.15)) ** 1.5)
        sqrt_i = math.sqrt(I)
        log_gamma = -A * (z ** 2) * (sqrt_i / (1.0 + sqrt_i) - 0.3 * I)
        return 10.0 ** log_gamma

    # Build metal-ligand stability matrix
    # Metals: M0 = Mg2+, M1 = Ca2+
    # Ligands: L_k in present_ligands
    m_totals = [total_mg, total_ca]
    m_keys = ["mg", "ca"]
    l_totals = [sum(v for k, v in comp_map.items() if lig in k) for lig in present_ligands]

    # Effective binding constants K'[m, l]
    k_prime: List[List[float]] = []
    for m_idx, m_key in enumerate(m_keys):
        row = []
        for l_idx, lig in enumerate(present_ligands):
            data = _BUFFER_PKA_DB.get(lig, {})
            log_k = data.get(f"log_k_{m_key}", 0.0)
            if log_k > 0:
                k_val = 10.0 ** log_k
                k_eff = k_val * alpha_map.get(lig, 1.0)
            else:
                k_eff = 0.0
            row.append(k_eff)
        k_prime.append(row)

    # Solve competitive equilibrium via Newton-Raphson in log-space
    n_m = len(m_totals)
    n_l = len(l_totals)
    n_vars = n_m + n_l

    # Initial guesses: if total is 0, set to very small number
    curr_m = [max(m * 0.5, 1e-12) for m in m_totals]
    curr_l = [max(l * 0.5, 1e-12) for l in l_totals]

    for iteration in range(50):
        # Variables: x = [ln(M0), ln(M1), ln(L0), ln(L1), ...]
        residuals = []
        # Residuals for metals: F_m_j = M_j * (1 + sum_k K'_{j,k} L_k) - M_tot_j
        for j in range(n_m):
            if m_totals[j] <= 1e-15:
                curr_m[j] = 0.0
                residuals.append(0.0)
                continue
            binding_sum = sum(k_prime[j][k] * curr_l[k] for k in range(n_l))
            calc_tot = curr_m[j] * (1.0 + binding_sum)
            residuals.append(calc_tot - m_totals[j])

        # Residuals for ligands: F_l_k = L_k * (1 + sum_j K'_{j,k} M_j) - L_tot_k
        for k in range(n_l):
            if l_totals[k] <= 1e-15:
                curr_l[k] = 0.0
                residuals.append(0.0)
                continue
            binding_sum = sum(k_prime[j][k] * curr_m[j] for j in range(n_m))
            calc_tot = curr_l[k] * (1.0 + binding_sum)
            residuals.append(calc_tot - l_totals[k])

        res_norm = max(abs(r) for r in residuals) if residuals else 0.0
        if res_norm < 1e-12:
            break

        # Compute Jacobian J in log-space: J_ab = dF_a / d(ln X_b) = X_b * dF_a / dX_b
        J = [[0.0] * n_vars for _ in range(n_vars)]

        for j in range(n_m):
            if m_totals[j] <= 1e-15:
                J[j][j] = 1.0
                continue
            binding_sum = sum(k_prime[j][k] * curr_l[k] for k in range(n_l))
            J[j][j] = curr_m[j] * (1.0 + binding_sum)
            for k in range(n_l):
                J[j][n_m + k] = k_prime[j][k] * curr_m[j] * curr_l[k]

        for k in range(n_l):
            idx = n_m + k
            if l_totals[k] <= 1e-15:
                J[idx][idx] = 1.0
                continue
            binding_sum = sum(k_prime[j][k] * curr_m[j] for j in range(n_m))
            J[idx][idx] = curr_l[k] * (1.0 + binding_sum)
            for j in range(n_m):
                J[idx][j] = k_prime[j][k] * curr_l[k] * curr_m[j]

        # Solve J * delta_log = -residuals
        rhs = [-r for r in residuals]
        delta_log = _solve_linear_system(J, rhs)

        # Clamp per-iteration step size: |Delta log10 c_i| <= 1.0 (meaning |delta_log_i| <= ln(10))
        max_log10_step = max(abs(d) / math.log(10.0) for d in delta_log) if delta_log else 0.0
        if max_log10_step > 1.0:
            scale = 1.0 / max_log10_step
            delta_log = [d * scale for d in delta_log]

        # Damped backtracking line search on mass-balance residual norm ||r||_2
        curr_norm2 = math.sqrt(sum(r * r for r in residuals))
        best_alpha = 1.0
        alpha = 1.0
        for _ in range(8):
            cand_m = list(curr_m)
            cand_l = list(curr_l)
            for j in range(n_m):
                if m_totals[j] > 1e-15:
                    cand_m[j] = curr_m[j] * math.exp(alpha * delta_log[j])
            for k in range(n_l):
                if l_totals[k] > 1e-15:
                    cand_l[k] = curr_l[k] * math.exp(alpha * delta_log[n_m + k])

            cand_res = []
            for j in range(n_m):
                if m_totals[j] <= 1e-15:
                    cand_res.append(0.0)
                else:
                    bs = sum(k_prime[j][k] * cand_l[k] for k in range(n_l))
                    cand_res.append(cand_m[j] * (1.0 + bs) - m_totals[j])
            for k in range(n_l):
                if l_totals[k] <= 1e-15:
                    cand_res.append(0.0)
                else:
                    bs = sum(k_prime[j][k] * cand_m[j] for j in range(n_m))
                    cand_res.append(cand_l[k] * (1.0 + bs) - l_totals[k])
            cand_norm2 = math.sqrt(sum(r * r for r in cand_res))
            if cand_norm2 <= curr_norm2 or alpha < 0.05:
                best_alpha = alpha
                break
            alpha *= 0.5

        for j in range(n_m):
            if m_totals[j] > 1e-15:
                curr_m[j] *= math.exp(best_alpha * delta_log[j])
        for k in range(n_l):
            if l_totals[k] > 1e-15:
                curr_l[k] *= math.exp(best_alpha * delta_log[n_m + k])

    free_mg = curr_m[0] if n_m > 0 else 0.0
    free_ca = curr_m[1] if n_m > 1 else 0.0

    free_atp = 0.0
    for idx, lig in enumerate(present_ligands):
        if lig == "atp":
            free_atp = curr_l[idx]

    # Calculate individual species concentrations and charges
    species_list: List[SpeciesConcentration] = []

    # Free metals
    if total_mg > 0:
        species_list.append(SpeciesConcentration("Mg2+ (free)", free_mg, free_mg / total_mg, 2))
    if total_ca > 0:
        species_list.append(SpeciesConcentration("Ca2+ (free)", free_ca, free_ca / total_ca, 2))

    # Complexes and free ligand species
    for l_idx, lig in enumerate(present_ligands):
        tot = l_totals[l_idx]
        free_l = curr_l[l_idx]
        if tot <= 0:
            continue
        species_list.append(SpeciesConcentration(f"{lig.upper()} (free uncomplexed)", free_l, free_l / tot, -4 if lig in ("egta", "edta", "atp", "gtp") else -2))

        # Check complexes
        for m_idx, m_key in enumerate(m_keys):
            k_eff = k_prime[m_idx][l_idx]
            if k_eff > 0:
                c_complex = k_eff * curr_m[m_idx] * free_l
                m_label = "Mg" if m_key == "mg" else "Ca"
                species_list.append(SpeciesConcentration(f"{m_label}-{lig.upper()}", c_complex, c_complex / tot, -2))

    # Buffer species (e.g. Tris, HEPES, Phosphate)
    buffer_capacity = 0.0
    for name, c_tot in comp_map.items():
        base_name = next((b for b in ("tris", "hepes", "mops", "pipes", "mes", "phosphate", "pbs") if b in name), None)
        if base_name:
            data = _BUFFER_PKA_DB[base_name]
            pka_list = data["pka"]
            dpka = data["dpka_dt"]
            eff_pka = tuple(pk + dpka * dt for pk in pka_list)
            for pk in eff_pka:
                ka = 10.0 ** (-pk)
                # Buffer capacity component
                buffer_capacity += math.log(10.0) * c_tot * (ka * h_conc) / ((ka + h_conc) ** 2)

    buffer_capacity += math.log(10.0) * (h_conc + (1e-14 / h_conc))

    # Refine ionic strength from all species
    actual_i = 0.5 * (free_mg * 4.0 + free_ca * 4.0)
    for sp in species_list:
        actual_i += 0.5 * sp.concentration_m * (sp.charge ** 2)
    # Include uncomplexed background monovalents (e.g. Na+, K+, Cl-)
    actual_i = max(actual_i, 0.05)

    # Precipitation risk screening
    # Free phosphate and pyrophosphate species
    free_po4 = 0.0
    free_hpo4 = 0.0
    free_ppi = 0.0

    for l_idx, lig in enumerate(present_ligands):
        if lig in ("phosphate", "pbs"):
            free_po4 = curr_l[l_idx] * alpha_map.get(lig, 0.0)
            # Estimate HPO4 2-
            free_hpo4 = curr_l[l_idx] * 0.5
        elif lig == "ppi":
            free_ppi = curr_l[l_idx] * alpha_map.get(lig, 0.0)

    precip_checks: List[PrecipitationCheck] = []
    gamma_mg = get_davies_gamma(2, actual_i)
    gamma_ca = get_davies_gamma(2, actual_i)
    gamma_po4 = get_davies_gamma(3, actual_i)
    gamma_hpo4 = get_davies_gamma(2, actual_i)
    gamma_ppi = get_davies_gamma(4, actual_i)

    # 1. Mg2P2O7
    iap_mg_ppi = ((free_mg * gamma_mg) ** 2) * (free_ppi * gamma_ppi)
    ksp_mg_ppi = _KSP_DATABASE["Mg2P2O7"]["ksp"]
    si_mg_ppi = math.log10(iap_mg_ppi / ksp_mg_ppi) if iap_mg_ppi > 0 else -99.0
    precip_checks.append(PrecipitationCheck(
        salt_name="Mg2P2O7 (Magnesium Pyrophosphate)",
        ion_product=iap_mg_ppi,
        ksp=ksp_mg_ppi,
        saturation_index=si_mg_ppi,
        will_precipitate=si_mg_ppi > 0.0,
    ))

    # 2. Ca3(PO4)2
    iap_ca_po4 = ((free_ca * gamma_ca) ** 3) * ((free_po4 * gamma_po4) ** 2)
    ksp_ca_po4 = _KSP_DATABASE["Ca3(PO4)2"]["ksp"]
    si_ca_po4 = math.log10(iap_ca_po4 / ksp_ca_po4) if iap_ca_po4 > 0 else -99.0
    precip_checks.append(PrecipitationCheck(
        salt_name="Ca3(PO4)2 (Calcium Phosphate)",
        ion_product=iap_ca_po4,
        ksp=ksp_ca_po4,
        saturation_index=si_ca_po4,
        will_precipitate=si_ca_po4 > 0.0,
    ))

    # 3. MgHPO4
    iap_mg_hpo4 = (free_mg * gamma_mg) * (free_hpo4 * gamma_hpo4)
    ksp_mg_hpo4 = _KSP_DATABASE["MgHPO4"]["ksp"]
    si_mg_hpo4 = math.log10(iap_mg_hpo4 / ksp_mg_hpo4) if iap_mg_hpo4 > 0 else -99.0
    precip_checks.append(PrecipitationCheck(
        salt_name="MgHPO4 (Magnesium Hydrogen Phosphate)",
        ion_product=iap_mg_hpo4,
        ksp=ksp_mg_hpo4,
        saturation_index=si_mg_hpo4,
        will_precipitate=si_mg_hpo4 > 0.0,
    ))

    return BufferEquilibriumResult(
        target_ph=target_ph,
        actual_ph=target_ph,
        ionic_strength_m=round(actual_i, 5),
        temperature_celsius=temp_eff,
        free_mg_conc_m=free_mg,
        free_ca_conc_m=free_ca,
        free_atp_conc_m=free_atp,
        species=tuple(species_list),
        precipitation_risks=tuple(precip_checks),
        buffer_capacity_beta=round(buffer_capacity, 5),
    )

