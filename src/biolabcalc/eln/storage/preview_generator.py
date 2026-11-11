"""
Module: biolabcalc.eln.storage.preview_generator
Component: Lossless Web Preview Generator
Agent: @agent: eln-parser-agent
Architectural Role: Generates high-fidelity, web-optimized previews for scientific
images, 16-bit gel scans, electrophysiology sweeps, and chromatography traces.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageOps

from biolabcalc.eln.storage.blob_store import BlobStore


@dataclass
class PreviewResult:
    """
    Data descriptor for a generated preview asset.

    Attributes:
        preview_bytes (bytes): Raw binary payload of the generated preview (PNG or SVG).
        mime_type (str): Media MIME type ('image/png', 'image/svg+xml', etc.).
        width (int): Pixel width (or SVG viewBox width).
        height (int): Pixel height (or SVG viewBox height).
        original_sha256 (str): SHA-256 digest of the source raw data.
        preview_type (str): Categorization ('image', 'gel_scan', 'trace_svg', 'trace_png').
        metadata (Dict[str, Any]): Supplementary preview metadata (contrast parameters, channel names, etc.).

    Architectural Role:
        Payload object for web UI rendering and cached preview storage.
        @agent: eln-parser-agent
    """

    preview_bytes: bytes
    mime_type: str
    width: int
    height: int
    original_sha256: str
    preview_type: str
    metadata: Dict[str, Any]


class PreviewGenerator:
    """
    Scientific Preview Generation Engine.

    Generates web-ready previews across multiple laboratory modalities:
    - Standard microphotography & laboratory images (PNG, JPEG, WebP)
    - Bio-Rad & fluorometry 16-bit gel scans with auto-contrast & band enhancement
    - Multi-series chromatography and electrophysiology traces (pure vector SVG & PNG)

    Architectural Role:
        Transformation layer between raw instrument data blobs and browser/client presentation.
        @agent: eln-parser-agent
    """

    @classmethod
    def generate_image_preview(
        cls,
        data: bytes,
        max_dim: int = 1200,
        output_format: str = "PNG",
    ) -> PreviewResult:
        """
        Generate a web-optimized image preview from raw image bytes.

        Args:
            data (bytes): Input image file bytes (PNG, JPEG, TIFF, BMP, WebP).
            max_dim (int): Maximum bounding dimension (width or height) in pixels.
            output_format (str): Target format, typically 'PNG' or 'JPEG'.

        Returns:
            PreviewResult: Generated web preview descriptor.
        """
        orig_sha = BlobStore.compute_sha256(data)
        with Image.open(io.BytesIO(data)) as img:
            # Preserve color profile or convert to RGB/RGBA
            if img.mode in ("I;16", "I", "F"):
                # 16-bit or float image - scale to 8-bit
                return cls.generate_gel_preview(data)

            target_img = img.copy()
            if target_img.mode not in ("RGB", "RGBA", "L"):
                target_img = target_img.convert("RGBA" if "A" in target_img.mode else "RGB")

            # Scale if larger than max_dim
            w, h = target_img.size
            if max(w, h) > max_dim:
                scale = max_dim / float(max(w, h))
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                target_img = target_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            else:
                new_w, new_h = w, h

            out_buf = io.BytesIO()
            fmt = output_format.upper()
            mime = "image/png" if fmt == "PNG" else "image/jpeg"
            if fmt == "JPEG" and target_img.mode == "RGBA":
                # Flatten transparent background to white for JPEG
                bg = Image.new("RGB", target_img.size, (255, 255, 255))
                bg.paste(target_img, mask=target_img.split()[3])
                target_img = bg
            target_img.save(out_buf, format=fmt, optimize=True)
            out_bytes = out_buf.getvalue()

        return PreviewResult(
            preview_bytes=out_bytes,
            mime_type=mime,
            width=new_w,
            height=new_h,
            original_sha256=orig_sha,
            preview_type="image",
            metadata={"original_dimensions": [w, h], "output_format": fmt},
        )

    @classmethod
    def generate_gel_preview(
        cls,
        data: bytes,
        auto_contrast: bool = True,
        invert: bool = False,
        gamma: float = 1.0,
        black_percentile: float = 0.5,
        white_percentile: float = 99.5,
    ) -> PreviewResult:
        """
        Generate an enhanced 8-bit grayscale preview for 16-bit or 8-bit gel scans.

        Applies robust percentile contrast stretching and optional inversion (dark bands on light background).

        Args:
            data (bytes): Raw TIFF or image bytes.
            auto_contrast (bool): Whether to perform dynamic range normalization.
            invert (bool): Invert polarity for publication clarity (light-on-dark to dark-on-light).
            gamma (float): Gamma correction exponent (> 1.0 brightens faint bands).
            black_percentile (float): Lower clip percentile (0.0 to 10.0).
            white_percentile (float): Upper clip percentile (90.0 to 100.0).

        Returns:
            PreviewResult: High-contrast 8-bit PNG preview.
        """
        orig_sha = BlobStore.compute_sha256(data)
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
            # Handle 16-bit grayscale or float
            if img.mode in ("I;16", "I", "F"):
                # Use raw pixel sequence
                raw_pixels = list(img.getdata())
                if auto_contrast and raw_pixels:
                    sorted_px = sorted(raw_pixels)
                    n = len(sorted_px)
                    b_idx = int(n * (black_percentile / 100.0))
                    w_idx = min(n - 1, int(n * (white_percentile / 100.0)))
                    min_val = sorted_px[b_idx]
                    max_val = sorted_px[w_idx]
                    if max_val <= min_val:
                        max_val = min_val + 1.0

                    scaled_pixels = []
                    diff = max_val - min_val
                    for p in raw_pixels:
                        norm = max(0.0, min(1.0, (p - min_val) / diff))
                        if gamma != 1.0 and norm > 0:
                            norm = math.pow(norm, 1.0 / gamma)
                        val = int(norm * 255.0)
                        if invert:
                            val = 255 - val
                        scaled_pixels.append(val)
                else:
                    max_possible = 65535.0 if img.mode == "I;16" else 255.0
                    scaled_pixels = [int(min(255, (p / max_possible) * 255)) for p in raw_pixels]
                    if invert:
                        scaled_pixels = [255 - p for p in scaled_pixels]

                out_img = Image.new("L", (w, h))
                out_img.putdata(scaled_pixels)
            else:
                out_img = img.convert("L")
                if auto_contrast:
                    out_img = ImageOps.autocontrast(out_img, cutoff=(int(black_percentile), int(100 - white_percentile)))
                if invert:
                    out_img = ImageOps.invert(out_img)

            # Cap preview resolution to 1600 on longest edge
            if max(w, h) > 1600:
                scale = 1600 / float(max(w, h))
                nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                out_img = out_img.resize((nw, nh), Image.Resampling.LANCZOS)
            else:
                nw, nh = w, h

            out_buf = io.BytesIO()
            out_img.save(out_buf, format="PNG", optimize=True)
            preview_bytes = out_buf.getvalue()

        return PreviewResult(
            preview_bytes=preview_bytes,
            mime_type="image/png",
            width=nw,
            height=nh,
            original_sha256=orig_sha,
            preview_type="gel_scan",
            metadata={
                "auto_contrast": auto_contrast,
                "invert": invert,
                "gamma": gamma,
                "original_dimensions": [w, h],
            },
        )

    @classmethod
    def generate_trace_preview_svg(
        cls,
        x_data: List[float],
        y_series: Dict[str, List[float]],
        title: str = "",
        x_label: str = "Time / Volume",
        y_label: str = "Signal",
        width: int = 800,
        height: int = 400,
        markers: Optional[List[Dict[str, Any]]] = None,
    ) -> PreviewResult:
        """
        Generate a standalone, interactive-ready vector SVG preview for chromatography and electrophysiology traces.

        Args:
            x_data (List[float]): Abscissa coordinates (time in ms, volume in mL, wavelength in nm).
            y_series (Dict[str, List[float]]): Series name mapped to ordinate coordinates.
            title (str): Chart title.
            x_label (str): X-axis label with units.
            y_label (str): Y-axis label with units.
            width (int): SVG viewport width.
            height (int): SVG viewport height.
            markers (Optional[List[Dict[str, Any]]]): Auxiliary vertical lines or fraction boundary markers.

        Returns:
            PreviewResult: High-definition SVG descriptor.
        """
        raw_hash_source = f"{x_data[:10]}_{list(y_series.keys())}".encode("utf-8")
        orig_sha = BlobStore.compute_sha256(raw_hash_source)

        margin_left = 65
        margin_right = 35
        margin_top = 45
        margin_bottom = 55

        plot_w = width - margin_left - margin_right
        plot_h = height - margin_top - margin_bottom

        if not x_data or not y_series:
            # Fallback empty plot
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
                f'<rect width="{width}" height="{height}" fill="#1e1e1e"/>'
                f'<text x="{width // 2}" y="{height // 2}" fill="#888" text-anchor="middle" font-family="sans-serif">No trace data available</text>'
                f"</svg>"
            )
            return PreviewResult(
                preview_bytes=svg.encode("utf-8"),
                mime_type="image/svg+xml",
                width=width,
                height=height,
                original_sha256=orig_sha,
                preview_type="trace_svg",
                metadata={"title": title, "series_count": 0},
            )

        min_x, max_x = min(x_data), max(x_data)
        if max_x <= min_x:
            max_x = min_x + 1.0

        all_y = [val for s in y_series.values() for val in s if math.isfinite(val)]
        min_y = min(all_y) if all_y else 0.0
        max_y = max(all_y) if all_y else 1.0
        if max_y <= min_y:
            max_y = min_y + 1.0

        y_range = max_y - min_y
        min_y_padded = min_y - 0.05 * y_range
        max_y_padded = max_y + 0.05 * y_range
        y_span = max_y_padded - min_y_padded

        def transform_pt(x: float, y: float) -> Tuple[float, float]:
            px = margin_left + ((x - min_x) / (max_x - min_x)) * plot_w
            py = margin_top + (1.0 - ((y - min_y_padded) / y_span)) * plot_h
            return px, py

        # Distinct modern palette for scientific series
        palette = [
            "#3b82f6",  # Blue (e.g. UV280)
            "#ef4444",  # Red (e.g. UV260)
            "#10b981",  # Green (e.g. Conductivity)
            "#f59e0b",  # Amber (e.g. Concentration %B)
            "#8b5cf6",  # Purple (e.g. UV215)
            "#06b6d4",  # Cyan (e.g. Flow rate)
            "#ec4899",  # Pink
        ]

        svg_lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">',
            f'  <rect width="{width}" height="{height}" fill="#0f172a" rx="8" />',
            f'  <rect x="{margin_left}" y="{margin_top}" width="{plot_w}" height="{plot_h}" fill="#1e293b" rx="4" />',
        ]

        # Draw grid lines
        grid_lines = 5
        for i in range(grid_lines + 1):
            gy = margin_top + (plot_h * i / grid_lines)
            val_y = max_y_padded - (y_span * i / grid_lines)
            svg_lines.append(
                f'  <line x1="{margin_left}" y1="{gy}" x2="{margin_left + plot_w}" y2="{gy}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3" />'
            )
            svg_lines.append(
                f'  <text x="{margin_left - 8}" y="{gy + 4}" fill="#94a3b8" font-size="11" text-anchor="end">{val_y:.1f}</text>'
            )

        for i in range(grid_lines + 1):
            gx = margin_left + (plot_w * i / grid_lines)
            val_x = min_x + ((max_x - min_x) * i / grid_lines)
            svg_lines.append(
                f'  <line x1="{gx}" y1="{margin_top}" x2="{gx}" y2="{margin_top + plot_h}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3" />'
            )
            svg_lines.append(
                f'  <text x="{gx}" y="{margin_top + plot_h + 18}" fill="#94a3b8" font-size="11" text-anchor="middle">{val_x:.1f}</text>'
            )

        # Draw markers (fractions or events)
        if markers:
            for m in markers:
                mx = m.get("x", m.get("start_volume_ml", 0.0))
                label = m.get("label", m.get("fraction_id", ""))
                px, _ = transform_pt(mx, min_y)
                if margin_left <= px <= margin_left + plot_w:
                    svg_lines.append(
                        f'  <line x1="{px:.2f}" y1="{margin_top}" x2="{px:.2f}" y2="{margin_top + plot_h}" stroke="#f43f5e" stroke-width="1" stroke-dasharray="2,2" opacity="0.7"/>'
                    )
                    if label:
                        svg_lines.append(
                            f'  <text x="{px:.2f}" y="{margin_top + 14}" fill="#fb7185" font-size="9" text-anchor="middle" font-weight="600">{label}</text>'
                        )

        # Plot each series
        legend_items = []
        for s_idx, (name, y_pts) in enumerate(y_series.items()):
            color = palette[s_idx % len(palette)]
            pts_str = []
            step = max(1, len(x_data) // 1000)  # Downsample if excessive points for SVG
            for i in range(0, min(len(x_data), len(y_pts)), step):
                px, py = transform_pt(x_data[i], y_pts[i])
                pts_str.append(f"{px:.2f},{py:.2f}")

            if pts_str:
                polyline_d = " ".join(pts_str)
                svg_lines.append(
                    f'  <polyline points="{polyline_d}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />'
                )
                legend_items.append((name, color))

        # Title & Axis labels
        if title:
            svg_lines.append(
                f'  <text x="{margin_left}" y="28" fill="#f8fafc" font-size="14" font-weight="600">{title}</text>'
            )
        svg_lines.append(
            f'  <text x="{margin_left + plot_w // 2}" y="{height - 12}" fill="#cbd5e1" font-size="12" text-anchor="middle">{x_label}</text>'
        )
        svg_lines.append(
            f'  <text x="18" y="{margin_top + plot_h // 2}" fill="#cbd5e1" font-size="12" text-anchor="middle" transform="rotate(-90 18 {margin_top + plot_h // 2})">{y_label}</text>'
        )

        # Legend in top right
        leg_x = margin_left + plot_w - 10
        leg_y = 26
        for name, color in reversed(legend_items):
            svg_lines.append(
                f'  <circle cx="{leg_x}" cy="{leg_y - 4}" r="4" fill="{color}" />'
            )
            svg_lines.append(
                f'  <text x="{leg_x - 8}" y="{leg_y}" fill="#e2e8f0" font-size="11" text-anchor="end">{name}</text>'
            )
            leg_x -= (len(name) * 7 + 25)

        svg_lines.append("</svg>")
        svg_bytes = "\n".join(svg_lines).encode("utf-8")

        return PreviewResult(
            preview_bytes=svg_bytes,
            mime_type="image/svg+xml",
            width=width,
            height=height,
            original_sha256=orig_sha,
            preview_type="trace_svg",
            metadata={
                "title": title,
                "x_label": x_label,
                "y_label": y_label,
                "series_names": list(y_series.keys()),
            },
        )

    @classmethod
    def generate_trace_preview_png(
        cls,
        x_data: List[float],
        y_series: Dict[str, List[float]],
        title: str = "",
        x_label: str = "Time / Volume",
        y_label: str = "Signal",
        width: int = 800,
        height: int = 400,
    ) -> PreviewResult:
        """
        Generate a raster PNG trace preview using pure Pillow rendering.

        Args:
            x_data (List[float]): Abscissa coordinates.
            y_series (Dict[str, List[float]]): Series names mapped to ordinates.
            title (str): Plot title.
            x_label (str): X axis label.
            y_label (str): Y axis label.
            width (int): Output pixel width.
            height (int): Output pixel height.

        Returns:
            PreviewResult: PNG raster preview.
        """
        img = Image.new("RGB", (width, height), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)

        margin_left = 60
        margin_right = 30
        margin_top = 40
        margin_bottom = 50

        plot_w = width - margin_left - margin_right
        plot_h = height - margin_top - margin_bottom

        draw.rectangle(
            [margin_left, margin_top, margin_left + plot_w, margin_top + plot_h],
            fill=(30, 41, 59),
            outline=(51, 65, 85),
        )

        all_y = [val for s in y_series.values() for val in s if math.isfinite(val)]
        min_y = min(all_y) if all_y else 0.0
        max_y = max(all_y) if all_y else 1.0
        if max_y <= min_y:
            max_y = min_y + 1.0

        min_x, max_x = (min(x_data), max(x_data)) if x_data else (0.0, 1.0)
        if max_x <= min_x:
            max_x = min_x + 1.0

        palette = [
            (59, 130, 246),  # Blue
            (239, 68, 68),  # Red
            (16, 185, 129),  # Green
            (245, 158, 11),  # Amber
            (139, 92, 246),  # Purple
        ]

        for s_idx, (name, y_pts) in enumerate(y_series.items()):
            color = palette[s_idx % len(palette)]
            pts: List[Tuple[int, int]] = []
            step = max(1, len(x_data) // 600)
            for i in range(0, min(len(x_data), len(y_pts)), step):
                nx = (x_data[i] - min_x) / (max_x - min_x)
                ny = (y_pts[i] - min_y) / (max_y - min_y)
                px = int(margin_left + nx * plot_w)
                py = int(margin_top + (1.0 - ny) * plot_h)
                pts.append((px, py))

            if len(pts) >= 2:
                draw.line(pts, fill=color, width=2)

        out_buf = io.BytesIO()
        img.save(out_buf, format="PNG", optimize=True)
        out_bytes = out_buf.getvalue()
        orig_sha = BlobStore.compute_sha256(out_bytes)

        return PreviewResult(
            preview_bytes=out_bytes,
            mime_type="image/png",
            width=width,
            height=height,
            original_sha256=orig_sha,
            preview_type="trace_png",
            metadata={"title": title, "series": list(y_series.keys())},
        )

    @classmethod
    def generate_preview(
        cls,
        data: bytes,
        filename: str = "",
        mime_type: str = "",
    ) -> PreviewResult:
        """
        Master automated dispatcher generating the optimal preview representation.

        Args:
            data (bytes): Raw asset binary data.
            filename (str): Name of the file.
            mime_type (str): Media MIME type.

        Returns:
            PreviewResult: Optimal preview representation.
        """
        lower_fn = filename.lower()
        if not mime_type:
            mime_type = BlobStore.detect_mime_type(lower_fn)

        if "tiff" in mime_type or lower_fn.endswith((".scn", ".tif", ".tiff")):
            return cls.generate_gel_preview(data)
        elif mime_type.startswith("image/"):
            return cls.generate_image_preview(data)
        else:
            # Fallback text representation or empty preview
            return cls.generate_trace_preview_svg(
                x_data=[0.0, 1.0],
                y_series={"Signal": [0.0, 0.0]},
                title=filename or "Laboratory Document",
            )
