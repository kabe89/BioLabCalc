"""
Module: biolabcalc.eln.parsers.biorad_parser
Component: Bio-Rad Image Lab (.scn) and Scientific Gel TIFF Parser
Architectural Role: Ingests Bio-Rad Image Lab (.scn) gel documentation files and 16-bit
fluorescent/chemiluminescent TIFF scans, extracting optical exposure metadata, instrument
parameters, dynamic range matrices, and generating publication-ready web previews.
"""

from __future__ import annotations

import io
import math
import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageOps

from biolabcalc.eln.storage.blob_store import BlobStore


@dataclass
class ExposureMetadata:
    """
    Physical acquisition parameters for gel/blot documentation scans.

    Attributes:
        exposure_time_seconds (float): Sensor integration time in seconds.
        application_name (str): Staining chemistry or imaging protocol (e.g. 'Chemi', 'Coomassie Blue', 'Ethidium Bromide').
        illumination_source (str): Excitation source ('UV', 'Epi-white', 'Chemiluminescence', 'Trans-blue').
        filter_name (str): Optical emission filter (e.g. '590/110', '530/28', 'None').
        binning (str): Pixel binning setting (e.g. '1x1', '2x2', '3x3').
        instrument_model (str): Imager hardware model (e.g. 'ChemiDoc MP', 'GelDoc Go').
        acquisition_time (str): Timestamp of scan.
        dynamic_range_bits (int): Native bit-depth of image sensor (e.g. 16).

    Architectural Role:
        Preserves instrumentation provenance for analytical gel quantification.
    """

    exposure_time_seconds: float = 0.0
    application_name: str = "Standard Gel"
    illumination_source: str = "Trans-UV"
    filter_name: str = "Standard"
    binning: str = "1x1"
    instrument_model: str = "Bio-Rad ChemiDoc"
    acquisition_time: str = ""
    dynamic_range_bits: int = 16


@dataclass
class BioRadImage:
    """
    Parsed gel documentation scan with scaled web preview and matrix parameters.

    Attributes:
        file_format (str): Source format ('SCN', 'TIFF_16', 'TIFF_8', 'IMAGE').
        width (int): Pixel width.
        height (int): Pixel height.
        bit_depth (int): Bit depth of pixel data (8, 16, or 32).
        channels (int): Channel count (1 for grayscale, 3/4 for RGB/overlay).
        min_pixel_value (float): Minimum recorded raw intensity.
        max_pixel_value (float): Maximum recorded raw intensity.
        exposure (ExposureMetadata): Imaging system configuration.
        preview_png_bytes (bytes): Lossless web-renderable PNG preview.
        preview_width (int): Width of generated web preview.
        preview_height (int): Height of generated web preview.
        raw_metadata (Dict[str, Any]): Supplementary hardware tags.

    Architectural Role:
        LIMS domain entity representing gel electrophoretograms and western blots.
    """

    file_format: str
    width: int
    height: int
    bit_depth: int
    channels: int
    min_pixel_value: float
    max_pixel_value: float
    exposure: ExposureMetadata
    preview_png_bytes: bytes
    preview_width: int
    preview_height: int
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize metadata to dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation omitting raw image byte buffers.
        """
        return {
            "file_format": self.file_format,
            "dimensions": [self.width, self.height],
            "bit_depth": self.bit_depth,
            "channels": self.channels,
            "dynamic_range": [round(self.min_pixel_value, 1), round(self.max_pixel_value, 1)],
            "exposure_time_s": self.exposure.exposure_time_seconds,
            "application": self.exposure.application_name,
            "illumination": self.exposure.illumination_source,
            "instrument": self.exposure.instrument_model,
            "preview_dimensions": [self.preview_width, self.preview_height],
        }


class BioRadParser:
    """
    Parser for Bio-Rad Image Lab (.scn) and 16-bit scientific TIFF files.

    Performs dynamic range scaling (16-bit to 8-bit), background equalization,
    metadata extraction from Bio-Rad XML chunks/TIFF tags, and generates
    high-contrast web-renderable PNG previews.

    Architectural Role:
        Standardizes western blot and nucleic acid gel images into the ELN pipeline.
    """

    @classmethod
    def parse(
        cls,
        source: Union[bytes, str, Path],
        auto_contrast: bool = True,
        invert: bool = False,
        gamma: float = 1.0,
    ) -> BioRadImage:
        """
        Parse Bio-Rad .scn or scientific TIFF file.

        Args:
            source (Union[bytes, str, Path]): Path or raw file bytes.
            auto_contrast (bool): Perform percentile dynamic range normalization.
            invert (bool): Invert polarity (dark bands on light background).
            gamma (float): Contrast gamma exponent.

        Returns:
            BioRadImage: Structured image representation with web preview.
        """
        if isinstance(source, (str, Path)):
            with open(source, "rb") as f:
                data = f.read()
        elif isinstance(source, bytes):
            data = source
        else:
            raise TypeError(f"Unsupported source type: {type(source).__name__}")

        # Extract exposure metadata from Bio-Rad tags or embedded XML blocks
        exposure = cls._extract_metadata(data)

        # Parse pixel matrix using PIL
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
            mode = img.mode

            if mode in ("I;16", "I", "F"):
                bit_depth = 16
                channels = 1
                ext = img.getextrema()
                min_val = float(ext[0]) if ext else 0.0
                max_val = float(ext[1]) if ext else 65535.0

                # 16-to-8 bit scaling
                scaled_bytes, pw, ph = cls._scale_16_to_8(
                    img, auto_contrast=auto_contrast, invert=invert, gamma=gamma
                )
            else:
                bit_depth = 8
                channels = len(img.getbands())
                min_val, max_val = 0.0, 255.0

                # Scale 8-bit preview
                out_img = img.copy()
                if auto_contrast:
                    out_img = ImageOps.autocontrast(out_img.convert("L"))
                if invert:
                    out_img = ImageOps.invert(out_img.convert("L"))

                if max(w, h) > 1600:
                    scale = 1600 / float(max(w, h))
                    pw, ph = max(1, int(w * scale)), max(1, int(h * scale))
                    out_img = out_img.resize((pw, ph), Image.Resampling.LANCZOS)
                else:
                    pw, ph = w, h

                buf = io.BytesIO()
                out_img.save(buf, format="PNG", optimize=True)
                scaled_bytes = buf.getvalue()

        fmt_id = "SCN" if data.startswith((b"II*\x00", b"MM\x00*")) and b"Bio-Rad" in data[:4096] else "TIFF_16" if bit_depth == 16 else "TIFF_8"

        return BioRadImage(
            file_format=fmt_id,
            width=w,
            height=h,
            bit_depth=bit_depth,
            channels=channels,
            min_pixel_value=min_val,
            max_pixel_value=max_val,
            exposure=exposure,
            preview_png_bytes=scaled_bytes,
            preview_width=pw,
            preview_height=ph,
        )

    @classmethod
    def _scale_16_to_8(
        cls,
        img: Image.Image,
        auto_contrast: bool = True,
        invert: bool = False,
        gamma: float = 1.0,
        black_percentile: float = 0.2,
        white_percentile: float = 99.8,
    ) -> Tuple[bytes, int, int]:
        """Convert 16-bit grayscale image to 8-bit PNG preview with fast C-level Pillow operations."""
        w, h = img.size
        if w == 0 or h == 0:
            blank = Image.new("L", (1, 1))
            buf = io.BytesIO()
            blank.save(buf, format="PNG")
            return buf.getvalue(), 1, 1

        img_i = img.convert("I")
        ext = img_i.getextrema()
        min_v = float(ext[0]) if ext else 0.0
        max_v = float(ext[1]) if ext else 65535.0

        if not auto_contrast:
            min_v = 0.0
            max_v = 65535.0

        span = max(1.0, max_v - min_v)
        scale = 255.0 / span
        offset = -min_v * scale

        # Fast C-level linear point scaling into 8-bit L
        out_img = img_i.point(lambda p: p * scale + offset).convert("L")

        if gamma != 1.0 and gamma > 0.0:
            lut = [int(pow(i / 255.0, 1.0 / gamma) * 255.0) for i in range(256)]
            out_img = out_img.point(lut)

        if invert:
            out_img = ImageOps.invert(out_img)

        if max(w, h) > 1600:
            resize_scale = 1600 / float(max(w, h))
            pw, ph = max(1, int(w * resize_scale)), max(1, int(h * resize_scale))
            out_img = out_img.resize((pw, ph), Image.Resampling.LANCZOS)
        else:
            pw, ph = w, h

        buf = io.BytesIO()
        out_img.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), pw, ph

    @classmethod
    def _extract_metadata(cls, data: bytes) -> ExposureMetadata:
        """Scan raw binary for Bio-Rad XML blocks or string tags."""
        exposure = ExposureMetadata()

        # Check for XML block
        xml_match = re.search(rb"(<BioRadImage.*?</BioRadImage>)", data, re.DOTALL | re.IGNORECASE)
        if not xml_match:
            xml_match = re.search(rb"(<ImageLab.*?</ImageLab>)", data, re.DOTALL | re.IGNORECASE)

        if xml_match:
            try:
                xml_text = xml_match.group(1).decode("utf-8", errors="ignore")
                root = ET.fromstring(xml_text)

                def find_val(tag_name: str) -> str:
                    el = root.find(f".//{tag_name}")
                    return el.text.strip() if el is not None and el.text else ""

                exp_str = find_val("ExposureTime") or find_val("Exposure")
                if exp_str:
                    exposure.exposure_time_seconds = float(re.sub(r"[^\d\.]", "", exp_str))

                app = find_val("ApplicationName") or find_val("Application") or find_val("ProtocolName")
                if app:
                    exposure.application_name = app

                illum = find_val("IlluminationSource") or find_val("Illumination")
                if illum:
                    exposure.illumination_source = illum

                filt = find_val("FilterName") or find_val("Filter")
                if filt:
                    exposure.filter_name = filt

                binning = find_val("Binning")
                if binning:
                    exposure.binning = binning

                model = find_val("InstrumentModel") or find_val("Instrument")
                if model:
                    exposure.instrument_model = model

                return exposure
            except Exception:
                pass

        # String regex scan if structured XML not detected
        text_snip = data[:32768].decode("ascii", errors="ignore")
        exp_m = re.search(r"Exposure(?:Time)?[:\s=]+([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec)?", text_snip, re.IGNORECASE)
        if exp_m:
            try:
                exposure.exposure_time_seconds = float(exp_m.group(1))
            except ValueError:
                pass

        if "chemi" in text_snip.lower():
            exposure.application_name = "Chemiluminescence"
            exposure.illumination_source = "None (Chemi)"
        elif "coomassie" in text_snip.lower():
            exposure.application_name = "Coomassie Blue"
            exposure.illumination_source = "Trans-white"
        elif "ethidium" in text_snip.lower() or "etbr" in text_snip.lower():
            exposure.application_name = "Ethidium Bromide"
            exposure.illumination_source = "Trans-UV"
        elif "stain-free" in text_snip.lower():
            exposure.application_name = "Stain-Free Gel"
            exposure.illumination_source = "UV Activation"

        return exposure
