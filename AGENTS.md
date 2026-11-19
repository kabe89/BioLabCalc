# BioLabCalc AI Agent Operating Instructions

This document defines the operating rules, architectural invariants, and mandatory verification gates for all AI coding agents (Antigravity, Gemini Flash, Claude Code, Codex, Pi, OpenCode, Qwen, etc.) working on the `kabe89/BioLabCalc` repository.

## 1. Primary Knowledge Base & Skills
- **Architecture & CLI Map**: Always consult `.ai_docs/CLI_AND_MODULE_MAP.md` before adding or modifying CLI subcommands or core modules.
- **Maintenance Skills**:
  - `.agent/skills/biolabcalc-repo-guard/SKILL.md`: Python 3.8+ compatibility, architectural invariants, printables, and doc sync.
  - `.agent/skills/biolabcalc-eln-and-release-qa/SKILL.md`: ELN persistence, API wiring, Bio-Rad `.scn` parser, launchers, Docker, and PyPI release workflows.
  (Mirrored in `.agents/skills/` for universal agent compatibility).

## 2. Core Architectural Invariants
1. **Python 3.8+ Syntax Only**:
   - `requires-python = ">=3.8"`.
   - Never use Python 3.12+ f-string backslashes (PEP 701, e.g. `{s.replace('\n', '')}`).
   - Always include `from __future__ import annotations` when using PEP 604 (`X | Y`) or PEP 585 (`list[...]`) type hints.
2. **Zero-Dependency Core**:
   - `dependencies = []` in `pyproject.toml`.
   - Never import `Bio` (Biopython).
   - Guard optional dependencies (`openpyxl`, `matplotlib`, `Pillow`, `fastapi`, `uvicorn`, `sqlalchemy`, `PyYAML`) with `try...except ImportError`.
3. **Immutability & Types**:
   - Core dataclasses must use `@dataclass(frozen=True)` and coerce list/set collections to `tuple(...)` in `__post_init__`.
4. **Cross-Platform Safety & Resource Hygiene**:
   - Never pass multiline or long strings (>255 chars) directly to `Path(s).is_file()` without checking `"\n" not in s and len(s) < 255` and catching `OSError`.
   - Always close file handles, `openpyxl` workbooks (`wb.close()` in `try...finally`), and `matplotlib` figures (`plt.close(fig)`).
   - Use atomic writes (`_atomic_write_text`) for state/config files.

## 3. Mandatory Pre-Commit & Completion Verification Gate
Before completing any task or creating a pull request, run the following verification sequence. Every command must exit 0:

```bash
python scripts/ci_guard.py
PYTHONPATH=src python -W default -m unittest discover -s tests -v
python scripts/update_readme.py --check
python scripts/update_wiki.py --check
CI=true python scripts/security_audit.py
```

If documentation files were touched or if `scripts/update_ai_docs.py` is present:
```bash
python scripts/update_ai_docs.py --check
```
