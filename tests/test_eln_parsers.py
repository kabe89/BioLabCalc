"""
Test Suite: test_eln_parsers
Component: Scientific Parsers & HITL Vision-OCR Engine Verification
Agent: @agent: eln-parser-agent
Architectural Role: Comprehensive verification of ABF (v1/v2/ATF), FPLC (CSV/ASC/ZIP/RES),
NanoDrop (TSV/CSV/NDV/XLSX), Bio-Rad Image Lab (.scn/TIFF), Legacy DOCX/PDF, and HITL OCR
with structured [[UNCERTAIN:...]] token correction.
"""

import io
import math
import struct
import unittest
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

from PIL import Image

from biolabcalc.eln.parsers.abf_parser import ABFData, ABFParser
from biolabcalc.eln.parsers.biorad_parser import BioRadImage, BioRadParser
from biolabcalc.eln.parsers.doc_parser import DocParser, DocumentResult
from biolabcalc.eln.parsers.fplc_parser import FPLCParser, FPLCResult
from biolabcalc.eln.parsers.nanodrop_parser import NanoDropExperiment, NanoDropParser
from biolabcalc.eln.parsers.ocr_engine import OCREngine, OCRResult


class TestABFParser(unittest.TestCase):
    """Test Axon Binary Format and Axon Text Format parsing."""

    def test_parse_atf(self):
        atf_text = (
            "ATF\t1.0\n"
            "2\t3\n"
            '"AcquisitionMode=Episodic"\n'
            '"HoldingPotential=-70.0"\n'
            '"Time (s)"\t"IN 0 (pA)"\t"IN 1 (mV)"\n'
            "0.000\t-15.2\t-70.0\n"
            "0.001\t-15.5\t-70.1\n"
            "0.002\t120.4\t-20.0\n"
            "0.003\t-14.8\t-69.9\n"
        )
        data = ABFParser.parse(atf_text.encode("utf-8"))
        self.assertIsInstance(data, ABFData)
        self.assertEqual(data.file_format, "ATF")
        self.assertEqual(data.holding_potential_mv, -70.0)
        self.assertIn("IN 0 (pA)", data.channel_names)
        self.assertEqual(data.sweep_count, 1)
        self.assertTrue(len(data.thumbnails["IN 0 (pA)"][0]) > 0)

    def test_parse_abf1_binary(self):
        # Create synthetic valid ABF v1 binary header and data
        header = bytearray(2048)
        header[0:4] = b"ABF "
        struct.pack_into("<f", header, 4, 1.83)  # FileVersion
        struct.pack_into("<h", header, 8, 2)     # OperationMode = gap-free
        struct.pack_into("<i", header, 10, 400)  # ActualAcqLength = 400 samples
        struct.pack_into("<i", header, 16, 2)    # Sweep count = 2
        struct.pack_into("<i", header, 40, 4)    # DataSectionPtr = block 4 (4 * 512 = 2048)
        struct.pack_into("<i", header, 44, 0)    # No tags
        struct.pack_into("<h", header, 100, 0)   # DataFormat = int16
        struct.pack_into("<h", header, 120, 1)   # ADC channels = 1
        struct.pack_into("<f", header, 122, 100.0)  # 100 us sample interval
        struct.pack_into("<f", header, 244, -65.0)  # Holding potential
        header[684:684 + 16] = b"WholeCellPatch\x00"

        # Generate 400 int16 samples
        samples = [int(100.0 * math.sin(i * 0.1)) for i in range(400)]
        data_bytes = struct.pack(f"<{len(samples)}h", *samples)

        abf1_file = bytes(header) + data_bytes

        data = ABFParser.parse(abf1_file, target_thumbnail_points=50)
        self.assertEqual(data.file_format, "ABF1")
        self.assertEqual(data.operation_mode, "gap-free")
        self.assertEqual(data.holding_potential_mv, -65.0)
        self.assertEqual(data.protocol_name, "WholeCellPatch")
        self.assertEqual(data.sweep_count, 2)
        self.assertEqual(len(data.channel_names), 1)
        # Thumbnails should be bounded
        thumb = data.thumbnails[data.channel_names[0]][0]
        self.assertLessEqual(len(thumb), 50)

    def test_parse_abf2_binary(self):
        # Construct synthetic ABF2 file
        header = bytearray(512)
        header[0:4] = b"ABF2"
        struct.pack_into("<BBBB", header, 4, 0, 0, 0, 2)  # Version 2.0.0.0
        struct.pack_into("<I", header, 12, 1)              # Sweep count = 1
        struct.pack_into("<H", header, 30, 1)              # DataFormat = 1 (float32)

        # Build Section Map at offset 76
        # Section 0: ProtocolSection at block 1 (offset 512), 1 entry of 512 bytes
        # Section 1: ADCSection at block 2, 1 entry of 128 bytes
        # Section 2: DACSection at block 3, 1 entry of 64 bytes
        # Section 9: StringsSection at block 4, 1 entry of 128 bytes
        # Section 10: DataSection at block 5, 200 entries of 4 bytes (800 bytes)
        sec_map = [
            (1, 512, 1),  # ProtocolSection
            (2, 128, 1),  # ADCSection
            (3, 64, 1),   # DACSection
            (0, 0, 0),    # EpochSection
            (0, 0, 0),    # ADCPerDACSection
            (0, 0, 0),    # EpochPerDACSection
            (0, 0, 0),    # UserListSection
            (0, 0, 0),    # StatsRegionSection
            (0, 0, 0),    # MathSection
            (4, 128, 1),  # StringsSection
            (5, 4, 200),  # DataSection
            (0, 0, 0),    # TagSection
            (0, 0, 0),    # ScopeSection
            (0, 0, 0),    # DeltaSection
            (0, 0, 0),    # VoiceTagSection
            (0, 0, 0),    # SynchArraySection
        ]
        sec_offset = 76
        for u_block, u_bytes, n_entries in sec_map:
            struct.pack_into("<IIq", header, sec_offset, u_block, u_bytes, n_entries)
            sec_offset += 16

        # Block 1: Protocol
        proto_blk = bytearray(512)
        struct.pack_into("<h", proto_blk, 0, 2)     # OperationMode = gap-free
        struct.pack_into("<f", proto_blk, 2, 50.0)  # 50 us -> 20 kHz
        struct.pack_into("<I", proto_blk, 48, 1)    # String index 1

        # Block 2: ADCSection
        adc_blk = bytearray(512)
        struct.pack_into("<I", adc_blk, 14, 2)  # String index 2 for Channel Name
        struct.pack_into("<I", adc_blk, 18, 3)  # String index 3 for Units
        struct.pack_into("<f", adc_blk, 22, 1.0)  # Scale

        # Block 3: DACSection
        dac_blk = bytearray(512)
        struct.pack_into("<f", dac_blk, 12, -70.0)  # Holding potential

        # Block 4: StringsSection
        strings_blk = bytearray(512)
        raw_strs = b"\x00ActionPotentialProtocol\x00PrimaryCurrent\x00pA\x00"
        strings_blk[:len(raw_strs)] = raw_strs

        # Block 5: DataSection (200 float32 points)
        pts = [math.sin(i * 0.2) * 50.0 for i in range(200)]
        data_blk = struct.pack("<200f", *pts)

        abf2_file = bytes(header) + bytes(proto_blk) + bytes(adc_blk) + bytes(dac_blk) + bytes(strings_blk) + data_blk

        res = ABFParser.parse(abf2_file, target_thumbnail_points=40)
        self.assertEqual(res.file_format, "ABF2")
        self.assertEqual(res.sampling_rate_hz, 20000.0)
        self.assertEqual(res.holding_potential_mv, -70.0)
        self.assertEqual(res.protocol_name, "ActionPotentialProtocol")
        self.assertEqual(res.channel_names, ["PrimaryCurrent"])
        self.assertEqual(res.channel_units, ["pA"])
        self.assertTrue(len(res.thumbnails["PrimaryCurrent"][0]) > 0)


class TestFPLCParser(unittest.TestCase):
    """Test ÄKTA UNICORN FPLC parser."""

    def test_parse_csv_export(self):
        csv_content = (
            "UNICORN 7.0 Export\n"
            "Column: Superdex 200 Increase 10/300 GL\n"
            "Buffer A: 20 mM Tris-HCl pH 8.0, 150 mM NaCl, 1 mM DTT\n"
            "Buffer B: 20 mM Tris-HCl pH 8.0, 150 mM NaCl, 500 mM Imidazole\n"
            "Volume (ml)\tUV 1_280 (mAU)\tUV 2_260 (mAU)\tCond (mS/cm)\t% Conc B\tPreC Pressure (MPa)\tFraction\n"
            "10.0\t5.2\t2.8\t15.1\t0.0\t0.25\t\n"
            "11.0\t12.4\t6.2\t15.2\t0.0\t0.25\tA1\n"
            "12.0\t180.5\t90.2\t15.2\t0.0\t0.26\tA2\n"
            "13.0\t450.0\t225.0\t15.3\t0.0\t0.26\tA2\n"
            "14.0\t35.0\t18.0\t15.3\t0.0\t0.25\tA3\n"
            "15.0\t6.1\t3.0\t15.4\t0.0\t0.25\tB1\n"
        )
        res = FPLCParser.parse(csv_content.encode("utf-8"), filename="purification_run.csv")

        self.assertIsInstance(res, FPLCResult)
        self.assertEqual(res.file_format, "UNICORN_CSV")
        self.assertEqual(len(res.volume_ml), 6)
        self.assertEqual(max(res.uv280_mau), 450.0)

        # Column hardware verification
        self.assertIsNotNone(res.column)
        self.assertEqual(res.column.column_name, "Superdex 200 Increase 10/300 GL")
        self.assertEqual(res.column.bed_volume_ml, 24.0)
        self.assertEqual(res.column.void_volume_ml, 8.0)
        self.assertEqual(res.column.max_pressure_mpa, 5.0)

        # Buffer recipe extraction
        self.assertIsNotNone(res.buffer_a)
        self.assertEqual(res.buffer_a.ph, 8.0)
        self.assertIn("NaCl", res.buffer_a.primary_salt)
        self.assertIn("1 mM DTT", res.buffer_a.additives)

        self.assertIsNotNone(res.buffer_b)
        self.assertIn("500 mM Imidazole", res.buffer_b.additives)

        # Fractions check
        self.assertTrue(len(res.fractions) >= 3)
        peak_fracs = res.get_fraction_peaks(min_mau_threshold=100.0)
        self.assertTrue(any(f.fraction_id == "A2" for f in peak_fracs))

    def test_parse_asc_format(self):
        asc_content = (
            "Chromatogram: UV 1_280\n"
            "Volume (ml)\tmAU\n"
            "5.0\t10.0\n"
            "10.0\t80.0\n"
            "15.0\t20.0\n"
            "Chromatogram: Fraction\n"
            "Volume (ml)\tFraction\n"
            "5.0\tA1\n"
            "10.0\tA2\n"
        )
        res = FPLCParser.parse(asc_content.encode("utf-8"), filename="trace.asc")
        self.assertEqual(res.file_format, "UNICORN_ASC")
        self.assertEqual(len(res.volume_ml), 3)
        self.assertEqual(max(res.uv280_mau), 80.0)

    def test_parse_zip_archive(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "Curves.csv",
                "Volume (ml),UV 1_280 (mAU),Fraction\n1.0,15.0,A1\n2.0,150.0,A2\n3.0,10.0,\n"
            )
        res = FPLCParser.parse(buf.getvalue(), filename="run.zip")
        self.assertEqual(res.file_format, "UNICORN_ZIP")
        self.assertEqual(len(res.volume_ml), 3)


class TestNanoDropParser(unittest.TestCase):
    """Test NanoDrop spectrophotometer parser."""

    def test_parse_csv_samples(self):
        csv_data = (
            "Sample ID,User ID,Date and Time,Concentration,Units,A260,A280,260/280,260/230,A230,Pathlength,A340\n"
            "pET28a_Target,Researcher_1,2026-10-15 14:30,145.2,ng/µL,2.904,1.570,1.85,2.15,1.351,1.0,0.012\n"
            "Total_RNA_HeLa,Researcher_2,2026-10-15 14:32,320.5,ng/µL,8.012,3.986,2.01,2.18,3.675,1.0,0.005\n"
            "Contaminated_DNA,Researcher_1,2026-10-15 14:35,85.0,ng/µL,1.700,1.214,1.40,1.10,1.545,1.0,0.080\n"
        )
        exp = NanoDropParser.parse(csv_data.encode("utf-8"), filename="nanodrop_batch.csv")

        self.assertIsInstance(exp, NanoDropExperiment)
        self.assertEqual(len(exp.samples), 3)

        s1 = exp.samples[0]
        self.assertEqual(s1.sample_name, "pET28a_Target")
        self.assertEqual(s1.concentration, 145.2)
        self.assertEqual(s1.a260, 2.904)
        self.assertEqual(s1.ratio_260_280, 1.85)
        self.assertEqual(s1.ratio_260_230, 2.15)
        self.assertEqual(s1.quality_assessment, "Pure (Passed QC)")

        # Verify 220-350 nm spectrum array presence
        self.assertEqual(len(s1.spectrum_220_350), 131)  # 220 to 350 inclusive
        self.assertIn(260, s1.spectrum_220_350)

        # Contaminated sample QC check
        s3 = exp.samples[2]
        self.assertIn("Protein contamination", s3.quality_assessment)
        self.assertIn("Phenol / Guanidine", s3.quality_assessment)

    def test_parse_xlsx_archive(self):
        # Create minimal OpenXML xlsx container
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            shared_strings = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<si><t>Sample ID</t></si>'
                '<si><t>Concentration</t></si>'
                '<si><t>A260</t></si>'
                '<si><t>A280</t></si>'
                '<si><t>Sample_X</t></si>'
                '</sst>'
            )
            sheet = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData>'
                '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c></row>'
                '<row r="2"><c r="A2" t="s"><v>4</v></c><c r="B2"><v>55.5</v></c><c r="C2"><v>1.11</v></c><c r="D2"><v>0.60</v></c></row>'
                '</sheetData>'
                '</worksheet>'
            )
            zf.writestr("xl/sharedStrings.xml", shared_strings)
            zf.writestr("xl/worksheets/sheet1.xml", sheet)

        exp = NanoDropParser.parse(buf.getvalue(), filename="export.xlsx")
        self.assertEqual(exp.file_format, "XLSX")
        self.assertEqual(len(exp.samples), 1)
        self.assertEqual(exp.samples[0].sample_name, "Sample_X")
        self.assertEqual(exp.samples[0].concentration, 55.5)


class TestBioRadParser(unittest.TestCase):
    """Test Bio-Rad Image Lab (.scn) and TIFF parser."""

    def test_parse_biorad_tiff(self):
        # Create synthetic 16-bit TIFF with Bio-Rad XML metadata block
        img = Image.new("I;16", (120, 160), color=800)
        buf = io.BytesIO()
        img.save(buf, format="TIFF")
        tiff_bytes = bytearray(buf.getvalue())

        # Append Bio-Rad XML descriptor
        xml_metadata = (
            b"<BioRadImage>"
            b"<ExposureTime>4.5s</ExposureTime>"
            b"<ApplicationName>Coomassie Blue</ApplicationName>"
            b"<IlluminationSource>Trans-white</IlluminationSource>"
            b"<FilterName>None</FilterName>"
            b"<Binning>1x1</Binning>"
            b"<InstrumentModel>ChemiDoc MP</InstrumentModel>"
            b"</BioRadImage>"
        )
        scn_payload = bytes(tiff_bytes) + xml_metadata

        res = BioRadParser.parse(scn_payload, auto_contrast=True, invert=True)

        self.assertIsInstance(res, BioRadImage)
        self.assertEqual(res.width, 120)
        self.assertEqual(res.height, 160)
        self.assertEqual(res.bit_depth, 16)
        self.assertEqual(res.exposure.exposure_time_seconds, 4.5)
        self.assertEqual(res.exposure.application_name, "Coomassie Blue")
        self.assertEqual(res.exposure.illumination_source, "Trans-white")
        self.assertEqual(res.exposure.instrument_model, "ChemiDoc MP")

        # Verify generated PNG preview bytes
        self.assertTrue(len(res.preview_png_bytes) > 0)
        with Image.open(io.BytesIO(res.preview_png_bytes)) as preview_img:
            self.assertEqual(preview_img.format, "PNG")


class TestDocParser(unittest.TestCase):
    """Test legacy Word (.docx) and PDF document parser."""

    def test_parse_docx(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            doc_xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body>'
                '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Purification SOP</w:t></w:r></w:p>'
                '<w:p><w:r><w:t>Step 1: Equilibrate column with 5 CV buffer.</w:t></w:r></w:p>'
                '<w:tbl>'
                '<w:tr><w:tc><w:p><w:r><w:t>Component</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Amount</w:t></w:r></w:p></w:tc></w:tr>'
                '<w:tr><w:tc><w:p><w:r><w:t>NaCl</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>150 mM</w:t></w:r></w:p></w:tc></w:tr>'
                '</w:tbl>'
                '</w:body>'
                '</w:document>'
            )
            zf.writestr("word/document.xml", doc_xml)
            zf.writestr("word/media/gel_figure.png", b"\x89PNG\r\n\x1a\nfakeimagebytes")

        res = DocParser.parse(buf.getvalue(), filename="sop.docx")
        self.assertIsInstance(res, DocumentResult)
        self.assertEqual(res.file_format, "DOCX")
        self.assertEqual(res.title, "Purification SOP")
        self.assertEqual(len(res.paragraphs), 2)
        self.assertEqual(len(res.tables), 1)
        self.assertEqual(res.tables[0][0], ["Component", "Amount"])
        self.assertEqual(res.tables[0][1], ["NaCl", "150 mM"])
        self.assertEqual(len(res.images), 1)
        self.assertEqual(res.images[0].filename, "gel_figure.png")

        # Markdown representation
        md = res.to_markdown()
        self.assertIn("# Purification SOP", md)
        self.assertIn("| Component | Amount |", md)

    def test_parse_pdf_stream(self):
        # Create minimal synthetic PDF with text and stream
        raw_stream = b"BT\n(Protocol Overview) Tj\n(Run sample on 12% SDS-PAGE gel.) Tj\nET"
        compressed = zlib.compress(raw_stream)

        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Length " + str(len(compressed)).encode("ascii") + b" /Filter /FlateDecode >>\n"
            b"stream\n" + compressed + b"\nendstream\nendobj\n"
            b"xref\n0 2\n0000000000 65535 f \n0000000010 00000 n \ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        )

        res = DocParser.parse(pdf_bytes, filename="protocol.pdf")
        self.assertEqual(res.file_format, "PDF")
        self.assertTrue(len(res.paragraphs) >= 1)
        texts = [p.text for p in res.paragraphs]
        self.assertTrue(any("Protocol Overview" in t for t in texts))


class TestOCREngine(unittest.TestCase):
    """Test Human-in-the-Loop OCR Engine and token correction."""

    def test_transcribe_and_uncertain_tag_serialization(self):
        text = (
            "# Lysis Buffer Protocol\n"
            "Dissolve 0.5 mg/mL lysozyme in 50 mL buffer.\n"
            "Add 1 mM DTT and 10 uL benzonase."
        )
        res = OCREngine.transcribe_text(text, modality="handwritten_notebook")

        self.assertIsInstance(res, OCRResult)
        # Check that 0.5 mg/mL was flagged as uncertain and serialized with the exact required format:
        # [[UNCERTAIN:id="token_id" text="extracted_text" conf=0.xx bbox="[x, y, w, h]" candidates="['cand1', 'cand2']"]]
        self.assertTrue(res.uncertain_token_count >= 1)
        self.assertIn("[[UNCERTAIN:id=", res.markdown)
        self.assertIn('text="0.5', res.markdown)
        self.assertIn("conf=", res.markdown)
        self.assertIn("bbox=", res.markdown)
        self.assertIn("candidates=", res.markdown)

        # Query uncertain tokens list
        uncertain_tokens = OCREngine.get_uncertain_tokens(res.markdown)
        self.assertTrue(len(uncertain_tokens) >= 1)
        first_uncertain = uncertain_tokens[0]
        self.assertTrue(first_uncertain["id"].startswith("tok_"))
        self.assertIsInstance(first_uncertain["bbox"], list)
        self.assertIsInstance(first_uncertain["candidates"], list)

    def test_human_correction_api(self):
        # Given a markdown text with an uncertain token
        initial_md = (
            'Add [[UNCERTAIN:id="tok_42" text="0.5 mg/mL" conf=0.64 '
            'bbox="[120, 450, 80, 25]" candidates="[\'0.5 mg/mL\', \'0.05 mg/mL\', \'5 mg/mL\']"]] '
            'of BSA to each tube.'
        )

        # Human verifies and corrects token value to 0.5 mg/mL
        corrected_md = OCREngine.correct_token(
            markdown_text=initial_md,
            token_id="tok_42",
            corrected_value="0.5 mg/mL",
        )

        self.assertEqual(corrected_md, "Add 0.5 mg/mL of BSA to each tube.")
        self.assertNotIn("[[UNCERTAIN:", corrected_md)

    def test_batch_accept_all_top_candidates(self):
        initial_md = (
            'Mix [[UNCERTAIN:id="tok_1" text="10 µL" conf=0.75 bbox="[10, 10, 50, 20]" candidates="[\'10 µL\', \'100 µL\']"]] '
            'with [[UNCERTAIN:id="tok_2" text="0.5 mg/mL" conf=0.64 bbox="[70, 10, 80, 20]" candidates="[\'0.5 mg/mL\', \'5 mg/mL\']"]].'
        )
        cleaned_md = OCREngine.accept_all_top_candidates(initial_md)
        self.assertEqual(cleaned_md, "Mix 10 µL with 0.5 mg/mL.")
        self.assertNotIn("[[UNCERTAIN:", cleaned_md)

    def test_reject_token(self):
        initial_md = 'Reading was [[UNCERTAIN:id="tok_99" text="1.23" conf=0.40 bbox="[0,0,0,0]" candidates="[\'1.23\']"]] mAU.'
        rejected_md = OCREngine.reject_token(initial_md, "tok_99")
        self.assertEqual(rejected_md, "Reading was [ILLEGIBLE] mAU.")


if __name__ == "__main__":
    unittest.main()
