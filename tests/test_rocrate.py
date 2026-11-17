"""
Tests for RO-Crate (.eln) Export and Import Services
"""

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.eln.services.document_vault_service import (
    DocumentVaultService,
    export_eln_rocrate,
    import_eln_rocrate,
)


class TestROCrate(unittest.TestCase):
    def test_export_and_import_rocrate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            vault = DocumentVaultService(base_dir=tmp_path / "cas_vault")

            # Ingest a sample document
            doc = vault.ingest_document(
                data=b"Sample Protocol Content for RO-Crate",
                title="Ni-NTA Purification SOP",
                category="Protocol",
                filename="sop_ni_nta.txt",
                tags=["purification", "his-tag"],
            )

            archive_path = str(tmp_path / "campaign_export.eln")

            # Test export (monkeypatch default vault lookup or pass base_dir)
            import biolabcalc.eln.services.document_vault_service as dvs
            orig_get_vault = dvs.get_document_vault_service
            dvs.get_document_vault_service = lambda: vault

            try:
                res_path = export_eln_rocrate("EXP-BIO-99", archive_path)
                self.assertTrue(Path(res_path).exists())

                # Validate zip contents
                with zipfile.ZipFile(res_path, "r") as zf:
                    names = zf.namelist()
                    self.assertIn("ro-crate-metadata.json", names)
                    self.assertIn("campaign.json", names)
                    self.assertIn("files/sop_ni_nta.txt", names)

                    # Inspect ro-crate-metadata.json
                    meta = json.loads(zf.read("ro-crate-metadata.json").decode("utf-8"))
                    self.assertEqual(meta.get("@context"), "https://w3id.org/ro/crate/1.1/context")
                    self.assertIn("@graph", meta)
                    graph = meta["@graph"]
                    root_dataset = next(item for item in graph if item["@id"] == "./")
                    self.assertIn("BioLabCalc Campaign Archive: EXP-BIO-99", root_dataset["name"])

                # Test import into clean vault
                import_vault = DocumentVaultService(base_dir=tmp_path / "import_cas")
                dvs.get_document_vault_service = lambda: import_vault

                import_res = import_eln_rocrate(res_path)
                self.assertEqual(import_res["status"], "imported")
                self.assertEqual(import_res["campaign_id"], "EXP-BIO-99")
                self.assertEqual(import_res["files_imported_count"], 1)

            finally:
                dvs.get_document_vault_service = orig_get_vault

    def test_invalid_rocrate_missing_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_zip = Path(tmpdir) / "corrupt.eln"
            with zipfile.ZipFile(bad_zip, "w") as zf:
                zf.writestr("some_file.txt", b"hello world")

            with self.assertRaises(ValueError) as ctx:
                import_eln_rocrate(str(bad_zip))
            self.assertIn("ro-crate-metadata.json", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
