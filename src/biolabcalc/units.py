"""Universal unit parsing and normalization for laboratory calculations.

Enables functions and CLI commands to accept flexible numeric inputs or human-readable
strings with metric prefixes (e.g., '500 uL', '0.5 mL', '25 mM', '10 µM', '1.5 ug').
"""

from __future__ import annotations
import re
from typing import Union

class UnitParser:
    """Robust parser and converter for laboratory volume, concentration, mass, and molar amounts."""

    VOLUME_FACTORS = {
        "l": 1e6,
        "liter": 1e6,
        "liters": 1e6,
        "ml": 1e3,
        "milliliter": 1e3,
        "milliliters": 1e3,
        "ul": 1.0,
        "µl": 1.0,
        "microliter": 1.0,
        "microliters": 1.0,
        "nl": 1e-3,
        "nanoliter": 1e-3,
        "pl": 1e-6,
    }

    MASS_CONC_FACTORS = {
        "mg/ml": 1.0,
        "ug/ul": 1.0,
        "µg/µl": 1.0,
        "g/l": 1.0,
        "ug/ml": 1e-3,
        "µg/ml": 1e-3,
        "ng/ul": 1e-3,
        "ng/ml": 1e-6,
    }
    CONC_FACTORS = {
        "m": 1e3,
        "molar": 1e3,
        "mm": 1.0,
        "millimolar": 1.0,
        "um": 1e-3,
        "µm": 1e-3,
        "micromolar": 1e-3,
        "nm": 1e-6,
        "nanomolar": 1e-6,
        "pm": 1e-9,
        "picomolar": 1e-9,
        "fm": 1e-12,
        "femtomolar": 1e-12,
    }

    MASS_FACTORS = {
        "g": 1e6,
        "gram": 1e6,
        "grams": 1e6,
        "mg": 1e3,
        "milligram": 1e3,
        "milligrams": 1e3,
        "ug": 1.0,
        "µg": 1.0,
        "microgram": 1.0,
        "micrograms": 1.0,
        "ng": 1e-3,
        "nanogram": 1e-3,
        "nanograms": 1e-3,
        "pg": 1e-6,
        "fg": 1e-9,
    }

    MOLE_FACTORS = {
        "mol": 1e9,
        "mole": 1e9,
        "moles": 1e9,
        "mmol": 1e6,
        "umol": 1e3,
        "µmol": 1e3,
        "nmol": 1.0,
        "nanomole": 1.0,
        "nanomoles": 1.0,
        "pmol": 1e-3,
        "picomole": 1e-3,
        "picomoles": 1e-3,
        "fmol": 1e-6,
        "amol": 1e-9,
        "attomole": 1e-9,
        "attomoles": 1e-9,
    }

    @staticmethod
    def _parse_raw(val: Union[str, float, int]) -> tuple[float, str]:
        if isinstance(val, (int, float)):
            return float(val), ""
        s = str(val).strip().replace(" ", "").replace(",", "")
        match = re.match(r"^([+-]?[0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)([a-zA-Zµ/]*)$", s)
        if not match:
            raise ValueError(f"Unable to parse numeric laboratory quantity from string: '{val}'")
        num_str, unit_str = match.groups()
        return float(num_str), unit_str.lower()

    @classmethod
    def parse_volume(cls, val: Union[str, float, int], target_unit: str = "ul") -> float:
        """Parse volume input string or float and normalize to target_unit (default: 'ul')."""
        num, unit = cls._parse_raw(val)
        if not unit:
            return num
        t_unit = target_unit.lower()
        if unit not in cls.VOLUME_FACTORS:
            raise ValueError(f"Unknown volume unit '{unit}'. Supported: {list(cls.VOLUME_FACTORS.keys())}")
        if t_unit not in cls.VOLUME_FACTORS:
            raise ValueError(f"Unknown target volume unit '{target_unit}'.")
        val_in_ul = num * cls.VOLUME_FACTORS[unit]
        return round(val_in_ul / cls.VOLUME_FACTORS[t_unit], 6)

    @classmethod
    def parse_concentration(cls, val: Union[str, float, int], target_unit: str = "mm") -> float:
        """Parse concentration input string or float and normalize to target_unit (default: 'mm').

        Automatically recognizes and differentiates molar concentrations (M, mM, µM, nM, pM, fM)
        from mass concentrations (mg/mL, µg/µL, ng/µL, µg/mL).
        """
        num, unit = cls._parse_raw(val)
        if not unit:
            return num
        t_unit = target_unit.lower().replace("µ", "u")
        unit_clean = unit.replace("µ", "u")

        # If input has '/' (e.g. mg/mL, ug/uL), it is a mass concentration
        if "/" in unit_clean:
            if unit_clean not in cls.MASS_CONC_FACTORS:
                raise ValueError(f"Unknown mass concentration unit '{unit}'. Supported: {list(cls.MASS_CONC_FACTORS.keys())}")
            # If target_unit was left as default 'mm' or has no '/', auto-default to 'mg/ml'
            if "/" not in t_unit:
                t_unit = "mg/ml"
            val_in_mg_ml = num * cls.MASS_CONC_FACTORS[unit_clean]
            return round(val_in_mg_ml / cls.MASS_CONC_FACTORS[t_unit], 6)

        # Input is molar (no '/')
        if "/" in t_unit:
            raise ValueError(f"Cannot convert molar concentration '{val}' to mass concentration '{target_unit}' without molecular weight.")

        if unit_clean not in cls.CONC_FACTORS:
            raise ValueError(f"Unknown molar concentration unit '{unit}'. Supported: {list(cls.CONC_FACTORS.keys())}")
        if t_unit not in cls.CONC_FACTORS:
            raise ValueError(f"Unknown target concentration unit '{target_unit}'.")
        val_in_mm = num * cls.CONC_FACTORS[unit_clean]
        return round(val_in_mm / cls.CONC_FACTORS[t_unit], 6)

    @classmethod
    def parse_mass(cls, val: Union[str, float, int], target_unit: str = "ug") -> float:
        """Parse mass input string or float and normalize to target_unit (default: 'ug')."""
        num, unit = cls._parse_raw(val)
        if not unit:
            return num
        t_unit = target_unit.lower()
        if unit not in cls.MASS_FACTORS:
            raise ValueError(f"Unknown mass unit '{unit}'. Supported: {list(cls.MASS_FACTORS.keys())}")
        if t_unit not in cls.MASS_FACTORS:
            raise ValueError(f"Unknown target mass unit '{target_unit}'.")
        val_in_ug = num * cls.MASS_FACTORS[unit]
        return round(val_in_ug / cls.MASS_FACTORS[t_unit], 6)

    @classmethod
    def parse_moles(cls, val: Union[str, float, int], target_unit: str = "nmol") -> float:
        """Parse molar input string or float and normalize to target_unit (default: 'nmol')."""
        num, unit = cls._parse_raw(val)
        if not unit:
            return num
        t_unit = target_unit.lower()
        if unit not in cls.MOLE_FACTORS:
            raise ValueError(f"Unknown molar unit '{unit}'. Supported: {list(cls.MOLE_FACTORS.keys())}")
        if t_unit not in cls.MOLE_FACTORS:
            raise ValueError(f"Unknown target molar unit '{target_unit}'.")
        val_in_nmol = num * cls.MOLE_FACTORS[unit]
        return round(val_in_nmol / cls.MOLE_FACTORS[t_unit], 6)
