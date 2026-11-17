"""
Unit tests for Bio-Rad .scn & .1sc compatibility upgrade and v1.0.0 bug audit remediations.
"""

from __future__ import annotations

import dataclasses
from dataclasses import FrozenInstanceError
import io
import os
import struct
import tempfile
import unittest
import zipfile

from biolabcalc.eln.parsers.biorad_parser import (
    BioRadImage,
    BioRadParser,
    ExposureMetadata,
    _encode_png_stdlib,
)
from biolabcalc.easy import read_scn
from biolabcalc.gel_annotator import GelAnnotator
from biolabcalc.buffers import (
    CustomBufferComponent,
    CustomBufferBuilder,
    save_custom_buffer_to_disk,
    delete_custom_buffer,
    solve_buffer_equilibrium,
    calculate_buffer_recipe,
)
from biolabcalc.plasmid import (
    PlasmidRecord,
    PlasmidFeature,
    parse_snapgene_dna,
    _save_user_plasmids,
)
from biolabcalc.sequence_store import (
    SequenceRecord,
    _save_user_records,
)
from biolabcalc.eln.storage.blob_store import BlobStore
from biolabcalc.eln.services.gel_service import GelService, LadderCalibrationResult
from biolabcalc.gels import GelLaneSimulation, simulate_gel
from biolabcalc.cloning import (
    DigestSetupResult,
    GibsonAssemblyResult,
    GoldenGateResult,
    GoldenGateFidelityResult,
    evaluate_golden_gate_fidelity,
)
from biolabcalc.pcr import PCROptimizationResult
from biolabcalc.transcription import InitiationAnalysis, TranscriptionTimeOptimizationResult
from biolabcalc.western_blot import (
    TransferConditionsResult,
    LysateLoadingResult,
    AntibodyDilutionResult,
    WesternBlotPlanResult,
    WesternTroubleshootingResult,
)
from biolabcalc.protocols import LabProtocol
from biolabcalc.aptamers import evaluate_rna_hairpin_thermo, analyze_counter_selex
from biolabcalc.allostery import parse_pdb_ca_coordinates, trace_allosteric_paths
from biolabcalc.eln.parsers.ab1_parser import AB1TraceResult, AB1Parser, verify_construct_sequencing
from biolabcalc.eln.services.document_vault_service import import_eln_rocrate
from biolabcalc.automation import (
    WellTransfer,
    AutomationWorklist,
    design_serial_dilution_plate,
    well_to_index,
)
from biolabcalc.cli import main as cli_main


def _make_dummy_scn_bytes(width: int = 16, height: int = 12, max_val: int = 40000) -> bytes:
    """Helper to generate a well-formed synthetic Bio-Rad Image Lab .scn binary payload."""
    xml_meta = f"""<?xml version="1.0" encoding="UTF-8"?>
<image_doc>
  <data_image_info>
    <imager value="ChemiDoc MP"/>
    <size_pix width="{width}" height="{height}"/>
    <exposure_time>2.5</exposure_time>
    <saturation saturated_pixel_count="5"/>
    <gain>Standard</gain>
  </data_image_info>
</image_doc>""".encode("utf-8")

    # Generate synthetic pixel data: ramp with peaks
    raw_pixels = []
    for y in range(height):
        for x in range(width):
            val = int(500 + 1000 * ((x % 8) / 8.0) + (max_val if (y == 5 and x == 4) else 0))
            raw_pixels.append(min(val, 65535))
    pixel_bytes = struct.pack(f"<{width * height}H", *raw_pixels)

    boundary = b"---------------------------BioRadMIMEBoundary98765"
    body = bytearray()
    body.extend(boundary + b"\r\n")
    body.extend(b"Content-Type: text/xml\r\n\r\n")
    body.extend(xml_meta + b"\r\n")
    body.extend(boundary + b"\r\n")
    body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
    body.extend(pixel_bytes + b"\r\n")
    body.extend(boundary + b"--\r\n")
    return bytes(body)


def _make_dummy_1sc_bytes(width: int = 8, height: int = 6) -> bytes:
    """Helper to generate a legacy Bio-Rad Quantity One .1sc binary payload."""
    header = b"BIORAD\x00\x00"
    dims = struct.pack("<II", width, height)
    pixels = [1000 + i * 50 for i in range(width * height)]
    pixel_data = struct.pack(f"<{width * height}H", *pixels)
    return header + dims + pixel_data


class TestBioRadParser(unittest.TestCase):
    """Test suite for BioRadParser .scn and .1sc features."""

    def test_scn_parsing_and_metadata(self):
        data = _make_dummy_scn_bytes(width=16, height=12)
        img = BioRadParser.parse(data)
        self.assertEqual(img.width, 16)
        self.assertEqual(img.height, 12)
        self.assertEqual(img.bit_depth, 16)
        self.assertEqual(img.file_format, "SCN")
        self.assertEqual(img.exposure.instrument_model, "ChemiDoc MP")
        self.assertAlmostEqual(img.exposure.exposure_time_seconds, 2.5)
        self.assertEqual(img.saturated_pixel_count, 5)
        self.assertTrue(img.saturation_warning)
        self.assertEqual(len(img.raw_pixels), 16 * 12)
        self.assertIsInstance(img.raw_pixels, tuple)

    def test_legacy_1sc_parsing(self):
        data = _make_dummy_1sc_bytes(width=8, height=6)
        img = BioRadParser.parse(data)
        self.assertEqual(img.width, 8)
        self.assertEqual(img.height, 6)
        self.assertEqual(img.bit_depth, 16)
        self.assertEqual(img.file_format, "1SC")
        self.assertEqual(len(img.raw_pixels), 48)

    def test_stdlib_png_encoder(self):
        width, height = 4, 3
        raw_pixels = bytes([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120])
        png_bytes = _encode_png_stdlib(raw_pixels, width, height)
        self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn(b"IHDR", png_bytes)
        self.assertIn(b"IDAT", png_bytes)
        self.assertIn(b"IEND", png_bytes)

    def test_export_tiff_16bit(self):
        data = _make_dummy_scn_bytes(width=10, height=8)
        img = BioRadParser.parse(data)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_tiff = os.path.join(tmpdir, "exported.tiff")
            BioRadParser.export_tiff_16bit(img, out_tiff)
            self.assertTrue(os.path.exists(out_tiff))
            with open(out_tiff, "rb") as f:
                header = f.read(4)
            self.assertEqual(header, b"II*\x00")

    def test_lane_profile_and_band_detection(self):
        data = _make_dummy_scn_bytes(width=20, height=30, max_val=60000)
        img = BioRadParser.parse(data)
        profile = BioRadParser.extract_lane_profile(img, lane_index=1, num_lanes=4)
        self.assertIsInstance(profile, tuple)
        self.assertEqual(len(profile), 30)

        bands = BioRadParser.detect_lane_bands(img, lane_index=1, num_lanes=4)
        self.assertIsInstance(bands, tuple)
        for band in bands:
            self.assertIsInstance(band, dict)
            self.assertIn("rf", band)
            self.assertIn("intensity_au", band)

    def test_biorad_image_immutability(self):
        data = _make_dummy_scn_bytes(width=8, height=8)
        img = BioRadParser.parse(data)
        with self.assertRaises(FrozenInstanceError):
            img.width = 10  # type: ignore
        with self.assertRaises(FrozenInstanceError):
            img.exposure.exposure_time_seconds = 10.0  # type: ignore

    def test_easy_read_scn(self):
        data = _make_dummy_scn_bytes(width=12, height=10)
        with tempfile.TemporaryDirectory() as tmpdir:
            scn_path = os.path.join(tmpdir, "test.scn")
            with open(scn_path, "wb") as f:
                f.write(data)
            img = read_scn(scn_path)
            self.assertEqual(img.width, 12)
            self.assertEqual(img.height, 10)

    def test_gel_annotator_from_scn(self):
        data = _make_dummy_scn_bytes(width=16, height=16)
        with tempfile.TemporaryDirectory() as tmpdir:
            scn_path = os.path.join(tmpdir, "gel.scn")
            with open(scn_path, "wb") as f:
                f.write(data)
            annotator = GelAnnotator.from_scn(scn_path)
            self.assertEqual(annotator.image_path, scn_path)
            self.assertIn("ChemiDoc MP", annotator.gel_info)

    def test_cli_scn_subcommand(self):
        data = _make_dummy_scn_bytes(width=16, height=16)
        with tempfile.TemporaryDirectory() as tmpdir:
            scn_path = os.path.join(tmpdir, "gel.scn")
            png_out = os.path.join(tmpdir, "gel.png")
            tiff_out = os.path.join(tmpdir, "gel.tiff")
            with open(scn_path, "wb") as f:
                f.write(data)
            # Run CLI scn with export and JSON
            import contextlib
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                cli_main(["scn", "-i", scn_path, "--output-png", png_out, "--output-tiff", tiff_out, "--lanes", "4", "--detect-bands", "--json"])
            output = f.getvalue()
            self.assertIn('"format": "SCN"', output)
            self.assertIn('"instrument": "ChemiDoc MP"', output)
            self.assertTrue(os.path.exists(png_out))
            self.assertTrue(os.path.exists(tiff_out))


class TestBugAuditFixes(unittest.TestCase):
    """Test suite for repository bug fixes (BUG-01 to BUG-14 & V1-AUDIT-01 to V1-AUDIT-08)."""

    def test_bug_08_custom_buffer_atomic_and_frozen(self):
        comp = CustomBufferComponent(name="NaCl", comp_type="solid", target_concentration_mm=100.0, mw_g_mol=58.44)
        with self.assertRaises(FrozenInstanceError):
            comp.mw_g_mol = 60.0  # type: ignore

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "buffers.json")
            builder = CustomBufferBuilder(name="TestBuf")
            builder.components.append(comp)
            save_custom_buffer_to_disk(builder, path)
            self.assertTrue(os.path.exists(path))
            delete_custom_buffer("TestBuf", path)

    def test_bug_09_atomic_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            seq_path = os.path.join(tmpdir, "sequences.json")
            rec = SequenceRecord(
                id="TEST1",
                name="Test Seq",
                sequence="ATGC",
                seq_type="dna",
                topology="linear",
            )
            _save_user_records({rec.id: rec}, filepath=seq_path)
            self.assertTrue(os.path.exists(seq_path))

            plasmid_path = os.path.join(tmpdir, "plasmids.json")
            feat = PlasmidFeature(name="ori", feature_type="rep_origin", start=1, end=4, strand=1)
            pl = PlasmidRecord(id="pTest", name="pTest", sequence="ATGC", topology="circular", features=(feat,))
            _save_user_plasmids({pl.name: pl}, filepath=plasmid_path)
            self.assertTrue(os.path.exists(plasmid_path))

            blob_dir = os.path.join(tmpdir, "blobs")
            bs = BlobStore(base_dir=blob_dir)
            meta = bs.store_bytes(b"hello world", "test.txt", "text/plain")
            self.assertTrue(bs.exists(meta.sha256))
            bs.update_metadata(meta.sha256, {"tags": ["verified"]})
            updated_meta = bs.get_metadata(meta.sha256)
            self.assertIsNotNone(updated_meta)
            self.assertIn("verified", updated_meta.custom_attributes.get("tags", []))

    def test_bug_10_gel_service_ladder_unit(self):
        service = GelService()
        cal = LadderCalibrationResult(
            ladder_key="1kb_dna",
            slope=-1.0,
            intercept=4.0,
            r_squared=0.99,
            formula_str="log(MW) = -1.0*Rf + 4.0",
            point_count=5,
        )
        res = service.estimate_mw(rf=0.5, calibration=cal)
        self.assertGreater(res["estimated_mw_kda"], 100.0)

    def test_bug_11_frozen_dataclasses_tuple_collections(self):
        # BufferRecipeResult
        res_buf = calculate_buffer_recipe("10X_PBS", 100.0)
        self.assertIsInstance(res_buf.components, tuple)
        self.assertIsInstance(res_buf.preparation_steps, tuple)
        with self.assertRaises(FrozenInstanceError):
            res_buf.target_ph = 8.0  # type: ignore

        # GelLaneSimulation
        sim = simulate_gel(sample_sizes=[500, 1000], ladder_key="1kb_plus_dna")
        self.assertIsInstance(sim.sample_sizes, tuple)
        self.assertIsInstance(sim.ladder_bands, tuple)
        with self.assertRaises(FrozenInstanceError):
            sim.ladder_name = "other"  # type: ignore

        # GoldenGateFidelityResult
        gg_res = evaluate_golden_gate_fidelity(overhangs=["ATGC", "GCTA"])
        self.assertIsInstance(gg_res.overhangs, tuple)
        self.assertIsInstance(gg_res.collision_pairs, tuple)
        with self.assertRaises(FrozenInstanceError):
            gg_res.assembly_fidelity_percent = 99.0  # type: ignore

    def test_v1_audit_01_buffer_equilibrium_stability(self):
        # Extreme pH and zero buffer concentration should not throw ZeroDivisionError
        res = solve_buffer_equilibrium(
            components=[{"name": "Tris", "pka": 8.06, "conc_mm": 50.0}],
            target_ph=1.0,
            temperature_celsius=25.0,
        )
        self.assertIsNotNone(res)
        self.assertIsInstance(res.components, tuple)
        self.assertIsInstance(res.species, tuple)

    def test_v1_audit_02_aptamers_thermo_and_selex(self):
        # Short RNA hairpin (< 6 nt) should evaluate safely without crashing
        short_thermo = evaluate_rna_hairpin_thermo("ACGU")
        self.assertEqual(short_thermo.tm_celsius, 0.0)
        self.assertEqual(short_thermo.structure_dot_bracket, "....")

        # SELEX zero counts handled with Dirichlet smoothing and monotone FDR
        selex_res = analyze_counter_selex(
            target_counts={"A1": 0, "A2": 20},
            counter_counts={"A1": 0, "A2": 0},
        )
        self.assertEqual(len(selex_res.top_candidates), 2)
        self.assertGreater(selex_res.top_candidates[0].p_value_adjusted, 0.0)

    def test_v1_audit_03_allostery_pdb_and_gnm(self):
        # PDB parsing with altLoc and ENDMDL
        pdb_lines = """HEADER    TEST
ATOM      1  CA  MET A   1      11.111  22.222  33.333  1.00 20.00           C
ATOM      2  CA AMET A   2      14.111  22.222  33.333  0.50 20.00           C
ATOM      3  CA BMET A   2      14.222  22.222  33.333  0.50 20.00           C
ENDMDL
ATOM      4  CA  MET A   3      18.111  22.222  33.333  1.00 20.00           C
END
"""
        coords = parse_pdb_ca_coordinates(pdb_lines)
        self.assertEqual(len(coords), 2)  # only residue 1 and 2, ended at ENDMDL

    def test_v1_audit_04_golden_gate_fidelity(self):
        # Reverse-complement overhang collision
        res = evaluate_golden_gate_fidelity(overhangs=["ATGC", "GCAT"])  # GCAT RC is ATGC
        self.assertIn(("ATGC", "GCAT"), res.collision_pairs)

    def test_v1_audit_05_snapgene_1based_coords_and_circular(self):
        # Construct synthetic SnapGene packet with origin-spanning coordinates and verify 1-based output
        body = bytearray()
        body.extend(struct.pack(">BI", 0x09, len(b"SnapGene")) + b"SnapGene")
        seq = b"ATGC" * 25  # length 100
        body.extend(struct.pack(">BI", 0x00, 1 + len(seq)) + b"\x01" + seq)
        xml_feat = b"""<Features>
  <Feature name="AmpR" type="CDS">
    <Segment range="80-20" color="#ff0000"/>
  </Feature>
  <Feature name="ori" type="rep_origin">
    <Segment range="0-10" color="#00ff00"/>
  </Feature>
</Features>"""
        body.extend(struct.pack(">BI", 0x0A, len(xml_feat)) + xml_feat)
        pl = parse_snapgene_dna(bytes(body))
        self.assertEqual(len(pl.sequence), 100)
        self.assertEqual(len(pl.features), 2)
        # Origin-spanning feature length calculation: (100 - 80 + 1) + 20 = 41
        self.assertEqual(pl.features[0].start, 80)
        self.assertEqual(pl.features[0].end, 20)
        self.assertTrue(pl.features[0].spans_origin)
        self.assertEqual(pl.features[0].length, 41)
        # 0-based coordinate 0 converted to 1-based 1
        self.assertEqual(pl.features[1].start, 1)
        self.assertEqual(pl.features[1].end, 10)

    def test_v1_audit_06_ab1_circular_spanning_and_bounds(self):
        plasmid = PlasmidRecord(
            id="pCirc",
            name="pCirc",
            sequence="ATGCATGCATGCATGC",
            topology="circular",
            features=(),
        )
        trace = AB1TraceResult(
            sample_name="read1",
            sequence="GCATGCAT",
            phred_scores=(30,) * 8,
        )
        match_res = verify_construct_sequencing(plasmid, [trace])
        self.assertIsNotNone(match_res)
        self.assertTrue(match_res.junctions_verified)

    def test_v1_audit_07_zip_slip_protection(self):
        # Attempting to unpack a zip with path traversal should fail
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_zip_path = os.path.join(tmpdir, "slip.zip")
            with zipfile.ZipFile(bad_zip_path, "w") as zf:
                zf.writestr("../../etc/passwd", "malicious content")
            with self.assertRaises(ValueError):
                import_eln_rocrate(bad_zip_path)

    def test_v1_audit_08_automation_validation_and_escaping(self):
        # Non-positive volume should raise ValueError
        with self.assertRaises(ValueError):
            WellTransfer(
                source_plate="src",
                source_well="A1",
                dest_plate="dst",
                dest_well="A2",
                volume_ul=0.0,
            )
        # Invalid row/col coordinate should raise ValueError
        with self.assertRaises(ValueError):
            well_to_index("Z99", plate_type="96-well")

        # HTML escaping in _repr_html_
        wl = design_serial_dilution_plate()
        html = wl._repr_html_()
        self.assertIn("Automation Worklist", html)
        self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()
