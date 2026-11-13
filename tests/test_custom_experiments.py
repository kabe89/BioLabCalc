"""
Module: tests.test_custom_experiments
Component: Unit and Integration Test Suite for No-Code Experiment Customization Architecture
Architectural Role: Comprehensive verification of dynamic custom experiment schemas, pre-built templates,
safe AST mathematical formula evaluator (with security injection containment), form data validation,
topological formula dependency resolution, entry persistence, and REST API endpoints.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from typing import Any, Dict

# Sys.path bootstrap so test suite executes standalone
_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.eln.api.app import ASGIApplication, TestClient
from biolabcalc.eln.api.routes.custom_experiments import router as custom_experiments_router
from biolabcalc.eln.schema.custom_experiments import (
    CustomExperimentEntry,
    CustomExperimentTemplate,
    FieldDefinition,
    SectionDefinition,
    get_prebuilt_templates,
)
from biolabcalc.eln.services.custom_experiment_service import (
    SafeASTFormulaEvaluator,
    get_custom_experiment_service,
)


class TestPrebuiltTemplates(unittest.TestCase):
    """
    Test suite verifying pre-built experiment templates, their metadata, and serialization.
    """

    def test_prebuilt_templates_catalog(self) -> None:
        """Verify all 6 pre-built templates exist and have valid structure."""
        templates = get_prebuilt_templates()
        self.assertEqual(len(templates), 6)

        expected_ids = {
            "tpl_general_notebook",
            "tpl_molecular_cloning",
            "tpl_protein_expression",
            "tpl_cell_culture",
            "tpl_electrophysiology",
            "tpl_blank_canvas",
        }
        found_ids = {t.id for t in templates}
        self.assertEqual(found_ids, expected_ids)

        for t in templates:
            self.assertTrue(len(t.name) > 0)
            self.assertTrue(len(t.category) > 0)
            self.assertTrue(len(t.description) > 0)
            self.assertTrue(len(t.sections) > 0)
            for s in t.sections:
                self.assertTrue(len(s.id) > 0)
                self.assertTrue(len(s.title) > 0)
                self.assertTrue(isinstance(s.fields, list))

    def test_template_dict_and_yaml_serialization(self) -> None:
        """Verify CustomExperimentTemplate serializes to/from dict and YAML seamlessly."""
        templates = get_prebuilt_templates()
        protein_tpl = next(t for t in templates if t.id == "tpl_protein_expression")

        # 1. to_dict and from_dict
        d = protein_tpl.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["id"], "tpl_protein_expression")
        self.assertIn("sections", d)

        reconstructed_from_dict = CustomExperimentTemplate.from_dict(d)
        self.assertEqual(reconstructed_from_dict.id, protein_tpl.id)
        self.assertEqual(len(reconstructed_from_dict.sections), len(protein_tpl.sections))

        # 2. to_yaml and from_yaml
        yaml_str = protein_tpl.to_yaml()
        self.assertIsInstance(yaml_str, str)
        self.assertIn("tpl_protein_expression", yaml_str)

        reconstructed_from_yaml = CustomExperimentTemplate.from_yaml(yaml_str)
        self.assertEqual(reconstructed_from_yaml.id, protein_tpl.id)
        self.assertEqual(reconstructed_from_yaml.name, protein_tpl.name)
        self.assertEqual(len(reconstructed_from_yaml.sections), len(protein_tpl.sections))

    def test_entry_dict_and_yaml_serialization(self) -> None:
        """Verify CustomExperimentEntry serializes to/from dict and YAML seamlessly."""
        entry = CustomExperimentEntry(
            id="ENTRY-TEST-001",
            template_id="tpl_general_notebook",
            campaign_id="CMP-001",
            title="Notebook Log Day 1",
            form_data={"objective": "Test PCR amplification", "reagents": "Q5 Master Mix"},
            calculated_values={"yield_pct": 88.5},
            status="completed",
            approval_status="approved",
            operator_id="test_researcher",
        )

        # 1. to_dict and from_dict
        d = entry.to_dict()
        self.assertEqual(d["id"], "ENTRY-TEST-001")
        self.assertEqual(d["calculated_values"]["yield_pct"], 88.5)

        rebuilt_entry = CustomExperimentEntry.from_dict(d)
        self.assertEqual(rebuilt_entry.id, entry.id)
        self.assertEqual(rebuilt_entry.operator_id, "test_researcher")

        # 2. to_yaml and from_yaml
        yaml_str = entry.to_yaml()
        self.assertIn("ENTRY-TEST-001", yaml_str)
        rebuilt_from_yaml = CustomExperimentEntry.from_yaml(yaml_str)
        self.assertEqual(rebuilt_from_yaml.id, entry.id)
        self.assertEqual(rebuilt_from_yaml.title, entry.title)


class TestASTFormulaEvaluator(unittest.TestCase):
    """
    Test suite verifying safe AST mathematical expression evaluation and injection blocking.
    """

    def setUp(self) -> None:
        self.service = get_custom_experiment_service()

    def test_basic_arithmetic(self) -> None:
        """Verify standard arithmetic operations and precedence."""
        ctx = {"a": 10, "b": 5, "c": 2}

        # Addition, subtraction, multiplication, division
        self.assertEqual(self.service.evaluate_formula("a + b", ctx), 15)
        self.assertEqual(self.service.evaluate_formula("a - b", ctx), 5)
        self.assertEqual(self.service.evaluate_formula("a * b", ctx), 50)
        self.assertEqual(self.service.evaluate_formula("a / b", ctx), 2.0)

        # Modulo, floor division, power
        self.assertEqual(self.service.evaluate_formula("a % 3", ctx), 1)
        self.assertEqual(self.service.evaluate_formula("a // 3", ctx), 3)
        self.assertEqual(self.service.evaluate_formula("b ** c", ctx), 25)

        # Operator precedence & parentheses
        self.assertEqual(self.service.evaluate_formula("a + b * c", ctx), 20)
        self.assertEqual(self.service.evaluate_formula("(a + b) * c", ctx), 30)
        self.assertEqual(self.service.evaluate_formula("((a - b) * 4) / c", ctx), 10.0)

        # Unary operations
        self.assertEqual(self.service.evaluate_formula("-a", ctx), -10)
        self.assertEqual(self.service.evaluate_formula("+b", ctx), 5)

    def test_math_functions(self) -> None:
        """Verify whitelisted mathematical functions."""
        ctx = {"x": 16.0, "y": 3.14159, "neg": -42.7, "val": 100.0}

        self.assertEqual(self.service.evaluate_formula("sqrt(x)", ctx), 4.0)
        self.assertEqual(self.service.evaluate_formula("abs(neg)", ctx), 42.7)
        self.assertEqual(self.service.evaluate_formula("round(y, 2)", ctx), 3.14)
        self.assertEqual(self.service.evaluate_formula("min(x, 10, 25)", ctx), 10)
        self.assertEqual(self.service.evaluate_formula("max(x, 10, 25)", ctx), 25)
        self.assertAlmostEqual(self.service.evaluate_formula("log(exp(2))", ctx), 2.0)
        self.assertEqual(self.service.evaluate_formula("log10(val)", ctx), 2.0)
        self.assertEqual(self.service.evaluate_formula("log2(x)", ctx), 4.0)
        self.assertEqual(self.service.evaluate_formula("ceil(3.2)", ctx), 4)
        self.assertEqual(self.service.evaluate_formula("floor(3.8)", ctx), 3)
        self.assertEqual(self.service.evaluate_formula("pow(2, 3)", ctx), 8)

    def test_mathematical_constants(self) -> None:
        """Verify mathematical constants pi and e are accessible."""
        res_pi = self.service.evaluate_formula("round(pi, 4)", {})
        self.assertEqual(res_pi, 3.1416)

        res_e = self.service.evaluate_formula("round(e, 4)", {})
        self.assertEqual(res_e, 2.7183)

    def test_division_by_zero(self) -> None:
        """Verify division or modulo by zero raises ZeroDivisionError."""
        with self.assertRaises(ZeroDivisionError):
            self.service.evaluate_formula("10 / 0", {})

        with self.assertRaises(ZeroDivisionError):
            self.service.evaluate_formula("10 // 0", {})

        with self.assertRaises(ZeroDivisionError):
            self.service.evaluate_formula("10 % 0", {})

    def test_variable_missing(self) -> None:
        """Verify referencing undefined variables raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            self.service.evaluate_formula("a + unknown_var", {"a": 10})
        self.assertIn("unknown_var", str(cm.exception))

    def test_security_injection_blocked(self) -> None:
        """
        Verify security containment: all dangerous nodes, modules, builtins,
        eval, exec, attribute traversal, and comprehensions are strictly blocked.
        """
        attacks = [
            "__import__('os').system('ls')",
            "__import__('sys').exit(0)",
            "open('/etc/passwd', 'r')",
            "eval('2 + 2')",
            "exec('x = 1')",
            "getattr(math, 'pi')",
            "globals()",
            "locals()",
            "vars()",
            "x.__class__",
            "x.__class__.__bases__[0].__subclasses__()",
            "x.__globals__",
            "[x for x in (1, 2, 3)]",
            "{x: x for x in (1, 2)}",
            "{1, 2, 3}",
            "lambda x: x + 1",
            "x[0]",
            "x['key']",
            "a = 5",
            "x.y",
            "_private_var",
            "__file__",
        ]

        for attack in attacks:
            with self.subTest(attack=attack):
                with self.assertRaises((ValueError, SyntaxError)):
                    self.service.evaluate_formula(attack, {"x": [1, 2], "_private_var": 10})

    def test_power_dos_protection(self) -> None:
        """Verify excessively high power exponents are rejected to prevent Denial-of-Service."""
        with self.assertRaises(ValueError) as cm:
            self.service.evaluate_formula("10 ** 100000", {})
        self.assertIn("safe evaluation threshold", str(cm.exception))


class TestFormValidation(unittest.TestCase):
    """
    Test suite verifying strict validation of custom experiment entry data.
    """

    def setUp(self) -> None:
        self.service = get_custom_experiment_service()
        self.template = self.service.get_template("tpl_protein_expression")
        self.assertIsNotNone(self.template)

    def test_valid_data_passes(self) -> None:
        """Verify well-formed data passes validation without error."""
        valid_data = {
            "target_protein": "Recombinant MBP",
            "expression_host": "E. coli BL21(DE3)",
            "culture_volume_l": 1.0,
            "induction_od600": 0.6,
            "iptg_concentration_mm": 0.4,
            "harvest_pellet_mass_g": 8.2,
            "lysis_buffer_volume_ml": 40.0,
            "column_type": "HisTrap FF 5mL",
            "elution_volume_ml": 5.0,
            "absorbance_a280": 0.85,
            "extinction_coefficient": 1.45,
        }
        # Should not raise
        self.service.validate_entry_data(self.template, valid_data)

    def test_missing_required_field_raises(self) -> None:
        """Verify omitting a required field raises ValueError."""
        invalid_data = {
            # "target_protein" missing!
            "expression_host": "E. coli BL21(DE3)",
            "culture_volume_l": 1.0,
            "induction_od600": 0.6,
            "harvest_pellet_mass_g": 8.2,
            "lysis_buffer_volume_ml": 40.0,
            "column_type": "HisTrap FF 5mL",
            "elution_volume_ml": 5.0,
            "absorbance_a280": 0.85,
            "extinction_coefficient": 1.45,
        }
        with self.assertRaises(ValueError) as cm:
            self.service.validate_entry_data(self.template, invalid_data)
        self.assertIn("target_protein", str(cm.exception))

    def test_non_numeric_value_for_number_field_raises(self) -> None:
        """Verify passing non-numeric strings to number fields raises ValueError."""
        invalid_data = {
            "target_protein": "MBP",
            "expression_host": "E. coli BL21(DE3)",
            "culture_volume_l": "one_liter",  # Not a valid float
            "induction_od600": 0.6,
            "harvest_pellet_mass_g": 8.2,
            "lysis_buffer_volume_ml": 40.0,
            "column_type": "HisTrap FF 5mL",
            "elution_volume_ml": 5.0,
            "absorbance_a280": 0.85,
            "extinction_coefficient": 1.45,
        }
        with self.assertRaises(ValueError) as cm:
            self.service.validate_entry_data(self.template, invalid_data)
        self.assertIn("must be a number", str(cm.exception))

    def test_numeric_min_and_max_bounds(self) -> None:
        """Verify numeric value bounds (min_value, max_value) are enforced."""
        # Culture volume min_value is 0.01
        below_min = {
            "target_protein": "MBP",
            "expression_host": "E. coli BL21(DE3)",
            "culture_volume_l": 0.001,  # Below min 0.01
            "induction_od600": 0.6,
            "harvest_pellet_mass_g": 8.2,
            "lysis_buffer_volume_ml": 40.0,
            "column_type": "HisTrap FF 5mL",
            "elution_volume_ml": 5.0,
            "absorbance_a280": 0.85,
            "extinction_coefficient": 1.45,
        }
        with self.assertRaises(ValueError) as cm:
            self.service.validate_entry_data(self.template, below_min)
        self.assertIn("below minimum allowed", str(cm.exception))

        # Induction OD600 max_value is 30.0
        above_max = {
            "target_protein": "MBP",
            "expression_host": "E. coli BL21(DE3)",
            "culture_volume_l": 1.0,
            "induction_od600": 35.0,  # Above max 30.0
            "harvest_pellet_mass_g": 8.2,
            "lysis_buffer_volume_ml": 40.0,
            "column_type": "HisTrap FF 5mL",
            "elution_volume_ml": 5.0,
            "absorbance_a280": 0.85,
            "extinction_coefficient": 1.45,
        }
        with self.assertRaises(ValueError) as cm:
            self.service.validate_entry_data(self.template, above_max)
        self.assertIn("exceeds maximum allowed", str(cm.exception))

    def test_select_field_allowed_options(self) -> None:
        """Verify select fields only accept options defined in the template."""
        invalid_host = {
            "target_protein": "MBP",
            "expression_host": "Unauthorized Host Strain X",
            "culture_volume_l": 1.0,
            "induction_od600": 0.6,
            "harvest_pellet_mass_g": 8.2,
            "lysis_buffer_volume_ml": 40.0,
            "column_type": "HisTrap FF 5mL",
            "elution_volume_ml": 5.0,
            "absorbance_a280": 0.85,
            "extinction_coefficient": 1.45,
        }
        with self.assertRaises(ValueError) as cm:
            self.service.validate_entry_data(self.template, invalid_host)
        self.assertIn("not in allowed options", str(cm.exception))

    def test_date_and_table_validation(self) -> None:
        """Verify date format check and table row structure checks."""
        gen_tpl = self.service.get_template("tpl_general_notebook")
        blank_tpl = self.service.get_template("tpl_blank_canvas")

        # Invalid date format
        with self.assertRaises(ValueError) as cm:
            self.service.validate_entry_data(
                gen_tpl,
                {
                    "experiment_date": "yesterday",
                    "objective": "Test",
                    "protocol_steps": "Run gel",
                    "results_summary": "Passed",
                },
            )
        self.assertIn("valid date formatted as YYYY-MM-DD", str(cm.exception))

        # Valid date
        self.service.validate_entry_data(
            gen_tpl,
            {
                "experiment_date": "2026-11-13",
                "objective": "Test",
                "protocol_steps": "Run gel",
                "results_summary": "Passed",
            },
        )

        # Invalid table format (not a list)
        with self.assertRaises(ValueError) as cm:
            self.service.validate_entry_data(
                blank_tpl,
                {"experiment_title": "Custom Test", "measurements": "not-a-list"},
            )
        self.assertIn("must be a list", str(cm.exception))


class TestFullEntryCreationWithFormulas(unittest.TestCase):
    """
    Test suite verifying end-to-end entry creation with dynamic formula evaluation across pre-built templates.
    """

    def setUp(self) -> None:
        self.service = get_custom_experiment_service()
        self.service.clear_for_testing()

    def test_protein_expression_entry_calculations(self) -> None:
        """Verify protein expression formulas: concentration, total yield, and specific yield."""
        form_data = {
            "target_protein": "T7 RNA Polymerase",
            "expression_host": "E. coli BL21(DE3)",
            "culture_volume_l": 4.0,
            "induction_od600": 0.8,
            "harvest_pellet_mass_g": 32.0,
            "lysis_buffer_volume_ml": 160.0,
            "column_type": "HisTrap FF 5mL",
            "elution_volume_ml": 20.0,
            "absorbance_a280": 2.5,
            "extinction_coefficient": 1.25,
        }
        entry = self.service.create_entry(
            template_id="tpl_protein_expression",
            campaign_id="CMP-PROT-01",
            title="T7 RNAP Purification Run 1",
            form_data=form_data,
            operator_id="op_specialist_01",
        )

        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.template_id, "tpl_protein_expression")
        self.assertEqual(entry.campaign_id, "CMP-PROT-01")

        # Check calculated values:
        # 1. concentration = 2.5 / 1.25 = 2.0 mg/mL
        self.assertEqual(entry.calculated_values["protein_concentration_mg_ml"], 2.0)
        # 2. total yield = 2.0 * 20.0 = 40.0 mg
        self.assertEqual(entry.calculated_values["total_protein_mg"], 40.0)
        # 3. specific yield = 40.0 / 4.0 = 10.0 mg/L
        self.assertEqual(entry.calculated_values["specific_yield_mg_per_l"], 10.0)

    def test_molecular_cloning_entry_calculations(self) -> None:
        """Verify molecular cloning stoichiometric insert mass calculation."""
        form_data = {
            "vector_name": "pET-28a(+)",
            "vector_size_bp": 5369.0,
            "insert_name": "gfp_mut2",
            "insert_size_bp": 720.0,
            "assembly_method": "Gibson Assembly",
            "vector_mass_ng": 100.0,
            "molar_ratio": 3.0,
            "reaction_volume_ul": 20.0,
            "incubation_temp_c": 50.0,
            "incubation_time_min": 60.0,
            "competent_cells": "DH5alpha",
            "selection_antibiotic": "Kanamycin (50 ug/mL)",
        }
        entry = self.service.create_entry(
            template_id="tpl_molecular_cloning",
            campaign_id="CMP-CLON-01",
            title="pET28a-GFP Gibson Assembly",
            form_data=form_data,
            operator_id="cloning_tech",
        )

        # Expected required insert: (100 * (720 / 5369)) * 3.0 = 40.230955...
        expected_insert_ng = (100.0 * (720.0 / 5369.0)) * 3.0
        self.assertAlmostEqual(
            entry.calculated_values["required_insert_ng"], expected_insert_ng, places=4
        )

    def test_cell_culture_viability_calculations(self) -> None:
        """Verify cell culture viability percentage and density calculations."""
        form_data = {
            "cell_line_name": "HEK293T",
            "passage_number": 12,
            "culture_vessel": "T-75 Flask",
            "medium_type": "DMEM + 10% FBS",
            "total_cells": 10000000.0,
            "viable_cells": 9600000.0,
            "total_volume_ml": 10.0,
        }
        entry = self.service.create_entry(
            template_id="tpl_cell_culture",
            campaign_id="CMP-CELL-01",
            title="HEK293T P12 Count",
            form_data=form_data,
        )

        # Viability = (9.6e6 / 1.0e7) * 100 = 96.0%
        self.assertEqual(entry.calculated_values["viability_percent"], 96.0)
        # Viable density = 9.6e6 / 10.0 = 960000 cells/mL
        self.assertEqual(entry.calculated_values["viable_cell_density"], 960000.0)

    def test_electrophysiology_current_density_calculations(self) -> None:
        """Verify patch-clamp current density (pA/pF) formula calculation."""
        form_data = {
            "cell_id": "CHO-Kv1.3-004",
            "recording_mode": "Whole-cell",
            "internal_solution": "K-Gluconate Internal",
            "external_solution": "Standard Ringer Bath",
            "pipette_resistance_mohm": 3.5,
            "seal_resistance_gohm": 2.8,
            "cell_capacitance_pf": 20.0,
            "holding_potential_mv": -70.0,
            "peak_inward_current_pa": -1200.0,
        }
        entry = self.service.create_entry(
            template_id="tpl_electrophysiology",
            campaign_id="CMP-EPHYS-01",
            title="Kv1.3 Outward Current Recording",
            form_data=form_data,
        )

        # Density = abs(-1200) / 20 = 60.0 pA/pF
        self.assertEqual(entry.calculated_values["current_density_pa_pf"], 60.0)

    def test_chained_and_cyclic_dependency_resolution(self) -> None:
        """Verify multi-level formula dependencies and detection of cyclic dependencies."""
        # 1. Multi-level chained template
        chained_template = CustomExperimentTemplate(
            id="tpl_chained_test",
            name="Chained Formula Test",
            category="Test",
            description="Tests multi-step topological evaluation",
            sections=[
                SectionDefinition(
                    id="sec_math",
                    title="Math Fields",
                    fields=[
                        FieldDefinition(id="base_val", label="Base", type="number", required=True),
                        FieldDefinition(id="step_1", label="Step 1", type="formula", formula="base_val * 2"),
                        FieldDefinition(id="step_2", label="Step 2", type="formula", formula="step_1 + 10"),
                        FieldDefinition(id="step_3", label="Step 3", type="formula", formula="step_2 ** 2"),
                    ],
                )
            ],
        )
        self.service.register_template(chained_template)
        computed = self.service.compute_entry_values(chained_template, {"base_val": 5.0})
        self.assertEqual(computed["step_1"], 10.0)
        self.assertEqual(computed["step_2"], 20.0)
        self.assertEqual(computed["step_3"], 400.0)

        # 2. Cyclic dependency template
        cyclic_template = CustomExperimentTemplate(
            id="tpl_cyclic_test",
            name="Cyclic Formula Test",
            category="Test",
            description="Tests cycle detection",
            sections=[
                SectionDefinition(
                    id="sec_cycle",
                    title="Cyclic Fields",
                    fields=[
                        FieldDefinition(id="field_a", label="A", type="formula", formula="field_b + 1"),
                        FieldDefinition(id="field_b", label="B", type="formula", formula="field_a * 2"),
                    ],
                )
            ],
        )
        self.service.register_template(cyclic_template)
        with self.assertRaises(ValueError) as cm:
            self.service.compute_entry_values(cyclic_template, {})
        self.assertIn("Cyclic or unresolved dependency", str(cm.exception))


class TestCustomExperimentAPI(unittest.TestCase):
    """
    Test suite verifying REST API endpoints for templates and custom entries.
    """

    def setUp(self) -> None:
        self.service = get_custom_experiment_service()
        self.service.clear_for_testing()

        # Mount router onto standalone ASGI application for testing
        self.app = ASGIApplication()
        self.app.router.include_router(custom_experiments_router)
        self.client = TestClient(self.app)

    def test_list_and_filter_templates(self) -> None:
        """Verify GET /api/v1/custom-experiments/templates and category filtering."""
        # 1. List all
        resp = self.client.get("/api/v1/custom-experiments/templates")
        self.assertEqual(resp["status_code"], 200)
        self.assertEqual(resp["json"]["status"], "success")
        self.assertGreaterEqual(resp["json"]["count"], 6)

        # 2. Filter by category
        cat_resp = self.client.get("/api/v1/custom-experiments/templates?category=Electrophysiology")
        self.assertEqual(cat_resp["status_code"], 200)
        self.assertEqual(cat_resp["json"]["count"], 1)
        self.assertEqual(cat_resp["json"]["templates"][0]["id"], "tpl_electrophysiology")

    def test_get_template_by_id(self) -> None:
        """Verify GET /api/v1/custom-experiments/templates/{template_id}."""
        # 1. Success
        resp = self.client.get("/api/v1/custom-experiments/templates/tpl_molecular_cloning")
        self.assertEqual(resp["status_code"], 200)
        self.assertEqual(resp["json"]["template"]["name"], "Molecular Cloning & Assembly")

        # 2. 404 on missing
        not_found = self.client.get("/api/v1/custom-experiments/templates/non_existent_tpl_id")
        self.assertEqual(not_found["status_code"], 404)

    def test_register_new_template(self) -> None:
        """Verify POST /api/v1/custom-experiments/templates."""
        new_tpl_payload = {
            "id": "tpl_qpcr_assay",
            "name": "RT-qPCR Relative Expression Assay",
            "category": "Molecular Biology",
            "description": "2^(-ddCt) fold-change calculation for gene expression analysis.",
            "version": "1.0.0",
            "sections": [
                {
                    "id": "ct_data",
                    "title": "Cycle Thresholds (Ct)",
                    "fields": [
                        {"id": "gene_name", "label": "Target Gene", "type": "text", "required": True},
                        {"id": "ct_target", "label": "Target Gene Ct", "type": "number", "required": True},
                        {"id": "ct_reference", "label": "Reference Gene Ct", "type": "number", "required": True},
                        {
                            "id": "delta_ct",
                            "label": "Delta Ct",
                            "type": "formula",
                            "formula": "ct_target - ct_reference",
                        },
                    ],
                }
            ],
        }
        resp = self.client.post("/api/v1/custom-experiments/templates", payload=new_tpl_payload)
        self.assertEqual(resp["status_code"], 201)
        self.assertEqual(resp["json"]["template"]["id"], "tpl_qpcr_assay")

        # Verify it can be retrieved
        fetch_resp = self.client.get("/api/v1/custom-experiments/templates/tpl_qpcr_assay")
        self.assertEqual(fetch_resp["status_code"], 200)
        self.assertEqual(fetch_resp["json"]["template"]["name"], "RT-qPCR Relative Expression Assay")

    def test_create_and_retrieve_entry(self) -> None:
        """Verify POST and GET /api/v1/custom-experiments/entries."""
        payload = {
            "template_id": "tpl_protein_expression",
            "campaign_id": "CMP-API-01",
            "title": "API Purification Run",
            "form_data": {
                "target_protein": "Nanobody Nb12",
                "expression_host": "E. coli BL21(DE3)",
                "culture_volume_l": 2.5,
                "induction_od600": 0.75,
                "harvest_pellet_mass_g": 18.0,
                "lysis_buffer_volume_ml": 90.0,
                "column_type": "HisTrap HP 1mL",
                "elution_volume_ml": 8.0,
                "absorbance_a280": 1.5,
                "extinction_coefficient": 1.2,
            },
        }

        # 1. Create entry
        create_resp = self.client.post("/api/v1/custom-experiments/entries", payload=payload)
        self.assertEqual(create_resp["status_code"], 201)
        entry_data = create_resp["json"]["entry"]
        self.assertTrue(entry_data["id"].startswith("ENTRY-CUST-"))
        self.assertEqual(entry_data["title"], "API Purification Run")

        # Check calculated concentration: 1.5 / 1.2 = 1.25 mg/mL
        self.assertEqual(entry_data["calculated_values"]["protein_concentration_mg_ml"], 1.25)
        # Check total yield: 1.25 * 8.0 = 10.0 mg
        self.assertEqual(entry_data["calculated_values"]["total_protein_mg"], 10.0)
        # Check specific yield: 10.0 / 2.5 = 4.0 mg/L
        self.assertEqual(entry_data["calculated_values"]["specific_yield_mg_per_l"], 4.0)

        # 2. Retrieve entry
        entry_id = entry_data["id"]
        get_resp = self.client.get(f"/api/v1/custom-experiments/entries/{entry_id}")
        self.assertEqual(get_resp["status_code"], 200)
        self.assertEqual(get_resp["json"]["entry"]["id"], entry_id)
        self.assertEqual(get_resp["json"]["entry"]["calculated_values"]["total_protein_mg"], 10.0)

        # 3. 404 for missing entry
        missing_resp = self.client.get("/api/v1/custom-experiments/entries/NON_EXISTENT_ENTRY")
        self.assertEqual(missing_resp["status_code"], 404)

    def test_create_entry_validation_errors(self) -> None:
        """Verify API returns 400 when form validation fails or 404 when template is missing."""
        # 1. Missing template_id in payload
        res_no_tpl = self.client.post("/api/v1/custom-experiments/entries", payload={"title": "No template"})
        self.assertEqual(res_no_tpl["status_code"], 400)

        # 2. Non-existent template
        res_bad_tpl = self.client.post(
            "/api/v1/custom-experiments/entries",
            payload={"template_id": "non_existent", "form_data": {}},
        )
        self.assertEqual(res_bad_tpl["status_code"], 404)

        # 3. Missing required field in form_data
        res_missing_field = self.client.post(
            "/api/v1/custom-experiments/entries",
            payload={
                "template_id": "tpl_protein_expression",
                "form_data": {
                    # target_protein missing!
                    "expression_host": "E. coli BL21(DE3)",
                },
            },
        )
        self.assertEqual(res_missing_field["status_code"], 400)
        self.assertIn("target_protein", res_missing_field["json"]["message"])

    def test_template_export_and_import_api(self) -> None:
        """Verify template export and import REST routes."""
        # 1. Export as JSON
        export_json = self.client.get("/api/v1/custom-experiments/templates/tpl_general_notebook/export?fmt=json")
        self.assertEqual(export_json["status_code"], 200)
        self.assertIn("data", export_json["json"])

        # 2. Export as YAML
        export_yaml = self.client.get("/api/v1/custom-experiments/templates/tpl_general_notebook/export?fmt=yaml")
        self.assertEqual(export_yaml["status_code"], 200)
        self.assertEqual(export_yaml["json"]["format"], "yaml")

        # 3. Import
        imported_payload = {
            "payload": {
                "id": "tpl_imported_via_api",
                "name": "Imported Assay",
                "category": "Assays",
                "description": "Imported via test",
                "sections": [],
            }
        }
        import_resp = self.client.post("/api/v1/custom-experiments/templates/import", payload=imported_payload)
        self.assertEqual(import_resp["status_code"], 201)
        self.assertEqual(import_resp["json"]["template"]["id"], "tpl_imported_via_api")


if __name__ == "__main__":
    unittest.main()
