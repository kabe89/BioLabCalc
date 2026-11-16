"""Unit tests for TEA (The Elm Architecture) State Engine & Interactive Workbench (v0.4.0)."""

import os
import tempfile
import unittest
from dataclasses import FrozenInstanceError

from biolabcalc.interactive_plasmid import (
    get_plasmid_workbench_html,
    render_plasmid_map_svg,
    save_plasmid_workbench_html,
)
from biolabcalc.plasmid import STANDARD_PLASMID_CATALOG
from biolabcalc.tea_runtime import (
    BioLabModel,
    Cmd,
    InsertGeneMsg,
    LoadPlasmidMsg,
    RedoMsg,
    RunDigestMsg,
    SelectEnzymesMsg,
    SetViewModeMsg,
    TEAStore,
    UndoMsg,
    update,
    view,
)


class TestTEARuntime(unittest.TestCase):
    """Test suite for TEA immutability, update dispatch, undo/redo time travel, and workbench."""

    def test_model_immutability(self) -> None:
        """BioLabModel must be an immutable frozen dataclass."""
        model = BioLabModel()
        with self.assertRaises(FrozenInstanceError):
            model.status_message = "Mutated"  # type: ignore[misc]

    def test_load_plasmid_msg(self) -> None:
        """LoadPlasmidMsg loads plasmid from catalog and returns updated model with Cmd."""
        model = BioLabModel()
        new_model, cmd = update(LoadPlasmidMsg("pUC19"), model)
        self.assertIsNotNone(new_model.current_plasmid)
        self.assertEqual(new_model.current_plasmid.name, "pUC19")
        self.assertIn("Loaded plasmid 'pUC19'", new_model.status_message)
        self.assertEqual(cmd.action, "plasmid_loaded")
        self.assertEqual(cmd.payload.get("name"), "pUC19")

    def test_select_enzymes_msg(self) -> None:
        """SelectEnzymesMsg sets tuple of active restriction enzymes."""
        model = BioLabModel()
        new_model, cmd = update(SelectEnzymesMsg(("EcoRI", "HindIII")), model)
        self.assertEqual(new_model.selected_enzymes, ("EcoRI", "HindIII"))
        self.assertEqual(cmd.action, "enzymes_selected")

    def test_run_digest_msg(self) -> None:
        """RunDigestMsg simulates in-silico restriction digestion on loaded plasmid."""
        store = TEAStore()
        store.dispatch(LoadPlasmidMsg("pUC19"))
        store.dispatch(SelectEnzymesMsg(("EcoRI", "HindIII")))
        new_model, cmd = store.dispatch(RunDigestMsg(dna_mass_ug=1.0))
        self.assertIsNotNone(new_model.digest_prediction)
        self.assertEqual(new_model.digest_prediction.fragment_count, 2)
        self.assertEqual(cmd.action, "digest_completed")

    def test_insert_gene_msg(self) -> None:
        """InsertGeneMsg performs directional cloning assembly into vector."""
        store = TEAStore()
        store.dispatch(LoadPlasmidMsg("pET-28a(+)"))
        egfp = (
            "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTAAACGGCCACAAGTTCAGCGTGTCCGGC"
            "GAGGGCGAGGGCGATGCCACCTACGGCAAGCTGACCCTGAAGTTCATCTGCACCACCGGCAAGCTGCCCGTGCCCTGGCCCACCCTCGTGACCACC"
            "CTGACCTACGGCGTGCAGTGCTTCAGCCGCTACCCCGACCACATGAAGCAGCACGACTTCTTCAAGTCCGCCATGCCCGAAGGCTACGTCCAGGAG"
            "CGCACCATCTTCTTCAAGGACGACGGCAACTACAAGACCCGCGCCGAGGTGAAGTTCGAGGGCGACACCCTGGTGAACCGCATCGAGCTGAAGGGC"
            "ATCGACTTCAAGGAGGACGGCAACATCCTGGGGCACAAGCTGGAGTACAACTACAACAGCCACAACGTCTATATCATGGCCGACAAGCAGAAGAAC"
            "GGCATCAAGGTGAACTTCAAGATCCGCCACAACATCGAGGACGGCAGCGTGCAGCTCGCCGACCACTACCAGCAGAACACCCCCATCGGCGACGGC"
            "CCCGTGCTGCTGCCCGACAACCACTACCTGAGCACCCAGTCCGCCCTGAGCAAAGACCCCAACGAGAAGCGCGATCACATGGTCCTGCTGGAGTTC"
            "GTGACCGCCGCCGGGATCACTCTCGGCATGGACGAGCTGTACAAGTAA"
        )
        new_model, cmd = store.dispatch(
            InsertGeneMsg(gene_name="EGFP", sequence=egfp, mode="restriction_ligation", enzyme_5="BamHI", enzyme_3="XhoI")
        )
        self.assertIsNotNone(new_model.engineering_result)
        self.assertEqual(new_model.engineering_result.target_gene_name, "EGFP")
        self.assertTrue(new_model.engineering_result.in_frame)
        self.assertEqual(cmd.action, "gene_inserted")

    def test_undo_and_redo_time_travel(self) -> None:
        """UndoMsg and RedoMsg traverse state history without mutation."""
        store = TEAStore()
        # Step 0: Initial empty state
        self.assertIsNone(store.model.current_plasmid)

        # Step 1: Load pUC19
        store.dispatch(LoadPlasmidMsg("pUC19"))
        self.assertEqual(store.model.current_plasmid.name, "pUC19")

        # Step 2: Select enzymes
        store.dispatch(SelectEnzymesMsg(("EcoRI", "HindIII")))
        self.assertEqual(store.model.selected_enzymes, ("EcoRI", "HindIII"))

        # Step 3: Run digest
        store.dispatch(RunDigestMsg())
        self.assertIsNotNone(store.model.digest_prediction)

        # Undo Step 3 (revert digest)
        store.dispatch(UndoMsg())
        self.assertIsNone(store.model.digest_prediction)
        self.assertEqual(store.model.selected_enzymes, ("EcoRI", "HindIII"))

        # Undo Step 2 (revert enzyme selection)
        store.dispatch(UndoMsg())
        self.assertEqual(store.model.selected_enzymes, ())
        self.assertEqual(store.model.current_plasmid.name, "pUC19")

        # Undo Step 1 (revert load)
        store.dispatch(UndoMsg())
        self.assertIsNone(store.model.current_plasmid)

        # Redo Step 1 (re-apply load)
        store.dispatch(RedoMsg())
        self.assertEqual(store.model.current_plasmid.name, "pUC19")

        # Redo Step 2 (re-apply enzyme selection)
        store.dispatch(RedoMsg())
        self.assertEqual(store.model.selected_enzymes, ("EcoRI", "HindIII"))

        # Redo Step 3 (re-apply digest)
        store.dispatch(RedoMsg())
        self.assertIsNotNone(store.model.digest_prediction)

    def test_view_markdown_generation(self) -> None:
        """View function renders comprehensive Markdown summary of model state."""
        store = TEAStore()
        store.dispatch(LoadPlasmidMsg("pUC19"))
        store.dispatch(SelectEnzymesMsg(("EcoRI", "BamHI")))
        store.dispatch(RunDigestMsg())
        md = store.view(mode="markdown")
        self.assertIn("# BioLabCalc Plasmid Engineering & Gel Workbench", md)
        self.assertIn("pUC19", md)
        self.assertIn("Restriction Digest Prediction", md)
        self.assertIn("EcoRI", md)

    def test_render_plasmid_map_svg(self) -> None:
        """Render circular plasmid map SVG with features and restriction cuts."""
        puc19 = STANDARD_PLASMID_CATALOG["pUC19"]
        svg = render_plasmid_map_svg(puc19)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertIn("pUC19", svg)
        self.assertIn("2,686 bp", svg)
        self.assertIn("AmpR", svg)

    def test_get_plasmid_workbench_html(self) -> None:
        """Workbench HTML generator produces responsive single-page web application."""
        app_html = get_plasmid_workbench_html()
        self.assertIn("<!DOCTYPE html>", app_html)
        self.assertIn("BioLabCalc Interactive Plasmid & Gel Workbench", app_html)
        self.assertIn("canvas id=\"gelCanvas\"", app_html)
        self.assertIn("pET-28a(+)", app_html)

    def test_save_plasmid_workbench_html(self) -> None:
        """Workbench HTML saver writes file to disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "workbench.html")
            saved_path = save_plasmid_workbench_html(out_file)
            self.assertTrue(os.path.exists(saved_path))
            with open(saved_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("BioLabCalc", content)


if __name__ == "__main__":
    unittest.main()
