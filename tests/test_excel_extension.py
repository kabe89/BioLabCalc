import os
import sys
import tempfile
import unittest
import mimetypes

if not getattr(mimetypes, "inited", False):
    try:
        mimetypes.init()
    except (PermissionError, OSError):
        mimetypes.inited = True

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

try:
    import openpyxl
    from biolabcalc.excel_extension import generate_lab_notebook_template, export_analysis_to_excel, batch_process_excel
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

from biolabcalc.transcription import calculate_ivt_yield
from biolabcalc.pcr import calculate_pcr_kinetics

@unittest.skipUnless(HAS_OPENPYXL, "openpyxl required for Excel extension tests")
class TestExcelExtension(unittest.TestCase):
    def test_generate_template(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = os.path.join(tmp_dir, "test_gen_template.xlsx")
            res_path = generate_lab_notebook_template(out_path)
            self.assertTrue(os.path.exists(res_path))
            wb = openpyxl.load_workbook(res_path)
            try:
                self.assertIn("IVT_Stoichiometry", wb.sheetnames)
                self.assertIn("PCR_Optimization", wb.sheetnames)
                self.assertIn("Protein_Quantification", wb.sheetnames)
                self.assertIn("Primer_Design_Log", wb.sheetnames)

                # Issue 7 verification: Master mix formulas
                ws_pcr = wb["PCR_Optimization"]
                self.assertEqual(ws_pcr.cell(row=8, column=5).value, "=D8*$B$5*$D$5")
                self.assertEqual(ws_pcr.cell(row=9, column=5).value, "=D9*$B$5*$D$5")
                self.assertEqual(ws_pcr.cell(row=13, column=5).value, "=D13*$B$5*$D$5")

                # Issue 8 verification: Standard curve regression formula with absolute coordinates
                ws_prot = wb["Protein_Quantification"]
                self.assertEqual(ws_prot.cell(row=20, column=5).value, "=(D20-INTERCEPT($B$20:$B$25,$A$20:$A$25))/SLOPE($B$20:$B$25,$A$20:$A$25)")
            finally:
                wb.close()

    def test_export_analysis(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = os.path.join(tmp_dir, "test_export_analysis.xlsx")
            ivt = calculate_ivt_yield("GGGAAUGCAUGCAUGC", measured_yield_ug=25.0)
            pcr = calculate_pcr_kinetics(amplicon_len_bp=400, template_ng=5.0)
            export_analysis_to_excel(out_path, ivt_results=[ivt], pcr_results=[pcr])
            self.assertTrue(os.path.exists(out_path))
            wb = openpyxl.load_workbook(out_path)
            try:
                self.assertIn("IVT_Results", wb.sheetnames)
                self.assertIn("PCR_Results", wb.sheetnames)
                # Issue 14 verification: No dummy template sheets in export
                self.assertNotIn("Solution_Prep_NanoDrop", wb.sheetnames)
                self.assertNotIn("Fluorophore_Modifications", wb.sheetnames)
                self.assertNotIn("Ecoli_Growth_Optimization", wb.sheetnames)
            finally:
                wb.close()

    def test_batch_process_excel(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            in_path = os.path.join(tmp_dir, "test_unit_batch_in.xlsx")
            out_path = os.path.join(tmp_dir, "test_unit_batch_out.xlsx")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["ID", "Sequence", "Type"])
            ws.append(["Oligo_1", "ATGCCGTCCAGGCTGCTGGTC", "DNA"])
            ws.append(["RNA_1", "GGGAGACCCAAGCUGGCCUGUGUGUACAGCCGAAUG", "RNA"])
            ws.append(["dsDNA_1", "ATGCCGTCCAGGCTGCTGGTC", "dsDNA"])
            ws.append(["Plasmid_1", "ATGCCGTCCAGGCTGCTGGTC", "plasmid"])
            wb.save(in_path)
            wb.close()

            res = batch_process_excel(in_path, out_path)
            self.assertTrue(os.path.exists(res))
            out_wb = openpyxl.load_workbook(res)
            try:
                self.assertIn("Batch_Analysis_Results", out_wb.sheetnames)
                ws_out = out_wb["Batch_Analysis_Results"]
                self.assertEqual(ws_out.cell(row=4, column=2).value, "Oligo_1")
                self.assertGreater(ws_out.cell(row=4, column=6).value, 5000)
                # Check dsDNA and Plasmid rows
                self.assertEqual(ws_out.cell(row=6, column=2).value, "dsDNA_1")
                self.assertEqual(ws_out.cell(row=6, column=3).value, "dsDNA")
                self.assertEqual(ws_out.cell(row=7, column=2).value, "Plasmid_1")
                self.assertEqual(ws_out.cell(row=7, column=3).value, "Plasmid")
            finally:
                out_wb.close()

if __name__ == '__main__':
    unittest.main()
