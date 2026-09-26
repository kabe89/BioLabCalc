import unittest
import os
import json
from biolabcalc.lab_report import LabReport, MeasurementRecord, new_lab_report, record_measurement
from biolabcalc.easy import new_report, record, export_report
from biolabcalc.transcription import calculate_ivt_yield
from biolabcalc.spectroscopy import assess_nanodrop_purity
from biolabcalc.pcr import calculate_pcr_kinetics

class TestLabReport(unittest.TestCase):
    def test_create_and_add_records(self):
        rep = LabReport(title="Test Experiment", experimenter="Test Researcher", project="Demo")
        r1 = rep.add_record(sample_id="S1", parameter="Yield", value=50.0, unit="ug", target=50.0, tolerance_pct=10.0)
        self.assertEqual(r1.status, "PASS")
        self.assertEqual(r1.percent_deviation, 0.0)

        # 12% deviation with 10% tolerance -> FLAG (within 1.5x tolerance)
        r2 = rep.add_record(sample_id="S2", parameter="Yield", value=56.0, unit="ug", target=50.0, tolerance_pct=10.0)
        self.assertEqual(r2.status, "FLAG")
        self.assertEqual(r2.percent_deviation, 12.0)

        # 30% deviation -> FAIL (> 1.5x tolerance)
        r3 = rep.add_record(sample_id="S3", parameter="Yield", value=65.0, unit="ug", target=50.0, tolerance_pct=10.0)
        self.assertEqual(r3.status, "FAIL")

    def test_replicate_statistics(self):
        rep = LabReport()
        rep.add_record("Rep-1", "OD600", 0.80, "AU")
        rep.add_record("Rep-1", "OD600", 0.82, "AU")
        rep.add_record("Rep-1", "OD600", 0.78, "AU")

        stats = rep.calculate_statistics(sample_id="Rep-1", parameter="OD600")
        self.assertEqual(len(stats), 1)
        s = stats[0]
        self.assertEqual(s.count, 3)
        self.assertEqual(s.mean, 0.80)
        self.assertEqual(s.min_value, 0.78)
        self.assertEqual(s.max_value, 0.82)
        self.assertAlmostEqual(s.cv_percent, 2.5, delta=0.2)

    def test_record_biolabcalc_outputs(self):
        rep = LabReport()

        # 1. NanoDrop
        purity = assess_nanodrop_purity(a260=1.2, a280=0.6, a230=0.55, sample_type="rna")
        recs_nano = rep.record_nanodrop("Sample-RNA", purity)
        self.assertGreaterEqual(len(recs_nano), 3)

        # 2. IVT
        ivt = calculate_ivt_yield("GGGAAUGCAUGCAUGC", measured_yield_ug=35.0)
        recs_ivt = rep.record_ivt("IVT-Transcript", ivt)
        self.assertGreaterEqual(len(recs_ivt), 4)

        # 3. PCR
        pcr = calculate_pcr_kinetics(amplicon_len_bp=500, template_ng=5.0, cycles=30)
        recs_pcr = rep.record_pcr("PCR-Amplicon", pcr)
        self.assertGreaterEqual(len(recs_pcr), 3)

        # 4. Western
        recs_wb = rep.record_western("GluK2-Lane1", band_mw_kda=102.0, intensity_au=15400.0, target_kda=102.5)
        self.assertEqual(len(recs_wb), 2)
        self.assertEqual(recs_wb[0].status, "PASS")

    def test_export_formats(self):
        rep = new_lab_report(title="Full Export Test", experimenter="Alice", project="Project-Alpha")
        rep.add_record("A1", "Yield", 42.0, "ug", target=40.0)
        rep.add_record("A1", "Yield", 43.0, "ug", target=40.0)
        rep.add_conclusion("Experiment completed successfully with high yield.")

        # Markdown
        md_file = "/tmp/test_report_out.md"
        rep.to_markdown(md_file)
        self.assertTrue(os.path.exists(md_file))
        with open(md_file, "r") as f:
            content = f.read()
            self.assertIn("Full Export Test", content)
            self.assertIn("Replicate Statistics", content)

        # CSV
        csv_file = "/tmp/test_report_out.csv"
        rep.to_csv(csv_file)
        self.assertTrue(os.path.exists(csv_file))

        # JSON
        json_file = "/tmp/test_report_out.json"
        rep.to_json(json_file)
        self.assertTrue(os.path.exists(json_file))
        with open(json_file, "r") as f:
            data = json.load(f)
            self.assertEqual(data["title"], "Full Export Test")
            self.assertEqual(len(data["records"]), 2)

        # Excel
        xl_file = "/tmp/test_report_out.xlsx"
        rep.to_excel(xl_file)
        self.assertTrue(os.path.exists(xl_file))
        self.assertGreater(os.path.getsize(xl_file), 4000)

    def test_easy_report_api(self):
        r = new_report("Easy Report", experimenter="Bob")
        rec = record("Sample-Easy", "Concentration", 125.0, "ng/uL", target=120.0)
        self.assertEqual(rec.sample_id, "Sample-Easy")

        out = export_report("/tmp/easy_report.md")
        self.assertTrue(os.path.exists("/tmp/easy_report.md"))

if __name__ == '__main__':
    unittest.main()
