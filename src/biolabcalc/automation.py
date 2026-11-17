"""
Module: biolabcalc.automation
Component: 96/384-Well Microplate Designer & Liquid-Handler Protocol Generator
Architectural Role: Pure-Python high-throughput liquid-handling automation engine
supporting serial dilutions, PCR master-mix distribution, ELISA/BCA standard curves,
and direct protocol compilation for Labcyte Echo (CSV), Opentrons OT-2/Flex (Python),
and PyLabRobot (JSON).

Adheres strictly to TEA immutability principles:
- Frozen domain dataclasses (@dataclass(frozen=True)).
- Immutable collections (Tuple[...]).
- Zero mandatory external dependencies (pure Python standard library).
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


# ============================================================================
# Coordinate Geometry & Well Indexing
# ============================================================================

ROW_LABELS_96: Tuple[str, ...] = tuple("ABCDEFGH")
ROW_LABELS_384: Tuple[str, ...] = tuple("ABCDEFGHIJKLMNOP")


def get_plate_dimensions(plate_type: str = "96-well") -> Tuple[int, int]:
    """Return (num_rows, num_cols) for standard microplate formats."""
    ptype = plate_type.lower().replace(" ", "").replace("-", "").replace("_", "")
    if "384" in ptype:
        return 16, 24
    return 8, 12


def index_to_well(index: int, plate_type: str = "96-well", by_row: bool = True) -> str:
    """
    Convert zero-based integer index to well coordinate (e.g., 0 -> 'A1').
    
    If by_row is True: indices advance A1, A2, ..., A12, B1, ...
    If by_row is False: indices advance A1, B1, ..., H1, A2, ...
    """
    n_rows, n_cols = get_plate_dimensions(plate_type)
    total_wells = n_rows * n_cols
    if index < 0 or index >= total_wells:
        raise ValueError(f"Well index {index} is out of bounds for {plate_type} (0 .. {total_wells - 1}).")

    row_labels = ROW_LABELS_384 if n_rows == 16 else ROW_LABELS_96

    if by_row:
        row_idx = index // n_cols
        col_idx = index % n_cols
    else:
        row_idx = index % n_rows
        col_idx = index // n_rows

    return f"{row_labels[row_idx]}{col_idx + 1}"


def well_to_index(well: str, plate_type: str = "96-well", by_row: bool = True) -> int:
    """Convert well coordinate (e.g. 'A1', 'H12') to zero-based integer index."""
    clean_well = well.strip().upper()
    if not clean_well or not clean_well[0].isalpha() or not clean_well[1:].isdigit():
        raise ValueError(f"Invalid well format: '{well}'. Expected e.g. 'A1', 'B12'.")

    row_char = clean_well[0]
    col_num = int(clean_well[1:])

    n_rows, n_cols = get_plate_dimensions(plate_type)
    row_labels = ROW_LABELS_384 if n_rows == 16 else ROW_LABELS_96

    if row_char not in row_labels:
        raise ValueError(f"Row '{row_char}' out of bounds for {plate_type}.")
    if col_num < 1 or col_num > n_cols:
        raise ValueError(f"Column '{col_num}' out of bounds for {plate_type} (1 .. {n_cols}).")

    row_idx = row_labels.index(row_char)
    col_idx = col_num - 1

    if by_row:
        return (row_idx * n_cols) + col_idx
    return (col_idx * n_rows) + row_idx


# ============================================================================
# Frozen Domain Models
# ============================================================================

@dataclass(frozen=True)
class WellTransfer:
    """Individual pipetting transfer operation."""
    source_plate: str
    source_well: str
    dest_plate: str
    dest_well: str
    volume_ul: float
    reagent_name: str = ""
    notes: str = ""

    def __post_init__(self):
        if self.volume_ul <= 0:
            raise ValueError(f"Transfer volume must be strictly positive: got {self.volume_ul} µL.")
        for w in (self.source_well, self.dest_well):
            if w:
                clean_w = w.strip().upper()
                if len(clean_w) >= 2 and clean_w[0].isalpha() and clean_w[1:].isdigit() and len(clean_w) <= 3:
                    row_char = clean_w[0]
                    col_num = int(clean_w[1:])
                    if row_char > "P" or col_num > 24 or col_num < 1:
                        raise ValueError(f"Well coordinate '{w}' is out of bounds.")


@dataclass(frozen=True)
class PlateMap:
    """Immutable 2D microplate layout containing sample assignments, volumes, and concentrations."""
    plate_id: str
    plate_type: str = "96-well"
    well_contents: Tuple[Tuple[str, str], ...] = ()      # ((well_id, sample_name), ...)
    volumes_ul: Tuple[Tuple[str, float], ...] = ()        # ((well_id, volume_ul), ...)
    concentrations: Tuple[Tuple[str, float], ...] = ()    # ((well_id, conc), ...)
    metadata: Tuple[Tuple[str, str], ...] = ()

    def get_content(self, well: str) -> str:
        w_clean = well.strip().upper()
        for wid, content in self.well_contents:
            if wid == w_clean:
                return content
        return ""

    def get_volume(self, well: str) -> float:
        w_clean = well.strip().upper()
        for wid, vol in self.volumes_ul:
            if wid == w_clean:
                return vol
        return 0.0

    def get_concentration(self, well: str) -> float:
        w_clean = well.strip().upper()
        for wid, conc in self.concentrations:
            if wid == w_clean:
                return conc
        return 0.0

    def _repr_html_(self) -> str:
        """Render visual 2D microplate grid diagram for Jupyter notebooks."""
        import html
        n_rows, n_cols = get_plate_dimensions(self.plate_type)
        row_labels = ROW_LABELS_384 if n_rows == 16 else ROW_LABELS_96

        header_th = "".join(f"<th style='width: 32px; padding: 4px; font-size: 10px; color: #64748B; text-align: center;'>{c}</th>" for c in range(1, n_cols + 1))

        rows_html = []
        for r_idx, r_label in enumerate(row_labels):
            cells = [f"<td style='padding: 2px 6px; font-weight: bold; font-size: 10px; color: #64748B; text-align: center;'>{r_label}</td>"]
            for c_idx in range(1, n_cols + 1):
                well_id = f"{r_label}{c_idx}"
                content = self.get_content(well_id)
                vol = self.get_volume(well_id)
                conc = self.get_concentration(well_id)

                bg_color = "#F8FAFC"
                border_color = "#E2E8F0"
                tooltip = f"{well_id}: Empty"

                if content:
                    tooltip = f"{well_id}: {html.escape(content)} ({vol:.1f} µL)"
                    if conc > 0:
                        tooltip += f" [{conc:g}]"
                    bg_color = "#DBEAFE" if "sample" in content.lower() or "standard" in content.lower() else "#DCFCE7"
                    border_color = "#93C5FD" if "sample" in content.lower() or "standard" in content.lower() else "#86EFAC"

                cells.append(
                    f"<td title='{tooltip}' style='width: 28px; height: 24px; padding: 0; text-align: center; "
                    f"background: {bg_color}; border: 1px solid {border_color}; border-radius: 4px; font-size: 8.5px; color: #1E293B; cursor: pointer;'>"
                    f"</td>"
                )
            rows_html.append(f"<tr>{''.join(cells)}</tr>")

        return (
            f'<div style="font-family: system-ui, sans-serif; border: 1px solid #CBD5E1; border-radius: 8px; padding: 12px; background: #FFFFFF; max-width: fit-content; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">'
            f'<strong style="font-size: 13px; color: #0F172A;">Plate: {html.escape(self.plate_id)}</strong>'
            f'<span style="background: #F1F5F9; color: #475569; font-size: 10.5px; font-weight: 600; padding: 2px 6px; border-radius: 8px;">{self.plate_type}</span>'
            f'</div>'
            f'<table style="border-collapse: separate; border-spacing: 2px;">'
            f'<tr><th style="width: 20px;"></th>{header_th}</tr>'
            f'{"".join(rows_html)}'
            f'</table>'
            f'</div>'
        )


@dataclass(frozen=True)
class AutomationWorklist:
    """Complete executable liquid-handling pipetting worklist and layout definition."""
    name: str
    transfers: Tuple[WellTransfer, ...]
    plates: Tuple[PlateMap, ...]
    total_volume_ul: float = 0.0
    notes: Tuple[str, ...] = ()

    def __post_init__(self):
        for f in ("transfers", "plates", "notes"):
            val = getattr(self, f, ())
            if isinstance(val, (list, set, tuple)):
                object.__setattr__(self, f, tuple(val))

    def _repr_html_(self) -> str:
        """Render worklist summary with interactive plate diagrams for Jupyter notebooks."""
        import html
        plates_html = "".join(f"<div style='margin-bottom: 12px;'>{p._repr_html_()}</div>" for p in self.plates)
        return (
            f'<div style="font-family: system-ui, sans-serif; margin-bottom: 10px;">'
            f'<div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 12px; margin-bottom: 10px;">'
            f'<strong style="font-size: 14px; color: #0F172A;">Automation Worklist: {html.escape(self.name)}</strong>'
            f'<span style="margin-left: 12px; color: #64748B; font-size: 12px;">{len(self.transfers)} transfers • {self.total_volume_ul:.1f} µL total</span>'
            f'</div>'
            f'{plates_html}'
            f'</div>'
        )


# ============================================================================
# High-Level Microplate Automation Designers
# ============================================================================

def design_serial_dilution_plate(
    start_conc: float = 100.0,
    dilution_factor: float = 2.0,
    num_points: int = 8,
    replicates: int = 3,
    plate_type: str = "96-well",
    start_row: str = "A",
    start_col: int = 1,
    initial_volume_ul: float = 100.0,
    transfer_volume_ul: float = 50.0,
    diluent_name: str = "Assay Buffer",
    sample_name: str = "Standard",
) -> AutomationWorklist:
    """
    Design a serial dilution series across a 96-well or 384-well microplate.
    
    Parameters:
        start_conc: Highest standard concentration (e.g. 100.0 ng/mL).
        dilution_factor: Fold dilution per step (e.g. 2.0 for 1:2, 10.0 for 1:10).
        num_points: Number of dilution steps (e.g. 8 points, last point is typically blank).
        replicates: Number of replicate rows or columns (e.g. triplicates = 3).
        plate_type: "96-well" or "384-well".
        initial_volume_ul: Total liquid volume in wells after mixing.
        transfer_volume_ul: Volume transferred from well to well.
    """
    if dilution_factor <= 1.0:
        raise ValueError(f"Dilution factor must be > 1.0, got {dilution_factor}.")
    if num_points <= 1:
        raise ValueError(f"num_points must be at least 2, got {num_points}.")
    if replicates <= 0:
        raise ValueError("replicates must be strictly positive.")

    n_rows, n_cols = get_plate_dimensions(plate_type)
    row_labels = ROW_LABELS_384 if n_rows == 16 else ROW_LABELS_96

    start_r_idx = row_labels.index(start_row.upper())
    if start_r_idx + replicates > n_rows:
        raise ValueError(f"Replicates ({replicates}) exceed available plate rows from '{start_row}'.")
    if start_col + num_points - 1 > n_cols:
        raise ValueError(f"Dilution points ({num_points}) exceed available columns from {start_col}.")

    transfers: List[WellTransfer] = []
    well_contents: List[Tuple[str, str]] = []
    volumes_ul: List[Tuple[str, float]] = []
    concentrations: List[Tuple[str, float]] = []

    # Calculate concentration points (last point is zero / blank)
    concs: List[float] = []
    c = float(start_conc)
    for p in range(num_points - 1):
        concs.append(round(c, 4))
        c /= dilution_factor
    concs.append(0.0)  # Blank control

    diluent_vol_prefill = initial_volume_ul - transfer_volume_ul

    # Build plate mapping and transfer worklist
    for rep in range(replicates):
        r_char = row_labels[start_r_idx + rep]

        # 1. Prefill diluent into points 2..N
        for pt_idx in range(1, num_points):
            dest_well = f"{r_char}{start_col + pt_idx}"
            transfers.append(
                WellTransfer(
                    source_plate="Reservoir_1",
                    source_well="A1",
                    dest_plate="Assay_Plate",
                    dest_well=dest_well,
                    volume_ul=diluent_vol_prefill if pt_idx < num_points - 1 else initial_volume_ul,
                    reagent_name=diluent_name,
                    notes=f"Prefill diluent to {dest_well}",
                )
            )

        # 2. Add starting stock to well 1
        first_well = f"{r_char}{start_col}"
        transfers.append(
            WellTransfer(
                source_plate="Sample_Rack",
                source_well=f"A{rep + 1}",
                dest_plate="Assay_Plate",
                dest_well=first_well,
                volume_ul=initial_volume_ul,
                reagent_name=f"{sample_name}_Stock",
                notes=f"Load initial standard stock into {first_well}",
            )
        )

        # 3. Serial transfers from col i to col i+1
        for pt_idx in range(num_points - 2):
            w_src = f"{r_char}{start_col + pt_idx}"
            w_dst = f"{r_char}{start_col + pt_idx + 1}"
            transfers.append(
                WellTransfer(
                    source_plate="Assay_Plate",
                    source_well=w_src,
                    dest_plate="Assay_Plate",
                    dest_well=w_dst,
                    volume_ul=transfer_volume_ul,
                    reagent_name=f"{sample_name}_Transfer",
                    notes=f"Serial transfer {transfer_volume_ul} µL from {w_src} to {w_dst} and mix",
                )
            )

        # Record well annotations
        for pt_idx in range(num_points):
            w_id = f"{r_char}{start_col + pt_idx}"
            name = f"{sample_name}_Point_{pt_idx + 1}" if pt_idx < num_points - 1 else "Blank_Control"
            well_contents.append((w_id, name))
            volumes_ul.append((w_id, initial_volume_ul))
            concentrations.append((w_id, concs[pt_idx]))

    assay_plate = PlateMap(
        plate_id="Assay_Plate",
        plate_type=plate_type,
        well_contents=tuple(well_contents),
        volumes_ul=tuple(volumes_ul),
        concentrations=tuple(concentrations),
    )

    tot_vol = sum(t.volume_ul for t in transfers)

    return AutomationWorklist(
        name=f"Serial_Dilution_{dilution_factor}x_{sample_name}",
        transfers=tuple(transfers),
        plates=(assay_plate,),
        total_volume_ul=round(tot_vol, 2),
        notes=(
            f"Dilution factor: 1:{dilution_factor:g}",
            f"Concentration range: {concs[0]} to {concs[-2]} (plus blank)",
            f"Replicates: {replicates}",
        ),
    )


def design_pcr_setup_plate(
    num_reactions: int,
    master_mix_volume_ul: float = 20.0,
    template_volume_ul: float = 5.0,
    plate_type: str = "96-well",
    destination_plate_id: str = "PCR_Plate",
) -> AutomationWorklist:
    """
    Design master mix and template distribution for 96/384-well PCR setup.
    """
    if num_reactions <= 0:
        raise ValueError("num_reactions must be strictly positive.")

    n_rows, n_cols = get_plate_dimensions(plate_type)
    max_reactions = n_rows * n_cols
    if num_reactions > max_reactions:
        raise ValueError(f"Reactions ({num_reactions}) exceed plate capacity ({max_reactions}).")

    transfers: List[WellTransfer] = []
    well_contents: List[Tuple[str, str]] = []
    volumes: List[Tuple[str, float]] = []

    for idx in range(num_reactions):
        dest_well = index_to_well(idx, plate_type=plate_type, by_row=True)
        # Distribute master mix
        transfers.append(
            WellTransfer(
                source_plate="MasterMix_Reservoir",
                source_well="A1",
                dest_plate=destination_plate_id,
                dest_well=dest_well,
                volume_ul=master_mix_volume_ul,
                reagent_name="PCR_MasterMix",
                notes=f"Dispense {master_mix_volume_ul} µL Master Mix to {dest_well}",
            )
        )
        # Distribute template DNA
        src_temp_well = index_to_well(idx, plate_type="96-well", by_row=True)
        transfers.append(
            WellTransfer(
                source_plate="Template_Plate",
                source_well=src_temp_well,
                dest_plate=destination_plate_id,
                dest_well=dest_well,
                volume_ul=template_volume_ul,
                reagent_name=f"Template_{idx + 1}",
                notes=f"Add {template_volume_ul} µL Template from {src_temp_well} to {dest_well}",
            )
        )
        well_contents.append((dest_well, f"Reaction_{idx + 1}"))
        volumes.append((dest_well, master_mix_volume_ul + template_volume_ul))

    pcr_plate = PlateMap(
        plate_id=destination_plate_id,
        plate_type=plate_type,
        well_contents=tuple(well_contents),
        volumes_ul=tuple(volumes),
    )

    tot_vol = sum(t.volume_ul for t in transfers)

    return AutomationWorklist(
        name=f"PCR_Setup_{num_reactions}_Reactions",
        transfers=tuple(transfers),
        plates=(pcr_plate,),
        total_volume_ul=round(tot_vol, 2),
        notes=(
            f"Reaction volume: {master_mix_volume_ul + template_volume_ul:.1f} µL",
            f"Total reactions: {num_reactions}",
        ),
    )


# ============================================================================
# Liquid Handler Protocol Exporters
# ============================================================================

def export_echo_csv(
    worklist: AutomationWorklist,
    filepath: Optional[Union[str, Path]] = None,
) -> str:
    """
    Export worklist to Labcyte / Beckman Coulter Echo acoustic liquid handler CSV format.
    
    Echo pick list schema:
    Source Plate Name,Source Well,Destination Plate Name,Destination Well,Transfer Volume
    (Transfer Volume is in nanoliters: volume_ul * 1000.0).
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([
        "Source Plate Name",
        "Source Well",
        "Destination Plate Name",
        "Destination Well",
        "Transfer Volume",
    ])

    for t in worklist.transfers:
        transfer_vol_nl = round(t.volume_ul * 1000.0, 1)
        writer.writerow([
            t.source_plate,
            t.source_well,
            t.dest_plate,
            t.dest_well,
            transfer_vol_nl,
        ])

    csv_text = output.getvalue()

    if filepath is not None:
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(csv_text, encoding="utf-8")

    return csv_text


def export_opentrons_protocol(
    worklist: AutomationWorklist,
    filepath: Optional[Union[str, Path]] = None,
    robot_type: str = "Flex",
    pipette_name: str = "flex_1channel_50",
) -> str:
    """
    Compile worklist to executable standalone Opentrons Python protocol (API v2.16+).
    Compatible with OT-2 and Opentrons Flex.
    """
    clean_name = worklist.name.replace(" ", "_")
    source_plates = sorted(list(set(t.source_plate for t in worklist.transfers)))
    dest_plates = sorted(list(set(t.dest_plate for t in worklist.transfers)))

    code_lines = [
        '"""',
        f'Opentrons Protocol: {worklist.name}',
        'Generated automatically by BioLabCalc Automation Engine',
        '"""',
        '',
        'from opentrons import protocol_api',
        '',
        'metadata = {',
        f'    "protocolName": "{worklist.name}",',
        '    "author": "BioLabCalc Core",',
        '    "description": "High-precision automated liquid handling protocol",',
        '    "apiLevel": "2.16"',
        '}',
        '',
        'def run(protocol: protocol_api.ProtocolContext):',
        '    # Labware setup',
        '    tiprack = protocol.load_labware("opentrons_flex_96_tiprack_50ul", "D1")',
        f'    pipette = protocol.load_instrument("{pipette_name}", "right", tip_racks=[tiprack])',
        '',
        '    plates = {}',
    ]

    deck_slots = ["C1", "C2", "B1", "B2", "A1", "A2", "D2"]
    slot_idx = 0

    all_plates = sorted(list(set(source_plates + dest_plates)))
    for p_name in all_plates:
        slot = deck_slots[slot_idx % len(deck_slots)]
        slot_idx += 1
        code_lines.append(f'    plates["{p_name}"] = protocol.load_labware("corning_96_wellplate_360ul_flat", "{slot}")')

    code_lines.append('')
    code_lines.append('    # Execution transfers')
    for t in worklist.transfers:
        code_lines.append(
            f'    pipette.transfer({t.volume_ul:.1f}, '
            f'plates["{t.source_plate}"]["{t.source_well}"], '
            f'plates["{t.dest_plate}"]["{t.dest_well}"], '
            f'new_tip="always")'
        )

    code_lines.append('')
    script_str = "\n".join(code_lines)

    if filepath is not None:
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(script_str, encoding="utf-8")

    return script_str


def export_pylabrobot_json(
    worklist: AutomationWorklist,
    filepath: Optional[Union[str, Path]] = None,
) -> str:
    """
    Export worklist to JSON worklist specification for PyLabRobot / Hamilton / Tecan robots.
    """
    data = {
        "version": "1.0",
        "name": worklist.name,
        "total_volume_ul": worklist.total_volume_ul,
        "transfers": [
            {
                "source": {"plate": t.source_plate, "well": t.source_well},
                "destination": {"plate": t.dest_plate, "well": t.dest_well},
                "volume_ul": t.volume_ul,
                "reagent": t.reagent_name,
                "notes": t.notes,
            }
            for t in worklist.transfers
        ],
        "plates": [
            {
                "plate_id": p.plate_id,
                "plate_type": p.plate_type,
                "wells": [
                    {
                        "well_id": wid,
                        "content": p.get_content(wid),
                        "volume_ul": p.get_volume(wid),
                        "concentration": p.get_concentration(wid),
                    }
                    for wid, _ in p.well_contents
                ],
            }
            for p in worklist.plates
        ],
    }

    json_str = json.dumps(data, indent=2)

    if filepath is not None:
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json_str, encoding="utf-8")

    return json_str
