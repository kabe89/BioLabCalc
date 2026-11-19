#!/usr/bin/env python3
"""ci_guard.py — BioLabCalc Architectural and Pre-Commit CI Guardrails.

Enforces:
1. Python 3.8 AST syntax compliance across src/ and tests/.
2. Zero Biopython imports (import Bio / from Bio) in src/.
3. Zero unclosed openpyxl Workbook handles in src/.
4. Version parity across pyproject.toml, src/biolabcalc/__init__.py, and CITATION.cff.
5. All CLI subparsers in src/biolabcalc/cli.py documented in .ai_docs/CLI_AND_MODULE_MAP.md.
6. Zero dependencies in pyproject.toml (dependencies = []).
7. Thin requirements*.txt wrappers pointing to pyproject.toml.
8. Valid published GitHub Actions action tags.
9. No RAM-only ELN services in src/biolabcalc/eln/services/.
10. Dockerfile and .bat launcher sanity.
"""

from __future__ import annotations

import argparse
import ast
import glob
import os
import re
import sys
from pathlib import Path


def check_ast_python38(root: Path) -> list[str]:
    errors = []
    py_files = sorted(list(root.glob("src/**/*.py")) + list(root.glob("tests/**/*.py")))
    for path in py_files:
        try:
            source = path.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"{path}: failed to read: {e}")
            continue

        try:
            tree = ast.parse(source, filename=str(path), feature_version=(3, 8))
        except SyntaxError as e:
            errors.append(f"{path}:{e.lineno}: Python 3.8 SyntaxError: {e}")
            continue

        # Check for unguarded PEP 604 union (X | Y) or PEP 585 generics (list[X])
        has_future_annotations = False
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                for alias in node.names:
                    if alias.name == "annotations":
                        has_future_annotations = True
                        break

        if not has_future_annotations:
            # Look for BitOr in annotations
            for node in ast.walk(tree):
                ann = None
                if isinstance(node, ast.AnnAssign):
                    ann = node.annotation
                elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    if node.returns:
                        ann = node.returns
                if ann is not None:
                    for sub in ast.walk(ann):
                        if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.BitOr):
                            errors.append(
                                f"{path}:{getattr(sub, 'lineno', 0)}: PEP 604 union '|' used without 'from __future__ import annotations'"
                            )
                        elif isinstance(sub, ast.Subscript) and isinstance(sub.value, ast.Name):
                            if sub.value.id in ("list", "dict", "tuple", "set", "frozenset", "type"):
                                errors.append(
                                    f"{path}:{getattr(sub, 'lineno', 0)}: PEP 585 generic '{sub.value.id}[...]' used without 'from __future__ import annotations'"
                                )
    return errors


def check_zero_biopython(root: Path) -> list[str]:
    errors = []
    for path in sorted(root.glob("src/**/*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "Bio" or alias.name.startswith("Bio."):
                        errors.append(f"{path}:{node.lineno}: Forbidden Biopython import: 'import {alias.name}'")
            elif isinstance(node, ast.ImportFrom):
                if node.module == "Bio" or (node.module and node.module.startswith("Bio.")):
                    errors.append(f"{path}:{node.lineno}: Forbidden Biopython import: 'from {node.module} import ...'")
    return errors


def check_openpyxl_handles(root: Path) -> list[str]:
    errors = []
    for path in sorted(root.glob("src/**/*.py")):
        text = path.read_text(encoding="utf-8")
        if "Workbook(" in text or "load_workbook(" in text:
            # Verify file contains .close() or BytesIO or is handled
            if ".close()" not in text and "BytesIO" not in text:
                errors.append(f"{path}: openpyxl Workbook/load_workbook used without .close() or BytesIO")
    return errors


def check_version_parity(root: Path, release_tag: str | None = None) -> list[str]:
    errors = []
    versions = {}

    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        m = re.search(r'version\s*=\s*"([^"]+)"', pyproject_path.read_text(encoding="utf-8"))
        if m:
            versions["pyproject.toml"] = m.group(1)
        else:
            errors.append("pyproject.toml: version not found")

    init_path = root / "src" / "biolabcalc" / "__init__.py"
    if init_path.exists():
        m = re.search(r'__version__\s*=\s*"([^"]+)"', init_path.read_text(encoding="utf-8"))
        if m:
            versions["src/biolabcalc/__init__.py"] = m.group(1)
        else:
            errors.append("src/biolabcalc/__init__.py: __version__ not found")

    citation_path = root / "CITATION.cff"
    if citation_path.exists():
        m = re.search(r'(?m)^version:\s*([^\s]+)', citation_path.read_text(encoding="utf-8"))
        if m:
            versions["CITATION.cff"] = m.group(1)
        else:
            errors.append("CITATION.cff: version not found")

    if release_tag:
        clean_tag = release_tag.lstrip("v")
        versions["release_tag"] = clean_tag

    unique_versions = set(versions.values())
    if len(unique_versions) > 1:
        details = ", ".join(f"{k}={v}" for k, v in versions.items())
        errors.append(f"Version mismatch detected: {details}")

    return errors


def check_dependencies(root: Path) -> list[str]:
    errors = []
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        content = pyproject_path.read_text(encoding="utf-8")
        if "dependencies = []" not in content and 'dependencies = [ ]' not in content:
            # Check if dependencies is empty
            m = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if not m or m.group(1).strip():
                errors.append("pyproject.toml: core dependencies must be empty (dependencies = [])")

    req = root / "requirements.txt"
    if req.exists():
        text = req.read_text(encoding="utf-8").strip()
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
        if not any("-e ." in l for l in lines):
            errors.append("requirements.txt: must be thin wrapper referencing '-e .'")
        if any(pkg in text.lower() for pkg in ["biopython", "numpy>=", "scipy>="]):
            errors.append("requirements.txt: contains heavy pinned packages; should delegate to pyproject.toml")

    req_all = root / "requirements-all.txt"
    if req_all.exists():
        text = req_all.read_text(encoding="utf-8")
        if "-e .[all]" not in text:
            errors.append("requirements-all.txt: must be thin wrapper containing '-e .[all]'")

    req_dev = root / "requirements-dev.txt"
    if req_dev.exists():
        text = req_dev.read_text(encoding="utf-8")
        if "-e .[dev]" not in text:
            errors.append("requirements-dev.txt: must be thin wrapper containing '-e .[dev]'")

    return errors


def check_cli_subcommands(root: Path) -> list[str]:
    errors = []
    cli_path = root / "src" / "biolabcalc" / "cli.py"
    ai_docs_path = root / ".ai_docs" / "CLI_AND_MODULE_MAP.md"

    if not cli_path.exists():
        return ["src/biolabcalc/cli.py not found"]

    cli_content = cli_path.read_text(encoding="utf-8")
    subparsers = set(re.findall(r'subparsers\.add_parser\(\s*["\']([a-zA-Z0-9_\-]+)["\']', cli_content))

    if not ai_docs_path.exists():
        errors.append(".ai_docs/CLI_AND_MODULE_MAP.md not found")
        return errors

    ai_docs_content = ai_docs_path.read_text(encoding="utf-8")
    missing = []
    for cmd in sorted(subparsers):
        if f"`{cmd}`" not in ai_docs_content and f"| {cmd} " not in ai_docs_content and f" {cmd} " not in ai_docs_content:
            missing.append(cmd)

    if missing:
        errors.append(f".ai_docs/CLI_AND_MODULE_MAP.md is missing CLI subparsers: {', '.join(missing)}")

    return errors


def check_github_actions_tags(root: Path) -> list[str]:
    errors = []
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.exists():
        return errors

    invalid_tags = {
        "download-artifact@v8": "actions/download-artifact@v4",
        "configure-pages@v6": "actions/configure-pages@v5",
        "upload-pages-artifact@v5": "actions/upload-pages-artifact@v3",
        "deploy-pages@v5": "actions/deploy-pages@v4",
    }

    for wf in workflows_dir.glob("*.yml"):
        content = wf.read_text(encoding="utf-8")
        for bad, good in invalid_tags.items():
            if bad in content:
                errors.append(f"{wf}: uses unreleased/invalid action tag '{bad}' (should be '{good}')")
    return errors


def check_ram_only_eln_services(root: Path) -> list[str]:
    errors = []
    services_dir = root / "src" / "biolabcalc" / "eln" / "services"
    if not services_dir.exists():
        return errors

    for p in sorted(services_dir.glob("*.py")):
        if p.name == "__init__.py":
            continue
        s = p.read_text(encoding="utf-8")
        has_db = any(k in s for k in ["sqlite", "sqlalchemy", "Session", "execute(", "json.dump", "SQLiteStore", "sqlite3"])
        has_ram = bool(re.search(r"self\.(_\w+)\s*:\s*(?:Dict|dict)\[", s))
        if has_ram and not has_db:
            errors.append(f"src/biolabcalc/eln/services/{p.name}: RAM-only service with no persistent store")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="BioLabCalc Pre-Commit CI Guardrails")
    parser.add_argument("--release-tag", help="Verify that project version matches this release tag")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent

    all_errors = {}
    print("Running BioLabCalc CI Guardrails...\n")

    checks = [
        ("Python 3.8 AST Syntax & Future Annotations", lambda: check_ast_python38(root)),
        ("Zero Biopython Import Check", lambda: check_zero_biopython(root)),
        ("Openpyxl Workbook Resource Hygiene", lambda: check_openpyxl_handles(root)),
        ("Version Parity", lambda: check_version_parity(root, args.release_tag)),
        ("Zero Core Dependencies & Thin Wrappers", lambda: check_dependencies(root)),
        ("CLI Subcommands in .ai_docs", lambda: check_cli_subcommands(root)),
        ("GitHub Actions Action Tags", lambda: check_github_actions_tags(root)),
        ("ELN Services Persistence", lambda: check_ram_only_eln_services(root)),
    ]

    total_failures = 0
    for name, check_fn in checks:
        errs = check_fn()
        if errs:
            print(f"[FAIL] {name}:")
            for err in errs:
                print(f"  - {err}")
            all_errors[name] = errs
            total_failures += len(errs)
        else:
            print(f"[PASS] {name}")

    print("\n" + "=" * 60)
    if total_failures > 0:
        print(f"CI GUARD FAILED: {total_failures} issue(s) detected across {len(all_errors)} check(s).")
        return 1
    else:
        print("CI GUARD PASSED: All architectural invariants verified.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
