import unittest
import os
import tempfile
from biolabcalc.protocols import (
    PROTOCOL_CATALOG,
    LabProtocol,
    list_protocols,
    get_protocol,
    format_protocol_markdown,
    export_all_protocols_markdown,
)

class TestProtocols(unittest.TestCase):
    def test_catalog_size(self):
        self.assertGreaterEqual(len(PROTOCOL_CATALOG), 10)

    def test_list_protocols_all(self):
        all_p = list_protocols()
        self.assertEqual(len(all_p), len(PROTOCOL_CATALOG))

    def test_list_protocols_by_category(self):
        rna_p = list_protocols("RNA")
        self.assertGreaterEqual(len(rna_p), 1)
        self.assertTrue(all("RNA" in p.category for p in rna_p))

    def test_get_protocol_exact(self):
        p = get_protocol("ntp_neutralization")
        self.assertIsInstance(p, LabProtocol)
        self.assertEqual(p.protocol_id, "ntp_neutralization")
        self.assertIn("NTP", p.title)

    def test_get_protocol_fuzzy(self):
        p = get_protocol("ivt")
        self.assertEqual(p.protocol_id, "t7_ivt_transcription")

    def test_get_protocol_not_found(self):
        with self.assertRaises(KeyError):
            get_protocol("completely_non_existent_protocol_xyz")

    def test_format_markdown(self):
        p = get_protocol("ecoli_transformation")
        md = format_protocol_markdown(p)
        self.assertIn("# Heat-Shock Transformation", md)
        self.assertIn("Reagents & Stock Solutions", md)
        self.assertIn("Step-by-Step Bench Protocol", md)
        self.assertIn("Troubleshooting & Failure Analysis", md)

    def test_export_markdown(self):
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            export_all_protocols_markdown(tmp_path)
            self.assertTrue(os.path.exists(tmp_path))
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("BioLabCalc Standard Laboratory Protocols Compendium", content)
            self.assertIn("Table of Contents", content)
            for p_id in PROTOCOL_CATALOG.keys():
                self.assertIn(f"name=\"{p_id}\"", content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == '__main__':
    unittest.main()
