"""
Module: biolabcalc.eln.parsers.biorad_parser
Component: Bio-Rad Image Lab (.scn), Quantity One (.1sc) and Scientific Gel TIFF Parser
Architectural Role: Ingests Bio-Rad Image Lab (.scn) MIME-multipart binary files,
legacy Bio-Rad Quantity One (.1sc) scans, and 16-bit fluorescent/chemiluminescent TIFFs.
Extracts optical exposure metadata, instrument parameters, and dynamic range matrices,
and provides 1D lane densitometry and standards-compliant 16-bit TIFF export.
Zero mandatory external dependencies (pure Python standard library fallback).
"""

from __future__ import annotations

import base64
import html
import io
import math
import os
import re
import struct
import tempfile
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None  # type: ignore
    ImageOps = None  # type: ignore

from biolabcalc.eln.storage.blob_store import BlobStore


@dataclass(frozen=True)
class ExposureMetadata:
    """
    Physical acquisition parameters for gel/blot documentation scans.

    Attributes:
        exposure_time_seconds (float): Sensor integration time in seconds.
        application_name (str): Staining chemistry or imaging protocol (e.g. 'Chemi', 'Coomassie Blue').
        illumination_source (str): Excitation source ('UV', 'Epi-white', 'Chemiluminescence').
        filter_name (str): Optical emission filter.
        binning (str): Pixel binning setting (e.g. '1x1', '2x2').
        instrument_model (str): Imager hardware model (e.g. 'ChemiDoc MP', 'GelDoc Go').
        acquisition_time (str): Timestamp of scan.
        dynamic_range_bits (int): Native bit-depth of image sensor (e.g. 16).
        gain (float): Analog or digital sensor gain multiplier.
        serial_number (str): Instrument serial number.
        image_name (str): Scan descriptor or protocol name.
        physical_size_x_um (float): Calibrated pixel pitch X in micrometers.
        physical_size_y_um (float): Calibrated pixel pitch Y in micrometers.
    """

    exposure_time_seconds: float = 0.0
    application_name: str = "Standard Gel"
    illumination_source: str = "Trans-UV"
    filter_name: str = "Standard"
    binning: str = "1x1"
    instrument_model: str = "Bio-Rad ChemiDoc"
    acquisition_time: str = ""
    dynamic_range_bits: int = 16
    gain: float = 1.0
    serial_number: str = ""
    image_name: str = ""
    physical_size_x_um: float = 0.0
    physical_size_y_um: float = 0.0


@dataclass(frozen=True)
class BioRadImage:
    """
    Parsed gel documentation scan with scaled web preview and matrix parameters.

    Attributes:
        file_format (str): Source format ('SCN', '1SC', 'TIFF_16', 'TIFF_8', 'IMAGE').
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
        saturated_pixel_count (int): Count of pixels at sensor saturation limit.
        raw_pixels (Tuple[int, ...]): Immutable sequence of raw pixel intensities.
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
    saturated_pixel_count: int = 0
    raw_pixels: Tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.raw_pixels, tuple):
            object.__setattr__(self, "raw_pixels", tuple(self.raw_pixels))

    @property
    def saturation_warning(self) -> bool:
        """True if any pixels reached sensor saturation threshold."""
        return self.saturated_pixel_count > 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to dictionary (omitting raw image byte buffers)."""
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
            "saturated_pixels": self.saturated_pixel_count,
        }

    def _repr_html_(self) -> str:
        """Render inline base64 PNG preview card and QC table for Jupyter notebooks."""
        b64 = base64.b64encode(self.preview_png_bytes).decode("ascii")
        esc = html.escape
        sat_warn = ""
        if self.saturated_pixel_count > 0:
            sat_warn = (
                f'<div style="color: #dc2626; font-weight: bold; margin-top: 6px;">'
                f'&#9888; Warning: {self.saturated_pixel_count:,} saturated pixel(s) detected '
                f'(Western blot quantitation may be non-linear)</div>'
            )
        return (
            f'<div style="font-family: system-ui, -apple-system, sans-serif; border: 1px solid #e5e7eb; '
            f'border-radius: 8px; padding: 16px; max-width: 650px; background: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">'
            f'  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">'
            f'    <h3 style="margin: 0; color: #111827; font-size: 16px;">Bio-Rad Gel Scan ({esc(self.file_format)})</h3>'
            f'    <span style="background: #eff6ff; color: #1d4ed8; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 9999px;">'
            f'      {self.width} &times; {self.height} px • {self.bit_depth}-bit</span>'
            f'  </div>'
            f'  <div style="text-align: center; background: #000000; padding: 8px; border-radius: 4px; margin-bottom: 10px;">'
            f'    <img src="data:image/png;base64,{b64}" style="max-width: 100%; height: auto; display: inline-block;" alt="Gel Preview" />'
            f'  </div>'
            f'  {sat_warn}'
            f'  <table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12.5px;">'
            f'    <tr style="border-bottom: 1px solid #f3f4f6;"><td style="font-weight: 600; color: #4b5563; padding: 4px;">Instrument</td><td>{esc(self.exposure.instrument_model)}</td></tr>'
            f'    <tr style="border-bottom: 1px solid #f3f4f6;"><td style="font-weight: 600; color: #4b5563; padding: 4px;">Application</td><td>{esc(self.exposure.application_name)}</td></tr>'
            f'    <tr style="border-bottom: 1px solid #f3f4f6;"><td style="font-weight: 600; color: #4b5563; padding: 4px;">Exposure Time</td><td>{self.exposure.exposure_time_seconds:g} s (Binning: {esc(self.exposure.binning)})</td></tr>'
            f'    <tr style="border-bottom: 1px solid #f3f4f6;"><td style="font-weight: 600; color: #4b5563; padding: 4px;">Dynamic Range</td><td>{self.min_pixel_value:g} &ndash; {self.max_pixel_value:g} AU</td></tr>'
            f'  </table>'
            f'</div>'
        )


def _encode_png_stdlib(gray_bytes: bytes, width: int, height: int) -> bytes:
    """
    Encode an 8-bit grayscale image to PNG bytes using Python stdlib struct and zlib.
    Zero external dependencies.
    """
    if isinstance(gray_bytes, (list, tuple)):
        gray_bytes = bytes(min(255, max(0, int(b))) for b in gray_bytes)

    if width <= 0 or height <= 0:
        width, height = 1, 1
        gray_bytes = b"\x00"

    # PNG Signature
    sig = b"\x89PNG\r\n\x1a\n"

    # IHDR Chunk: width(4B), height(4B), bit_depth=8(1B), color_type=0(1B, grayscale), comp=0, filter=0, interlace=0
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr_chunk = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

    # IDAT Chunk: Each scanline begins with filter byte 0x00
    raw_scanlines = bytearray()
    row_stride = width
    for row in range(height):
        raw_scanlines.append(0)  # Filter type 0 (None)
        start = row * row_stride
        raw_scanlines.extend(gray_bytes[start : start + row_stride])

    compressed = zlib.compress(bytes(raw_scanlines), level=6)
    idat_crc = zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF
    idat_chunk = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc)

    # IEND Chunk
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

    return sig + ihdr_chunk + idat_chunk + iend_chunk


def _scale_pixels_to_8bit(
    pixels: Sequence[int],
    width: int,
    height: int,
    bit_depth: int,
    auto_contrast: bool = True,
    invert: bool = False,
    gamma: float = 1.0,
    black_percentile: float = 0.2,
    white_percentile: float = 99.8,
) -> Tuple[bytes, int, int]:
    """
    Convert raw pixels (8-bit or 16-bit) to an 8-bit web-renderable PNG preview
    with percentile contrast stretching, gamma correction, and inversion.
    """
    n_pix = len(pixels)
    if n_pix == 0 or width <= 0 or height <= 0:
        return _encode_png_stdlib(b"\x00", 1, 1), 1, 1

    max_limit = 65535 if bit_depth == 16 else 255

    if auto_contrast:
        hist = [0] * (max_limit + 1)
        for p in pixels:
            clamped = max(0, min(max_limit, p))
            hist[clamped] += 1

        target_low = int(n_pix * (black_percentile / 100.0))
        target_high = int(n_pix * (white_percentile / 100.0))

        cum = 0
        min_v = 0
        for val, cnt in enumerate(hist):
            cum += cnt
            if cum >= target_low:
                min_v = val
                break

        cum = 0
        max_v = max_limit
        for val, cnt in enumerate(hist):
            cum += cnt
            if cum >= target_high:
                max_v = val
                break

        if min_v >= max_v:
            min_v = min(pixels)
            max_v = max(pixels)
        if min_v == max_v:
            max_v = min_v + 1.0
    else:
        min_v = 0.0
        max_v = float(max_limit)

    span = max(1.0, float(max_v - min_v))
    scale = 255.0 / span
    offset = -float(min_v) * scale

    # Precompute 256-entry lookup table for gamma and invert
    lut = bytearray(256)
    for i in range(256):
        val = i
        if gamma != 1.0 and gamma > 0.0:
            val = int(pow(i / 255.0, 1.0 / gamma) * 255.0 + 0.5)
            val = max(0, min(255, val))
        if invert:
            val = 255 - val
        lut[i] = val

    # Map pixels to 8-bit bytes
    out_bytes = bytearray(n_pix)
    for idx, p in enumerate(pixels):
        v = int(p * scale + offset)
        if v < 0:
            v = 0
        elif v > 255:
            v = 255
        out_bytes[idx] = lut[v]

    pw, ph = width, height
    # Use Pillow for Lanczos downsampling when Pillow is installed and image is large
    if Image is not None and max(width, height) > 1600:
        resize_scale = 1600.0 / float(max(width, height))
        pw, ph = max(1, int(width * resize_scale)), max(1, int(height * resize_scale))
        pil_img = Image.frombytes("L", (width, height), bytes(out_bytes))
        resample = getattr(Image, "Resampling", Image).LANCZOS
        resized = pil_img.resize((pw, ph), resample)
        buf = io.BytesIO()
        resized.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), pw, ph

    return _encode_png_stdlib(bytes(out_bytes), width, height), pw, ph


def _parse_uncompressed_tiff_stdlib(data: bytes) -> Optional[Tuple[int, int, int, int, List[int]]]:
    """
    Pure-Python standard library baseline uncompressed TIFF parser.
    Fallback when Pillow is not installed.
    Returns (width, height, bit_depth, channels, pixels) or None if unsupported.
    """
    if len(data) < 8:
        return None
    endian = "<" if data[:2] == b"II" else ">" if data[:2] == b"MM" else None
    if endian is None:
        return None
    magic = struct.unpack(f"{endian}H", data[2:4])[0]
    if magic != 42:
        return None

    ifd_offset = struct.unpack(f"{endian}I", data[4:8])[0]
    if ifd_offset + 2 > len(data):
        return None

    num_entries = struct.unpack(f"{endian}H", data[ifd_offset : ifd_offset + 2])[0]
    tags: Dict[int, Any] = {}
    curr = ifd_offset + 2
    for _ in range(num_entries):
        if curr + 12 > len(data):
            break
        tag, typ, cnt, val = struct.unpack(f"{endian}HHI4s", data[curr : curr + 12])
        curr += 12
        if typ == 3:  # SHORT
            val_int = struct.unpack(f"{endian}H", val[:2])[0]
            tags[tag] = val_int
        elif typ == 4:  # LONG
            val_int = struct.unpack(f"{endian}I", val)[0]
            tags[tag] = val_int

    width = tags.get(256)
    height = tags.get(257)
    bits = tags.get(258, 8)
    compression = tags.get(259, 1)
    strip_offset = tags.get(273)
    strip_bytes = tags.get(279)

    if not width or not height or compression != 1 or strip_offset is None:
        return None

    expected_len = width * height * (2 if bits == 16 else 1)
    raw_strip = data[strip_offset : strip_offset + (strip_bytes or expected_len)]
    if len(raw_strip) < expected_len:
        return None

    if bits == 16:
        pixels = list(struct.unpack(f"{endian}{width * height}H", raw_strip[:expected_len]))
    else:
        pixels = list(raw_strip[:expected_len])
    return width, height, bits, 1, pixels


class BioRadParser:
    """
    Parser for Bio-Rad Image Lab (.scn), Quantity One (.1sc), and scientific TIFF files.

    Performs MIME-multipart demultiplexing, XML metadata extraction, dynamic range scaling
    (16-bit to 8-bit), background equalization, 1D lane densitometry profile extraction,
    band peak detection, and standards-compliant 16-bit TIFF export.
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
        Parse Bio-Rad .scn, .1sc, or scientific TIFF file.

        Args:
            source (Union[bytes, str, Path]): Path or raw file bytes.
            auto_contrast (bool): Perform percentile dynamic range normalization.
            invert (bool): Invert polarity (dark bands on light background).
            gamma (float): Contrast gamma exponent.

        Returns:
            BioRadImage: Structured image representation with web preview and raw pixels.
        """
        if isinstance(source, (str, Path)):
            with open(source, "rb") as f:
                data = f.read()
        elif isinstance(source, (bytes, bytearray)):
            data = bytes(source)
        else:
            raise TypeError(f"Unsupported source type: {type(source).__name__}")

        # Check Format 1: Native Bio-Rad Image Lab .scn (MIME Multipart Stream)
        is_scn_multipart = (
            b"Generated by Image Lab" in data[:256]
            or b"multipart/" in data[:512]
            or (b"Content-Type: text/xml" in data[:4096] and b"Content-Type: application/octet-stream" in data[:4096])
        )
        if is_scn_multipart:
            decoded = cls._decode_scn_multipart(data, auto_contrast=auto_contrast, invert=invert, gamma=gamma)
            if decoded is not None:
                return decoded

        # Check Format 2: Legacy Bio-Rad Quantity One .1sc Files
        is_1sc = (
            data.startswith(b"Bio-Rad")
            or data.startswith(b"BIORAD")
            or b"Quantity One" in data[:256]
            or b".1sc" in data[:64]
            or (isinstance(source, (str, Path)) and str(source).lower().endswith(".1sc"))
        )
        if is_1sc:
            decoded_1sc = cls._decode_1sc(data, auto_contrast=auto_contrast, invert=invert, gamma=gamma)
            if decoded_1sc is not None:
                return decoded_1sc

        # Check Format 3: Bio-Rad Exported TIFF & Hybrid Test Payloads
        return cls._decode_tiff_or_image(data, auto_contrast=auto_contrast, invert=invert, gamma=gamma)

    @classmethod
    def _decode_scn_multipart(
        cls,
        data: bytes,
        auto_contrast: bool = True,
        invert: bool = False,
        gamma: float = 1.0,
    ) -> Optional[BioRadImage]:
        """Demultiplex and decode MIME-multipart Bio-Rad Image Lab .scn stream."""
        def collect_mime_parts(content: bytes, parent_header: bytes = b"") -> Tuple[List[str], List[bytes]]:
            bm = re.search(rb'boundary=["\']?([^"\'\r\n;]+)["\']?', parent_header)
            if not bm:
                bm = re.search(rb'boundary=["\']?([^"\'\r\n;]+)["\']?', content[:4096])
            if not bm:
                line_m = re.search(rb'--([a-zA-Z0-9_\-]+)', content[:1024])
                if line_m:
                    boundary = line_m.group(1).strip()
                else:
                    return [], []
            else:
                boundary = bm.group(1).strip()

            raw_parts = content.split(b"--" + boundary)
            xml_parts: List[str] = []
            raw_blocks: List[bytes] = []

            for part in raw_parts:
                if not part or part.startswith(b"--"):
                    continue

                h_end = -1
                sep_len = 0
                for sep in (b"\r\n\r\n", b"\n\n"):
                    idx = part.find(sep)
                    if idx != -1:
                        h_end = idx
                        sep_len = len(sep)
                        break
                if h_end == -1:
                    continue

                header_bytes = part[:h_end]
                body = part[h_end + sep_len :]

                ct_m = re.search(rb"content-type:\s*([^\r\n;]+)", header_bytes, re.IGNORECASE)
                content_type = ct_m.group(1).strip().lower() if ct_m else b""

                cl_m = re.search(rb"content-length:\s*(\d+)", header_bytes, re.IGNORECASE)
                if cl_m:
                    content_length = int(cl_m.group(1))
                    body = body[:content_length]
                else:
                    if body.endswith(b"\r\n"):
                        body = body[:-2]
                    elif body.endswith(b"\n"):
                        body = body[:-1]

                if b"multipart" in content_type or b"boundary=" in header_bytes:
                    sub_xml, sub_raw = collect_mime_parts(body, parent_header=header_bytes)
                    xml_parts.extend(sub_xml)
                    raw_blocks.extend(sub_raw)
                elif b"text/xml" in content_type or body.startswith(b"<?xml") or body.startswith(b"<!DOCTYPE XML"):
                    xml_parts.append(body.rstrip(b"\x00 \r\n\t").decode("utf-8", errors="ignore"))
                elif b"application/octet-stream" in content_type or len(body) > 10000:
                    raw_blocks.append(body)

            return xml_parts, raw_blocks

        xml_parts, raw_blocks = collect_mime_parts(data)

        # Parse XML metadata across all collected XML trees
        roots: List[ET.Element] = []
        for xt in xml_parts:
            try:
                clean_xml = re.sub(r'\s+xmlns="[^"]+"', '', xt)
                roots.append(ET.fromstring(clean_xml))
            except Exception:
                pass

        def get_el(*tags: str) -> Optional[ET.Element]:
            for root in roots:
                for t in tags:
                    el = root.find(f".//{t}")
                    if el is not None:
                        return el
            return None

        def get_val(el: Optional[ET.Element], *attrs: str) -> str:
            if el is None:
                return ""
            for a in attrs:
                if a in el.attrib:
                    return el.attrib[a]
            return el.text.strip() if el.text else ""

        width = 0
        height = 0
        bit_depth = 16
        channels = 1
        endian_char = "<"
        physical_x = 0.0
        physical_y = 0.0
        exp_time = 0.0
        gain = 1.0
        app_name = "Standard Gel"
        img_name = ""
        inst_model = "Bio-Rad ChemiDoc"
        serial_no = ""
        binning = "1x1"
        acq_time = ""
        xml_sat_count = 0

        sat_el = get_el("saturation")
        if sat_el is not None and "saturated_pixel_count" in sat_el.attrib:
            try:
                xml_sat_count = int(sat_el.attrib["saturated_pixel_count"])
            except Exception:
                pass

        size_pix = get_el("size_pix", "org_size_pix")
        if size_pix is not None:
            width = int(size_pix.attrib.get("width", 0))
            height = int(size_pix.attrib.get("height", 0))
        if not width or not height:
            w_el = get_el("Width", "width")
            h_el = get_el("Height", "height")
            if w_el is not None:
                val = get_val(w_el, "value")
                if val and val.isdigit():
                    width = int(val)
            if h_el is not None:
                val = get_val(h_el, "value")
                if val and val.isdigit():
                    height = int(val)

        scanner = get_el("scanner")
        if scanner is not None and "max_value" in scanner.attrib:
            try:
                mv = int(scanner.attrib["max_value"])
                bit_depth = 8 if mv <= 256 else 16
            except Exception:
                pass

        endian_el = get_el("endian")
        if endian_el is not None:
            eval_str = get_val(endian_el, "value").lower()
            if "big" in eval_str:
                endian_char = ">"
            elif "little" in eval_str:
                endian_char = "<"

        ch_el = get_el("channel_count")
        if ch_el is not None:
            cval = get_val(ch_el, "value")
            if cval and cval.isdigit():
                channels = int(cval)

        size_mm = get_el("size_mm")
        if size_mm is not None and width > 0 and height > 0:
            try:
                w_mm = float(size_mm.attrib.get("width", 0.0))
                h_mm = float(size_mm.attrib.get("height", 0.0))
                physical_x = (w_mm / width) * 1000.0
                physical_y = (h_mm / height) * 1000.0
            except Exception:
                pass

        exp_el = get_el("exposure_time", "ExposureTime", "Exposure")
        if exp_el is not None:
            eval_str = get_val(exp_el, "value")
            if eval_str:
                try:
                    exp_time = float(re.sub(r"[^\d\.]", "", eval_str))
                except Exception:
                    pass

        gain_el = get_el("application_gain", "Gain")
        if gain_el is not None:
            gval = get_val(gain_el, "value")
            if gval:
                try:
                    gain = float(gval)
                except Exception:
                    pass

        name_el = get_el("name", "ApplicationName", "ProtocolName")
        if name_el is not None:
            nval = get_val(name_el, "value")
            if nval:
                img_name = nval
                app_name = img_name

        app_el = get_el("application", "Application", "ApplicationName")
        if app_el is not None:
            aval = get_val(app_el, "value", "name")
            if aval:
                app_name = aval

        imager_el = get_el("imager", "InstrumentModel", "Instrument")
        if imager_el is not None:
            ival = get_val(imager_el, "value")
            if ival:
                inst_model = ival

        exc_el = get_el("excitation_source", "application_lightSource", "IlluminationSource")
        if exc_el is not None:
            eval_str = get_val(exc_el, "value")
            if eval_str:
                illum = eval_str

        sn_el = get_el("serial_number", "SerialNumber")
        if sn_el is not None:
            sval = get_val(sn_el, "value")
            if sval:
                serial_no = sval

        bin_el = get_el("binning", "Binning")
        if bin_el is not None:
            bval = get_val(bin_el, "value")
            if bval:
                binning = bval

        date_el = get_el("image_date", "AcquisitionTime", "Date")
        if date_el is not None:
            dval = get_val(date_el, "value")
            if dval:
                acq_time = dval

        if width <= 0 or height <= 0:
            return None

        bytes_per_sample = bit_depth // 8
        expected_bytes = width * height * channels * bytes_per_sample

        pixel_block = None
        for blk in raw_blocks:
            if len(blk) == expected_bytes:
                pixel_block = blk
                break
        if pixel_block is None and raw_blocks:
            pixel_block = max(raw_blocks, key=len)

        if pixel_block is None or len(pixel_block) < expected_bytes:
            return None

        n_pixels = width * height * channels
        if bit_depth == 16:
            raw_pixels = struct.unpack(f"{endian_char}{n_pixels}H", pixel_block[:expected_bytes])
            sat_threshold = 65535
        else:
            raw_pixels = struct.unpack(f"{n_pixels}B", pixel_block[:expected_bytes])
            sat_threshold = 255

        sat_count = sum(1 for p in raw_pixels if p >= sat_threshold)
        if xml_sat_count > 0:
            sat_count = max(sat_count, xml_sat_count)
        min_val = float(min(raw_pixels)) if raw_pixels else 0.0
        max_val = float(max(raw_pixels)) if raw_pixels else float(sat_threshold)

        scaled_png, pw, ph = _scale_pixels_to_8bit(
            raw_pixels, width, height, bit_depth, auto_contrast=auto_contrast, invert=invert, gamma=gamma
        )

        illum = (
            "None (Chemi)" if "chemi" in app_name.lower()
            else "Trans-white" if "coomassie" in app_name.lower()
            else "UV Activation" if "stain-free" in app_name.lower()
            else "Trans-UV"
        )

        exposure = ExposureMetadata(
            exposure_time_seconds=exp_time,
            application_name=app_name or "Stain-Free SDS-PAGE",
            illumination_source=illum,
            filter_name="Standard",
            binning=binning,
            instrument_model=inst_model,
            acquisition_time=acq_time,
            dynamic_range_bits=bit_depth,
            gain=gain,
            serial_number=serial_no,
            image_name=img_name,
            physical_size_x_um=physical_x,
            physical_size_y_um=physical_y,
        )

        return BioRadImage(
            file_format="SCN",
            width=width,
            height=height,
            bit_depth=bit_depth,
            channels=channels,
            min_pixel_value=min_val,
            max_pixel_value=max_val,
            exposure=exposure,
            preview_png_bytes=scaled_png,
            preview_width=pw,
            preview_height=ph,
            saturated_pixel_count=sat_count,
            raw_pixels=raw_pixels,
        )

    @classmethod
    def _decode_1sc(
        cls,
        data: bytes,
        auto_contrast: bool = True,
        invert: bool = False,
        gamma: float = 1.0,
    ) -> Optional[BioRadImage]:
        """Decode legacy Bio-Rad Quantity One .1sc format."""
        width = 0
        height = 0
        raw_pixels: Tuple[int, ...] = ()

        # Look for explicit size markers or Data Block 7
        m = re.search(rb"Data Block 7.*?width=(\d+).*?height=(\d+)", data, re.DOTALL | re.IGNORECASE)
        if m:
            width = int(m.group(1))
            height = int(m.group(2))
        else:
            sz_m = re.search(rb"size=(\d+)[xX](\d+)", data[:1024])
            if sz_m:
                width = int(sz_m.group(1))
                height = int(sz_m.group(2))

        # Check binary block headers
        if width <= 0 or height <= 0:
            for off in (8, 10, 12, 16, 20, 24, 32, 64):
                if off + 8 <= len(data):
                    w, h = struct.unpack("<II", data[off : off + 8])
                    if 4 <= w <= 8192 and 4 <= h <= 8192 and off + 8 + w * h * 2 <= len(data):
                        width, height = w, h
                        pixel_bytes = data[off + 8 : off + 8 + w * h * 2]
                        raw_pixels = struct.unpack(f"<{w * h}H", pixel_bytes)
                        break

        # Check key-value header followed by binary payload
        if (width <= 0 or height <= 0) and len(data) > 128:
            header_end = data.find(b"\r\n\r\n")
            if header_end == -1:
                header_end = data.find(b"\n\n")
            if header_end != -1:
                header = data[:header_end].decode("ascii", errors="ignore")
                w_m = re.search(r"width=(\d+)", header, re.I)
                h_m = re.search(r"height=(\d+)", header, re.I)
                if w_m and h_m:
                    width = int(w_m.group(1))
                    height = int(w_m.group(2))
                    px_data = data[header_end + 2 : header_end + 2 + width * height * 2]
                    if len(px_data) == width * height * 2:
                        raw_pixels = struct.unpack(f"<{width * height}H", px_data)

        if width <= 0 or height <= 0:
            return None

        if not raw_pixels:
            expected = width * height * 2
            px_data = data[-expected:]
            if len(px_data) == expected:
                raw_pixels = struct.unpack(f"<{width * height}H", px_data)
            else:
                return None

        bit_depth = 16
        sat_count = sum(1 for p in raw_pixels if p >= 65535)
        min_val = float(min(raw_pixels)) if raw_pixels else 0.0
        max_val = float(max(raw_pixels)) if raw_pixels else 65535.0

        scaled_png, pw, ph = _scale_pixels_to_8bit(
            raw_pixels, width, height, bit_depth, auto_contrast=auto_contrast, invert=invert, gamma=gamma
        )

        exposure = ExposureMetadata(
            application_name="Quantity One Gel",
            instrument_model="Bio-Rad Quantity One",
            dynamic_range_bits=16,
        )

        return BioRadImage(
            file_format="1SC",
            width=width,
            height=height,
            bit_depth=16,
            channels=1,
            min_pixel_value=min_val,
            max_pixel_value=max_val,
            exposure=exposure,
            preview_png_bytes=scaled_png,
            preview_width=pw,
            preview_height=ph,
            saturated_pixel_count=sat_count,
            raw_pixels=raw_pixels,
        )

    @classmethod
    def _decode_tiff_or_image(
        cls,
        data: bytes,
        auto_contrast: bool = True,
        invert: bool = False,
        gamma: float = 1.0,
    ) -> BioRadImage:
        """Decode exported TIFF or standard image using Pillow with pure-Python stdlib fallback."""
        exposure = cls._extract_metadata(data)

        # 1. Try pure-Python uncompressed TIFF parser first if Image is None
        if Image is None:
            parsed_tiff = _parse_uncompressed_tiff_stdlib(data)
            if parsed_tiff is not None:
                w, h, bit_depth, channels, raw_px = parsed_tiff
                sat_threshold = 65535 if bit_depth == 16 else 255
                sat_count = sum(1 for p in raw_px if p >= sat_threshold)
                min_v = float(min(raw_px)) if raw_px else 0.0
                max_v = float(max(raw_px)) if raw_px else float(sat_threshold)
                scaled_bytes, pw, ph = _scale_pixels_to_8bit(
                    raw_px, w, h, bit_depth, auto_contrast=auto_contrast, invert=invert, gamma=gamma
                )
                fmt_id = "SCN" if (b"Bio-Rad" in data[:4096] or b"<BioRadImage>" in data) else ("TIFF_16" if bit_depth == 16 else "TIFF_8")
                return BioRadImage(
                    file_format=fmt_id,
                    width=w,
                    height=h,
                    bit_depth=bit_depth,
                    channels=channels,
                    min_pixel_value=min_v,
                    max_pixel_value=max_v,
                    exposure=exposure,
                    preview_png_bytes=scaled_bytes,
                    preview_width=pw,
                    preview_height=ph,
                    saturated_pixel_count=sat_count,
                    raw_pixels=tuple(raw_px),
                )
            raise ValueError("Pillow is not installed and raw image is not a baseline uncompressed TIFF.")

        # 2. Parse using Pillow
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
            mode = img.mode

            if mode in ("I;16", "I", "F"):
                bit_depth = 16
                channels = 1
                raw_seq = list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())
                raw_px = tuple(raw_seq)
                min_val = float(min(raw_px)) if raw_px else 0.0
                max_val = float(max(raw_px)) if raw_px else 65535.0
                sat_count = sum(1 for p in raw_px if p >= 65535)

                scaled_bytes, pw, ph = _scale_pixels_to_8bit(
                    raw_px, w, h, 16, auto_contrast=auto_contrast, invert=invert, gamma=gamma
                )
            else:
                bit_depth = 8
                channels = len(img.getbands())
                raw_seq = list(img.convert("L").getdata())
                raw_px = tuple(raw_seq)
                min_val = float(min(raw_px)) if raw_px else 0.0
                max_val = float(max(raw_px)) if raw_px else 255.0
                sat_count = sum(1 for p in raw_px if p >= 255)

                out_img = img.copy()
                if auto_contrast and ImageOps is not None:
                    out_img = ImageOps.autocontrast(out_img.convert("L"))
                if invert and ImageOps is not None:
                    out_img = ImageOps.invert(out_img.convert("L"))

                if max(w, h) > 1600:
                    scale = 1600.0 / float(max(w, h))
                    pw, ph = max(1, int(w * scale)), max(1, int(h * scale))
                    resample = getattr(Image, "Resampling", Image).LANCZOS
                    out_img = out_img.resize((pw, ph), resample)
                else:
                    pw, ph = w, h

                buf = io.BytesIO()
                out_img.save(buf, format="PNG", optimize=True)
                scaled_bytes = buf.getvalue()

        fmt_id = "SCN" if (b"Bio-Rad" in data[:4096] or b"<BioRadImage>" in data) else ("TIFF_16" if bit_depth == 16 else "TIFF_8")

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
            saturated_pixel_count=sat_count,
            raw_pixels=raw_px,
        )

    @classmethod
    def export_tiff_16bit(cls, image: BioRadImage, output_path: Union[str, Path]) -> str:
        """
        Writes a standards-compliant uncompressed 16-bit grayscale TIFF.
        Uses pure-Python struct and atomic sibling temporary file replacement.
        """
        out_path = Path(output_path).resolve()
        os.makedirs(out_path.parent, exist_ok=True)

        w = image.width
        h = image.height
        n_pixels = w * h

        if len(image.raw_pixels) >= n_pixels:
            px = image.raw_pixels[:n_pixels]
        else:
            px = (0,) * n_pixels

        pixel_data = struct.pack(f"<{n_pixels}H", *px)
        strip_byte_count = len(pixel_data)

        # Baseline uncompressed little-endian TIFF layout:
        # 0x00: "II\x2a\x00" (4B)
        # 0x04: IFD offset = 8 (4B)
        # 0x08: IFD num_entries = 8 (2B)
        # 8 directory entries * 12B = 96B
        # 0x08 + 2 + 96 = 106
        # Next IFD offset: 0 (4B) -> total header + IFD = 110 bytes
        strip_offset = 110

        header = b"II\x2a\x00" + struct.pack("<I", 8)
        num_entries = 8

        def entry_short(tag: int, val: int) -> bytes:
            return struct.pack("<HHIHH", tag, 3, 1, val, 0)

        def entry_long(tag: int, val: int) -> bytes:
            return struct.pack("<HHII", tag, 4, 1, val)

        ifd_entries = (
            entry_long(256, w) +
            entry_long(257, h) +
            entry_short(258, 16) +
            entry_short(259, 1) +
            entry_short(262, 1) +
            entry_long(273, strip_offset) +
            entry_long(278, h) +
            entry_long(279, strip_byte_count)
        )

        ifd = struct.pack("<H", num_entries) + ifd_entries + struct.pack("<I", 0)
        full_content = header + ifd + pixel_data

        # Write atomically to sibling temp file
        temp_dir = str(out_path.parent)
        with tempfile.NamedTemporaryFile("wb", dir=temp_dir, delete=False) as tf:
            tf.write(full_content)
            tf.flush()
            os.fsync(tf.fileno())
            temp_name = tf.name

        os.replace(temp_name, str(out_path))
        return str(out_path)

    @classmethod
    def extract_lane_profile(
        cls,
        image: BioRadImage,
        lane_index: int,
        num_lanes: int = 10,
        lane_width_fraction: float = 0.5,
    ) -> Tuple[float, ...]:
        """
        Computes horizontally averaged background-subtracted intensity from top (Rf=0.0)
        to bottom (Rf=1.0) for 1-based lane_index (1 <= lane_index <= num_lanes).
        """
        if num_lanes < 1:
            raise ValueError("num_lanes must be >= 1")
        if not (1 <= lane_index <= num_lanes):
            raise ValueError(f"lane_index must be between 1 and {num_lanes}")

        w = image.width
        h = image.height
        if w <= 0 or h <= 0 or not image.raw_pixels:
            return tuple(0.0 for _ in range(max(1, h)))

        lane_w = w / float(num_lanes)
        center_x = (lane_index - 0.5) * lane_w
        half_w = max(0.5, 0.5 * lane_w * lane_width_fraction)

        col_start = max(0, int(math.floor(center_x - half_w)))
        col_end = min(w - 1, int(math.ceil(center_x + half_w)))
        n_cols = max(1, col_end - col_start + 1)

        raw_profile: List[float] = []
        for r in range(h):
            row_offset = r * w
            row_sum = sum(image.raw_pixels[row_offset + c] for c in range(col_start, col_end + 1))
            raw_profile.append(row_sum / float(n_cols))

        baseline = min(raw_profile) if raw_profile else 0.0
        bg_subtracted = tuple(max(0.0, float(val - baseline)) for val in raw_profile)
        return bg_subtracted

    @classmethod
    def detect_lane_bands(
        cls,
        image: BioRadImage,
        lane_index: int,
        num_lanes: int = 10,
        min_prominence: float = 0.08,
    ) -> Tuple[Dict[str, Any], ...]:
        """
        Automatically detects band peaks along the lane profile and returns Tuple of dicts:
        {"rf": float, "intensity_au": float, "integrated_area_au": float, "saturated": bool}
        compatible with GelService.tag_lane().
        """
        profile = cls.extract_lane_profile(
            image, lane_index=lane_index, num_lanes=num_lanes, lane_width_fraction=0.5
        )
        h = len(profile)
        if h < 3:
            return ()

        max_val = max(profile)
        if max_val <= 0.0:
            return ()

        norm_profile = [v / max_val for v in profile]

        peaks = []
        for i in range(1, h - 1):
            if norm_profile[i] > norm_profile[i - 1] and norm_profile[i] >= norm_profile[i + 1]:
                left_val = norm_profile[i]
                left_idx = i
                for j in range(i - 1, -1, -1):
                    if norm_profile[j] < left_val:
                        left_val = norm_profile[j]
                        left_idx = j
                    elif norm_profile[j] > left_val:
                        break

                right_val = norm_profile[i]
                right_idx = i
                for j in range(i + 1, h):
                    if norm_profile[j] < right_val:
                        right_val = norm_profile[j]
                        right_idx = j
                    elif norm_profile[j] > right_val:
                        break

                prominence = norm_profile[i] - max(left_val, right_val)
                if prominence >= min_prominence:
                    peaks.append((i, left_idx, right_idx))

        lane_w = image.width / float(num_lanes)
        center_x = (lane_index - 0.5) * lane_w
        half_w = max(0.5, 0.5 * lane_w * 0.5)
        col_start = max(0, int(math.floor(center_x - half_w)))
        col_end = min(image.width - 1, int(math.ceil(center_x + half_w)))
        sat_val = 65535 if image.bit_depth == 16 else 255

        bands = []
        for peak_idx, l_idx, r_idx in peaks:
            rf = round(peak_idx / float(h - 1 if h > 1 else 1), 4)
            intensity_au = round(profile[peak_idx], 2)
            area = round(sum(profile[l_idx : r_idx + 1]), 2)

            is_sat = False
            if image.raw_pixels:
                for r in range(max(0, peak_idx - 1), min(h, peak_idx + 2)):
                    row_off = r * image.width
                    for c in range(col_start, col_end + 1):
                        if image.raw_pixels[row_off + c] >= sat_val:
                            is_sat = True
                            break
                    if is_sat:
                        break

            bands.append({
                "rf": rf,
                "intensity_au": intensity_au,
                "integrated_area_au": area,
                "saturated": is_sat,
            })

        return tuple(bands)

    @classmethod
    def _extract_metadata(cls, data: bytes) -> ExposureMetadata:
        """Scan raw binary for Bio-Rad XML blocks or string tags."""
        exposure_dict = {
            "exposure_time_seconds": 0.0,
            "application_name": "Standard Gel",
            "illumination_source": "Trans-UV",
            "filter_name": "Standard",
            "binning": "1x1",
            "instrument_model": "Bio-Rad ChemiDoc",
            "acquisition_time": "",
            "dynamic_range_bits": 16,
            "gain": 1.0,
            "serial_number": "",
            "image_name": "",
            "physical_size_x_um": 0.0,
            "physical_size_y_um": 0.0,
        }

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
                    exposure_dict["exposure_time_seconds"] = float(re.sub(r"[^\d\.]", "", exp_str))

                app = find_val("ApplicationName") or find_val("Application") or find_val("ProtocolName")
                if app:
                    exposure_dict["application_name"] = app

                illum = find_val("IlluminationSource") or find_val("Illumination")
                if illum:
                    exposure_dict["illumination_source"] = illum

                filt = find_val("FilterName") or find_val("Filter")
                if filt:
                    exposure_dict["filter_name"] = filt

                binning = find_val("Binning")
                if binning:
                    exposure_dict["binning"] = binning

                model = find_val("InstrumentModel") or find_val("Instrument")
                if model:
                    exposure_dict["instrument_model"] = model

                return ExposureMetadata(**exposure_dict)
            except Exception:
                pass

        # String regex scan if structured XML not detected
        text_snip = data[:32768].decode("ascii", errors="ignore")
        exp_m = re.search(r"Exposure(?:Time)?[:\s=]+([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec)?", text_snip, re.IGNORECASE)
        if exp_m:
            try:
                exposure_dict["exposure_time_seconds"] = float(exp_m.group(1))
            except ValueError:
                pass

        if "chemi" in text_snip.lower():
            exposure_dict["application_name"] = "Chemiluminescence"
            exposure_dict["illumination_source"] = "None (Chemi)"
        elif "coomassie" in text_snip.lower():
            exposure_dict["application_name"] = "Coomassie Blue"
            exposure_dict["illumination_source"] = "Trans-white"
        elif "ethidium" in text_snip.lower() or "etbr" in text_snip.lower():
            exposure_dict["application_name"] = "Ethidium Bromide"
            exposure_dict["illumination_source"] = "Trans-UV"
        elif "stain-free" in text_snip.lower():
            exposure_dict["application_name"] = "Stain-Free Gel"
            exposure_dict["illumination_source"] = "UV Activation"

        return ExposureMetadata(**exposure_dict)
