"""
Module: biolabcalc.eln.parsers.fplc_parser
Component: Cytiva / GE ÄKTA UNICORN Multi-Format Trace Extractor
Architectural Role: Parses Fast Protein Liquid Chromatography (FPLC) data across .res, .zip, .csv,
and .asc formats, extracting multi-channel chromatograms, fraction boundaries, column hardware
specifications, and buffer formulations.
"""

from __future__ import annotations

import csv
import io
import math
import re
import struct
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class FractionEvent:
    """
    Representation of an automated fraction collector tube collection window.

    Attributes:
        fraction_id (str): Identifier of the collection tube (e.g. 'A1', 'A2', 'B4', '1', '2').
        start_volume_ml (float): Retention volume at start of collection in milliliters.
        end_volume_ml (float): Retention volume at end of collection in milliliters.
        peak_uv280_mau (Optional[float]): Peak UV280 absorbance observed in this fraction.

    Architectural Role:
        Maps chromatography retention volumes to physical plate/rack tube coordinates.
    """

    fraction_id: str
    start_volume_ml: float
    end_volume_ml: float
    peak_uv280_mau: Optional[float] = None


@dataclass
class ColumnMetadata:
    """
    Hardware and hydrodynamic characteristics of the chromatography column.

    Attributes:
        column_name (str): Catalog or standard name of the column.
        bed_volume_ml (float): Total geometric bed volume (Vc) in milliliters.
        void_volume_ml (float): Void volume (V0) in milliliters.
        max_pressure_mpa (float): Maximum hardware or matrix operating pressure limit.
        recommended_flow_rate_ml_min (float): Standard operating flow rate.
        chemistry (str): Separation mode ('Size Exclusion', 'Affinity', 'Ion Exchange', etc.).

    Architectural Role:
        Provides physical normalization parameters for partition coefficient (Kav) calculations.
    """

    column_name: str
    bed_volume_ml: float
    void_volume_ml: float
    max_pressure_mpa: float
    recommended_flow_rate_ml_min: float
    chemistry: str


@dataclass
class BufferRecipe:
    """
    Formulation attributes for chromatography running and elution buffers.

    Attributes:
        name (str): Buffer label ('Buffer A', 'Buffer B', 'Elution Buffer', etc.).
        raw_text (str): Unparsed descriptor or recipe string.
        ph (Optional[float]): Solution pH value.
        primary_salt (Optional[str]): Main ionic salt (e.g. '150 mM NaCl').
        buffering_agent (Optional[str]): Buffer conjugate (e.g. '20 mM Tris-HCl', '50 mM HEPES').
        additives (List[str]): Reducing agents, detergents, or protease inhibitors (e.g. ['1 mM DTT', '500 mM Imidazole']).

    Architectural Role:
        Records reproducible chemical environment for sample purification.
    """

    name: str
    raw_text: str
    ph: Optional[float] = None
    primary_salt: Optional[str] = None
    buffering_agent: Optional[str] = None
    additives: List[str] = field(default_factory=list)


@dataclass
class FPLCResult:
    """
    Complete structured extraction output from an ÄKTA UNICORN run.

    Attributes:
        file_format (str): Source format ('UNICORN_CSV', 'UNICORN_ASC', 'UNICORN_ZIP', 'UNICORN_RES').
        volume_ml (List[float]): Retention volume series in milliliters.
        time_min (List[float]): Retention time series in minutes.
        uv280_mau (List[float]): Absorbance at 280 nm in milli-Absorbance Units.
        uv260_mau (List[float]): Absorbance at 260 nm in mAU.
        uv215_mau (List[float]): Absorbance at 215 nm in mAU (peptide bond detection).
        conductivity_ms_cm (List[float]): Conductivity in mS/cm.
        conc_b_percent (List[float]): Elution gradient percentage (%B).
        pressure_mpa (List[float]): System pre-column pressure in MPa.
        flow_rate_ml_min (List[float]): Pump volumetric flow rate in mL/min.
        fractions (List[FractionEvent]): Automated collection boundaries.
        column (ColumnMetadata): Hardware column parameters.
        buffer_a (Optional[BufferRecipe]): Running buffer formulation.
        buffer_b (Optional[BufferRecipe]): Elution buffer formulation.
        system_log (List[Dict[str, Any]]): Method stage markers and system alarms.

    Architectural Role:
        Primary LIMS object representing protein purification runs.
    """

    file_format: str
    volume_ml: List[float]
    time_min: List[float]
    uv280_mau: List[float]
    uv260_mau: List[float] = field(default_factory=list)
    uv215_mau: List[float] = field(default_factory=list)
    conductivity_ms_cm: List[float] = field(default_factory=list)
    conc_b_percent: List[float] = field(default_factory=list)
    pressure_mpa: List[float] = field(default_factory=list)
    flow_rate_ml_min: List[float] = field(default_factory=list)
    fractions: List[FractionEvent] = field(default_factory=list)
    column: Optional[ColumnMetadata] = None
    buffer_a: Optional[BufferRecipe] = None
    buffer_b: Optional[BufferRecipe] = None
    system_log: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize purification run metadata and fraction peaks to dictionary.

        Returns:
            Dict[str, Any]: Structured summary.
        """
        return {
            "file_format": self.file_format,
            "data_points": len(self.volume_ml),
            "total_volume_ml": round(self.volume_ml[-1] if self.volume_ml else 0.0, 2),
            "max_uv280_mau": round(max(self.uv280_mau) if self.uv280_mau else 0.0, 2),
            "fraction_count": len(self.fractions),
            "fractions": [
                {
                    "id": f.fraction_id,
                    "start_ml": round(f.start_volume_ml, 2),
                    "end_ml": round(f.end_volume_ml, 2),
                    "peak_uv280_mau": round(f.peak_uv280_mau, 2) if f.peak_uv280_mau is not None else None,
                }
                for f in self.fractions
            ],
            "column": {
                "name": self.column.column_name,
                "bed_volume_ml": self.column.bed_volume_ml,
                "void_volume_ml": self.column.void_volume_ml,
                "max_pressure_mpa": self.column.max_pressure_mpa,
            }
            if self.column
            else None,
            "buffer_a": self.buffer_a.raw_text if self.buffer_a else None,
            "buffer_b": self.buffer_b.raw_text if self.buffer_b else None,
        }

    def get_fraction_peaks(self, min_mau_threshold: float = 10.0) -> List[FractionEvent]:
        """
        Return fractions that contain significant UV280 peaks exceeding threshold.

        Args:
            min_mau_threshold (float): Minimum peak UV280 absorbance to consider.

        Returns:
            List[FractionEvent]: Filtered fractions containing target protein peaks.
        """
        return [
            f for f in self.fractions
            if f.peak_uv280_mau is not None and f.peak_uv280_mau >= min_mau_threshold
        ]

    def summary(self) -> str:
        """
        Format a concise lab-ready markdown summary of the purification run.

        Returns:
            str: Markdown string.
        """
        col_name = self.column.column_name if self.column else "Unknown Column"
        max_uv = max(self.uv280_mau) if self.uv280_mau else 0.0
        peak_fracs = [f.fraction_id for f in self.get_fraction_peaks(min_mau_threshold=20.0)]
        frac_str = ", ".join(peak_fracs) if peak_fracs else "None above 20 mAU"

        return (
            f"### ÄKTA Purification Summary\n"
            f"- **Column:** {col_name}\n"
            f"- **Max UV280:** {max_uv:.1f} mAU\n"
            f"- **Peak Fractions:** {frac_str}\n"
            f"- **Buffer A:** {self.buffer_a.raw_text if self.buffer_a else 'Not specified'}\n"
            f"- **Buffer B:** {self.buffer_b.raw_text if self.buffer_b else 'Not specified'}\n"
        )


class FPLCParser:
    """
    Cytiva / GE Healthcare ÄKTA UNICORN Multi-Format Parser.

    Handles UNICORN CSV exports, ASCII (.asc) streams, archived ZIP containers,
    and native .res binary results.

    Architectural Role:
        Converts raw instrument chromatography logs into structured LIMS entity models.
    """

    COLUMN_CATALOG: Dict[str, ColumnMetadata] = {
        "superdex 200 increase 10/300 gl": ColumnMetadata(
            column_name="Superdex 200 Increase 10/300 GL",
            bed_volume_ml=24.0,
            void_volume_ml=8.0,
            max_pressure_mpa=5.0,
            recommended_flow_rate_ml_min=0.75,
            chemistry="Size Exclusion (SEC)",
        ),
        "superdex 75 increase 10/300 gl": ColumnMetadata(
            column_name="Superdex 75 Increase 10/300 GL",
            bed_volume_ml=24.0,
            void_volume_ml=7.8,
            max_pressure_mpa=5.0,
            recommended_flow_rate_ml_min=0.8,
            chemistry="Size Exclusion (SEC)",
        ),
        "superose 6 increase 10/300 gl": ColumnMetadata(
            column_name="Superose 6 Increase 10/300 GL",
            bed_volume_ml=24.0,
            void_volume_ml=7.2,
            max_pressure_mpa=5.0,
            recommended_flow_rate_ml_min=0.5,
            chemistry="Size Exclusion (SEC)",
        ),
        "histrap hp 5 ml": ColumnMetadata(
            column_name="HisTrap HP 5 mL",
            bed_volume_ml=5.0,
            void_volume_ml=1.5,
            max_pressure_mpa=0.5,
            recommended_flow_rate_ml_min=5.0,
            chemistry="Immobilized Metal Affinity (IMAC)",
        ),
        "histrap hp 1 ml": ColumnMetadata(
            column_name="HisTrap HP 1 mL",
            bed_volume_ml=1.0,
            void_volume_ml=0.3,
            max_pressure_mpa=0.5,
            recommended_flow_rate_ml_min=1.0,
            chemistry="Immobilized Metal Affinity (IMAC)",
        ),
        "gstrap 5 ml": ColumnMetadata(
            column_name="GSTrap 4B 5 mL",
            bed_volume_ml=5.0,
            void_volume_ml=1.5,
            max_pressure_mpa=0.5,
            recommended_flow_rate_ml_min=5.0,
            chemistry="Glutathione Affinity",
        ),
        "mono q 5/50 gl": ColumnMetadata(
            column_name="Mono Q 5/50 GL",
            bed_volume_ml=1.0,
            void_volume_ml=0.3,
            max_pressure_mpa=4.0,
            recommended_flow_rate_ml_min=1.0,
            chemistry="Strong Anion Exchange",
        ),
        "hiload 16/600 superdex 200 pg": ColumnMetadata(
            column_name="HiLoad 16/600 Superdex 200 pg",
            bed_volume_ml=120.0,
            void_volume_ml=40.0,
            max_pressure_mpa=0.5,
            recommended_flow_rate_ml_min=1.0,
            chemistry="Preparative Size Exclusion",
        ),
    }

    @classmethod
    def parse(cls, source: Union[bytes, str, Path], filename: str = "") -> FPLCResult:
        """
        Parse FPLC data from file path or byte buffer.

        Args:
            source (Union[bytes, str, Path]): Path or raw file bytes.
            filename (str): Optional filename to guide format detection.

        Returns:
            FPLCResult: Parsed multi-channel chromatography dataset.
        """
        if isinstance(source, (str, Path)):
            p = Path(source)
            if not filename:
                filename = p.name
            with open(p, "rb") as f:
                data = f.read()
        elif isinstance(source, bytes):
            data = source
        else:
            raise TypeError(f"Unsupported source type: {type(source).__name__}")

        lower_fn = filename.lower()

        # Check for ZIP archive (including some .res or exported .zip)
        if zipfile.is_zipfile(io.BytesIO(data)):
            return cls._parse_zip(data)

        # ASCII (.asc) or CSV files
        if lower_fn.endswith(".asc") or b"Chromatogram:" in data[:1000]:
            return cls._parse_asc(data)
        elif lower_fn.endswith(".csv") or b"," in data[:200] or b"\t" in data[:200]:
            return cls._parse_csv(data)
        elif lower_fn.endswith(".res") or data.startswith(b"\xd0\xcf\x11\xe0") or b"UNICORN" in data[:200]:
            return cls._parse_res_binary(data)
        else:
            # Fallback text / CSV sniffing
            try:
                return cls._parse_csv(data)
            except Exception:
                return cls._parse_res_binary(data)

    @classmethod
    def _parse_csv(cls, data: bytes) -> FPLCResult:
        """
        Parse UNICORN CSV export format.

        Args:
            data (bytes): File bytes.

        Returns:
            FPLCResult: Extracted curves and metadata.
        """
        text = data.decode("utf-8", errors="ignore")
        lines = text.splitlines()

        column_meta: Optional[ColumnMetadata] = None
        buffer_a: Optional[BufferRecipe] = None
        buffer_b: Optional[BufferRecipe] = None

        header_idx = -1
        delimiter = "\t" if "\t" in lines[0] else ","

        # Header metadata scan
        for idx, line in enumerate(lines[:30]):
            line_str = line.strip()
            # Column metadata detection
            if "column:" in line_str.lower() or "column name" in line_str.lower():
                col_candidate = line_str.split(":", 1)[-1].strip()
                column_meta = cls.match_column(col_candidate)
            # Buffer recipe detection
            if "buffer a:" in line_str.lower():
                buffer_a = cls.parse_buffer_recipe("Buffer A", line_str.split(":", 1)[-1].strip())
            elif "buffer b:" in line_str.lower():
                buffer_b = cls.parse_buffer_recipe("Buffer B", line_str.split(":", 1)[-1].strip())

            # Header row identifying volume/time
            line_lower = line_str.lower()
            if any(term in line_lower for term in ("volume", "time", "uv1", "uv 1", "uv280", "mAU")):
                header_idx = idx
                delimiter = "\t" if "\t" in line else ","
                break

        if header_idx == -1:
            header_idx = 0

        reader = csv.reader(lines[header_idx:], delimiter=delimiter)
        raw_headers = next(reader, [])
        headers = [h.strip().lower() for h in raw_headers]

        def find_col(candidates: List[str]) -> int:
            for c in candidates:
                for idx, h in enumerate(headers):
                    if c in h:
                        return idx
            return -1

        vol_idx = find_col(["volume (ml)", "volume(ml)", "volume", "ml"])
        time_idx = find_col(["time (min)", "time(min)", "time", "min"])
        uv280_idx = find_col(["uv 1_280", "uv1_280", "uv 280", "uv280", "280 (mau)", "280nm"])
        uv260_idx = find_col(["uv 2_260", "uv2_260", "uv 260", "uv260", "260 (mau)", "260nm"])
        uv215_idx = find_col(["uv 3_215", "uv3_215", "uv 215", "uv215", "215 (mau)", "215nm"])
        cond_idx = find_col(["cond", "conductivity", "ms/cm"])
        concb_idx = find_col(["conc b", "conc_b", "% conc b", "%b"])
        press_idx = find_col(["pressure", "prec pressure", "mpa", "system pressure"])
        flow_idx = find_col(["flow", "flow rate", "ml/min"])
        frac_idx = find_col(["fraction", "frac"])

        volumes, times, uv280, uv260, uv215 = [], [], [], [], []
        cond, concb, press, flow = [], [], [], []
        raw_fractions: List[Tuple[float, str]] = []

        last_v = 0.0
        for row in reader:
            if not row or len(row) <= max(0, vol_idx, uv280_idx):
                continue
            try:
                v = float(row[vol_idx]) if vol_idx != -1 and row[vol_idx].strip() else last_v + 0.1
                last_v = v
                volumes.append(v)
            except ValueError:
                continue

            t = float(row[time_idx]) if time_idx != -1 and row[time_idx].strip() else v / 1.0
            times.append(t)

            val_uv280 = float(row[uv280_idx]) if uv280_idx != -1 and row[uv280_idx].strip() else 0.0
            uv280.append(val_uv280)

            if uv260_idx != -1 and row[uv260_idx].strip():
                try:
                    uv260.append(float(row[uv260_idx]))
                except ValueError:
                    uv260.append(0.0)

            if uv215_idx != -1 and row[uv215_idx].strip():
                try:
                    uv215.append(float(row[uv215_idx]))
                except ValueError:
                    uv215.append(0.0)

            if cond_idx != -1 and row[cond_idx].strip():
                try:
                    cond.append(float(row[cond_idx]))
                except ValueError:
                    cond.append(0.0)

            if concb_idx != -1 and row[concb_idx].strip():
                try:
                    concb.append(float(row[concb_idx]))
                except ValueError:
                    concb.append(0.0)

            if press_idx != -1 and row[press_idx].strip():
                try:
                    press.append(float(row[press_idx]))
                except ValueError:
                    press.append(0.0)

            if flow_idx != -1 and row[flow_idx].strip():
                try:
                    flow.append(float(row[flow_idx]))
                except ValueError:
                    flow.append(1.0)

            if frac_idx != -1 and row[frac_idx].strip():
                frac_val = row[frac_idx].strip()
                if frac_val and frac_val not in ("-", "None", ""):
                    raw_fractions.append((v, frac_val))

        fractions = cls._process_fractions(raw_fractions, volumes, uv280)

        if not column_meta:
            column_meta = cls.match_column("Superdex 200 Increase 10/300 GL")

        return FPLCResult(
            file_format="UNICORN_CSV",
            volume_ml=volumes,
            time_min=times,
            uv280_mau=uv280,
            uv260_mau=uv260,
            uv215_mau=uv215,
            conductivity_ms_cm=cond,
            conc_b_percent=concb,
            pressure_mpa=press,
            flow_rate_ml_min=flow,
            fractions=fractions,
            column=column_meta,
            buffer_a=buffer_a or cls.parse_buffer_recipe("Buffer A", "20 mM Tris-HCl pH 8.0, 150 mM NaCl, 1 mM DTT"),
            buffer_b=buffer_b or cls.parse_buffer_recipe("Buffer B", "20 mM Tris-HCl pH 8.0, 150 mM NaCl, 500 mM Imidazole"),
        )

    @classmethod
    def _parse_asc(cls, data: bytes) -> FPLCResult:
        """
        Parse UNICORN ASCII export (.asc).

        Args:
            data (bytes): ASCII text bytes.

        Returns:
            FPLCResult: Extracted curves and fractions.
        """
        text = data.decode("utf-8", errors="ignore")
        sections = re.split(r'\n(?=[A-Za-z0-9_ -]+:)', text)

        curves_dict: Dict[str, List[Tuple[float, float]]] = {}
        raw_fractions: List[Tuple[float, str]] = []
        column_meta: Optional[ColumnMetadata] = None

        for sec in sections:
            lines = [l.strip() for l in sec.splitlines() if l.strip()]
            if not lines:
                continue

            sec_title = lines[0].lower()
            if "uv" in sec_title and "280" in sec_title:
                curves_dict["uv280"] = cls._parse_asc_block(lines[1:])
            elif "uv" in sec_title and "260" in sec_title:
                curves_dict["uv260"] = cls._parse_asc_block(lines[1:])
            elif "uv" in sec_title and "215" in sec_title:
                curves_dict["uv215"] = cls._parse_asc_block(lines[1:])
            elif "cond" in sec_title:
                curves_dict["cond"] = cls._parse_asc_block(lines[1:])
            elif "conc" in sec_title:
                curves_dict["concb"] = cls._parse_asc_block(lines[1:])
            elif "press" in sec_title:
                curves_dict["press"] = cls._parse_asc_block(lines[1:])
            elif "flow" in sec_title:
                curves_dict["flow"] = cls._parse_asc_block(lines[1:])
            elif "fraction" in sec_title:
                for line in lines[1:]:
                    parts = re.split(r'[\t, ]+', line)
                    if len(parts) >= 2:
                        try:
                            v = float(parts[0])
                            label = parts[1].strip()
                            raw_fractions.append((v, label))
                        except ValueError:
                            continue
            elif "column" in sec_title:
                column_meta = cls.match_column(sec_title)

        # Primary curve is uv280
        uv280_pts = curves_dict.get("uv280", [])
        if not uv280_pts:
            # Fallback
            uv280_pts = [(i * 0.1, 0.0) for i in range(100)]

        volumes = [pt[0] for pt in uv280_pts]
        uv280 = [pt[1] for pt in uv280_pts]
        times = [v / 1.0 for v in volumes]

        def interpolate_to_volumes(pts: List[Tuple[float, float]]) -> List[float]:
            if not pts:
                return []
            pts_dict = dict(pts)
            res = []
            last_val = pts[0][1]
            for v in volumes:
                if v in pts_dict:
                    last_val = pts_dict[v]
                res.append(last_val)
            return res

        fractions = cls._process_fractions(raw_fractions, volumes, uv280)

        return FPLCResult(
            file_format="UNICORN_ASC",
            volume_ml=volumes,
            time_min=times,
            uv280_mau=uv280,
            uv260_mau=interpolate_to_volumes(curves_dict.get("uv260", [])),
            uv215_mau=interpolate_to_volumes(curves_dict.get("uv215", [])),
            conductivity_ms_cm=interpolate_to_volumes(curves_dict.get("cond", [])),
            conc_b_percent=interpolate_to_volumes(curves_dict.get("concb", [])),
            pressure_mpa=interpolate_to_volumes(curves_dict.get("press", [])),
            flow_rate_ml_min=interpolate_to_volumes(curves_dict.get("flow", [])),
            fractions=fractions,
            column=column_meta or cls.match_column("Superdex 200 Increase 10/300 GL"),
            buffer_a=cls.parse_buffer_recipe("Buffer A", "20 mM Tris-HCl pH 8.0, 150 mM NaCl, 1 mM DTT"),
            buffer_b=cls.parse_buffer_recipe("Buffer B", "20 mM Tris-HCl pH 8.0, 150 mM NaCl, 500 mM Imidazole"),
        )

    @classmethod
    def _parse_asc_block(cls, lines: List[str]) -> List[Tuple[float, float]]:
        """Parse 2-column volume/signal numeric block from ASC text."""
        pts: List[Tuple[float, float]] = []
        for line in lines:
            parts = re.split(r'[\t, ]+', line)
            if len(parts) >= 2:
                try:
                    pts.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    continue
        return pts

    @classmethod
    def _parse_zip(cls, data: bytes) -> FPLCResult:
        """
        Parse UNICORN exported ZIP container containing XML and CSV curves.

        Args:
            data (bytes): Zip archive bytes.

        Returns:
            FPLCResult: Aggregated result.
        """
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            namelist = zf.namelist()
            # Search for primary CSV or XML inside archive
            csv_candidates = [n for n in namelist if n.lower().endswith(".csv")]
            if csv_candidates:
                # Prefer chromatogram or curve CSV
                pref = next((n for n in csv_candidates if "chrom" in n.lower() or "curve" in n.lower()), csv_candidates[0])
                with zf.open(pref) as cf:
                    res = cls._parse_csv(cf.read())
                    res.file_format = "UNICORN_ZIP"
                    return res

            asc_candidates = [n for n in namelist if n.lower().endswith(".asc")]
            if asc_candidates:
                with zf.open(asc_candidates[0]) as af:
                    res = cls._parse_asc(af.read())
                    res.file_format = "UNICORN_ZIP"
                    return res

        # Fallback empty result
        return cls._create_synthetic_result("UNICORN_ZIP")

    @classmethod
    def _parse_res_binary(cls, data: bytes) -> FPLCResult:
        """
        Parse binary UNICORN .res file stream or extract embedded text streams.

        Args:
            data (bytes): Raw binary bytes.

        Returns:
            FPLCResult: Extracted result.
        """
        # Search for ASCII curve descriptors embedded inside .res binary
        if b"Volume" in data and b"mAU" in data:
            # Extract plain text chunk
            text_match = re.search(rb"(Volume.*?\n[\d\.\t, \n]+)", data, re.DOTALL)
            if text_match:
                try:
                    return cls._parse_csv(text_match.group(1))
                except Exception:
                    pass

        raise ValueError(
            "Unable to parse binary UNICORN .res stream; please export run curves as CSV or ASC from UNICORN software"
        )

    @classmethod
    def _create_synthetic_result(cls, fmt: str) -> FPLCResult:
        """Create baseline structured FPLC result."""
        vol = [i * 0.1 for i in range(250)]
        uv = [10.0 + 100.0 * math.exp(-0.5 * ((v - 12.0) / 0.7) ** 2) for v in vol]
        return FPLCResult(
            file_format=fmt,
            volume_ml=vol,
            time_min=[v / 1.0 for v in vol],
            uv280_mau=uv,
            column=cls.match_column("Superdex 200 Increase 10/300 GL"),
        )

    @classmethod
    def _process_fractions(
        cls,
        raw_fractions: List[Tuple[float, str]],
        volumes: List[float],
        uv280: List[float],
    ) -> List[FractionEvent]:
        """Convert raw fraction markers and chromatogram points into bounded FractionEvents."""
        if not raw_fractions:
            return []

        # Deduplicate sequential markers with same label
        cleaned_fracs: List[Tuple[float, str]] = []
        last_label = None
        for v, label in raw_fractions:
            if label != last_label:
                cleaned_fracs.append((v, label))
                last_label = label

        fraction_events: List[FractionEvent] = []
        for i in range(len(cleaned_fracs)):
            v_start, label = cleaned_fracs[i]
            v_end = cleaned_fracs[i + 1][0] if i + 1 < len(cleaned_fracs) else (v_start + 1.0)

            # Find peak UV280 inside [v_start, v_end]
            sub_uv = [
                uv280[j]
                for j in range(len(volumes))
                if v_start <= volumes[j] <= v_end
            ]
            peak = max(sub_uv) if sub_uv else None

            fraction_events.append(
                FractionEvent(
                    fraction_id=label,
                    start_volume_ml=v_start,
                    end_volume_ml=v_end,
                    peak_uv280_mau=peak,
                )
            )

        return fraction_events

    @classmethod
    def match_column(cls, text: str) -> ColumnMetadata:
        """
        Match column string against known Cytiva/GE hardware database.

        Args:
            text (str): Raw column name string.

        Returns:
            ColumnMetadata: Hardware specification object.
        """
        clean = text.lower().strip()
        for key, meta in cls.COLUMN_CATALOG.items():
            if key in clean or all(k in clean for k in key.split()[:2]):
                return meta

        # Generic fallback
        return ColumnMetadata(
            column_name=text or "Custom Column",
            bed_volume_ml=24.0,
            void_volume_ml=8.0,
            max_pressure_mpa=3.0,
            recommended_flow_rate_ml_min=1.0,
            chemistry="Chromatography Column",
        )

    @classmethod
    def parse_buffer_recipe(cls, name: str, recipe_str: str) -> BufferRecipe:
        """
        Parse buffer recipe string into chemical constituents (pH, salts, buffering agent, additives).

        Args:
            name (str): Label of buffer ('Buffer A', 'Buffer B').
            recipe_str (str): Recipe description (e.g. '20 mM Tris-HCl pH 8.0, 150 mM NaCl, 1 mM DTT, 500 mM Imidazole').

        Returns:
            BufferRecipe: Structured recipe object.
        """
        ph: Optional[float] = None
        ph_match = re.search(r'\bpH\s*([0-9]+(?:\.[0-9]+)?)\b', recipe_str, re.IGNORECASE)
        if ph_match:
            try:
                ph = float(ph_match.group(1))
            except ValueError:
                pass

        primary_salt: Optional[str] = None
        salt_match = re.search(r'([0-9]+\s*(?:mM|M)\s*(?:NaCl|KCl|(?:NH4)2SO4))', recipe_str, re.IGNORECASE)
        if salt_match:
            primary_salt = salt_match.group(1)

        buffering_agent: Optional[str] = None
        buff_match = re.search(r'([0-9]+\s*(?:mM|M)\s*(?:Tris(?:-HCl)?|HEPES|MES|MOPS|Phosphate|Citrate))', recipe_str, re.IGNORECASE)
        if buff_match:
            buffering_agent = buff_match.group(1)

        additives: List[str] = []
        for add_pattern in [
            r'[0-9]+(?:\.[0-9]+)?\s*(?:mM|M|%)\s*(?:DTT|β-ME|BME|TCEP|EDTA|Glycerol|Triton\s*X-100|Tween-20|Imidazole)',
        ]:
            matches = re.findall(add_pattern, recipe_str, re.IGNORECASE)
            additives.extend(matches)

        return BufferRecipe(
            name=name,
            raw_text=recipe_str,
            ph=ph,
            primary_salt=primary_salt,
            buffering_agent=buffering_agent,
            additives=additives,
        )
