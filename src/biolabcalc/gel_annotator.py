"""Gel Labeling Add-on: Annotate gel electrophoresis images, label lanes, map molecular weights, and export publication-ready figures."""

from __future__ import annotations
import math
import os
from typing import Dict, List, Optional, Tuple, Any
from PIL import Image, ImageOps, ImageEnhance
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.drawing.image import Image as OpenpyxlImage

from .gels import LADDER_CATALOG, calculate_rf, GelBand

NAVY_HEADER = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
WHITE_BOLD_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
BOLD_FONT = Font(name="Calibri", size=11, bold=True)
REGULAR_FONT = Font(name="Calibri", size=11)
THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)


class GelAnnotator:
    """Publication-grade gel annotation and lane/molecular-weight labeling add-on."""

    def __init__(
        self,
        image_path: Optional[str] = None,
        num_lanes: int = 6,
        title: str = "Agarose Gel Electrophoresis",
        gel_info: str = "1.0% Agarose in 1X TAE",
        invert_colors: bool = False,
    ):
        self.image_path = image_path
        self.title = title
        self.gel_info = gel_info
        self.invert_colors = invert_colors
        self.raw_image: Optional[Image.Image] = None

        if image_path and os.path.exists(image_path):
            img = Image.open(image_path).convert("RGB")
            if invert_colors:
                img = ImageOps.invert(img)
            self.raw_image = img

        self.lanes: List[str] = [f"Lane {i+1}" for i in range(num_lanes)]
        self.ladder_lane: Optional[int] = 1
        self.ladder_type: str = "1kb_dna"
        self.ladder_side: str = "left"
        self.bands: List[Dict[str, Any]] = []

    @classmethod
    def from_image(
        cls,
        image_path: str,
        title: str = "Gel Electrophoresis Analysis",
        gel_info: str = "1.0% Agarose",
        invert_colors: bool = False,
    ) -> GelAnnotator:
        """Create a GelAnnotator instance from an existing gel image file (TIFF, PNG, JPG)."""
        return cls(image_path=image_path, title=title, gel_info=gel_info, invert_colors=invert_colors)

    @classmethod
    def synthetic(
        cls,
        num_lanes: int = 6,
        title: str = "Simulated Gel Electrophoresis",
        gel_info: str = "1.0% Agarose in 1X TAE",
        invert_colors: bool = True,
    ) -> GelAnnotator:
        """Create a GelAnnotator instance for rendering a synthetic gel schematic."""
        return cls(image_path=None, num_lanes=num_lanes, title=title, gel_info=gel_info, invert_colors=invert_colors)

    def set_lanes(self, lane_labels: List[str]) -> GelAnnotator:
        """Define custom names for each lane (e.g. ['Ladder', 'Ctrl', 'PCR Product', 'Digest'])."""
        self.lanes = [str(l).strip() for l in lane_labels]
        return self

    def add_ladder(
        self,
        lane_index: int = 1,
        ladder_type: str = "1kb_dna",
        side: str = "left",
    ) -> GelAnnotator:
        """Designate a lane as a molecular weight ladder and set the reference ladder type."""
        self.ladder_lane = lane_index
        self.ladder_type = ladder_type.lower().replace("-", "_").replace(" ", "_")
        self.ladder_side = side
        return self

    def add_band(
        self,
        lane_index: int,
        size_bp_or_kda: float,
        label: str = "",
        color: str = "#FFCC00",
        draw_arrow: bool = True,
    ) -> GelAnnotator:
        """Add an annotation for a specific band in a lane with optional callout arrow."""
        self.bands.append({
            "lane": lane_index,
            "size": size_bp_or_kda,
            "label": label or f"{size_bp_or_kda}",
            "color": color,
            "arrow": draw_arrow,
        })
        return self

    def _generate_synthetic_canvas(self, width: int = 900, height: int = 700) -> Image.Image:
        """Generate a realistic synthetic gel electrophoresis background with subtle gradient."""
        # Create dark or light background
        bg_val = 250 if self.invert_colors else 20
        img = Image.new("RGB", (width, height), color=(bg_val, bg_val, bg_val))
        return img

    def render(
        self,
        output_path: str,
        dpi: int = 300,
        show_ticks: bool = True,
        header_rotation: int = 40,
    ) -> str:
        """Render the fully annotated gel figure with lane labels, MW ladders, and callout arrows."""
        num_lanes = len(self.lanes)
        ladder_info = LADDER_CATALOG.get(self.ladder_type, LADDER_CATALOG["1kb_dna"])
        ladder_bands = sorted(ladder_info["bands"], reverse=True)
        min_size = min(ladder_bands)
        max_size = max(ladder_bands)
        unit = ladder_info["unit"]

        fig_width = max(7.0, num_lanes * 1.3 + 2.5)
        fig_height = 8.5
        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)

        # Plot background
        gel_left = 1.8
        gel_right = fig_width - 1.2
        gel_top = 7.0
        gel_bottom = 1.0
        gel_w = gel_right - gel_left
        gel_h = gel_top - gel_bottom

        if self.raw_image is not None:
            # Display user image in gel area
            ax.imshow(self.raw_image, extent=[gel_left, gel_right, gel_bottom, gel_top], aspect="auto")
        else:
            # Synthetic gel background
            bg_color = "#F4F5F7" if self.invert_colors else "#181A1F"
            well_color = "#D1D5DB" if self.invert_colors else "#2D3139"
            band_color = "#1F2937" if self.invert_colors else "#E5E7EB"

            gel_rect = patches.FancyBboxPatch(
                (gel_left, gel_bottom), gel_w, gel_h,
                boxstyle="round,pad=0.02,rounding_size=0.1",
                facecolor=bg_color, edgecolor="#6B7280", linewidth=1.5
            )
            ax.add_patch(gel_rect)

            # Draw loading wells at top
            lane_spacing = gel_w / num_lanes
            for i in range(num_lanes):
                lane_x = gel_left + (i + 0.5) * lane_spacing
                well_w = lane_spacing * 0.55
                well_h = 0.22
                well = patches.Rectangle(
                    (lane_x - well_w / 2, gel_top - 0.35), well_w, well_h,
                    facecolor=well_color, edgecolor="#9CA3AF", linewidth=0.8
                )
                ax.add_patch(well)

            # Draw synthetic ladder bands in ladder lane
            if self.ladder_lane is not None and 1 <= self.ladder_lane <= num_lanes:
                l_x = gel_left + (self.ladder_lane - 0.5) * lane_spacing
                bw = lane_spacing * 0.5
                for b_size in ladder_bands:
                    rf = calculate_rf(b_size, min_size, max_size)
                    by = gel_top - 0.45 - (rf * (gel_h - 0.8))
                    is_ref = b_size in ladder_info.get("reference_bands", [])
                    bh = 0.08 if is_ref else 0.045
                    alpha = 0.95 if is_ref else 0.75
                    band = patches.FancyBboxPatch(
                        (l_x - bw / 2, by - bh / 2), bw, bh,
                        boxstyle="round,pad=0.01",
                        facecolor=band_color, edgecolor="none", alpha=alpha
                    )
                    ax.add_patch(band)

            # Draw synthetic sample bands
            for b_spec in self.bands:
                lane_idx = b_spec["lane"]
                if 1 <= lane_idx <= num_lanes and lane_idx != self.ladder_lane:
                    s_x = gel_left + (lane_idx - 0.5) * lane_spacing
                    rf = calculate_rf(b_spec["size"], min_size, max_size)
                    by = gel_top - 0.45 - (rf * (gel_h - 0.8))
                    bw = lane_spacing * 0.52
                    bh = 0.06
                    band = patches.FancyBboxPatch(
                        (s_x - bw / 2, by - bh / 2), bw, bh,
                        boxstyle="round,pad=0.01",
                        facecolor=band_color, edgecolor="none", alpha=0.85
                    )
                    ax.add_patch(band)

        # Draw Lane Numbers and Headers
        lane_spacing = gel_w / num_lanes
        for i, lane_name in enumerate(self.lanes):
            lane_x = gel_left + (i + 0.5) * lane_spacing

            # Lane number pill
            ax.text(
                lane_x, gel_top + 0.15, f"{i+1}",
                ha="center", va="center", fontsize=9, fontweight="bold",
                color="#FFFFFF",
                bbox=dict(boxstyle="circle,pad=0.25", facecolor="#1F4E79", edgecolor="none")
            )

            # Lane sample label
            ax.text(
                lane_x, gel_top + 0.45, lane_name,
                ha="left", va="bottom", fontsize=10, fontweight="bold",
                rotation=header_rotation, color="#111827"
            )

        # Draw Ladder Molecular Weight Labels
        if show_ticks and self.ladder_lane is not None:
            l_x = gel_left + (self.ladder_lane - 0.5) * lane_spacing
            tick_x = gel_left - 0.15 if self.ladder_side == "left" else gel_right + 0.15
            ha_align = "right" if self.ladder_side == "left" else "left"

            # Ladder Title
            ax.text(
                tick_x, gel_top + 0.1, f"MW ({unit})",
                ha=ha_align, va="bottom", fontsize=9, fontweight="bold", color="#1F4E79"
            )

            for b_size in ladder_bands:
                rf = calculate_rf(b_size, min_size, max_size)
                by = gel_top - 0.45 - (rf * (gel_h - 0.8))
                is_ref = b_size in ladder_info.get("reference_bands", [])

                # Format label (e.g. 10000 -> 10 kb, 500 -> 500 bp, or 250 kDa)
                if unit == "bp" and b_size >= 1000:
                    lbl_str = f"{b_size / 1000:.1f}".rstrip("0").rstrip(".") + " kb"
                else:
                    lbl_str = f"{b_size} {unit}"

                if is_ref:
                    lbl_str += " *"

                # Line connecting ladder band to text
                ax.plot([tick_x + (0.08 if self.ladder_side == "left" else -0.08), tick_x], [by, by], color="#9CA3AF", linewidth=0.8, linestyle=":")
                ax.text(
                    tick_x, by, lbl_str,
                    ha=ha_align, va="center", fontsize=8.5,
                    fontweight="bold" if is_ref else "normal",
                    color="#1F4E79" if is_ref else "#4B5563"
                )

        # Draw Sample Band Annotations with Arrows
        for b_spec in self.bands:
            lane_idx = b_spec["lane"]
            if 1 <= lane_idx <= num_lanes:
                s_x = gel_left + (lane_idx - 0.5) * lane_spacing
                rf = calculate_rf(b_spec["size"], min_size, max_size)
                by = gel_top - 0.45 - (rf * (gel_h - 0.8))
                callout_text = b_spec["label"]

                if b_spec.get("arrow", True):
                    # Place callout offset to the right or above
                    target_x = s_x + (lane_spacing * 0.35)
                    text_x = s_x + (lane_spacing * 0.65)
                    ax.annotate(
                        callout_text,
                        xy=(s_x, by), xycoords="data",
                        xytext=(text_x, by + 0.15), textcoords="data",
                        arrowprops=dict(arrowstyle="->", color=b_spec["color"], lw=1.5),
                        ha="left", va="center", fontsize=8.5, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="#FEF3C7", edgecolor="#D97706", alpha=0.95),
                        color="#92400E"
                    )

        # Title and Gel Info
        ax.text(
            (gel_left + gel_right) / 2, fig_height - 0.45, self.title,
            ha="center", va="top", fontsize=14, fontweight="bold", color="#1F4E79"
        )
        ax.text(
            (gel_left + gel_right) / 2, fig_height - 0.85, self.gel_info,
            ha="center", va="top", fontsize=10, fontstyle="italic", color="#4B5563"
        )

        ax.set_xlim(0, fig_width)
        ax.set_ylim(0, fig_height)
        ax.axis("off")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)

        return output_path

    def embed_in_excel(self, excel_path: str, sheet_name: str = "Annotated_Gel") -> str:
        """Render gel figure and embed it along with an annotation data table into an Excel workbook."""
        wb = openpyxl.load_workbook(excel_path) if os.path.exists(excel_path) else openpyxl.Workbook()
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
        else:
            ws = wb.create_sheet(title=sheet_name)

        ws.views.sheetView[0].showGridLines = True
        ws.cell(row=1, column=1, value=self.title).font = Font(name="Calibri", size=16, bold=True, color="1F4E79")
        ws.cell(row=2, column=1, value=f"{self.gel_info} | Generated via BioLabCalc Gel Annotator").font = Font(name="Calibri", size=9, italic=True, color="595959")

        # Table of Lanes and Bands
        ws.cell(row=4, column=1, value="Lane Annotation Summary").font = Font(name="Calibri", size=12, bold=True, color="1F4E79")
        headers = ["Lane #", "Sample Name / Identity", "Type", "Observed Bands", "Target Size", "Notes"]
        for c_idx, h in enumerate(headers, 1):
            c = ws.cell(row=5, column=c_idx, value=h)
            c.fill = NAVY_HEADER
            c.font = WHITE_BOLD_FONT
            c.alignment = Alignment(horizontal="center")

        ladder_info = LADDER_CATALOG.get(self.ladder_type, LADDER_CATALOG["1kb_dna"])

        for idx, lane_name in enumerate(self.lanes, 1):
            row_idx = 5 + idx
            is_lad = (idx == self.ladder_lane)
            l_type = "MW Ladder" if is_lad else "Experimental Sample"

            # Find matching bands
            matched = [b for b in self.bands if b["lane"] == idx]
            bands_str = ", ".join(f"{b['size']} {ladder_info['unit']}" for b in matched) if matched else ("Ladder series" if is_lad else "-")
            target_str = ", ".join(b["label"] for b in matched) if matched else ("Standard markers" if is_lad else "Unannotated")

            vals = [idx, lane_name, l_type, bands_str, target_str, ladder_info["name"] if is_lad else ""]
            for c_idx, val in enumerate(vals, 1):
                cell = ws.cell(row=row_idx, column=c_idx, value=val)
                cell.font = REGULAR_FONT
                cell.border = THIN_BORDER
                cell.alignment = Alignment(horizontal="center" if c_idx in (1, 3) else "left")

        # Render image to temporary file and embed
        temp_img = os.path.join(os.path.dirname(os.path.abspath(excel_path)), "temp_gel_render.png")
        self.render(temp_img, dpi=180)

        img_obj = OpenpyxlImage(temp_img)
        # Position image below table
        img_start_row = 8 + len(self.lanes)
        ws.cell(row=img_start_row - 1, column=1, value="Electrophoresis Gel Figure").font = Font(name="Calibri", size=12, bold=True, color="1F4E79")
        ws.add_image(img_obj, f"A{img_start_row}")

        wb.save(excel_path)
        return excel_path
