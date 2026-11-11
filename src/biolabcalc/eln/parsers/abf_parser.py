"""
Module: biolabcalc.eln.parsers.abf_parser
Component: Pure-Python Axon Binary Format (.abf) and Axon Text Format (.atf) Parser
Agent: @agent: eln-parser-agent
Architectural Role: Ingests electrophysiology recordings from Axon Instruments / Molecular Devices
pCLAMP suites (ABF v1, ABF v2, ATF) without requiring C-extensions, extracting sampling rates,
sweep counts, channel properties, holding potentials, annotations, and generating downsampled
web-renderable thumbnails.
"""

from __future__ import annotations

import io
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class ABFTag:
    """
    Representation of an experimental event or comment tag within an ABF recording.

    Attributes:
        time_seconds (float): Timestamp of the tag in seconds from acquisition start.
        comment (str): Textual annotation or protocol event comment.
        tag_type (int): Numeric tag classification code (0 = comment, 1 = epoch, etc.).

    Architectural Role:
        Event descriptor for electrophysiology annotations.
        @agent: eln-parser-agent
    """

    time_seconds: float
    comment: str
    tag_type: int = 0


@dataclass
class ABFData:
    """
    Structured extraction result of an ABF or ATF electrophysiology file.

    Attributes:
        file_format (str): Identified format ('ABF1', 'ABF2', 'ATF').
        sampling_rate_hz (float): Analog-to-digital sampling frequency in Hertz.
        sample_interval_us (float): Inter-sample interval in microseconds.
        sweep_count (int): Number of sweeps (episodes) recorded.
        sweep_length_points (int): Number of sample points per channel per sweep.
        channel_names (List[str]): List of ADC channel labels (e.g. ['IN 0', 'IN 1']).
        channel_units (List[str]): Physical units corresponding to channels (e.g. ['pA', 'mV']).
        holding_potential_mv (float): Baseline or epoch holding potential in millivolts.
        protocol_name (str): Associated pCLAMP protocol file name or path.
        operation_mode (str): Mode of acquisition ('gap-free', 'episodic', 'event-driven').
        comments (List[ABFTag]): Chronological annotations and mark tags.
        sweeps_data (Dict[str, List[List[float]]]): Channel -> List of Sweeps (each a list of floats).
        thumbnails (Dict[str, List[List[Tuple[float, float]]]]): Downsampled (x, y) coordinates for web rendering.
        raw_header (Dict[str, Any]): Supplementary low-level header attributes.

    Architectural Role:
        Primary electrophysiology domain object used across ELN notebooks and viewers.
        @agent: eln-parser-agent
    """

    file_format: str
    sampling_rate_hz: float
    sample_interval_us: float
    sweep_count: int
    sweep_length_points: int
    channel_names: List[str]
    channel_units: List[str]
    holding_potential_mv: float
    protocol_name: str
    operation_mode: str
    comments: List[ABFTag] = field(default_factory=list)
    sweeps_data: Dict[str, List[List[float]]] = field(default_factory=dict)
    thumbnails: Dict[str, List[List[Tuple[float, float]]]] = field(default_factory=dict)
    raw_header: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize metadata and summary statistics to a JSON-compatible dictionary.

        Returns:
            Dict[str, Any]: Structured dictionary omitting raw full-resolution arrays.
        """
        return {
            "file_format": self.file_format,
            "sampling_rate_hz": self.sampling_rate_hz,
            "sample_interval_us": self.sample_interval_us,
            "sweep_count": self.sweep_count,
            "sweep_length_points": self.sweep_length_points,
            "channel_names": self.channel_names,
            "channel_units": self.channel_units,
            "holding_potential_mv": self.holding_potential_mv,
            "protocol_name": self.protocol_name,
            "operation_mode": self.operation_mode,
            "comments": [{"time_s": t.time_seconds, "text": t.comment} for t in self.comments],
            "thumbnail_sample_count": {
                ch: [len(sw) for sw in sw_list] for ch, sw_list in self.thumbnails.items()
            },
        }


class ABFParser:
    """
    Pure-Python Axon Binary Format (.abf) and Axon Text Format (.atf) parser.

    Supports:
        - ABF Version 1.x (magic 'ABF ')
        - ABF Version 2.x (magic 'ABF2')
        - ATF text files (magic 'ATF')
        - Auto-downsampling with peak-preserving min-max bucketing (200 points per sweep)

    Architectural Role:
        Parses high-throughput patch-clamp and field recordings into structured ELN representations.
        @agent: eln-parser-agent
    """

    @classmethod
    def parse(cls, source: Union[bytes, str, Path], target_thumbnail_points: int = 200) -> ABFData:
        """
        Parse raw ABF/ATF data from a file path or binary byte buffer.

        Args:
            source (Union[bytes, str, Path]): File path or raw bytes to parse.
            target_thumbnail_points (int): Number of coordinates to retain per sweep thumbnail.

        Returns:
            ABFData: Parsed recording metadata, sweep traces, and web thumbnails.

        Raises:
            ValueError: If the file header or magic bytes are unsupported.
        """
        if isinstance(source, (str, Path)):
            with open(source, "rb") as f:
                data = f.read()
        elif isinstance(source, bytes):
            data = source
        else:
            raise TypeError(f"Unsupported source type: {type(source).__name__}")

        if len(data) < 4:
            raise ValueError("File too short to be an ABF or ATF file.")

        magic = data[:4]
        if magic == b"ABF ":
            return cls._parse_abf1(data, target_thumbnail_points)
        elif magic == b"ABF2":
            return cls._parse_abf2(data, target_thumbnail_points)
        elif data.startswith(b"ATF") or magic.startswith(b"ATF"):
            return cls._parse_atf(data, target_thumbnail_points)
        else:
            raise ValueError(f"Unrecognized ABF signature: {magic!r}. Expected 'ABF ', 'ABF2', or 'ATF'.")

    @classmethod
    def _parse_abf1(cls, data: bytes, target_thumbnail_points: int) -> ABFData:
        """
        Parse ABF Version 1.x binary data.

        Args:
            data (bytes): Raw file bytes.
            target_thumbnail_points (int): Coordinates count for thumbnail downsampling.

        Returns:
            ABFData: Parsed electrophysiology data object.
        """
        file_version = struct.unpack_from("<f", data, 4)[0]
        operation_mode_code = struct.unpack_from("<h", data, 8)[0]
        actual_acq_length = struct.unpack_from("<i", data, 10)[0]
        actual_episodes = struct.unpack_from("<i", data, 16)[0]
        data_section_ptr = struct.unpack_from("<i", data, 40)[0]
        tag_section_ptr = struct.unpack_from("<i", data, 44)[0]
        num_tag_entries = struct.unpack_from("<i", data, 48)[0]
        data_format = struct.unpack_from("<h", data, 100)[0]  # 0: int16, 1: float32
        adc_num_channels = max(1, struct.unpack_from("<h", data, 120)[0])
        adc_sample_interval = struct.unpack_from("<f", data, 122)[0]

        # Holding potential at offset 244 (float32 array)
        try:
            holding_potential = float(struct.unpack_from("<f", data, 244)[0])
        except Exception:
            holding_potential = -70.0

        # Protocol path at offset 684 (384 bytes string)
        protocol_name = ""
        try:
            raw_proto = data[684 : 684 + 384].split(b"\x00")[0]
            protocol_name = raw_proto.decode("ascii", errors="ignore").strip()
            if "\\" in protocol_name:
                protocol_name = protocol_name.split("\\")[-1]
            elif "/" in protocol_name:
                protocol_name = protocol_name.split("/")[-1]
        except Exception:
            protocol_name = "DefaultProtocol"

        if not protocol_name:
            protocol_name = "Protocol_ABF1"

        modes = {
            1: "event-driven",
            2: "gap-free",
            3: "variable-length",
            4: "fixed-length",
            5: "waveform",
        }
        operation_mode = modes.get(operation_mode_code, "gap-free")

        # Sampling rate calculation
        if adc_sample_interval <= 0:
            adc_sample_interval = 100.0  # 100 us default
        sample_interval_us = adc_sample_interval * adc_num_channels
        sampling_rate_hz = 1_000_000.0 / sample_interval_us if sample_interval_us > 0 else 10000.0

        # Channel names
        channel_names = [f"IN {i}" for i in range(adc_num_channels)]
        channel_units = ["pA" if i == 0 else "mV" for i in range(adc_num_channels)]

        # Tags extraction
        comments: List[ABFTag] = []
        if tag_section_ptr > 0 and num_tag_entries > 0:
            tag_offset = tag_section_ptr * 512
            for t_idx in range(num_tag_entries):
                entry_offset = tag_offset + (t_idx * 64)
                if entry_offset + 64 <= len(data):
                    t_time_pts = struct.unpack_from("<i", data, entry_offset)[0]
                    t_text_raw = data[entry_offset + 4 : entry_offset + 60].split(b"\x00")[0]
                    t_text = t_text_raw.decode("ascii", errors="ignore").strip()
                    t_type = struct.unpack_from("<h", data, entry_offset + 60)[0]
                    t_sec = (t_time_pts * adc_sample_interval) / 1_000_000.0
                    comments.append(ABFTag(time_seconds=t_sec, comment=t_text, tag_type=t_type))

        # Data extraction
        data_byte_offset = data_section_ptr * 512
        sweep_count = max(1, actual_episodes)
        total_points = actual_acq_length
        points_per_sweep_total = total_points // sweep_count if sweep_count > 0 else total_points
        points_per_channel_sweep = points_per_sweep_total // adc_num_channels if adc_num_channels > 0 else points_per_sweep_total

        sweeps_data: Dict[str, List[List[float]]] = {ch: [] for ch in channel_names}

        if data_byte_offset < len(data) and points_per_channel_sweep > 0:
            # Unpack data
            if data_format == 0:  # int16
                elem_size = 2
                fmt = f"<{points_per_sweep_total}h"
            else:  # float32
                elem_size = 4
                fmt = f"<{points_per_sweep_total}f"

            for s in range(sweep_count):
                sw_offset = data_byte_offset + (s * points_per_sweep_total * elem_size)
                if sw_offset + (points_per_sweep_total * elem_size) <= len(data):
                    unpacked = struct.unpack_from(fmt, data, sw_offset)
                    # De-interleave channels
                    for ch_idx, ch_name in enumerate(channel_names):
                        ch_series = [float(unpacked[i]) for i in range(ch_idx, len(unpacked), adc_num_channels)]
                        sweeps_data[ch_name].append(ch_series)
                else:
                    # Provide dummy data if truncated
                    for ch_name in channel_names:
                        sweeps_data[ch_name].append([0.0] * points_per_channel_sweep)
        else:
            # Fallback zero-filled baseline
            points_per_channel_sweep = 1000
            for ch_name in channel_names:
                sweeps_data[ch_name].append([holding_potential] * points_per_channel_sweep)

        # Generate downsampled thumbnails
        thumbnails = cls._generate_thumbnails(
            sweeps_data, sample_interval_us, target_thumbnail_points
        )

        return ABFData(
            file_format="ABF1",
            sampling_rate_hz=round(sampling_rate_hz, 2),
            sample_interval_us=round(sample_interval_us, 4),
            sweep_count=len(sweeps_data[channel_names[0]]),
            sweep_length_points=points_per_channel_sweep,
            channel_names=channel_names,
            channel_units=channel_units,
            holding_potential_mv=holding_potential,
            protocol_name=protocol_name,
            operation_mode=operation_mode,
            comments=comments,
            sweeps_data=sweeps_data,
            thumbnails=thumbnails,
            raw_header={"file_version": file_version, "data_format": data_format},
        )

    @classmethod
    def _parse_abf2(cls, data: bytes, target_thumbnail_points: int) -> ABFData:
        """
        Parse ABF Version 2.x binary data.

        Args:
            data (bytes): Raw file bytes.
            target_thumbnail_points (int): Coordinates count for thumbnail downsampling.

        Returns:
            ABFData: Parsed electrophysiology data object.
        """
        # File version
        build, minor, bugfix, major = struct.unpack_from("<BBBB", data, 4)
        file_version = f"{major}.{bugfix}.{minor}.{build}"

        actual_episodes = struct.unpack_from("<I", data, 12)[0]
        data_format = struct.unpack_from("<H", data, 30)[0]  # 0: int16, 1: float32

        # Read 16 section map blocks starting at byte offset 76
        # Section struct: uBlockIndex (u32), uBytes (u32), llNumEntries (i64) -> 16 bytes
        sections: Dict[str, Tuple[int, int, int]] = {}
        section_names = [
            "ProtocolSection",
            "ADCSection",
            "DACSection",
            "EpochSection",
            "ADCPerDACSection",
            "EpochPerDACSection",
            "UserListSection",
            "StatsRegionSection",
            "MathSection",
            "StringsSection",
            "DataSection",
            "TagSection",
            "ScopeSection",
            "DeltaSection",
            "VoiceTagSection",
            "SynchArraySection",
        ]

        sec_offset = 76
        for name in section_names:
            if sec_offset + 16 <= len(data):
                u_block, u_bytes, num_entries = struct.unpack_from("<IIq", data, sec_offset)
                sections[name] = (u_block, u_bytes, num_entries)
                sec_offset += 16

        # Parse StringsSection
        strings: List[str] = [""]
        if "StringsSection" in sections:
            s_block, s_bytes, s_entries = sections["StringsSection"]
            s_start = s_block * 512
            s_end = s_start + (s_bytes * s_entries)
            if s_start < len(data):
                raw_strings_data = data[s_start:min(s_end, len(data))]
                # ABF2 strings are separated by \x00
                parsed_strs = [s.decode("ascii", errors="ignore").strip() for s in raw_strings_data.split(b"\x00")]
                strings.extend([s for s in parsed_strs if s])

        def get_string(idx: int) -> str:
            if 0 < idx < len(strings):
                return strings[idx]
            return ""

        # Parse ProtocolSection
        operation_mode = "gap-free"
        sample_interval_us = 50.0  # default 20 kHz
        protocol_name = "Protocol_ABF2"
        if "ProtocolSection" in sections:
            p_block, p_bytes, _ = sections["ProtocolSection"]
            p_start = p_block * 512
            if p_start + 16 <= len(data):
                op_mode_code = struct.unpack_from("<h", data, p_start)[0]
                seq_interval = struct.unpack_from("<f", data, p_start + 2)[0]
                if seq_interval > 0:
                    sample_interval_us = seq_interval
                proto_str_idx = struct.unpack_from("<I", data, p_start + 48)[0] if p_start + 52 <= len(data) else 0
                if proto_str_idx > 0:
                    protocol_name = get_string(proto_str_idx)

                modes = {1: "event-driven", 2: "gap-free", 3: "variable-length", 4: "fixed-length", 5: "waveform"}
                operation_mode = modes.get(op_mode_code, "gap-free")

        # Parse ADCSection
        channel_names: List[str] = []
        channel_units: List[str] = []
        instrument_scale_factors: List[float] = []
        if "ADCSection" in sections:
            adc_block, adc_bytes, adc_count = sections["ADCSection"]
            adc_start = adc_block * 512
            for ch_i in range(adc_count):
                ch_offset = adc_start + (ch_i * adc_bytes)
                if ch_offset + 60 <= len(data):
                    name_idx = struct.unpack_from("<I", data, ch_offset + 14)[0]
                    unit_idx = struct.unpack_from("<I", data, ch_offset + 18)[0]
                    scale = struct.unpack_from("<f", data, ch_offset + 22)[0]

                    ch_name = get_string(name_idx) or f"IN {ch_i}"
                    ch_unit = get_string(unit_idx) or ("pA" if ch_i == 0 else "mV")

                    channel_names.append(ch_name)
                    channel_units.append(ch_unit)
                    instrument_scale_factors.append(scale if scale != 0 else 1.0)

        if not channel_names:
            channel_names = ["IN 0"]
            channel_units = ["pA"]
            instrument_scale_factors = [1.0]

        # Parse DACSection for holding potential
        holding_potential = -70.0
        if "DACSection" in sections:
            dac_block, dac_bytes, dac_count = sections["DACSection"]
            dac_start = dac_block * 512
            if dac_start + 16 <= len(data) and dac_count > 0:
                try:
                    dac_holding = struct.unpack_from("<f", data, dac_start + 12)[0]
                    holding_potential = float(dac_holding)
                except Exception:
                    pass

        # Parse TagSection
        comments: List[ABFTag] = []
        if "TagSection" in sections:
            tag_block, tag_bytes, tag_count = sections["TagSection"]
            tag_start = tag_block * 512
            for ti in range(tag_count):
                to = tag_start + (ti * tag_bytes)
                if to + 64 <= len(data):
                    t_time_pts = struct.unpack_from("<i", data, to)[0]
                    t_str_raw = data[to + 4 : to + 60].split(b"\x00")[0]
                    t_text = t_str_raw.decode("ascii", errors="ignore").strip()
                    t_type = struct.unpack_from("<h", data, to + 60)[0]
                    t_sec = (t_time_pts * sample_interval_us) / 1_000_000.0
                    comments.append(ABFTag(time_seconds=t_sec, comment=t_text, tag_type=t_type))

        # Parse DataSection
        sweep_count = max(1, actual_episodes)
        sweeps_data: Dict[str, List[List[float]]] = {ch: [] for ch in channel_names}
        points_per_channel_sweep = 1000

        if "DataSection" in sections:
            d_block, d_bytes, d_entries = sections["DataSection"]
            d_start = d_block * 512
            d_total_bytes = d_bytes * d_entries
            elem_size = 2 if data_format == 0 else 4
            num_samples = d_total_bytes // elem_size
            num_channels = len(channel_names)

            if num_samples > 0 and num_channels > 0 and d_start + (num_samples * elem_size) <= len(data):
                fmt = f"<{num_samples}{'h' if data_format == 0 else 'f'}"
                unpacked = struct.unpack_from(fmt, data, d_start)

                total_points_per_sweep = num_samples // sweep_count if sweep_count > 0 else num_samples
                points_per_channel_sweep = total_points_per_sweep // num_channels

                for s_i in range(sweep_count):
                    s_begin = s_i * total_points_per_sweep
                    s_chunk = unpacked[s_begin : s_begin + total_points_per_sweep]
                    for ch_idx, ch_name in enumerate(channel_names):
                        raw_ch = [float(s_chunk[i]) for i in range(ch_idx, len(s_chunk), num_channels)]
                        sweeps_data[ch_name].append(raw_ch)

        if not sweeps_data[channel_names[0]]:
            for ch in channel_names:
                sweeps_data[ch].append([holding_potential] * points_per_channel_sweep)

        sampling_rate_hz = 1_000_000.0 / sample_interval_us if sample_interval_us > 0 else 20000.0

        thumbnails = cls._generate_thumbnails(
            sweeps_data, sample_interval_us, target_thumbnail_points
        )

        return ABFData(
            file_format="ABF2",
            sampling_rate_hz=round(sampling_rate_hz, 2),
            sample_interval_us=round(sample_interval_us, 4),
            sweep_count=len(sweeps_data[channel_names[0]]),
            sweep_length_points=points_per_channel_sweep,
            channel_names=channel_names,
            channel_units=channel_units,
            holding_potential_mv=holding_potential,
            protocol_name=protocol_name,
            operation_mode=operation_mode,
            comments=comments,
            sweeps_data=sweeps_data,
            thumbnails=thumbnails,
            raw_header={"file_version": file_version, "data_format": data_format},
        )

    @classmethod
    def _parse_atf(cls, data: bytes, target_thumbnail_points: int) -> ABFData:
        """
        Parse Axon Text Format (ATF) ASCII data.

        Args:
            data (bytes): Raw file text bytes.
            target_thumbnail_points (int): Coordinates count for thumbnail downsampling.

        Returns:
            ABFData: Parsed electrophysiology data object.
        """
        text = data.decode("utf-8", errors="ignore")
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        if not lines or not lines[0].startswith("ATF"):
            raise ValueError("Invalid ATF file header.")

        # Line 1: header line count and column count
        # Line 2+: Optional key=val attributes in quotes, e.g. "AcquisitionMode=Episodic"
        line_idx = 1
        num_header_records = 0
        num_columns = 0
        if len(lines) > 1 and "\t" in lines[1]:
            parts = lines[1].split("\t")
            try:
                num_header_records = int(parts[0].strip())
                num_columns = int(parts[1].strip())
                line_idx = 2
            except ValueError:
                pass

        header_tags: Dict[str, str] = {}
        comments: List[ABFTag] = []
        holding_potential = -70.0
        protocol_name = "Protocol_ATF"
        operation_mode = "gap-free"

        while line_idx < len(lines):
            line = lines[line_idx]
            line_idx += 1
            if line.startswith('"') and "=" in line:
                cleaned = line.strip('"')
                k, v = cleaned.split("=", 1)
                header_tags[k.strip()] = v.strip()
                if "mode" in k.lower():
                    operation_mode = v.strip().lower()
                elif "holding" in k.lower():
                    try:
                        holding_potential = float(v.strip())
                    except ValueError:
                        pass
                elif "protocol" in k.lower():
                    protocol_name = v.strip()
                elif "comment" in k.lower():
                    comments.append(ABFTag(time_seconds=0.0, comment=v.strip()))
            else:
                # Column headers line found
                col_headers = [c.strip().strip('"') for c in line.split("\t")]
                break
        else:
            col_headers = ["Time (s)", "Trace (pA)"]

        # Parse numeric tabular rows
        time_vals: List[float] = []
        columns_data: List[List[float]] = [[] for _ in range(max(1, len(col_headers) - 1))]

        for row_line in lines[line_idx:]:
            row_parts = row_line.split("\t")
            if len(row_parts) >= 2:
                try:
                    t_val = float(row_parts[0].strip())
                    time_vals.append(t_val)
                    for c_i in range(1, len(row_parts)):
                        if c_i - 1 < len(columns_data):
                            columns_data[c_i - 1].append(float(row_parts[c_i].strip()))
                except ValueError:
                    continue

        sample_interval_us = 100.0
        if len(time_vals) >= 2:
            dt_s = (time_vals[-1] - time_vals[0]) / max(1, len(time_vals) - 1)
            sample_interval_us = max(0.1, dt_s * 1_000_000.0)

        sampling_rate_hz = 1_000_000.0 / sample_interval_us

        channel_names = [col_headers[i + 1] if i + 1 < len(col_headers) else f"Trace {i+1}" for i in range(len(columns_data))]
        if not channel_names:
            channel_names = ["Trace 1"]
            columns_data = [[0.0] * max(1, len(time_vals))]

        sweeps_data: Dict[str, List[List[float]]] = {}
        for ch_idx, ch_name in enumerate(channel_names):
            sweeps_data[ch_name] = [columns_data[ch_idx]]

        thumbnails = cls._generate_thumbnails(
            sweeps_data, sample_interval_us, target_thumbnail_points
        )

        return ABFData(
            file_format="ATF",
            sampling_rate_hz=round(sampling_rate_hz, 2),
            sample_interval_us=round(sample_interval_us, 4),
            sweep_count=1,
            sweep_length_points=len(time_vals),
            channel_names=channel_names,
            channel_units=["pA" if "pA" in ch else "mV" for ch in channel_names],
            holding_potential_mv=holding_potential,
            protocol_name=protocol_name,
            operation_mode=operation_mode,
            comments=comments,
            sweeps_data=sweeps_data,
            thumbnails=thumbnails,
            raw_header=header_tags,
        )

    @classmethod
    def _generate_thumbnails(
        cls,
        sweeps_data: Dict[str, List[List[float]]],
        sample_interval_us: float,
        target_points: int = 200,
    ) -> Dict[str, List[List[Tuple[float, float]]]]:
        """
        Generate peak-preserving min-max downsampled thumbnails for fast web canvas and SVG rendering.

        Preserves electrophysiological spike amplitudes and EPSP/IPSP waveforms without aliasing.

        Args:
            sweeps_data (Dict[str, List[List[float]]]): Raw sweep series.
            sample_interval_us (float): Inter-sample interval in microseconds.
            target_points (int): Max points to produce per sweep (typically 200).

        Returns:
            Dict[str, List[List[Tuple[float, float]]]]: Channel -> List of Sweeps -> (time_ms, value).
        """
        thumbnails: Dict[str, List[List[Tuple[float, float]]]] = {}

        for ch_name, sweeps in sweeps_data.items():
            thumbnails[ch_name] = []
            for sweep in sweeps:
                n = len(sweep)
                if n <= target_points:
                    pts = [((i * sample_interval_us) / 1000.0, sweep[i]) for i in range(n)]
                    thumbnails[ch_name].append(pts)
                    continue

                # Min-Max bucketing
                bucket_count = max(2, target_points // 2)
                bucket_size = n / float(bucket_count)
                downsampled: List[Tuple[float, float]] = []

                for b in range(bucket_count):
                    start_idx = int(b * bucket_size)
                    end_idx = min(n, int((b + 1) * bucket_size))
                    if start_idx >= end_idx:
                        continue

                    min_idx = start_idx
                    max_idx = start_idx
                    min_val = sweep[start_idx]
                    max_val = sweep[start_idx]

                    for idx in range(start_idx + 1, end_idx):
                        val = sweep[idx]
                        if val < min_val:
                            min_val = val
                            min_idx = idx
                        elif val > max_val:
                            max_val = val
                            max_idx = idx

                    # Append in chronological order
                    t_min = (min_idx * sample_interval_us) / 1000.0
                    t_max = (max_idx * sample_interval_us) / 1000.0

                    if min_idx <= max_idx:
                        downsampled.append((round(t_min, 3), round(min_val, 3)))
                        if min_idx != max_idx:
                            downsampled.append((round(t_max, 3), round(max_val, 3)))
                    else:
                        downsampled.append((round(t_max, 3), round(max_val, 3)))
                        downsampled.append((round(t_min, 3), round(min_val, 3)))

                thumbnails[ch_name].append(downsampled)

        return thumbnails
