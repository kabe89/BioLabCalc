# Contributing to BioLabCalc 🧬🔬

Thank you for your interest in contributing to **BioLabCalc**! BioLabCalc is an open-source, multifaceted Python library, Electronic Lab Notebook (ELN), and Excel automation tool built for everyday molecular biology research, PCR stoichiometry, in vitro transcription (IVT), protein biochemistry, and wet-lab reproducibility.

We welcome contributions of all kinds: bug reports, new biological calculation modules, performance improvements, documentation updates, and test coverage expansions.

---

## Code of Conduct

All contributors and participants are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it to understand our community standards and expectations.

---

## How Can I Contribute?

### 1. Reporting Bugs & Issues
* Before opening a new issue, check existing GitHub issues to avoid duplicates.
* Clearly describe the issue, including:
  * Operating System and Python version (`python --version`).
  * Minimal reproducible example code.
  * Expected vs. observed calculation result (including numerical values and units).
  * Citations to standard references or formulas if mathematical discrepancies are found.

### 2. Suggesting New Calculation Modules
When proposing or adding a new wet-lab calculation (e.g., isothermal amplification, qPCR quantification models, lipid nanoparticle formulation math):
* Include peer-reviewed literature citations in the module and function docstrings.
* Explicitly state all assumptions, standard buffer conditions, temperature parameters, and range limitations.
* Specify input/output units in parameter names (e.g. `conc_ng_ul`, `volume_ml`, `mw_da`, `temp_celsius`).

### 3. Improving Documentation & Examples
* Clarify API docstrings with type hints and usage examples.
* Contribute workflow tutorials, Jupyter notebooks, or protocol templates in `examples/`.

---

## Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/kabe89/BioLabCalc.git
cd BioLabCalc
```

### 2. Set Up a Virtual Environment
```bash
# On Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

# On Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install in Editable Mode with Development Dependencies
```bash
pip install -e ".[dev]"
```

---

## Coding & Style Guidelines

### 1. Python Standards
* **Python Compatibility**: Python 3.8 through 3.12+.
* **Type Annotations**: Use PEP 484 type hints throughout all public functions and data classes.
* **Docstrings**: Provide clear, Google- or NumPy-style docstrings for every function, explaining:
  * Theoretical background and formula.
  * Literature citation (Author, Journal, Year, DOI/PMID).
  * Parameter descriptions with exact physical/chemical units.
  * Return value structure and raised exceptions.

### 2. Defensive Scientific Input Validation
* Validate biological sequences (e.g., ensure valid IUPAC nucleotide or amino acid codes).
* Validate physical boundaries (e.g., concentration > 0, volume ≥ 0, realistic temperature ranges).
* Provide helpful, actionable `ValueError` or `TypeError` messages when inputs fall outside physical limits.

### 3. Dependency Discipline
* BioLabCalc core calculations should remain fast, lightweight, and deterministic. Avoid adding heavy external dependencies unless strictly necessary for core scientific functionality.
* Permissive licensing: Any new optional or required dependency must have an OSI-approved permissive license (MIT, BSD, Apache 2.0).

---

## Running Tests

All mathematical and computational routines in BioLabCalc require unit test validation.

```bash
# Set PYTHONPATH to include src
# Linux / macOS:
export PYTHONPATH=src
python -m unittest discover tests

# Windows (PowerShell):
$env:PYTHONPATH="src"
python -m unittest discover tests

# Or using pytest:
pytest tests/
```

### Writing Tests
* Place new test cases under `tests/` with the filename pattern `test_<module_name>.py`.
* Include test cases comparing calculated values against published literature benchmark datasets or analytical controls.
* Include edge cases: empty strings, zero volumes, single-base sequences, extreme GC contents, and boundary temperatures.

---

## Commit & Pull Request Workflow

We follow standard GitHub Pull Request workflows and Conventional Commits:

### 1. Branch Naming
Create a descriptive branch for your work:
```bash
git checkout -b feat/luciferase-assay-calculations
# or
git checkout -b fix/tm-salt-correction-formula
```

### 2. Commit Messages
Write clear, conventional commit messages:
* `feat: add Gibson assembly equimolar ratio calculator`
* `fix: correct divalent cation adjustment in primer Tm`
* `docs: update ELN API endpoint specifications`
* `test: add unit test suite for IVT nucleotide depletion kinetics`

### 3. Submitting a Pull Request
1. Push your branch to your GitHub fork:
   ```bash
   git push origin feat/your-feature-name
   ```
2. Open a Pull Request against `main`.
3. Provide a clear summary of what changes were made, why they are needed, and how they were tested.
4. Ensure all continuous integration (CI) tests pass before requesting review.

---

## Community & Questions

Have questions, suggestions, or ideas?
* Open an issue on [GitHub Issues](https://github.com/kabe89/BioLabCalc/issues).
* Start a discussion on the repository forums.

Thank you for helping make molecular biology calculations accurate, transparent, and accessible to researchers everywhere! 🚀🧫
