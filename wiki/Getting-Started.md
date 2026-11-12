# Getting Started with BioLabCalc 🚀

This guide covers system prerequisites, installation methods, environment configuration, and verification steps to get BioLabCalc up and running in your laboratory environment.

---

## 📋 System Requirements

* **Operating System**: Linux, macOS, or Windows (10/11 / Server).
* **Python Version**: Python 3.8, 3.9, 3.10, 3.11, or 3.12.
* **Core Dependencies**: Zero required external binary dependencies for core mathematical, stoichiometric, and biophysical calculations.
* **Optional Features**:
  * `openpyxl`: Required for `.xlsx` workbook generation and batch spreadsheet processing.
  * `matplotlib`, `Pillow`: Required for headless gel image annotation.
  * `uvicorn`, `fastapi`: Required for running the production ASGI ELN web server (a zero-dependency pure-Python fallback server is included by default).

---

## 📦 Installation Methods

### 1. From PyPI (Standard Installation)

The easiest way to install BioLabCalc is via `pip`:

```bash
pip install biolabcalc
```

### 2. Installing Optional Feature Bundles

BioLabCalc provides modular installation extras so benchtop workstations only install what they need:

```bash
# Install with Excel workbook generation support (.xlsx templates and batch processing)
pip install "biolabcalc[excel]"

# Install with image processing and gel plot annotation support
pip install "biolabcalc[gel]"

# Install full development and testing suite (pytest, flake8, black)
pip install "biolabcalc[dev]"

# Install all optional components simultaneously
pip install "biolabcalc[excel,gel]"
```

### 3. Installing from GitHub Source (Development Mode)

If you are modifying the codebase or running the bleeding-edge version:

```bash
git clone https://github.com/kabe89/BioLabCalc.git
cd BioLabCalc
pip install -e ".[dev]"
```

---

## 🔍 Verifying the Installation

To verify that BioLabCalc is properly installed and accessible on your system PATH:

### Verification via Terminal CLI

```bash
biolabcalc --version
```

Output:
```text
BioLabCalc 0.3.5
```

Run a quick test calculation:
```bash
biolabcalc dilute -c1 "100 mM" -c2 "25 mM" -v2 "16 mL"
```

Expected Output:
```text
================================================================================
  BIOLABCALC SOLUTION DILUTION RECIPE (C1*V1 = C2*V2)
================================================================================
[*] Target Volume (V2):      16.00 mL
[*] Target Molarity (C2):    25.00 mM
[*] Stock Molarity (C1):     100.00 mM
--------------------------------------------------------------------------------
[+] Pipette Stock (V1):      4.00 mL
[+] Add Diluent:             12.00 mL
================================================================================
```

### Verification via Python REPL

```python
import biolabcalc as blc

print(blc.__version__)
mw = blc.calculate_dna_mw("ATGCCGTCCAGGCTGCTGGTC")
print(f"DNA Molecular Weight: {mw.average_mw:.2f} Da")
```

---

## 🧙‍♂️ Interactive Terminal Wizard (`biolabcalc wizard`)

For bench scientists who prefer not to memorize CLI flags, BioLabCalc features an interactive, guided prompt wizard:

```bash
biolabcalc wizard
```

The wizard presents a menu covering:
1. Solution Dilution ($C_1 V_1 = C_2 V_2$)
2. Buffer Recipe Scaling
3. Golden Gate Assembly (Type IIS)
4. Gibson Assembly Stoichiometry
5. Restriction Digest Setup
6. Primer Design & SantaLucia $T_m$
7. NanoDrop Purity Assessment
8. Nucleic Acid Precipitation & Extraction
9. In Vitro Transcription Yield & Capping
10. Western Blot Transfer Optimization

Each selection prompts you for the relevant variables with clear units, validates your inputs, and prints a formatted protocol card.

---

## 📓 Launching the Electronic Lab Notebook (ELN)

BioLabCalc includes a complete, browser-based Electronic Lab Notebook (ELN) and LIMS. To launch it locally:

```bash
biolabcalc eln --port 8080
```

By default:
* The server initializes a local SQLite database in your working directory (`.biolabcalc_data/eln_lims.db`).
* Content-Addressed Storage (CAS) is allocated for uploaded instrument raw data and spectra.
* Your default web browser will automatically open to `http://127.0.0.1:8080`.

For full ELN deployment instructions, including multi-user setups and PostgreSQL configuration, see [ELN System Architecture](Electronic-Lab-Notebook-(ELN)).

---

## 🧪 Next Steps

* Explore [Core Calculators & Stoichiometry](Core-Calculators-&-Biophysics) for molecular weight and unit math.
* Review [Molecular Cloning & Assembly](Molecular-Cloning-&-Assembly) for Golden Gate, Gibson, and restriction digest setups.
* Browse the [Complete CLI Subcommand Reference](CLI-Reference) for all 29 terminal commands.
