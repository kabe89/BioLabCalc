"""
Module: biolabcalc.eln.services.custom_experiment_service
Component: Custom No-Code Experiment Service & Safe AST Formula Evaluator
Architectural Role: Core service providing registration, validation, dependency-ordered formula
evaluation, safe AST mathematical expression parsing, entry persistence, and template import/export.
"""

from __future__ import annotations

import ast
import json
import math
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from ..schema.custom_experiments import (
    CustomExperimentEntry,
    CustomExperimentTemplate,
    FieldDefinition,
    SectionDefinition,
    get_prebuilt_templates,
)


class SafeASTFormulaEvaluator:
    """
    Sandboxed mathematical formula evaluator using Python's Abstract Syntax Tree (AST).

    Architectural Role: Executes arithmetic and scientific calculations defined in no-code
    experiment templates without ever invoking raw eval() or exec(). Restricts syntax to
    safe arithmetic operators, constants, variables, and an explicit whitelist of math functions.
    """

    SAFE_MATH_FUNCS: Dict[str, Callable[..., Any]] = {
        "min": min,
        "max": max,
        "round": round,
        "abs": abs,
        "log": math.log,
        "exp": math.exp,
        "sqrt": math.sqrt,
        "ceil": math.ceil,
        "floor": math.floor,
        "log10": math.log10,
        "log2": math.log2,
        "pow": pow,
    }

    SAFE_CONSTANTS: Dict[str, float] = {
        "pi": math.pi,
        "e": math.e,
    }

    ALLOWED_BIN_OPS = (
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
    )

    ALLOWED_UNARY_OPS = (
        ast.UAdd,
        ast.USub,
    )

    @classmethod
    def evaluate(cls, formula_str: str, context_dict: Optional[Dict[str, Any]] = None) -> Union[float, int]:
        """
        Safely parse and evaluate a mathematical formula string within a given context.

        Parameters:
            formula_str (str): Mathematical expression string (e.g. "(a * b) / c").
            context_dict (Optional[Dict[str, Any]]): Variable names and numeric values.

        Returns:
            Union[float, int]: Evaluated numerical result.

        Raises:
            ValueError: If expression contains disallowed nodes, forbidden functions,
                        missing variables, or math domain errors.
            ZeroDivisionError: If division by zero occurs.
        """
        if not formula_str or not formula_str.strip():
            raise ValueError("Formula string cannot be empty.")

        ctx = context_dict or {}

        try:
            tree = ast.parse(formula_str.strip(), mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Syntax error in formula '{formula_str}': {e}") from e

        return cls._eval_node(tree.body, ctx, formula_str)

    @classmethod
    def extract_variables(cls, formula_str: str) -> Set[str]:
        """
        Extract all variable identifiers referenced by a formula string.
        """
        if not formula_str or not formula_str.strip():
            return set()
        try:
            tree = ast.parse(formula_str.strip(), mode="eval")
        except SyntaxError:
            return set()

        variables: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                name = node.id
                if name not in cls.SAFE_MATH_FUNCS and name not in cls.SAFE_CONSTANTS:
                    variables.add(name)
        return variables

    @classmethod
    def _eval_node(cls, node: ast.AST, ctx: Dict[str, Any], formula_str: str) -> Union[float, int]:
        """Recursively evaluate an allowed AST node."""
        # 1. Constant numbers (Python 3.8+ ast.Constant)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return node.value
            raise ValueError(
                f"Disallowed constant type '{type(node.value).__name__}' in formula '{formula_str}'."
            )

        # Legacy Python AST Num fallback without triggering DeprecationWarning
        if type(node).__name__ == "Num":
            return getattr(node, "n")

        # 2. Binary operations (+, -, *, /, //, %, **)
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, cls.ALLOWED_BIN_OPS):
                raise ValueError(
                    f"Disallowed binary operator '{type(node.op).__name__}' in formula '{formula_str}'."
                )

            left = cls._eval_node(node.left, ctx, formula_str)
            right = cls._eval_node(node.right, ctx, formula_str)

            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, ast.Div):
                if right == 0:
                    raise ZeroDivisionError(f"Division by zero in formula '{formula_str}'.")
                return left / right
            elif isinstance(node.op, ast.FloorDiv):
                if right == 0:
                    raise ZeroDivisionError(f"Division by zero in formula '{formula_str}'.")
                return left // right
            elif isinstance(node.op, ast.Mod):
                if right == 0:
                    raise ZeroDivisionError(f"Modulo by zero in formula '{formula_str}'.")
                return left % right
            elif isinstance(node.op, ast.Pow):
                if abs(right) > 100:
                    raise ValueError(
                        f"Exponent {right} exceeds safe evaluation threshold in formula '{formula_str}'."
                    )
                return left ** right

        # 3. Unary operations (+x, -x)
        if isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, cls.ALLOWED_UNARY_OPS):
                raise ValueError(
                    f"Disallowed unary operator '{type(node.op).__name__}' in formula '{formula_str}'."
                )
            operand = cls._eval_node(node.operand, ctx, formula_str)
            if isinstance(node.op, ast.UAdd):
                return +operand
            elif isinstance(node.op, ast.USub):
                return -operand

        # 4. Variable lookup (Name)
        if isinstance(node, ast.Name):
            var_name = node.id
            if var_name.startswith("_"):
                raise ValueError(f"Access to private variable '{var_name}' is forbidden.")

            if var_name in cls.SAFE_CONSTANTS:
                return cls.SAFE_CONSTANTS[var_name]

            if var_name in ctx:
                val = ctx[var_name]
                if val is None or val == "":
                    raise ValueError(f"Variable '{var_name}' in formula is null or empty.")
                try:
                    num_val = float(val) if not isinstance(val, (int, float)) else val
                    return num_val
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        f"Variable '{var_name}' value '{val}' cannot be converted to a number."
                    ) from exc

            raise ValueError(f"Variable '{var_name}' not found in formula evaluation context.")

        # 5. Function calls (only whitelisted math functions)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError(f"Dynamic function invocation is forbidden in formula '{formula_str}'.")

            func_name = node.func.id
            if func_name.startswith("_") or func_name not in cls.SAFE_MATH_FUNCS:
                raise ValueError(f"Function '{func_name}' is not permitted in formula evaluation.")

            if node.keywords:
                raise ValueError(f"Keyword arguments are not supported in formula function '{func_name}'.")

            eval_args = [cls._eval_node(arg, ctx, formula_str) for arg in node.args]

            try:
                fn = cls.SAFE_MATH_FUNCS[func_name]
                res = fn(*eval_args)
                return res
            except ZeroDivisionError:
                raise
            except Exception as e:
                raise ValueError(f"Error evaluating math function '{func_name}': {e}") from e

        # All other AST nodes are strictly forbidden
        raise ValueError(
            f"Security restriction: Forbidden AST expression node '{type(node).__name__}' in formula '{formula_str}'."
        )


class CustomExperimentService:
    """
    Service coordinating custom no-code experiment templates, validation,
    formula evaluation, and entry persistence.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._templates: Dict[str, CustomExperimentTemplate] = {}
        self._entries: Dict[str, CustomExperimentEntry] = {}
        self._load_prebuilt_templates()

    def _load_prebuilt_templates(self) -> None:
        """Initialize the in-memory registry with standard pre-built templates."""
        for tpl in get_prebuilt_templates():
            self._templates[tpl.id] = tpl

    def evaluate_formula(
        self,
        formula_str: str,
        context_dict: Optional[Dict[str, Any]] = None,
    ) -> Union[float, int]:
        """
        Safely evaluate a mathematical formula expression against a context dictionary.
        """
        return SafeASTFormulaEvaluator.evaluate(formula_str, context_dict)

    def register_template(
        self,
        template_dict_or_obj: Union[CustomExperimentTemplate, Dict[str, Any]],
    ) -> CustomExperimentTemplate:
        """
        Register a new custom experiment template.

        Parameters:
            template_dict_or_obj: CustomExperimentTemplate instance or dictionary definition.

        Returns:
            CustomExperimentTemplate: The registered template.
        """
        if isinstance(template_dict_or_obj, CustomExperimentTemplate):
            tpl = template_dict_or_obj
        elif isinstance(template_dict_or_obj, dict):
            tpl = CustomExperimentTemplate.from_dict(template_dict_or_obj)
        else:
            raise ValueError("Template must be a CustomExperimentTemplate instance or dictionary.")

        if not tpl.id:
            tpl.id = f"tpl_custom_{uuid.uuid4().hex[:8]}"

        with self._lock:
            self._templates[tpl.id] = tpl
            return tpl

    def get_template(self, template_id: str) -> Optional[CustomExperimentTemplate]:
        """
        Retrieve a template by unique identifier.
        """
        with self._lock:
            return self._templates.get(template_id)

    def list_templates(self, category: Optional[str] = None) -> List[CustomExperimentTemplate]:
        """
        List all registered templates, optionally filtered by category.
        """
        with self._lock:
            templates = list(self._templates.values())
            if category:
                cat_lower = category.strip().lower()
                templates = [t for t in templates if t.category.lower() == cat_lower]
            return templates

    def validate_entry_data(
        self,
        template: CustomExperimentTemplate,
        form_data: Dict[str, Any],
    ) -> None:
        """
        Validate form data payload against template field definitions.

        Raises:
            ValueError: If a required field is missing, data types mismatch, or values are out of bounds.
        """
        data = form_data or {}

        for section in template.sections:
            for field in section.fields:
                field_id = field.id
                val = data.get(field_id)

                # Formula fields are computed, skip required check
                if field.type == "formula" or (field.formula and field.formula.strip()):
                    continue

                # Check required fields
                if field.required:
                    if val is None or (isinstance(val, str) and val.strip() == ""):
                        raise ValueError(f"Required field '{field.label}' ({field_id}) is missing.")

                # If value is present, validate types and boundaries
                if val is not None and val != "":
                    if field.type == "number":
                        try:
                            num = float(val)
                        except (ValueError, TypeError) as exc:
                            raise ValueError(
                                f"Field '{field.label}' ({field_id}) must be a number, got '{val}'."
                            ) from exc

                        if field.min_value is not None and num < field.min_value:
                            raise ValueError(
                                f"Field '{field.label}' ({field_id}) value {num} is below minimum allowed {field.min_value}."
                            )
                        if field.max_value is not None and num > field.max_value:
                            raise ValueError(
                                f"Field '{field.label}' ({field_id}) value {num} exceeds maximum allowed {field.max_value}."
                            )

                    elif field.type == "select":
                        if field.options and str(val) not in field.options:
                            raise ValueError(
                                f"Field '{field.label}' ({field_id}) value '{val}' is not in allowed options: {field.options}."
                            )

                    elif field.type == "date":
                        val_str = str(val).strip()
                        if not re.match(r"^\d{4}-\d{2}-\d{2}", val_str):
                            raise ValueError(
                                f"Field '{field.label}' ({field_id}) must be a valid date formatted as YYYY-MM-DD, got '{val}'."
                            )

                    elif field.type == "table":
                        if not isinstance(val, list):
                            raise ValueError(
                                f"Field '{field.label}' ({field_id}) must be a list of row dictionaries."
                            )
                        if field.columns:
                            for idx, row in enumerate(val):
                                if not isinstance(row, dict):
                                    raise ValueError(
                                        f"Row {idx} in table '{field.label}' must be a dictionary."
                                    )

    def compute_entry_values(
        self,
        template: CustomExperimentTemplate,
        form_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate all formula fields in a template using topological dependency resolution.

        Parameters:
            template (CustomExperimentTemplate): Target experiment template.
            form_data (Dict[str, Any]): Validated form data submitted by user.

        Returns:
            Dict[str, Any]: Dictionary mapping formula field IDs to computed numerical values.
        """
        # 1. Collect all formula fields
        formula_fields: Dict[str, FieldDefinition] = {}
        for section in template.sections:
            for field in section.fields:
                if field.type == "formula" or (field.formula and field.formula.strip()):
                    formula_fields[field.id] = field

        if not formula_fields:
            return {}

        # 2. Build initial numeric context
        context: Dict[str, Any] = {}
        for k, v in form_data.items():
            if v is not None and v != "":
                try:
                    context[k] = float(v) if not isinstance(v, (int, float)) else v
                except (ValueError, TypeError):
                    context[k] = v

        # 3. Extract dependencies for each formula field
        dependencies: Dict[str, Set[str]] = {}
        for fid, fld in formula_fields.items():
            deps = SafeASTFormulaEvaluator.extract_variables(fld.formula or "")
            # Only track dependencies that are other formula fields
            dependencies[fid] = {d for d in deps if d in formula_fields}

        # 4. Topologically resolve and compute formulas
        calculated_values: Dict[str, Any] = {}
        remaining = set(formula_fields.keys())

        while remaining:
            # Find fields whose dependencies have all been calculated
            ready = [fid for fid in remaining if dependencies[fid].issubset(calculated_values.keys())]

            if not ready:
                # Cyclic or unsatisfiable dependency among remaining formulas
                cycle_list = list(remaining)
                raise ValueError(
                    f"Cyclic or unresolved dependency detected among formula fields: {cycle_list}."
                )

            for fid in ready:
                fld = formula_fields[fid]
                formula_str = fld.formula or ""
                val = self.evaluate_formula(formula_str, context)
                calculated_values[fid] = val
                context[fid] = val
                remaining.remove(fid)

        return calculated_values

    def create_entry(
        self,
        template_id: str,
        campaign_id: Optional[str],
        title: str,
        form_data: Dict[str, Any],
        operator_id: Optional[str] = None,
    ) -> CustomExperimentEntry:
        """
        Validate input, compute formula fields, and create a new experiment entry.
        """
        template = self.get_template(template_id)
        if not template:
            raise KeyError(f"Template with ID '{template_id}' not found.")

        self.validate_entry_data(template, form_data)
        calculated = self.compute_entry_values(template, form_data)

        entry_id = f"ENTRY-CUST-{uuid.uuid4().hex[:8].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()

        entry = CustomExperimentEntry(
            id=entry_id,
            template_id=template_id,
            campaign_id=campaign_id,
            title=title or "Custom Experiment Entry",
            form_data=form_data,
            calculated_values=calculated,
            status="completed",
            approval_status="pending",
            operator_id=operator_id,
            created_at=now_iso,
            updated_at=now_iso,
        )

        with self._lock:
            self._entries[entry.id] = entry
            return entry

    def get_entry(self, entry_id: str) -> Optional[CustomExperimentEntry]:
        """
        Retrieve an experiment entry by its unique ID.
        """
        with self._lock:
            return self._entries.get(entry_id)

    def list_entries(
        self,
        campaign_id: Optional[str] = None,
        template_id: Optional[str] = None,
    ) -> List[CustomExperimentEntry]:
        """
        List all saved experiment entries, with optional filtering.
        """
        with self._lock:
            entries = list(self._entries.values())
            if campaign_id:
                entries = [e for e in entries if e.campaign_id == campaign_id]
            if template_id:
                entries = [e for e in entries if e.template_id == template_id]
            return entries

    def export_template(self, template_id: str, fmt: str = "json") -> str:
        """
        Export a template as serialized JSON or YAML.
        """
        template = self.get_template(template_id)
        if not template:
            raise KeyError(f"Template with ID '{template_id}' not found.")

        fmt_lower = fmt.lower().strip()
        if fmt_lower in ("yaml", "yml"):
            return template.to_yaml()
        return json.dumps(template.to_dict(), indent=2)

    def import_template(
        self,
        payload: Union[str, Dict[str, Any]],
        fmt: str = "json",
    ) -> CustomExperimentTemplate:
        """
        Import and register a template from a dictionary, JSON string, or YAML string.
        """
        fmt_lower = fmt.lower().strip()
        if isinstance(payload, str):
            if fmt_lower in ("yaml", "yml"):
                template = CustomExperimentTemplate.from_yaml(payload)
            else:
                try:
                    data = json.loads(payload)
                except Exception as e:
                    raise ValueError(f"Failed to parse JSON template payload: {e}") from e
                template = CustomExperimentTemplate.from_dict(data)
        elif isinstance(payload, dict):
            template = CustomExperimentTemplate.from_dict(payload)
        else:
            raise ValueError("Payload must be a dictionary or a JSON/YAML string.")

        return self.register_template(template)

    def clear_for_testing(self) -> None:
        """
        Reset internal template and entry registries for unit tests.
        """
        with self._lock:
            self._templates.clear()
            self._entries.clear()
            self._load_prebuilt_templates()


_global_custom_experiment_service = CustomExperimentService()


def get_custom_experiment_service() -> CustomExperimentService:
    """
    Get the singleton instance of CustomExperimentService.
    """
    return _global_custom_experiment_service
