import unittest
import os
import tempfile

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
        out_path = os.path.join(tempfile.gettempdir(), "test_gen_template.xlsx")
        res_path = generate_lab_notebook_template(out_path)
        self.assertTrue(os.path.exists(res_path))
        wb = openpyxl.load_workbook(res_path)
        self.assertIn("IVT_Stoichiometry", wb.sheetnames)
        self.assertIn("PCR_Optimization", wb.sheetnames)
        self.assertIn("Protein_Quantification", wb.sheetnames)
        self.assertIn("Primer_Design_Log", wb.sheetnames)

        # Issue 7 verification: Master mix formulas
        ws_pcr = wb["PCR_Optimization"]
        self.assertEqual(ws_pcr.cell(row=8, column=5).value, "=D8*$B$5*$D$5")
        self.assertEqual(ws_pcr.cell(row=9, column=5).value, "=D9*$B$5*$D$5")
        self.assertEqual(ws_pcr.cell(row=13, column=5).value, "=D13*$B$5*$D$5")

        # Issue 8 verification: Standard curve regression formula
        ws_prot = wb["Protein_Quantification"]
        self.assertEqual(ws_prot.cell(row=20, column=5).value, "=(D20-INTERCEPT(B20:B25, A20:A25))/SLOPE(B20:B25, A20:A25)")

    def test_export_analysis(self):
        out_path = os.path.join(tempfile.gettempdir(), "test_export_analysis.xlsx")
        ivt = calculate_ivt_yield("GGGAAUGCAUGCAUGC", measured_yield_ug=25.0)
        pcr = calculate_pcr_kinetics(amplicon_len_bp=400, template_ng=5.0)
        export_analysis_to_excel(out_path, ivt_results=[ivt], pcr_results=[pcr])
        self.assertTrue(os.path.exists(out_path))
        wb = openpyxl.load_workbook(out_path)
        self.assertIn("IVT_Results", wb.sheetnames)
        self.assertIn("PCR_Results", wb.sheetnames)
        # Issue 14 verification: No dummy template sheets in export
        self.assertNotIn("Solution_Prep_NanoDrop", wb.sheetnames)
        self.assertNotIn("Fluorophore_Modifications", wb.sheetnames)
        self.assertNotIn("Ecoli_Growth_Optimization", wb.sheetnames)

    def test_batch_process_excel(self):
        in_path = os.path.join(tempfile.gettempdir(), "test_unit_batch_in.xlsx")
        out_path = os.path.join(tempfile.gettempdir(), "test_unit_batch_out.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["ID", "Sequence", "Type"])
        ws.append(["Oligo_1", "ATGCCGTCCAGGCTGCTGGTC", "DNA"])
        ws.append(["RNA_1", "GGGAGACCCAAGCUGGCCUGUGUGUACAGCCGAAUG", "RNA"])
        wb.save(in_path)

        res = batch_process_excel(in_path, out_path)
        self.assertTrue(os.path.exists(res))
        out_wb = openpyxl.load_workbook(res)
        self.assertIn("Batch_Analysis_Results", out_wb.sheetnames)
        ws_out = out_wb["Batch_Analysis_Results"]
        self.assertEqual(ws_out.cell(row=4, column=2).value, "Oligo_1")
        self.assertGreater(ws_out.cell(row=4, column=6).value, 5000)

if __name__ == '__main__':
    unittest.main()
