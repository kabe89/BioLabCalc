"""Printable Protocol & Plate Benchtop Companion for BioLabCalc.

Engineered for laboratory bench workstations, clean hoods, and physical lab notebooks:
- 7-Stage thermodynamic "Enzyme-Last" order of addition
- Master mix overage calculation (+10% / +15% / discrete extra reactions)
- Pipette sizing intelligence (P2, P10, P20, P200, P1000)
- 96-well / 384-well / strip-tube visual layout map with orientation chamfer at A1
- Notebook trim guides (8"x10" and 7.5"x9.5") and tamper-evident paste seams
- Pure HTML5/CSS @media print engine (zero heavy C-dependencies)
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple


# 7-Stage Thermodynamic Addition Priority (Enzyme-Last Hierarchy)
ADDITION_PRIORITY: Dict[str, int] = {
    "water": 1,
    "solvent": 1,
    "buffer": 2,
    "salt": 2,
    "additive": 3,
    "enhancer": 3,
    "dntp": 4,
    "nucleotide": 4,
    "primer": 5,
    "probe": 5,
    "template": 6,
    "sample": 6,
    "enzyme": 7,
    "polymerase": 7,
    "ligase": 7,
}


@dataclass(frozen=True)
class BenchReagent:
    """Individual chemical or biological component in a laboratory master mix."""

    name: str
    stock_conc: str
    final_conc: str
    vol_per_rxn_ul: float
    total_vol_ul: float
    category: str = "reagent"
    temperature_badge: str = "[❄️ 4°C ICE]"
    mixing_note: str = "Invert to mix"
    addition_order: int = 5
    pipette_recommendation: str = "P10"
    is_separate_addition: bool = False  # e.g. Template DNA added to individual wells


@dataclass(frozen=True)
class MasterMixFormulation:
    """Formulation details for a scaled benchtop master mix."""

    total_reactions: int
    excess_percent: float
    multiplier: float
    single_rxn_volume_ul: float
    master_mix_total_volume_ul: float
    master_mix_aliquot_per_well_ul: float
    reagents: Tuple[BenchReagent, ...]
    pipette_for_master_mix: str
    pipette_for_aliquot: str


@dataclass(frozen=True)
class BenchWell:
    """Individual well coordinates and contents on a microplate or strip rack."""

    well_id: str  # e.g. "A1", "H12"
    row: str  # "A" - "H" / "A" - "P"
    col: int  # 1 - 12 / 1 - 24
    sample_name: str
    sample_type: Literal["sample", "control_pos", "control_neg", "blank", "empty"] = "sample"
    notes: str = ""


@dataclass(frozen=True)
class BenchPlateMap:
    """Plate layout grid for 96-well, 384-well, or 24-tube bench strip racks."""

    plate_type: Literal["96-well", "384-well", "24-tube", "8-strip"]
    wells: Tuple[BenchWell, ...]
    total_wells: int
    used_wells_count: int


@dataclass(frozen=True)
class GLPSignOffBlock:
    """Archival compliance and witness sign-off block for laboratory notebooks."""

    operator_name: str = ""
    date: str = ""
    project_id: str = ""
    protocol_id: str = ""
    notebook_number: str = ""
    page_number: str = ""
    witness_name: str = ""
    witness_date: str = ""


def determine_pipette_tool(vol_ul: float, verbose: bool = False) -> str:
    """Assign recommended micropipette based on target volume."""
    if vol_ul <= 0:
        return "—"
    if vol_ul <= 2.0:
        return "P2 (0.1–2 µL)" if verbose else "P2"
    elif vol_ul <= 10.0:
        return "P10 (0.5–10 µL)" if verbose else "P10"
    elif vol_ul <= 20.0:
        return "P20 (2–20 µL)" if verbose else "P20"
    elif vol_ul <= 200.0:
        return "P200 (20–200 µL)" if verbose else "P200"
    else:
        return "P1000 (100–1000 µL)" if verbose else "P1000"


def build_bench_master_mix(
    components: Optional[Sequence[Dict[str, Any]]] = None,
    total_reactions: Optional[int] = None,
    reaction_volume_ul: Optional[float] = None,
    excess_percent: float = 10.0,
    discrete_extra_rxns: int = 0,
    separate_template: bool = True,
    num_reactions: Optional[int] = None,
    reagents_per_rxn: Optional[Sequence[Dict[str, Any]]] = None,
    single_rxn_total_vol_ul: Optional[float] = None,
    aliquot_per_well_ul: Optional[float] = None,
) -> MasterMixFormulation:
    """Formulate a scaled master mix adhering to the Enzyme-Last addition hierarchy.

    Args:
        components: List of dicts with keys: name, stock_conc/stock, final_conc/final,
          vol_ul/volume_ul, category
        total_reactions: Number of samples/wells
        reaction_volume_ul: Optional total reaction volume to compute water QS
        excess_percent: Overage percentage (default: 10.0%)
        discrete_extra_rxns: Discrete dead-volume reactions (e.g. +2 for
          troughs)
    """
    actual_components = reagents_per_rxn if reagents_per_rxn is not None else (components or [])
    actual_reactions = num_reactions if num_reactions is not None else (total_reactions if total_reactions is not None else 1)
    actual_rxn_vol = single_rxn_total_vol_ul if single_rxn_total_vol_ul is not None else reaction_volume_ul

    multiplier = (actual_reactions + discrete_extra_rxns) * (1.0 + excess_percent / 100.0)

    reagents_out: List[BenchReagent] = []
    specified_vol = 0.0

    for c in actual_components:
        vol = float(c.get("volume_ul", c.get("vol_ul", 0.0)))
        cat = str(c.get("category", "reagent")).lower()
        if cat in ("water", "solvent"):
            continue
        specified_vol += vol

    # Auto-calculate Water QS if total reaction volume is specified
    water_vol = 0.0
    water_name = "Nuclease-Free Water (ddH2O)"
    if actual_rxn_vol is not None and actual_rxn_vol > specified_vol:
        water_vol = actual_rxn_vol - specified_vol
    elif any(str(c.get("category", "")).lower() in ("water", "solvent") for c in actual_components):
        for c in actual_components:
            if str(c.get("category", "")).lower() in ("water", "solvent"):
                water_vol = float(c.get("volume_ul", c.get("vol_ul", 0.0)))
                water_name = c.get("name", water_name)
                break

    # Add water first
    if water_vol > 0:
        tot_w = round(water_vol * multiplier, 2)
        reagents_out.append(
            BenchReagent(
                name=water_name,
                stock_conc="100%",
                final_conc="QS",
                vol_per_rxn_ul=round(water_vol, 2),
                total_vol_ul=tot_w,
                category="water",
                temperature_badge="[🌡️ 20°C RT / ❄️ 4°C]",
                mixing_note="Vortex gently before dispensing",
                addition_order=1,
                pipette_recommendation=determine_pipette_tool(tot_w),
                is_separate_addition=False,
            )
        )

    # Process remaining components
    for c in actual_components:
        cat = str(c.get("category", "reagent")).lower()
        if cat in ("water", "solvent"):
            continue

        vol = float(c.get("volume_ul", c.get("vol_ul", 0.0)))
        tot = round(vol * multiplier, 2)
        prio = ADDITION_PRIORITY.get(cat, 5)

        is_sep = bool(c.get("is_separate", c.get("is_separate_addition", False))) or (separate_template and (cat in ("template", "sample")))

        # Select temperature badge & mixing directive
        if cat in ("enzyme", "polymerase", "ligase"):
            badge = "[🧊 -20°C COLD BLOCK]"
            mix = "Flick 5x gently; NEVER VORTEX (shear sensitive)"
        elif cat in ("dntp", "nucleotide"):
            badge = "[❄️ 4°C ICE]"
            mix = "Pulse vortex & quick spin down"
        elif cat in ("buffer", "salt"):
            badge = "[🌡️ 20°C RT / ❄️ 4°C]"
            mix = "Vortex to ensure complete salt dissolution"
        elif is_sep:
            badge = "[❄️ 4°C ICE]"
            mix = "Pipette directly into designated well"
        else:
            badge = "[❄️ 4°C ICE]"
            mix = "Invert or pulse spin"

        reagents_out.append(
            BenchReagent(
                name=c.get("name", "Reagent"),
                stock_conc=str(c.get("stock_conc", c.get("stock", "—"))),
                final_conc=str(c.get("final_conc", c.get("final", "—"))),
                vol_per_rxn_ul=round(vol, 2),
                total_vol_ul=tot if not is_sep else vol,
                category=cat,
                temperature_badge=badge,
                mixing_note=mix,
                addition_order=prio,
                pipette_recommendation=determine_pipette_tool(tot if not is_sep else vol),
                is_separate_addition=is_sep,
            )
        )

    # Sort strictly by thermodynamic hierarchy (Enzyme-Last!)
    reagents_out.sort(key=lambda r: (r.is_separate_addition, r.addition_order, r.name))

    single_vol = single_rxn_total_vol_ul if single_rxn_total_vol_ul is not None else sum(r.vol_per_rxn_ul for r in reagents_out)
    mm_vol = sum(r.total_vol_ul for r in reagents_out if not r.is_separate_addition)
    aliquot_vol = aliquot_per_well_ul if aliquot_per_well_ul is not None else sum(r.vol_per_rxn_ul for r in reagents_out if not r.is_separate_addition)

    return MasterMixFormulation(
        total_reactions=actual_reactions,
        excess_percent=excess_percent,
        multiplier=round(multiplier, 2),
        single_rxn_volume_ul=round(single_vol, 2),
        master_mix_total_volume_ul=round(mm_vol, 2),
        master_mix_aliquot_per_well_ul=round(aliquot_vol, 2),
        reagents=tuple(reagents_out),
        pipette_for_master_mix=determine_pipette_tool(mm_vol),
        pipette_for_aliquot=determine_pipette_tool(aliquot_vol),
    )


def generate_plate_bench_sheet(
    samples: Optional[Sequence[str]] = None,
    replicates: int = 1,
    plate_type: Literal["96-well", "384-well", "24-tube", "8-strip"] = "96-well",
    controls: Optional[Sequence[Tuple[str, str]]] = None,
    sample_names: Optional[Sequence[str]] = None,
) -> BenchPlateMap:
    """Layout samples, replicates, and controls across standard microplates or strip tubes."""
    eff_samples = list(sample_names) if sample_names is not None else (list(samples) if samples is not None else [])
    items: List[Tuple[str, str]] = []
    # Add controls first if provided
    if controls:
        for c_name, c_type in controls:
            items.append((c_name, c_type))

    # Add samples with replicates
    for s in eff_samples:
        for rep in range(1, replicates + 1):
            s_lbl = f"{s} #{rep}" if replicates > 1 else s
            items.append((s_lbl, "sample"))

    wells: List[BenchWell] = []
    if plate_type == "96-well":
        rows = ["A", "B", "C", "D", "E", "F", "G", "H"]
        cols = list(range(1, 13))
        idx = 0
        for row in rows:
            for col in cols:
                w_id = f"{row}{col}"
                if idx < len(items):
                    s_name, s_type = items[idx]
                    wells.append(BenchWell(well_id=w_id, row=row, col=col, sample_name=s_name, sample_type=s_type))  # type: ignore
                    idx += 1
                else:
                    wells.append(BenchWell(well_id=w_id, row=row, col=col, sample_name="", sample_type="empty"))
        return BenchPlateMap(plate_type=plate_type, wells=tuple(wells), total_wells=96, used_wells_count=len(items))

    elif plate_type == "24-tube":
        # 3 strips of 8 tubes
        strip_letters = ["S1", "S2", "S3"]
        idx = 0
        for s_idx, strip in enumerate(strip_letters, 1):
            for t_num in range(1, 9):
                w_id = f"{strip}-T{t_num}"
                if idx < len(items):
                    s_name, s_type = items[idx]
                    wells.append(BenchWell(well_id=w_id, row=strip, col=t_num, sample_name=s_name, sample_type=s_type))  # type: ignore
                    idx += 1
                else:
                    wells.append(BenchWell(well_id=w_id, row=strip, col=t_num, sample_name="", sample_type="empty"))
        return BenchPlateMap(plate_type=plate_type, wells=tuple(wells), total_wells=24, used_wells_count=len(items))

    elif plate_type == "8-strip":
        idx = 0
        for t_num in range(1, 9):
            w_id = f"Tube-{t_num}"
            if idx < len(items):
                s_name, s_type = items[idx]
                wells.append(BenchWell(well_id=w_id, row="Strip", col=t_num, sample_name=s_name, sample_type=s_type))  # type: ignore
                idx += 1
            else:
                wells.append(BenchWell(well_id=w_id, row="Strip", col=t_num, sample_name="", sample_type="empty"))
        return BenchPlateMap(plate_type=plate_type, wells=tuple(wells), total_wells=8, used_wells_count=len(items))

    else:
        # 384-well plate
        rows = [chr(65 + i) for i in range(16)]  # A - P
        cols = list(range(1, 25))
        idx = 0
        for col in cols:
            for row in rows:
                w_id = f"{row}{col}"
                if idx < len(items):
                    s_name, s_type = items[idx]
                    wells.append(BenchWell(well_id=w_id, row=row, col=col, sample_name=s_name, sample_type=s_type))  # type: ignore
                    idx += 1
                else:
                    wells.append(BenchWell(well_id=w_id, row=row, col=col, sample_name="", sample_type="empty"))
        return BenchPlateMap(plate_type="384-well", wells=tuple(wells), total_wells=384, used_wells_count=len(items))


def render_bench_companion_html(
    title: str,
    formulation: Optional[MasterMixFormulation] = None,
    plate_map: Optional[BenchPlateMap] = None,
    sign_off: Optional[GLPSignOffBlock] = None,
    notebook_format: Literal["8x10", "7.5x9.5", "letter", "a4"] = "8x10",
    master_mix: Optional[MasterMixFormulation] = None,
    page_trim: Optional[str] = None,
) -> str:
    """Render self-contained HTML5 companion sheet with @media print CSS for lab notebooks."""
    so = sign_off or GLPSignOffBlock()
    mm = master_mix if master_mix is not None else formulation
    if mm is None:
        raise ValueError("A MasterMixFormulation must be provided via formulation or master_mix.")
    trim_fmt = page_trim if page_trim is not None else notebook_format

    # Notebook trim width / max-width styling
    if trim_fmt == "8x10":
        max_w = "7.6in"
        cut_label = "TRIM ALONG DASHED LINE TO FIT 8.0\" x 10.0\" HARDBOUND LAB NOTEBOOK"
    elif trim_fmt == "7.5x9.5":
        max_w = "7.1in"
        cut_label = "TRIM ALONG DASHED LINE TO FIT 7.5\" x 9.5\" SMYTH-SEWN NOTEBOOK"
    else:
        max_w = "100%"
        cut_label = "LABORATORY BENCHTOP PROTOCOL RECORD"

    # Separate master mix reagents vs individual template additions
    mm_reagents = [r for r in mm.reagents if not r.is_separate_addition]
    sep_reagents = [r for r in mm.reagents if r.is_separate_addition]

    html_out = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="UTF-8">',
        f"  <title>{html.escape(title)} - Benchtop Protocol Companion</title>",
        "  <style>",
        "    @page {",
        "      size: letter portrait;",
        "      margin: 0.35in;",
        "    }",
        "    * { box-sizing: border-box; }",
        "    body {",
        "      font-family: Arial, Helvetica, -apple-system, sans-serif;",
        "      color: #000000;",
        "      background: #FFFFFF;",
        "      margin: 0;",
        "      padding: 0;",
        "      font-size: 8.5pt;",
        "      line-height: 1.3;",
        "    }",
        "    .notebook-trim-box {",
        f"      max-width: {max_w};",
        "      margin: 0 auto;",
        "      border: 1.5px dashed #475569;",
        "      padding: 12px 14px;",
        "      background: #FFFFFF;",
        "      position: relative;",
        "    }",
        "    .cut-line-banner {",
        "      font-size: 7pt;",
        "      font-weight: 700;",
        "      color: #475569;",
        "      text-align: center;",
        "      letter-spacing: 0.5px;",
        "      margin-bottom: 8px;",
        "      padding-bottom: 4px;",
        "      border-bottom: 1px dotted #94A3B8;",
        "    }",
        "    .paste-seam-margin {",
        "      font-size: 6.5pt;",
        "      color: #64748B;",
        "      border: 1px dashed #CBD5E1;",
        "      background: #F8FAFC;",
        "      padding: 3px 6px;",
        "      text-align: center;",
        "      margin-bottom: 10px;",
        "      text-transform: uppercase;",
        "      letter-spacing: 0.5px;",
        "    }",
        "    .header-table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }",
        "    .header-table td { padding: 3px 0; vertical-align: top; }",
        "    .title-h1 { font-size: 13pt; font-weight: bold; margin: 0; color: #000000; }",
        "    .meta-tag { font-size: 7.5pt; color: #334155; }",
        "    .stat-pill { display: inline-block; border: 1px solid #000; padding: 2px 6px; font-weight: bold; font-size: 7.5pt; border-radius: 3px; margin-right: 4px; }",
        "    .section-title { font-size: 9.5pt; font-weight: bold; border-bottom: 1.5px solid #000; padding-bottom: 2px; margin: 10px 0 6px 0; text-transform: uppercase; letter-spacing: 0.5px; display: flex; justify-content: space-between; }",
        "    .bench-table { width: 100%; border-collapse: collapse; font-size: 8pt; margin-bottom: 10px; }",
        "    .bench-table th { background: #000000; color: #FFFFFF; font-weight: bold; padding: 4px 6px; text-align: left; font-size: 7.5pt; border: 1px solid #000; }",
        "    .bench-table td { border: 1px solid #000000; padding: 4px 6px; vertical-align: middle; }",
        "    .bench-table tr:nth-child(even) { background: #F8FAFC; }",
        "    .check-box { width: 13px; height: 13px; border: 1.5px solid #000; display: inline-block; vertical-align: middle; margin-right: 4px; background: #FFF; }",
        "    .temp-badge { font-size: 7pt; font-weight: bold; border: 1px solid #64748B; padding: 1px 4px; border-radius: 3px; background: #FFF; white-space: nowrap; }",
        "    .plate-grid-container { margin: 8px 0; }",
        "    .plate-table { width: 100%; border-collapse: collapse; text-align: center; font-size: 7pt; }",
        "    .plate-table th { background: #E2E8F0; color: #000; font-weight: bold; padding: 3px; border: 1px solid #94A3B8; }",
        "    .plate-cell { border: 1.2px solid #000; height: 26px; vertical-align: top; padding: 2px; position: relative; background: #FFF; }",
        "    .plate-cell.control-cell { border: 2px double #000; background: #F1F5F9; font-weight: bold; }",
        "    .plate-cell.empty-cell { border: 1px dotted #CBD5E1; color: #94A3B8; }",
        "    .well-check { position: absolute; right: 2px; top: 2px; width: 8px; height: 8px; border: 1px solid #000; }",
        "    .chamfer-notch { display: inline-block; width: 0; height: 0; border-top: 6px solid #000; border-right: 6px solid transparent; margin-right: 2px; }",
        "    .sign-off-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 7.5pt; }",
        "    .sign-off-table td { border: 1px solid #000; padding: 4px 6px; }",
        "    .print-button-bar { text-align: center; margin: 15px 0; }",
        "    .print-btn { background: #1F4E79; color: white; border: none; padding: 8px 18px; font-size: 10pt; font-weight: bold; border-radius: 6px; cursor: pointer; }",
        "    @media print {",
        "      .print-button-bar { display: none !important; }",
        "      .notebook-trim-box { border: 1.5px dashed #000000 !important; }",
        "      body { print-color-adjust: exact; -webkit-print-color-adjust: exact; }",
        "    }",
        "  </style>",
        "</head>",
        "<body>",
        '  <div class="print-button-bar">',
        '    <button class="print-btn" onclick="window.print()">🖨️ Print Protocol Companion Sheet</button>',
        "  </div>",
        '  <div class="notebook-trim-box">',
        f'    <div class="cut-line-banner">✄ - - - {cut_label} - - - ✄</div>',
        '    <div class="paste-seam-margin">[ TAPE / GLUE SEAM — OPERATOR INITIAL & DATE ACROSS BORDER AND PAGE ]</div>',
        '    <table class="header-table">',
        "      <tr>",
        f'        <td><h1 class="title-h1">🧬 {html.escape(title)}</h1>',
        f'        <div class="meta-tag">Generated via BioLabCalc | Zero-Server Air-Gapped Benchtop Companion</div></td>',
        '        <td style="text-align: right;">',
        f'          <span class="stat-pill">RXNS: {mm.total_reactions} (+{mm.excess_percent:g}%)</span>',
        f'          <span class="stat-pill">VOL: {mm.single_rxn_volume_ul:g} µL</span>',
        f'          <span class="stat-pill">TOTAL: {mm.master_mix_total_volume_ul:g} µL</span>',
        "        </td>",
        "      </tr>",
        "    </table>",
        '    <div class="section-title">',
        "      <span>1. Master Mix Formulation (Enzyme-Last Order)</span>",
        f"      <span style=\"font-size:7.5pt; font-weight:normal;\">Dispense <strong>{mm.master_mix_aliquot_per_well_ul:g} µL</strong>/well using <strong>{html.escape(mm.pipette_for_aliquot)}</strong></span>",
        "    </div>",
        '    <table class="bench-table">',
        "      <thead>",
        "        <tr>",
        '          <th style="width: 30px;">Done</th>',
        '          <th style="width: 25px;">#</th>',
        "          <th>Component / Reagent</th>",
        '          <th style="width: 75px;">Stock</th>',
        '          <th style="width: 75px;">Final</th>',
        f'          <th style="width: 70px;">1 Rxn ({mm.single_rxn_volume_ul:g} µL)</th>',
        f'          <th style="width: 85px;">{mm.total_reactions} Rxns (x{mm.multiplier:g})</th>',
        '          <th style="width: 90px;">Pipette Tool</th>',
        "          <th>Temp & Directive</th>",
        "        </tr>",
        "      </thead>",
        "      <tbody>",
    ]

    for idx, r in enumerate(mm_reagents, 1):
        html_out.extend(
            [
                "        <tr>",
                '          <td style="text-align: center;"><span class="check-box"></span></td>',
                f'          <td style="text-align: center; font-weight: bold;">{idx}</td>',
                f"          <td><strong>{html.escape(r.name)}</strong></td>",
                f"          <td>{html.escape(r.stock_conc)}</td>",
                f"          <td>{html.escape(r.final_conc)}</td>",
                f'          <td style="text-align: right; font-weight: bold;">{r.vol_per_rxn_ul:g} µL</td>',
                f'          <td style="text-align: right; font-weight: bold; background: #FEF3C7;">{r.total_vol_ul:g} µL</td>',
                f"          <td>{html.escape(r.pipette_recommendation)}</td>",
                f'          <td><span class="temp-badge">{html.escape(r.temperature_badge)}</span> <span style="font-size:7pt; color:#475569;">{html.escape(r.mixing_note)}</span></td>',
                "        </tr>",
            ]
        )

    html_out.extend(
        [
            "      </tbody>",
            "    </table>",
        ]
    )

    if sep_reagents:
        html_out.extend(
            [
                '    <div class="section-title">2. Separate Additions (Individual Sample / Template)</div>',
                '    <table class="bench-table">',
                "      <thead>",
                "        <tr>",
                '          <th style="width: 30px;">Done</th>',
                "          <th>Component</th>",
                '          <th style="width: 75px;">Stock</th>',
                '          <th style="width: 75px;">Final</th>',
                '          <th style="width: 80px;">Vol / Well</th>',
                '          <th style="width: 100px;">Pipette Tool</th>',
                "          <th>Directive</th>",
                "        </tr>",
                "      </thead>",
                "      <tbody>",
            ]
        )
        for r in sep_reagents:
            html_out.extend(
                [
                    "        <tr>",
                    '          <td style="text-align: center;"><span class="check-box"></span></td>',
                    f"          <td><strong>{html.escape(r.name)}</strong></td>",
                    f"          <td>{html.escape(r.stock_conc)}</td>",
                    f"          <td>{html.escape(r.final_conc)}</td>",
                    f'          <td style="text-align: right; font-weight: bold;">{r.vol_per_rxn_ul:g} µL</td>',
                    f"          <td>{html.escape(r.pipette_recommendation)}</td>",
                    f'          <td><span class="temp-badge">{html.escape(r.temperature_badge)}</span> {html.escape(r.mixing_note)}</td>',
                    "        </tr>",
                ]
            )
        html_out.extend(["      </tbody>", "    </table>"])

    # Render Visual Plate Map
    if plate_map is not None:
        html_out.extend(
            [
                '    <div class="section-title">',
                f"      <span>3. Visual {html.escape(plate_map.plate_type.upper())} Loading Map</span>",
                f'      <span style="font-size:7.5pt; font-weight:normal;"><span class="chamfer-notch"></span>Notch at A1 | Used: <strong>{plate_map.used_wells_count} / {plate_map.total_wells}</strong></span>',
                "    </div>",
                '    <div class="plate-grid-container">',
            ]
        )

        if plate_map.plate_type == "96-well":
            rows = ["A", "B", "C", "D", "E", "F", "G", "H"]
            cols = list(range(1, 13))
            well_dict = {w.well_id: w for w in plate_map.wells}

            html_out.append('      <table class="plate-table"><thead><tr><th style="width:20px;"></th>')
            for c in cols:
                html_out.append(f"<th>{c}</th>")
            html_out.append("</tr></thead><tbody>")

            for r in rows:
                html_out.append(f"<tr><th>{r}</th>")
                for c in cols:
                    wid = f"{r}{c}"
                    w = well_dict.get(wid)
                    if w and w.sample_name:
                        is_ctrl = w.sample_type.startswith("control")
                        c_cls = "plate-cell control-cell" if is_ctrl else "plate-cell"
                        s_disp = html.escape(w.sample_name)
                        if len(s_disp) > 10:
                            s_disp = s_disp[:9] + "…"
                        html_out.append(
                            f'<td class="{c_cls}"><span class="well-check"></span><span style="font-size:6.5pt; color:#64748B;">{wid}</span><br/><strong>{s_disp}</strong></td>'
                        )
                    else:
                        html_out.append(
                            f'<td class="plate-cell empty-cell"><span style="font-size:6.5pt;">{wid}</span></td>'
                        )
                html_out.append("</tr>")
            html_out.append("</tbody></table>")

        elif plate_map.plate_type in ("24-tube", "8-strip"):
            well_dict = {w.well_id: w for w in plate_map.wells}
            html_out.append('      <table class="bench-table"><thead><tr><th>Rack / Strip</th>')
            for t in range(1, 9):
                html_out.append(f"<th>Tube {t}</th>")
            html_out.append("</tr></thead><tbody>")

            strip_names = (
                ["S1", "S2", "S3"] if plate_map.plate_type == "24-tube" else ["Strip"]
            )
            for s in strip_names:
                html_out.append(f"<tr><td><strong>{s}</strong></td>")
                for t in range(1, 9):
                    wid = f"{s}-T{t}" if plate_map.plate_type == "24-tube" else f"Tube-{t}"
                    w = well_dict.get(wid)
                    if w and w.sample_name:
                        html_out.append(
                            f'<td><span class="check-box"></span><strong>{html.escape(w.sample_name)}</strong></td>'
                        )
                    else:
                        html_out.append('<td style="color:#94A3B8;">—</td>')
                html_out.append("</tr>")
            html_out.append("</tbody></table>")

        html_out.append("    </div>")

    # Archival GLP/GMP Sign-off block
    html_out.extend(
        [
            '    <div class="section-title">4. Physical Notebook & Archival Compliance Sign-Off</div>',
            '    <table class="sign-off-table">',
            "      <tr>",
            f'        <td style="width: 25%;"><strong>Operator Name:</strong> {html.escape(so.operator_name)}</td>',
            '        <td style="width: 25%;"><strong>Operator Signature:</strong></td>',
            f'        <td style="width: 25%;"><strong>Date Executed:</strong> {html.escape(so.date)}</td>',
            f'        <td style="width: 25%;"><strong>Project ID:</strong> {html.escape(so.project_id)}</td>',
            "      </tr>",
            "      <tr>",
            f'        <td><strong>Protocol / SOP ID:</strong> {html.escape(so.protocol_id)}</td>',
            f'        <td><strong>Notebook / Page #:</strong> {html.escape(so.notebook_number)} p.{html.escape(so.page_number)}</td>',
            f'        <td><strong>Witness / Reviewer:</strong> {html.escape(so.witness_name)}</td>',
            f'        <td><strong>Witness Signature & Date:</strong> {html.escape(so.witness_date)}</td>',
            "      </tr>",
            "      <tr>",
            '        <td colspan="4" style="font-size: 6.5pt; color: #475569; font-style: italic;">',
            "          I confirm that all formulations and protocol parameters were executed strictly in accordance with standard operating procedures and entered concurrently into this laboratory record.",
            "        </td>",
            "      </tr>",
            "    </table>",
            "  </div>",
            "</body>",
            "</html>",
        ]
    )

    return "\n".join(html_out)
