# Command-Line Interface (CLI) Reference

BioLabCalc provides a command-line interface via the `biolabcalc` binary. The CLI provides 30 specialized subcommands spanning molecular biology calculations, protocol planning, image processing, spreadsheet generation, and web-based laboratory interfaces.

```bash
biolabcalc <subcommand> [options]
```

To view global help or help for a specific subcommand:

```bash
biolabcalc --help
biolabcalc <subcommand> --help
```

---

## Command Quick Reference

| Command | Category | Function |
| :--- | :--- | :--- |
| [`dilute`](#1-dilute) | General Bench | Solves $C_1 V_1 = C_2 V_2$ for any single missing parameter |
| [`wizard`](#2-wizard) | General Bench | Interactive guided step-by-step bench calculation wizard |
| [`mw`](#3-mw) | Molecular Weight | Calculates average and monoisotopic MW for DNA, RNA, and proteins |
| [`ivt`](#4-ivt) | Transcription | Calculates IVT yield, NTP consumption, PPi release, and turnover |
| [`pcr`](#5-pcr) | Amplification | Computes PCR kinetics, dNTP consumption, and plateau cycle |
| [`pcr-opt`](#6-pcr-opt) | Amplification | Recommends annealing temperatures, extension times, and cycling |
| [`protein`](#7-protein) | Protein Science | Direct $A_{280}$ Beer-Lambert quantification and yield |
| [`primers`](#8-primers) | Primers | Thermodynamic primer pair design with SantaLucia nearest-neighbor |
| [`nanodrop`](#9-nanodrop) | Spectroscopy | Standardized solution recipes and predicted NanoDrop $A_{260}$ |
| [`fluo`](#10-fluo) | Fluorescence | Fluorophore addition MW and Degree of Labeling (DOL) |
| [`gel`](#11-gel) | Electrophoresis | Simulates gel electrophoresis bands against MW ladders in ASCII |
| [`ecoli`](#12-ecoli) | Microbiology | E. coli doubling times, time to target OD, and plasmid/protein yields |
| [`excel-template`](#13-excel-template) | Excel Integration | Generates a 7-sheet dynamic Excel laboratory notebook template |
| [`annotate-gel`](#14-annotate-gel) | Imaging | Headless gel image lane labeling, ladder mapping, and callouts |
| [`interactive-gel`](#15-interactive-gel) | Imaging | Launches browser-based drag-and-drop gel calibrator/interpolator |
| [`batch-excel`](#16-batch-excel) | Excel Integration | Batch processes sequence tables from an Excel spreadsheet |
| [`digest`](#17-digest) | Cloning | Plans single or double restriction enzyme digests with buffer match |
| [`ligate`](#18-ligate) | Cloning | Calculates T4 DNA ligation insert masses and molar ratios |
| [`gibson`](#19-gibson) | Cloning | Plans multi-fragment Gibson Assembly / NEBuilder HiFi reactions |
| [`buffer`](#20-buffer) | Buffers | Computes chemical masses and instructions for standard/custom buffers|
| [`precipitate`](#21-precipitate) | Precipitation | Calculates ethanol/isopropanol nucleic acid precipitation recipes |
| [`ntp-ph`](#22-ntp-ph) | Transcription | Calculates NaOH volume required to neutralize NTP stocks to pH 7.5 |
| [`golden-gate`](#23-golden-gate) | Cloning | Formulates Type IIS Golden Gate assembly reactions and cycling |
| [`purity`](#24-purity) | Spectroscopy | Evaluates $A_{260}/A_{280}$ and $A_{260}/A_{230}$ ratios for contaminants |
| [`pci`](#25-pci) | Extraction | Plans Phenol:Chloroform:Isoamyl alcohol extraction protocols |
| [`ivt-time`](#26-ivt-time) | Transcription | Predicts optimal IVT incubation time and kinetic plateau |
| [`hepes`](#27-hepes) | Buffers | Formulates 10X/5X HEPES-KOH IVT buffer with temperature compensation|
| [`western`](#28-western) | Western Blot | Plans Western blot SDS-PAGE, transfer, antibodies, and troubleshooting|
| [`report`](#29-report) | Data Logging | Records experimental QC data and exports Markdown/Excel/JSON |
| [`eln`](#30-eln) | Web Applications | Launches Electronic Lab Notebook (ELN) and LIMS web server |

---

## Subcommand Details

### 1. `dilute`

Solves the universal dilution equation $C_1 V_1 = C_2 V_2$ for any single missing variable. Accepts numbers or human-readable strings with unit suffixes (e.g., `'100 mM'`, `'25 mM'`, `'16 mL'`).

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-c1` | `--conc1` | String / Float | `None` | Stock concentration (e.g., `'100 mM'`, `'10 mg/mL'`) |
| `-v1` | `--vol1` | String / Float | `None` | Stock volume to pipette (e.g., `'4 mL'`, `'50 uL'`) |
| `-c2` | `--conc2` | String / Float | `None` | Target working concentration (e.g., `'25 mM'`) |
| `-v2` | `--vol2` | String / Float | `None` | Target final volume (e.g., `'16 mL'`) |

#### Example

```bash
biolabcalc dilute -c1 "100 mM" -c2 "25 mM" -v2 "16 mL"
```

```text
=================================================================
DILUTION CALCULATOR (C1 * V1 = C2 * V2)
=================================================================
Stock Concentration (C1):    100.0 mM
Stock Volume to Add (V1):     4.000 mL (4,000.0 µL)
Target Concentration (C2):   25.0 mM
Final Total Volume (V2):      16.000 mL (16,000.0 µL)
Diluent Volume Needed:        12.000 mL (12,000.0 µL)
=================================================================
```

---

### 2. `wizard`

Launches an interactive, menu-driven CLI wizard guiding researchers through standard benchtop calculations.

#### Options

*No required options.* Alias: `biolabcalc interactive`.

#### Example

```bash
biolabcalc wizard
```

---

### 3. `mw`

Computes average and monoisotopic molecular weights, nucleotide/residue lengths, and GC content for DNA, RNA, or protein sequences. For RNA, customized 5', 3', and backbone chemistries can be modeled.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-s` | `--sequence` | String | *Required* | Sequence string |
| `-t` | `--type` | Choice | `dna` | `dna`, `rna`, or `protein` |
| | `--ds` | Flag | `False` | Double-stranded calculation (DNA only) |
| | `--end-5`, `--end5` | Choice | `hydroxyl` | 5' state: `hydroxyl`, `monophosphate`, `triphosphate` |
| | `--end-3`, `--end3` | Choice | `hydroxyl` | 3' state: `hydroxyl`, `monophosphate`, `diphosphate`, `triphosphate`, `cyclic_phosphate` |
| | `--backbone` | Choice | `monophosphate`| `monophosphate` or `phosphorothioate` |

#### Example

```bash
biolabcalc mw -s "GGGAGACCCAAGCUGGCCUUGAUCCAG" -t rna --end-5 triphosphate
```

```text
============================================================
Sequence Type:       ssRNA
Length:              27
Average MW:          8,859.34 Da
Monoisotopic MW:     8,853.0842 Da
Terminal Chemistry:  5'-triphosphate | 3'-hydroxyl
Backbone Linkage:    monophosphate
GC Content:          63.0%
============================================================
```

---

### 4. `ivt`

Calculates *in vitro* transcription (IVT) reaction stoichiometry, limiting NTP identification, percentage incorporation efficiency, pyrophosphate ($\text{PPi}$) release, proton generation, and transcript copy turnover. Automatically detects and trims upstream T7, T3, and SP6 promoters.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-s` | `--sequence` | String | *Required* | Template DNA or RNA sequence |
| `-v` | `--volume` | String / Float | `20.0 uL` | Total reaction volume |
| `-y` | `--yield-ug` | String / Float | `40.0 ug` | Measured or target RNA yield |
| | `--ntp-mm` | Float | `5.0` | Initial concentration of each NTP (mM) |
| | `--no-trim-promoter`| Flag | `False` | Disables automated 5' promoter trimming |
| | `--add-gg` | Integer | `0` | Forces N leading 5' Guanines (e.g., `2` for 5'-GG) |
| | `--cap` | Choice | `None` | Cap analog: `CleanCap_AG`, `CleanCap_GG`, `ARCA`, `m7G` |
| | `--mod-ntp` | Choice | `None` | Modified nucleotide: `m1Psi`, `Psi`, `5moU`, `m5C` |
| | `--buffer` | Choice | `hepes` | Reaction buffer: `hepes` or `tris` |
| | `--temp` | Float | `37.0` | Incubation temperature (°C) |

#### Example

```bash
biolabcalc ivt -s "TAATACGACTCACTATAGGGAGACCCAAGCUGGCC" -v "20 uL" -y "48 ug" --ntp-mm 5.0
```

```text
=================================================================
IN VITRO TRANSCRIPTION (IVT) YIELD & STOICHIOMETRY
=================================================================
Transcribed RNA Length:     18 nt
RNA Molecular Weight:       5,966.62 Da
Promoter Trimmed:           T7 (17 nt removed)
Initiation Rating:          OPTIMAL (5'-GGG motif)
Measured RNA Yield:         48.00 µg (8.0 pmol)
Theoretical Maximum:        66.29 µg (Limiting: ATP)
Incorporation Efficiency:   72.4%
Pyrophosphate (PPi):        23.32 µg (136.78 nmol)
Free Initial Mg2+:          4.0 mM
Protons (H+) Released:      136.78 nmol
Optimal Incubation Time:    ~2.00 hours at 37°C
Buffer Evaluation:          HEPES recommended (preserves neutral pH against H+ release)
=================================================================
```

---

### 5. `pcr`

Models exponential PCR amplification kinetics, primer/template copy numbers, cycle-by-cycle dNTP depletion, and plateaus.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-l` | `--length` | Integer | *Required* | Amplicon length in base pairs |
| `-t` | `--template-ng` | String / Float | *Required* | Initial template mass (e.g., `'10 ng'`, `10`) |
| `-c` | `--cycles` | Integer | `30` | Number of thermocycling cycles |

#### Example

```bash
biolabcalc pcr -l 850 -t 10 -c 30
```

```text
=================================================================
PCR KINETICS & REACTION STOICHIOMETRY
=================================================================
Amplicon Length:            850 bp (MW: 524,800.00 Da)
Initial Template:           10.0 ng (10,854,924 copies)
Cycles Run:                 30 (Efficiency: 95.0%)
Amplicon Yield:             1,850.40 ng (3.526 pmol)
Limiting Reagent:           dNTPs (dGTP)
Plateau Cycle:              Cycle 28
Theoretical Max:            2.45 µg
=================================================================
```

---

### 6. `pcr-opt`

Calculates recommended annealing temperatures ($T_a$), denaturation times, extension durations, and touchdown cycling profiles tailored to specific polymerases (Taq, Q5, Phusion, KAPA).

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| | `--fwd-tm`, `--tm-fwd` | Float | *Required* | Forward primer $T_m$ (°C) |
| | `--rev-tm`, `--tm-rev` | Float | *Required* | Reverse primer $T_m$ (°C) |
| `-l` | `--length` | Integer | *Required* | Amplicon length in base pairs |
| `-p` | `--polymerase`, `--poly`| Choice | `taq` | Polymerase: `taq`, `q5`, `phusion`, `kapa` |
| | `--gc` | Float | `50.0` | Amplicon GC percentage |

#### Example

```bash
biolabcalc pcr-opt --fwd-tm 61.5 --rev-tm 62.0 -l 1200 -p q5 --gc 58.0
```

```text
============================================================
PCR PROTOCOL OPTIMIZATION
============================================================
Polymerase:                 Q5
Recommended Annealing Ta:   64.5 °C
Denaturation:               98 °C (30 sec)
Extension Time:             36 sec at 72 °C (30 sec/kb)
Touchdown Profile:          Start at 69.5 °C for 5 cycles
Cycling Schedule:           30-35 cycles: 98°C 10s, 64.5°C 15s, 72°C 36s
============================================================
```

---

### 7. `protein`

Quantifies protein concentrations and total yields from ultraviolet absorbance readings at 280 nm ($A_{280}$) using sequence-derived extinction coefficients ($\varepsilon_{280}$, Pace et al. 1995).

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-s` | `--sequence` | String | *Required* | Amino acid sequence (one-letter code) |
| `-a` | `--a280` | Float | *Required* | Absorbance at 280 nm |
| `-v` | `--volume-ml`| Float | `1.0` | Purified stock volume in mL |

#### Example

```bash
biolabcalc protein -s "MKWVTFISLLLLFSSAYSRGVFRRDTHKSEIAHRFKDLGE" -a 0.850 -v 2.5
```

```text
=================================================================
PROTEIN QUANTIFICATION (A280 BEER-LAMBERT)
=================================================================
Sequence Length:            40 aa
Molecular Weight:           4,668.42 Da
Molar Extinction ε280:      5,500 M^-1 cm^-1
Concentration:              0.7215 mg/mL (721.46 µg/mL)
Molarity:                   154.54 µM
Total Yield:                1.8036 mg (1,803.6 µg)
=================================================================
```

---

### 8. `primers`

Performs thermodynamic primer pair design on target DNA sequences using SantaLucia nearest-neighbor parameters, reporting $T_m$, GC clamps, hairpin stability, and cross-dimerization risks.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-s` | `--sequence` | String | *Required* | Target template DNA sequence |
| | `--target-tm` | Float | `60.0` | Target melting temperature (°C) |

#### Example

```bash
biolabcalc primers -s "ATGCCGTCCAGGCTGCTGGTCCTCGCTCTGCTGCCACTGCTGCTGAGCCAGGCAGTGAGCGTGTCACCACTGG" --target-tm 60.0
```

```text
======================================================================
THERMODYNAMIC PRIMER DESIGN RESULTS (5 pairs found)
======================================================================
Pair #1 (Score: 94.2, Amplicon: 74 bp, ΔTm: 0.8°C):
  Forward: ATGCCGTCCAGGCTGCT (Tm: 60.4°C, GC: 64.7%, Clamp: True)
  Reverse: CCAGTGGTGACACGCTC (Tm: 59.6°C, GC: 64.7%, Clamp: True)
======================================================================
```

---

### 9. `nanodrop`

Calculates pipetting recipes to achieve target micromolar concentrations and predicts exact expected NanoDrop readings, including raw 1 mm pedestal values and sequence-specific extinction corrections.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-u`, `-m` | `--molarity-um` | Float | *Required* | Target molarity in µM (e.g., `4.0`) |
| `-v` | `--volume-ul` | Float | *Required* | Target volume in µL (e.g., `500.0`)|
| `-t` | `--type` | Choice | `rna` | `rna`, `dna`, `ssdna`, `dsdna`, `protein`|
| `-s` | `--sequence` | String | `None` | Optional sequence string |
| `-l` | `--length` | Integer | `100` | Sequence length (used if sequence omitted)|
| | `--stock-ng-ul`, `--stock`| Float | `None` | Stock concentration for dilution |
| | `--end-5`, `--end5` | Choice | `hydroxyl` | 5' state: `hydroxyl`, `monophosphate`, `triphosphate` |

#### Example

```bash
biolabcalc nanodrop -u 4.0 -v 500.0 -t rna --length 36 --stock-ng-ul 600.0
```

```text
======================================================================
STANDARDIZED SOLUTION PREPARATION & NANODROP PREDICTIONS
======================================================================
Target Solution:            4.0 µM in 500.0 µL (ssRNA)
Biomolecule MW:             11,610.00 g/mol (Da)
Required Moles:             2.000 nmol (2,000.0 pmol)
Required Mass:              23.220 µg (23,220.0 ng)
Actual Physical Conc.:      46.44 ng/µL
----------------------------------------------------------------------
WHAT YOU SHOULD GET AT THE NANODROP:
  Expected A260 (10 mm path):     1.161 AU (Generic factor mode)
  Expected A260 (1 mm pedestal): 0.1161 AU (Raw pedestal reading)
  Reading in NanoDrop RNA-40 Mode:46.44 ng/µL
  Expected A260/A280 Ratio:      ~2.00 (Pure RNA)
----------------------------------------------------------------------
Protocol: Dilute 38.70 µL of 600.0 ng/µL stock with 461.30 µL buffer to reach 500.0 µL.
======================================================================
```

---

### 10. `fluo`

Calculates molecular weight increments and spectral parameters (excitation, emission, extinction coefficients, and correction factors $\text{CF}_{260}/\text{CF}_{280}$) for fluorophore-conjugated molecules.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-s` | `--sequence` | String | `None` | Macromolecular sequence |
| `-t` | `--type` | Choice | `dna` | `dna`, `rna`, or `protein` |
| `-d` | `--dye` | String | `None` | Dye identifier (e.g., `FAM`, `Cy3`, `Cy5`, `Alexa488`) |
| | `--info` | String | `None` | Query fluorophore database parameters (e.g. `--info FAM`) |
| | `--dol` | Flag | `False` | Calculate Degree of Labeling (DOL) |
| | `--a-dye` | Float | `None` | Absorbance at dye absorbance maximum ($\lambda_{\text{max}}$) |
| | `--a280` | Float | `None` | Absorbance at 280 nm for protein conjugate |
| | `--a260` | Float | `None` | Absorbance at 260 nm for oligonucleotide conjugate |
| | `--prot-e280` | Float | `None` | Protein extinction coefficient $\varepsilon_{280}$ ($\text{M}^{-1}\text{cm}^{-1}$) |
| | `--dna-e260` | Float | `None` | Oligo extinction coefficient $\varepsilon_{260}$ ($\text{M}^{-1}\text{cm}^{-1}$) |
| | `--pathlength` | Float | `1.0` | Cuvette pathlength in cm |

#### Examples

**Fluorophore Modification:**

```bash
biolabcalc fluo -s "ATGCCGTCCAGGCTGCT" -t dna -d FAM
```

```text
============================================================
FLUOROPHORE MODIFICATION: 6-FAM
============================================================
Unmodified MW:       5,248.40 Da
Modified MW:         5,785.90 Da (+537.5 Da)
Excitation / Emission:495 nm / 520 nm (Green / FITC channel)
Extinction Coeff:    75,000 M^-1 cm^-1
Correction Factors:  CF260 = 0.30 | CF280 = 0.17
============================================================
```

**Fluorophore Information Query:**

```bash
biolabcalc fluo --info FAM
```

**Degree of Labeling (DOL) Calculation:**

```bash
biolabcalc fluo --dol -d ALEXA488 --a-dye 0.820 --a280 0.640 --prot-e280 210000
```

---

### 11. `gel`

Simulates relative electrophoretic migration ($R_f$) of sample band sizes against a molecular weight ladder and renders an ASCII schematic in the terminal.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-s` | `--sizes` | Float list | *Required* | Space-separated band sizes (bp or kDa) |
| `-l` | `--ladder` | Choice | `1kb_dna` | `1kb_dna`, `100bp_dna`, `low_range_ssdna`, `protein_broad_range` |

#### Example

```bash
biolabcalc gel -s 500 1200 3500 -l 1kb_dna
```

---

### 12. `ecoli`

Calculates bacterial culture generation times, hours required to reach induction $\text{OD}_{600}$ from a given starter density, total biomass, and theoretical plasmid/protein yields.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| | `--init-od` | Float | `0.05` | Initial culture $\text{OD}_{600}$ |
| | `--target-od`| Float | `0.60` | Target induction $\text{OD}_{600}$ |
| | `--temp` | Float | `37.0` | Growth temperature (°C) |
| | `--media` | Choice | `LB` | Growth media: `LB`, `2xYT`, `TB`, `M9` |
| | `--plasmid` | String | `pUC` | Plasmid replicon type: `pUC`, `pET`, `pBR322` |
| | `--vol-ml` | Float | `1000.0` | Culture volume in mL |

#### Example

```bash
biolabcalc ecoli --init-od 0.05 --target-od 0.65 --media LB --vol-ml 500
```

```text
============================================================
E. COLI GROWTH & PLASMID OPTIMIZATION
============================================================
Doubling Time:              20.0 min (LB at 37.0°C)
Time from OD 0.05 to 0.65:  1h 14m (3.7 doublings)
Cell Density at Target OD:  520,000,000 cells/mL
------------------------------------------------------------
Estimated Plasmid Yield (pUC, 500 mL culture):
  Theoretical Yield:        1,450.0 µg
  Typical Kit Recovery:     797.5 µg
============================================================
```

---

### 13. `excel-template`

Generates an authoritative, 7-sheet dynamic laboratory notebook template (`.xlsx`) populated with formulas, conditional formatting, and standard curve regression engines.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-o` | `--output` | String | `biolabcalc_notebook.xlsx` | Output Excel file path |

#### Example

```bash
biolabcalc excel-template -o "Q4_Project_Notebook.xlsx"
```

---

### 14. `annotate-gel`

Renders publication-ready annotated gel figures (PNG) from raw gel images or synthetic schematics. Supports lane labeling, ladder mapping, callout arrows, and embedding directly into an Excel workbook.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-i` | `--image` | String | `None` | Path to raw gel image (TIFF, PNG, JPG). If omitted, renders synthetic gel. |
| `-l` | `--lanes` | String | `Ladder,Ctrl,Sample1,Sample2` | Comma-separated lane names |
| | `--ladder` | Choice | `1kb_dna` | Ladder type: `1kb_dna`, `100bp_dna`, `low_range_ssdna`, `protein_broad_range` |
| | `--ladder-lane`| Integer | `1` | 1-based ladder lane number |
| | `--ladder-side`| Choice | `left` | MW scale placement: `left` or `right` |
| `-b` | `--bands` | String | `None` | Bands to annotate: `'lane:size:label'` separated by commas |
| `-t` | `--title` | String | `Agarose Gel Electrophoresis Analysis` | Figure title |
| | `--info` | String | `1.0% Agarose...` | Subtitle describing gel conditions |
| `-o` | `--output` | String | `annotated_gel.png` | Output figure path |
| | `--excel` | String | `None` | Target Excel file to embed figure and lane table |
| | `--invert` | Flag | `False` | Inverts image colors |

#### Example

```bash
biolabcalc annotate-gel \
  -l "Ladder,Uncut,Digest" \
  --ladder 1kb_dna \
  -b "3:3200:Backbone,3:850:Insert" \
  -t "Cloning Verification" \
  -o "annotated_clones.png" \
  --excel "Cloning_Log.xlsx"
```

---

### 15. `interactive-gel`

Launches the client-side drag-and-drop gel annotator and molecular weight calculator in a web browser, or exports the standalone offline HTML file.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-p` | `--port` | Integer | `8501` | Local web server port |
| | `--save-html` | String | `None` | Path to export self-contained offline HTML file |
| | `--no-browser`| Flag | `False` | Suppresses automatic browser launch |

#### Example

```bash
# Launch interactive local server
biolabcalc interactive-gel --port 8501

# Or export standalone HTML for air-gapped computers
biolabcalc interactive-gel --save-html "gel_tool.html"
```

---

### 16. `batch-excel`

Reads a multi-row sequence table from an Excel file (`.xlsx`), validates sequences, computes molecular weights, extinction coefficients, and molar equivalents, and writes an annotated results workbook.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-i` | `--input` | String | *Required* | Input `.xlsx` file containing sequence records |
| `-o` | `--output` | String | `batch_results.xlsx` | Output annotated `.xlsx` file path |

#### Example

```bash
biolabcalc batch-excel -i "oligo_order.xlsx" -o "oligo_analysis.xlsx"
```

---

### 17. `digest`

Plans single or double restriction endonuclease digestion reactions, identifying compatible buffers (rCutSmart, NEBuffer series), incubation temperatures, heat-inactivation protocols, and pipetting recipes.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| | `--dna-ug` | Float | *Required* | Substrate DNA mass in µg |
| `-v` | `--volume` | Float | `50.0` | Total reaction volume in µL |
| `-e1`| `--enzyme-1` | String | `EcoRI` | First restriction enzyme name |
| `-e2`| `--enzyme-2` | String | `None` | Optional second enzyme for double digest |
| | `--dna-conc` | Float | `None` | Stock DNA concentration (ng/µL) |

#### Example

```bash
biolabcalc digest --dna-ug 2.0 -v 50.0 -e1 EcoRI-HF -e2 BamHI-HF --dna-conc 250.0
```

```text
=================================================================
RESTRICTION DIGESTION SETUP
=================================================================
Enzyme 1:             EcoRI-HF (G^AATTC, 5_prime_sticky)
Enzyme 2:             BamHI-HF (G^GATCC, 5_prime_sticky)
Recommended Buffer:   rCutSmart Buffer (100% activity for both enzymes)
Incubation:           37°C for 60 min
Heat Inactivation:    Inactivate at 80°C for 20 min (or column purify)
-----------------------------------------------------------------
Pipetting Recipe:
  DNA Template (250.0 ng/µL)      :  8.00 µL
  10X rCutSmart Buffer            :  5.00 µL
  EcoRI-HF (20 U/µL)              :  1.00 µL (20 U)
  BamHI-HF (20 U/µL)              :  1.00 µL (20 U)
  Nuclease-Free Water             : 35.00 µL
  Total Reaction Volume           : 50.00 µL
=================================================================
```

---

### 18. `ligate`

Calculates required insert DNA mass and pipetting setup for sticky- or blunt-end T4 DNA ligations based on vector size, insert size, and target molar ratio.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| | `--vec-bp` | Integer | *Required* | Vector length in base pairs |
| | `--ins-bp` | Integer | *Required* | Insert length in base pairs |
| | `--vec-ng` | Float | `50.0` | Vector mass in ng |
| `-r` | `--ratio` | Float | `3.0` | Insert:vector molar ratio |
| `-v` | `--volume` | Float | `20.0` | Reaction volume in µL |

#### Example

```bash
biolabcalc ligate --vec-bp 4200 --ins-bp 850 --vec-ng 50 --ratio 3.0
```

```text
=================================================================
DNA LIGATION SETUP
=================================================================
Vector (4200 bp):         50.0 ng (0.018 pmol)
Insert (850 bp):          30.4 ng (0.054 pmol)
Molar Ratio (Insert:Vector):3.0 : 1
-----------------------------------------------------------------
Pipetting Recipe:
  Vector DNA                         :  2.00 µL
  Insert DNA                         :  3.04 µL
  10X T4 DNA Ligase Buffer           :  2.00 µL
  T4 DNA Ligase (400 U/µL)           :  1.00 µL
  Nuclease-Free Water                : 11.96 µL
Protocol: Incubate at 16°C for 2-16 hours or room temp (22°C) for 2 hours.
=================================================================
```

---

### 19. `gibson`

Formulates multi-fragment isothermal assembly reactions (Gibson Assembly / NEBuilder HiFi), computing picomolar quantities, fragment masses, and master mix pipetting volumes.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| | `--vec-bp` | Integer | *Required* | Destination vector length in bp |
| | `--ins-bp` | Int list| *Required* | Space-separated insert lengths in bp |
| | `--vec-ng` | Float | `100.0` | Vector mass in ng |
| `-r` | `--ratio` | Float | `2.0` | Molar ratio of inserts to vector |

#### Example

```bash
biolabcalc gibson --vec-bp 5000 --ins-bp 1200 800 --vec-ng 100 --ratio 2.0
```

```text
=================================================================
GIBSON ASSEMBLY / NEBUILDER SETUP
=================================================================
Vector (5000 bp):         100.0 ng
Insert #1 (1200 bp):      48.0 ng
Insert #2 (800 bp):       32.0 ng
Total DNA Input:          0.092 pmol (Optimal: 0.02 - 0.2 pmol)
-----------------------------------------------------------------
Pipetting Recipe:
  DNA Fragment Pool                  : 10.00 µL
  2X NEBuilder / Gibson Master Mix   : 10.00 µL
Protocol: Incubate at 50°C for 60 minutes in a thermocycler with heated lid.
=================================================================
```

---

### 20. `buffer`

Calculates chemical masses, stock volumes, and pH adjustment instructions for standard and custom laboratory buffers. Supports volume scaling and an interactive custom buffer builder.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-b` | `--buffer` | String | `None` | Buffer name (e.g., `50X_TAE`, `10X_PBS`, `10X_HEPES_IVT`)|
| `-v` | `--volume-ml`| Float | `1000.0` | Target preparation volume in mL |
| | `--custom` | Flag | `False` | Launches interactive custom buffer builder |
| | `--list` | Flag | `False` | Lists all standard and custom buffers |
| | `--list-custom`| Flag | `False` | Lists custom buffers saved on disk |

#### Example

```bash
biolabcalc buffer -b "10X_PBS" -v 2000
```

```text
=================================================================
BUFFER RECIPE: 10X Phosphate Buffered Saline (PBS)
=================================================================
Target Volume:        2,000 mL (2.00 L)
Target pH:            7.4 ± 0.1 at 25°C
Storage:              Room temperature (15-25°C)
-----------------------------------------------------------------
Reagent Formulations:
  Sodium chloride (NaCl)      :  160.000 g     [1.37 M] (7647-14-5)
  Potassium chloride (KCl)    :    4.000 g     [27 mM] (7447-40-7)
  Disodium phosphate (Na2HPO4):   28.800 g     [100 mM] (7558-79-4)
  Monopotassium phosphate     :    4.900 g     [18 mM] (7778-77-0)
-----------------------------------------------------------------
Preparation Instructions:
  1. Dissolve reagents in 1600 mL distilled H2O.
  2. Adjust pH to 7.4 with concentrated HCl or NaOH.
  3. Add distilled H2O to final volume of 2000 mL. Autoclave or filter sterilize.
=================================================================
```

---

### 21. `precipitate`

Generates volume-scaled ethanol or isopropanol precipitation protocols for DNA or RNA, including salt choices, glycogen carrier additions, and centrifugation speeds.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-v` | `--volume-ul`| Float | *Required* | Aqueous sample volume in µL |
| `-t` | `--type` | Choice | `dna` | Nucleic acid type: `dna` or `rna` |
| `-a` | `--alcohol` | Choice | `ethanol` | Alcohol: `ethanol` or `isopropanol` |
| `-s` | `--salt` | Choice | `naoac` | Salt: `naoac`, `nh4oac`, `licl`, `nacl` |
| | `--carrier` / `--no-carrier` | Flag | `True` | Include or exclude glycogen carrier |

#### Example

```bash
biolabcalc precipitate -v 100 -t rna -a ethanol -s naoac
```

```text
=================================================================
NUCLEIC ACID PRECIPITATION PROTOCOL (ssRNA)
=================================================================
Sample Volume:        100.0 µL
Salt Added:           Sodium Acetate 3M pH 5.2 (10.0 µL, 0.1 vol)
Alcohol Added:        100% Cold Ethanol (275.0 µL, 2.5 vol)
Carrier Added:        Glycogen (20 mg/mL) (1.0 µL)
-----------------------------------------------------------------
Procedure:
  1. Incubation:      -20°C for 1 hour or -80°C for 30 minutes.
  2. Centrifuge:      Spin at ≥ 16,000 x g for 30 min at 4°C.
  3. Supernatant:     Carefully aspirate supernatant without dislodging pellet.
  4. Wash:            Add 200 µL 70% ethanol, spin 5 min, remove supernatant.
  5. Dry:             Air-dry pellet for 5-10 min (do not over-dry).
  6. Resuspend:       Resuspend in nuclease-free water or 1 mM sodium citrate pH 6.4.
=================================================================
```

---

### 22. `ntp-ph`

Calculates the exact volume of sodium hydroxide ($\text{NaOH}$) needed to neutralize commercial disodium NTP stocks to physiological pH 7.5, preventing transcript degradation and $\text{Mg}^{2+}$ precipitation.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-v`, `-v1` | `--initial-vol` | Float | `4.0` | Initial stock volume in mL |
| `-c`, `-c1` | `--initial-conc`| Float | `100.0`| Initial stock concentration in mM |
| `-V`, `-v2` | `--target-vol` | Float | `16.0` | Target final volume in mL |
| `-C`, `-c2` | `--target-conc` | Float | `25.0` | Target final concentration in mM |
| `-p` | `--target-ph`, `--ph` | Float | `7.5` | Target pH |
| `-f` | `--form`, `--starting-form` | Choice | `disodium_salt`| Chemical form: `disodium_salt`, `pre_neutralized`, `free_acid` |
| `-s` | `--species` | Choice | `equimolar_mix`| `equimolar_mix`, `ATP`, `CTP`, `GTP`, `UTP` |
| `-b` | `--base-molarity`| Float | `5.0` | Molarity of NaOH stock in M |

#### Example

```bash
biolabcalc ntp-ph -v 4.0 -c 100.0 -V 16.0 -C 25.0 -f disodium_salt
```

```text
=================================================================
NTP SOLUTION PREPARATION & pH ADJUSTMENT
=================================================================
Target Solution:      25.0 mM equimolar_mix (Total Volume: 16.0 mL)
Target pH:            7.50
Starting Stock:       4.0 mL @ 100.0 mM (disodium_salt)
Total NTP Quantity:   400.0 µmol (0.400 mmol)
OH- Equivalents:      0.850 eq / mol NTP
Total NaOH Required:  340.0 µmol (0.3400 mmol)
-----------------------------------------------------------------
Calculated NaOH Volumes by Stock Concentration:
  5M    NaOH:     68.0 µL (0.068 mL)
  10M   NaOH:     34.0 µL (0.034 mL)
Diluent Water (approx): 11.932 mL (bring to 16.0 mL mark)
=================================================================
```

---

### 23. `golden-gate`

Calculates one-pot assembly stoichiometry and thermocycling schedules for Golden Gate cloning using Type IIS restriction enzymes (BsaI, BsmBI, BbsI).

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| | `--vec-bp` | Integer | *Required* | Destination vector length in bp |
| | `--ins-bp` | Int list| *Required* | Space-separated insert lengths in bp |
| | `--fmol` | Float | `20.0` | Target vector quantity in fmol |
| | `--enzyme` | String | `BsaI-HFv2` | Type IIS enzyme name |
| | `--ratio` | Float | `2.0` | Insert:vector molar ratio |

#### Example

```bash
biolabcalc golden-gate --vec-bp 4500 --ins-bp 1200 650 --fmol 20 --enzyme BsaI-HFv2
```

```text
=================================================================
GOLDEN GATE ASSEMBLY SETUP (BsaI-HFv2)
=================================================================
Vector (4500 bp):         59.2 ng (20.0 fmol)
Insert #1 (1200 bp):      31.6 ng (40.0 fmol)
Insert #2 (650 bp):       17.1 ng (40.0 fmol)
Insert:Vector Molar Ratio:  2.0 : 1
Total DNA Mass:             107.9 ng
-----------------------------------------------------------------
1-Pot Pipetting Recipe:
  T4 DNA Ligase Buffer (10X)         :  2.00 µL
  T4 DNA Ligase                      :  1.00 µL
  Type IIS Enzyme (BsaI-HFv2)        :  1.00 µL
  DNA Pool (Vector + Inserts)        : 10.00 µL
  Nuclease-Free Water                :  6.00 µL
-----------------------------------------------------------------
Thermocycling Schedule:
  30 cycles of: 37°C for 3 min (digest) -> 16°C for 4 min (ligate)
  Final digestion: 50°C for 5 min
  Heat inactivation: 80°C for 10 min
=================================================================
```

---

### 24. `purity`

Analyzes micro-volume spectrophotometer absorbance readings ($A_{260}$, $A_{280}$, $A_{230}$), diagnoses chemical contamination (phenol, guanidine salts, EDTA, carbohydrates, proteins), and computes turbidity-corrected concentrations.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| | `--a260` | Float | *Required* | Absorbance at 260 nm |
| | `--a280` | Float | *Required* | Absorbance at 280 nm |
| | `--a230` | Float | *Required* | Absorbance at 230 nm |
| `-t` | `--type` | Choice | `rna` | Sample type: `rna` or `dna` |

#### Example

```bash
biolabcalc purity --a260 1.250 --a280 0.625 --a230 0.580 -t rna
```

```text
=================================================================
NANODROP NUCLEIC ACID PURITY ASSESSMENT (ssRNA)
=================================================================
Absorbance Readings:        A260 = 1.250 | A280 = 0.625 | A230 = 0.580
A260 / A280 Ratio:          2.00 (Ideal: ~2.0 for RNA, ~1.8 for DNA)
A260 / A230 Ratio:          2.16 (Ideal: 2.0 – 2.2)
Purity Status:              PURE
Estimated True Conc.:       50.0 ng/µL
-----------------------------------------------------------------
Diagnostic Observations:
  * Pure RNA spectrum. Ratios match standard benchmarks.
=================================================================
```

---

### 25. `pci`

Formulates Phenol:Chloroform:Isoamyl alcohol ($25:24:1$) phase separation protocols for nucleic acid clean-up, selecting correct phenol pH (pH 4.5 for RNA partitioning; pH 8.0 for DNA partitioning).

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-v` | `--volume` | Float | *Required* | Aqueous sample volume in µL |
| `-t` | `--type` | Choice | `rna` | Target: `rna` or `dna` |
| | `--ph` | Float | `None` | Phenol pH (`4.5` for RNA, `8.0` for DNA) |

#### Example

```bash
biolabcalc pci -v 200 -t rna
```

```text
=================================================================
PHENOL:CHLOROFORM EXTRACTION PROTOCOL
=================================================================
Reagent Grade:              Acid Phenol:Chloroform (pH 4.5 ± 0.2)
Target Nucleic Acid:        RNA (DNA partitions into organic/interphase)
Aqueous Phase Behavior:     Upper aqueous phase contains target RNA
-----------------------------------------------------------------
Pipetting Recipe:
  Acid Phenol:Chloroform (25:24:1)   : 200.00 µL (1:1 vol)
  Chloroform:Isoamyl Alcohol (24:1)  : 200.00 µL (back extraction)
-----------------------------------------------------------------
Protocol Steps:
  1. Add 200.0 µL Acid Phenol:Chloroform to 200.0 µL sample.
  2. Vortex vigorously for 30 seconds.
  3. Centrifuge at 16,000 x g for 5 minutes at 4°C.
  4. Transfer upper aqueous phase (~180 µL) to fresh tube.
  5. Add 180.0 µL Chloroform:Isoamyl alcohol to remove residual phenol.
  6. Centrifuge 5 min at 4°C and recover final aqueous phase.
=================================================================
```

---

### 26. `ivt-time`

Predicts the kinetic trajectory of *in vitro* transcription reactions, recommending incubation times that maximize full-length yield while minimizing $3'$ heterogeneity and degradation.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-l` | `--length` | Integer | *Required* | Transcript length in nucleotides |
| | `--temp` | Float | `37.0` | Incubation temperature (°C) |
| | `--no-ipp` | Flag | `False` | Omits inorganic pyrophosphatase (IPP) |

#### Example

```bash
biolabcalc ivt-time -l 1500 --temp 37.0
```

```text
=================================================================
IVT TRANSCRIPTION TIME & KINETIC OPTIMIZATION (1500 nt)
=================================================================
Incubation Temperature:     37.0 °C (Standard T7)
Recommended Reaction Time:  2.00 hours (Window: 1.5–2.5 h)
Plateau Time:               ~2.50 hours
3' Heterogeneity Hazard:    Low (Reaction terminated before NTP starvation)
Degradation Hazard:         Low
-----------------------------------------------------------------
Predicted Synthesis Trajectory:
  0.50 h :  35.0% yield -> Exponential Phase
  1.00 h :  68.0% yield -> Linear Phase
  1.50 h :  88.0% yield -> Deceleration Phase
  2.00 h :  96.0% yield -> Near Plateau
  2.50 h : 100.0% yield -> Full Plateau
=================================================================
```

---

### 27. `hepes`

Calculates recipes for concentrated (10X or 5X) HEPES-KOH IVT reaction buffers, compensating for temperature-dependent ionization shifts ($\Delta\text{p}K_a / \Delta T = -0.014 / ^\circ\text{C}$).

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-v` | `--volume` | String | `50 mL` | Buffer stock preparation volume |
| | `--stock` | Integer | `10` | Concentration factor (e.g., `10` for 10X) |
| | `--ph` | Float | `7.50` | Target pH at reaction temperature (37°C) |

#### Example

```bash
biolabcalc hepes -v "50 mL" --stock 10 --ph 7.50
```

```text
======================================================================
10X HEPES-KOH IVT REACTION BUFFER RECIPE (50.0 mL)
======================================================================
Target Reaction pH (37°C):   7.50
Preparation pH (25°C):       7.67 (compensates for ΔpKa/ΔT = -0.014/°C)
----------------------------------------------------------------------
Component Formula & Concentrations:
  HEPES free acid          :  4.766 g    (400 mM in 10X)
  KOH pellets (or 5M KOH)  :  Adjust to pH 7.67 at 25°C
  Magnesium acetate        :  2.145 g    (200 mM in 10X)
  Spermidine               :  0.145 g    (20 mM in 10X)
  DTT                      :  0.771 g    (100 mM in 10X)
----------------------------------------------------------------------
Buffer Advantage: HEPES does not chelate Mg2+ and maintains pH during H+ release.
======================================================================
```

---

### 28. `western`

Generates experimental plans for Western blotting (SDS-PAGE matrix percentage, transfer parameters, lysate loading recipes, antibody dilutions) and diagnoses common blot artifacts.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-n`, `-target` | `--name`, `--target` | String | `Target Protein` | Target protein name |
| `-m` | `--mw` | Float | `None` | Target molecular weight in kDa |
| `-c` | `--conc` | Float | `2.5` | Lysate concentration in mg/mL |
| `-l`, `--ug` | `--load-ug` | Float | `20.0` | Target protein mass per lane (µg) |
| | `--phospho` | Flag | `False` | Phospho-specific target (enforces BSA blocking) |
| | `--membrane-protein`, `--membrane`| Flag | `False` | Transmembrane target (enforces 70°C denaturation) |
| | `--transfer` | Choice | `wet_tank` | Transfer method: `wet_tank`, `semi_dry`, `fast_semi_dry` |
| | `--membrane` | Choice | `pvdf` | Membrane: `pvdf` or `nitrocellulose` |
| | `--troubleshoot`| String | `None` | Artifact symptom to diagnose |

#### Example 1: Planning an Experiment

```bash
biolabcalc western -n "GluK2 Kainate Receptor" -m 100.0 -c 2.5 -l 25.0 --membrane-protein
```

```text
======================================================================
WESTERN BLOT EXPERIMENTAL PLAN: GluK2 Kainate Receptor (100.0 kDa)
======================================================================
1. GEL RESOLUTION & RUNNING CONDITIONS:
   Recommended Matrix:    8% SDS-PAGE (Tris-Glycine)
   Running Parameters:    80V through stacking gel (20 min), then 120V (70 min)
----------------------------------------------------------------------
2. SAMPLE PREPARATION & LOADING (Target: 25.0 µg / lane):
   Lysate Stock Conc:     2.50 mg/mL
   Per-Lane Volumes:      10.00 µL Lysate + 3.33 µL 4X Sample Buffer
   Denaturation:          70°C for 10 minutes (transmembrane protein: DO NOT BOIL)
----------------------------------------------------------------------
3. ELECTROTRANSFER CONDITIONS (WET_TANK -> PVDF):
   Membrane Pore Size:    0.45 µm
   Membrane Activation:   Pre-wet in 100% Methanol for 30 sec, then equilibrate in transfer buffer
   Transfer Buffer:       Towbin Buffer with 10% Methanol + 0.05% SDS
   Transfer Run:          100V constant for 90 min at 4°C with ice pack
----------------------------------------------------------------------
4. IMMUNODETECTION & BLOCKING:
   Blocking Solution:     5% Non-fat Dry Milk in 1X TBST (1 hour at RT)
   Primary Antibody:      1:1000 dilution in 5% BSA/TBST (Overnight at 4°C)
======================================================================
```

#### Example 2: Diagnosing an Artifact

```bash
biolabcalc western --troubleshoot ghost_bands
```

```text
======================================================================
WESTERN BLOT DIAGNOSTIC & TROUBLESHOOTING: ghost_bands
======================================================================
Likely Root Causes:
  * Substrate burnout / ECL substrate exhaustion due to excessive HRP activity
  * Excessive secondary antibody concentration
Corrective Actions:
  [+] Dilute secondary antibody 2- to 5-fold further (e.g. 1:10,000 instead of 1:2,000)
  [+] Reduce exposure time or re-incubate membrane with fresh ECL substrate
======================================================================
```

---

### 29. `report`

Records wet-lab measurements against target specifications, applies automated QC tolerance evaluations (`PASS`, `FLAGGED`, `FAIL`), and exports structured reports to Markdown, Excel, CSV, or JSON.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-t` | `--title` | String | `Laboratory Experiment Report` | Experiment title |
| `-r` | `--researcher`| String | `Researcher` | Experimenter name |
| `-p` | `--project` | String | `General` | Project / notebook ID |
| | `--obj`, `--objective` | String | `""` | Experimental objective |
| `-s` | `--sample` | String | `None` | Sample ID (e.g., `Sample_1`) |
| | `--param` | String | `None` | Assay or parameter (e.g., `Yield`) |
| `-v` | `--value`, `--val` | Float | `None` | Measured value |
| `-u` | `--unit` | String | `""` | Measurement unit |
| | `--target` | Float | `None` | Expected target value |
| | `--tolerance`, `--tol` | Float | `None` | Deviation tolerance (%) |
| | `--conclusion` | String | `None` | Add conclusion or key takeaway |
| `-o` | `--output` | String | `None` | Output path (`.md`, `.xlsx`, `.csv`, `.json`)|
| | `--interactive`| Flag | `False` | Launches interactive terminal data recorder |

#### Example

```bash
biolabcalc report \
  -t "IVT Batch QC" \
  -r "K. Vance" \
  -s "IVT_Batch_01" \
  --param "RNA_Yield" \
  -v 48.2 \
  -u "ug" \
  --target 50.0 \
  --tolerance 10.0 \
  -o "Batch_01_QC.md"
```

---

### 30. `eln`

Launches the Electronic Lab Notebook (ELN) and Laboratory Information Management System (LIMS) web server.

#### Options

| Flag | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `-p` | `--port` | Integer | `8080` | Local HTTP port |
| | `--host` | String | `127.0.0.1` | Network interface binding |
| | `--db-url` | String | `None` | SQLite / PostgreSQL connection URL |
| | `--no-browser`| Flag | `False` | Suppresses automatic browser launch |

#### Example

```bash
biolabcalc eln --port 8080
```
