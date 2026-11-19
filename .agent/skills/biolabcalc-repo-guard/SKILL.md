---
name: biolabcalc-repo-guard
description: Enforce cross-machine Python 3.8+ compatibility, architectural invariants, printable quality, and automated doc sync on the BioLabCalc repository. Use whenever editing, refactoring, debugging, or auditing BioLabCalc Python modules, tests, requirements, or documentation, especially when running with Gemini Flash or other fast coding agents.
---

# biolabcalc-repo-guard

Prevent cross-machine breakages, silent import regressions, and documentation drift across the BioLabCalc repository using fast, mechanical verification checks after every edit.

## When to Use
- Editing any Python module in `src/biolabcalc/` or `tests/`
- Adding or modifying CLI subcommands, Excel/HTML printables, or dependencies
- Auditing BioLabCalc with Gemini Flash, Antigravity, Claude Code, or Codex
- Preparing a commit, pull request, or release build

## Steps

### 1. Edit One Subsystem at a Time
Keep every change scoped to a single file or tightly coupled pair (implementation + unit test). Never refactor unrelated modules in the same pass, because fast models lose track of local imports and helper scopes across large diffs.

### 2. Enforce Python 3.8+ Syntax Compatibility
BioLabCalc declares `requires-python = ">=3.8"`. Never use Python 3.12+ f-string backslashes (PEP 701) or unguarded Python 3.10+ union syntax (`X | Y` without `from __future__ import annotations`).

After every edit, verify Python 3.8 syntax across the entire repository:

```bash
python -c "
import ast, glob, sys
for p in sorted(glob.glob('src/**/*.py', recursive=True) + glob.glob('tests/**/*.py', recursive=True)):
    src = open(p, encoding='utf-8').read()
    ast.parse(src, filename=p, feature_version=(3, 8))
print('PY38 AST CHECK PASSED')
"
```

### 3. Enforce Core Architectural Invariants
Check these five rules before running tests:
1. **Frozen dataclasses**: Use `@dataclass(frozen=True)` and coerce list/set fields to `tuple(...)` in `__post_init__`.
2. **Zero-dependency core**: Keep `dependencies = []` in `pyproject.toml`. Never import Bio (Biopython). Guard openpyxl, matplotlib, Pillow, fastapi, uvicorn, sqlalchemy, and PyYAML with `try...except ImportError`.
3. **No out-of-scope helper imports**: When moving code into a helper method (for example, `_build_excel_content()`), move or re-import any locally imported symbols (`PatternFill`, `Font`, `Border`) inside that helper.
4. **Cross-OS path and file-handle safety**: Never pass multiline text into `Path(s).is_file()` without checking `"\n" not in s and len(s) < 255` and catching `OSError`. Always close openpyxl workbooks (`wb.close()` in `try...finally`) and PIL.Image handles (`with Image.open(...)`).
5. **Atomic disk writes**: Write JSON/config files to a sibling temporary file, call `f.flush()` and `os.fsync(f.fileno())`, close the handle, and call `os.replace(tmp, target)`.

### 4. Verify Printables and Smoke Tests
Whenever touching `lab_report.py`, `protocols.py`, `excel_extension.py`, `gel_annotator.py`, or any HTML app (`interactive_gel.py`, `interactive_plasmid.py`, `eln/web/`):
- Execute `LabReport.to_excel()` and `generate_lab_notebook_template()` in a `tempfile.TemporaryDirectory()` to confirm zero NameError or unclosed handle issues.
- Confirm Excel sheets set `ws.page_setup.fitToWidth = 1` and `ws.sheet_properties.pageSetUpPr.fitToPage = True`.
- Confirm HTML apps include `@media print` CSS and a working `window.print()` trigger.

### 5. Run the Mandatory Verification Gate
Run all checks below before finishing. Stop and fix any nonzero exit code:

```bash
python scripts/ci_guard.py
PYTHONPATH=src python -W default -m unittest discover -s tests -v
python scripts/update_readme.py --check
python scripts/update_wiki.py --check
CI=true python scripts/security_audit.py
```

If `scripts/update_ai_docs.py` exists, run `python scripts/update_ai_docs.py --check` to confirm `.ai_docs/CLI_AND_MODULE_MAP.md` matches `cli.py` and `src/biolabcalc/`.

## Gotchas
- **Python 3.14 developer machine trap**: Code that passes on Python 3.12-3.14 can crash on Python 3.8-3.11. Always run the `ast.parse(..., feature_version=(3, 8))` check.
- **Stale requirements.txt drift**: Keep `requirements.txt`, `requirements-all.txt`, and `requirements-dev.txt` as thin wrappers around `pyproject.toml` (`-e .`, `-e .[all]`, `-e .[dev]`) instead of duplicating version pins.
- **Committed build artifacts**: Never leave stale `dist/*.tar.gz` or `docs_site/*.html` out of sync with `src/biolabcalc/`. Rebuild `docs_site/` via `python scripts/build_pages_demo.py` after any interactive HTML edit.
