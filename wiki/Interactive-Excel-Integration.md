# Interactive Excel Integration

BioLabCalc includes a native Excel extension (`excel_extension.py`) built on `openpyxl`. It provides bidirectional integration between Python calculation pipelines and Microsoft Excel or LibreOffice Calc spreadsheets:

1. **Dynamic Lab Notebook Templates (`generate_lab_notebook_template`)**: Generates pre-configured, multi-sheet laboratory workbooks containing live Excel formulas, data validation blocks, and standard curve regression engines.
2. **Automated Batch Processing (`batch_process_excel`)**: Ingests multi-row sequence tables from `.xlsx` spreadsheets, computes molecular weights, extinction coefficients, and molar quantities, and exports styled analytical reports.
3. **Structured Object Export (`export_analysis_to_excel`)**: Converts native Python dataclass results (`IVTResult`, `PCRResult`, `ProteinYieldResult`, `PrimerPair`) directly into multi-tab workbooks.

---

## 1. Visual Styling & Color Coding Architecture

All generated spreadsheets follow an standardized laboratory typography and styling convention designed for clarity at the bench.

```
+------------------------------------------------------------------------------------------+
| #1F4E79 (Deep Navy Header) - Bold White Text, Center Aligned                             |
+------------------------------------------------------------------------------------------+
| #2F5597 (Medium Blue Subheader) - Bold White Text, Section Labels                        |
+------------------------------------------------------------------------------------------+
| #FFF2CC (Light Yellow Fill) - User Input Cells (Editable values: volumes, ODs, concs)    |
+------------------------------------------------------------------------------------------+
| #E2EFDA (Light Green Fill)  - Calculated Cells (Live Excel formulas: never overwrite)   |
+------------------------------------------------------------------------------------------+
| #D9E1F2 (Soft Lavender/Ice) - Context / Reference Cells (MW constants, conversion factors)|
+------------------------------------------------------------------------------------------+
```

### Style Constants Table

| Style Element | Hex Code | RGB Equivalent | Purpose / Application |
| :--- | :--- | :--- | :--- |
| **`NAVY_HEADER`** | `#1F4E79` | `rgb(31, 78, 121)` | Top table headers, primary worksheet section banners |
| **`BLUE_SUBHEADER`**| `#2F5597` | `rgb(47, 85, 151)` | Sub-tables, intermediate calculation categories |
| **`INPUT_FILL`** | `#FFF2CC` | `rgb(255, 242, 204)`| **Editable inputs**: Concentrations, volumes, readings |
| **`CALC_FILL`** | `#E2EFDA` | `rgb(226, 239, 218)`| **Dynamic formulas**: Mass balances, stoichiometry, yields |
| **`ACCENT_FILL`** | `#D9E1F2` | `rgb(217, 225, 242)`| Read-only constants, molecular weight references |
| **`WHITE_BOLD_FONT`**| `#FFFFFF` | `rgb(255, 255, 255)`| High-contrast bold header text (Calibri 11 pt) |
| **`TITLE_FONT`** | `#1F4E79` | `rgb(31, 78, 121)` | Worksheet title block (Calibri 16 pt, Bold) |
| **`NOTE_FONT`** | `#595959` | `rgb(89, 89, 89)` | Instructional subtitles and protocol guidance (Calibri 9 pt, Italic)|

---

## 2. Seven-Sheet Lab Notebook Architecture

Running `biolabcalc excel-template -o My_Notebook.xlsx` (or calling `generate_lab_notebook_template`) constructs a comprehensive 7-sheet interactive workbook. Each worksheet targets a core wet-lab workflow with interconnected live formulas.

```
My_Notebook.xlsx
 ├── 1. IVT_Stoichiometry
 ├── 2. PCR_Optimization
 ├── 3. Protein_Quantification
 ├── 4. Primer_Design_Log
 ├── 5. Solution_Prep_NanoDrop
 ├── 6. Fluorophore_Modifications
 └── 7. Ecoli_Growth_Optimization
```

---

### Sheet 1: `IVT_Stoichiometry`

Models *in vitro* transcription reactions driven by T7, T3, or SP6 RNA polymerases. It links template DNA stoichiometry to limiting NTP consumption, pyrophosphate precipitation risk, and transcript copy turnover.

#### 1. Input Parameters (Rows 5–15)

| Cell | Parameter Name | Default Value | Unit | Role |
| :--- | :--- | :--- | :--- | :--- |
| **`B6`** | Reaction Volume | `20.0` | µL | Total reaction mixture volume |
| **`B7`** | Template DNA Mass | `1000.0` | ng | Linearized plasmid or purified amplicon |
| **`B8`** | Template DNA Length | `3500` | bp | Full length of template DNA |
| **`B9`** | Transcript Length | `1200` | nt | Target single-stranded RNA sequence length |
| **`B10`**| Transcript GC Content| `52.0` | % | Base composition |
| **`B11`**| Measured RNA Yield | `45.0` | µg | Post-purification quantified yield |
| **`B12`**| Starting ATP Conc. | `5.0` | mM | Nucleotide substrate starting molarity |
| **`B13`**| Starting CTP Conc. | `5.0` | mM | Nucleotide substrate starting molarity |
| **`B14`**| Starting GTP Conc. | `5.0` | mM | Nucleotide substrate starting molarity |
| **`B15`**| Starting UTP Conc. | `5.0` | mM | Nucleotide substrate starting molarity |

#### 2. Live Formulas & Stoichiometric Metrics (Rows 18–27)

```
+----------------------------------------------------------------------------------------------------+
| Metric                            | Excel Formula                                 | Unit           |
+-----------------------------------+-----------------------------------------------+----------------+
| RNA Molecular Weight (approx)     | =B9*321.4+177.98                              | g/mol (Da)     |
| RNA Synthesized                   | =B11                                          | µg             |
| RNA Amount (pmol)                 | =(B20*1000000)/B19                            | pmol           |
| Total NTPs Initial per Base       | =B6*B12                                       | nmol           |
| Theoretical Max RNA Yield         | =(B22/(B9*0.25))*B19/1000                     | µg             |
| Incorporation Efficiency          | =(B20/B23)*100                                | %              |
| Pyrophosphate (PPi) Released      | =(B21*(B9-1))/1000                            | nmol           |
| Transcript Turnover Ratio         | =B21/((B7*1000)/(B8*617.96+36.04))            | RNA / DNA      |
+----------------------------------------------------------------------------------------------------+
```

- **RNA Molecular Weight (`B19`)**: Models an average mononucleotide weight of $321.4\text{ g/mol}$ plus the $177.98\text{ g/mol}$ contribution of the 5' triphosphate end group ($5'\text{-pppG}$).
- **Pyrophosphate Released (`B25`)**: Quantifies the stoichiometric accumulation of $\text{PPi}$, which precipitates $\text{Mg}^{2+}$ as insoluble magnesium pyrophosphate ($\text{Mg}_2\text{P}_2\text{O}_7$) when exceeding $10\text{--}15\text{ mM}$.
- **Transcript Turnover Ratio (`B26`)**: Calculates the number of full-length RNA transcripts produced per template DNA molecule.

---

### Sheet 2: `PCR_Optimization`

Provides dynamic master mix calculations with pipetting overage scaling and qPCR amplification efficiency modeling.

#### 1. Master Mix Scaling Table

- **Reaction Count (`B5`)**: Number of tubes (e.g., `12`).
- **Excess Multiplier (`D5`)**: Pipetting loss overage factor (e.g., `1.10` for +10% overage).

```
+----------------------------------------------------------------------------------------------------+
| Component             | Stock Conc.   | Final Conc.    | 1x Vol (µL) | Master Mix Total (µL)       |
+-----------------------+---------------+----------------+-------------+-----------------------------+
| Nuclease-Free Water   | —             | —              | 34.5        | =D8*$B$5*$D$5               |
| 5X PCR Buffer         | 5X            | 1X             | 10.0        | =D9*$B$5*$D$5               |
| dNTP Mix              | 10 mM each    | 0.2 mM each    | 1.0         | =D10*$B$5*$D$5              |
| Forward Primer        | 10 µM         | 0.4 µM         | 2.0         | =D11*$B$5*$D$5              |
| Reverse Primer        | 10 µM         | 0.4 µM         | 2.0         | =D12*$B$5*$D$5              |
| DNA Polymerase        | 2 U/µL        | 1 U            | 0.5         | =D13*$B$5*$D$5              |
| Template DNA          | —             | —              | 2.0         | (Add directly to tubes)     |
+-----------------------+---------------+----------------+-------------+-----------------------------+
| Total Volume          |               |                | =SUM(D8:D14)| =SUM(E8:E13)                |
+----------------------------------------------------------------------------------------------------+
```

#### 2. Quantitative PCR (qPCR) Efficiency

Calculates exponential amplification efficiency from standard curve dilution series:

$$E = 10^{-\frac{1}{\text{slope}}} - 1$$

$$\text{Efficiency } (\%) = \left( 10^{-\frac{1}{\text{slope}}} - 1 \right) \cdot 100$$

- **Input Slope (`B18`)**: e.g., `-3.322` (ideal slope for 2-fold doubling per cycle).
- **Amplification Factor (`B19`)**: `=10^(-1/B18)` (ideal: `2.000`).
- **Efficiency Percentage (`B20`)**: `=(B19-1)*100` (ideal: `100.0%`). Acceptable bench range is $90\%\text{--}110\%$ (slope between $-3.58$ and $-3.10$).

---

### Sheet 3: `Protein_Quantification`

Implements direct UV $A_{280}$ absorbance calculations and linear regression interpolation for colorimetric protein assays (BCA, Bradford, Lowry).

#### 1. Direct $A_{280}$ Beer-Lambert Method

$$A_{280} = \varepsilon_{280} \cdot b \cdot c$$

Where:
- Protein MW (`B6`): Target polypeptide molecular weight in Da.
- Extinction Coefficient $\varepsilon_{280}$ (`B7`): Calculated via Pace et al. (1995) formula based on Trp, Tyr, and Cystine residues.
- Measured Absorbance (`B8`): Pathlength-corrected absorbance reading.
- Path Length $b$ (`B9`): $1.0\text{ cm}$ for standard cuvettes, $0.1\text{ cm}$ for 1 mm micro-volume pedestals.
- Sample Volume (`B10`): Total purified solution volume in mL.
- Dilution Factor (`B11`): Dilution factor applied before reading.

Live formulas:
- **Concentration (mg/mL) (`B13`)**: `=((B8*B11)/(B7*B9))*B6`
- **Concentration (µg/mL) (`B14`)**: `=B13*1000`
- **Total Yield (mg) (`B15`)**: `=B13*B10`
- **Total Yield (ng) (`B16`)**: `=B15*1000000`

#### 2. Colorimetric Assay Standard Curve (BCA / Bradford)

Interpolates unknown sample concentrations using dynamic linear regression formulas:

$$\text{Concentration } (\mu\text{g/mL}) = \frac{A_{\text{sample}} - \text{Intercept}}{\text{Slope}}$$

```excel
= (D20 - INTERCEPT(B20:B25, A20:A25)) / SLOPE(B20:B25, A20:A25)
```

Where:
- `A20:A25`: Known BSA standard concentrations ($0, 125, 250, 500, 750, 1000\text{ }\mu\text{g/mL}$).
- `B20:B25`: Measured absorbance values for the standards.
- `D20`: Absorbance of the unknown experimental sample.
- Sample Total Yield (mg): `=(E20*F20)/1000`

---

### Sheet 4: `Primer_Design_Log`

A structured tracking table for oligonucleotide primers, logging sequences, melting temperatures ($T_m$), GC content, $3'$ GC clamps, self-dimer scores, and expected amplicon lengths.

```
+--------------------------------------------------------------------------------------------------------+
| Primer ID     | Target Gene  | Direction | Sequence (5' -> 3')   | Len | Tm (°C) | GC (%) | 3' Clamp   |
+---------------+--------------+-----------+-----------------------+-----+---------+--------+------------+
| GluK2_Exon1_F | GluK2 Rec    | Forward   | ATGCCGTCCAGGCTGCTGGTC | 21  | 62.4    | 61.9   | Yes (2)    |
| GluK2_Exon1_R | GluK2 Rec    | Reverse   | TCACTTGTCGTCGTCATCCTT | 21  | 58.7    | 47.6   | No (0)     |
+--------------------------------------------------------------------------------------------------------+
```

---

### Sheet 5: `Solution_Prep_NanoDrop`

Calculates pipetting recipes to achieve target micromolar concentrations and predicts corresponding micro-volume spectrophotometer readings (NanoDrop).

#### 1. Solution Stoichiometry Formulas

- **Required Moles (nmol) (`B15`)**: `=(B6*B7)/1000` (Target Molarity $\mu\text{M} \times$ Volume $\mu\text{L} / 1000$)
- **Required Moles (pmol) (`B16`)**: `=B15*1000`
- **Required Mass (µg) (`B17`)**: `=(B15*B10)/1000` ($\text{nmol} \times \text{MW} / 1000$)
- **Required Mass (ng) (`B18`)**: `=B17*1000`
- **Target Concentration (ng/µL) (`B19`)**: `=B18/B7`
- **Stock Volume to Pipette (µL) (`B20`)**: `=IF(B11>0, B18/B11, 0)`
- **Buffer Volume to Add (µL) (`B21`)**: `=IF(B11>0, B7-B20, B7)`

#### 2. Spectrophotometer Predictions

- **Normalized $A_{260}$ (10 mm path) (`B26`)**: `=B19/40.0` (using $40\text{ }\mu\text{g/mL per } A_{260}$ for ssRNA; $50$ for dsDNA, $33$ for ssDNA).
- **Pedestal $A_{260}$ (1 mm physical gap) (`B27`)**: `=B26*0.1` (raw unscaled instrument reading).
- **$A_{260}/A_{280}$ Purity Baseline**: `2.00` for pure RNA, `1.80` for pure dsDNA.

---

### Sheet 6: `Fluorophore_Modifications`

Maintains a spectral library of fluorophores and calculates the Degree of Labeling (DOL) for fluorescently tagged oligonucleotides and antibodies.

#### Built-in Fluorophore Reference Table

| Dye ID | Common Name | Added MW (Da) | $\lambda_{\text{ex}}$ (nm) | $\lambda_{\text{em}}$ (nm) | $\varepsilon_{\text{max}}$ ($\text{M}^{-1}\text{cm}^{-1}$) | $\text{CF}_{260}$ | $\text{CF}_{280}$ | Fluorophore Channel |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FAM** | 6-FAM | 537.5 | 495 | 520 | 75,000 | 0.30 | 0.17 | Green (FITC) |
| **Cy3** | Cyanine 3 | 767.0 | 550 | 570 | 150,000 | 0.08 | 0.05 | Orange-Red (TRITC) |
| **Cy5** | Cyanine 5 | 793.0 | 650 | 670 | 250,000 | 0.05 | 0.05 | Far-Red (Cy5) |
| **AF488** | Alexa Fluor 488| 643.4 | 495 | 519 | 73,000 | 0.30 | 0.11 | Bright Green |
| **AF647** | Alexa Fluor 647| 1250.0 | 650 | 665 | 270,000 | 0.03 | 0.03 | Far-Red |
| **TexasRed**| Texas Red-X | 816.9 | 596 | 620 | 85,000 | 0.23 | 0.18 | Deep Red |
| **TAMRA** | TAMRA | 527.5 | 557 | 583 | 65,000 | 0.32 | 0.36 | Rose |
| **BHQ-1** | Black Hole Q 1 | 518.5 | 534 | — | 34,000 | 0.35 | 0.25 | Dark Quencher |

#### Degree of Labeling (DOL) Formulas

$$\text{DOL} = \frac{c_{\text{dye}}}{c_{\text{biomolecule}}} = \frac{A_{\text{max}} \cdot \varepsilon_{\text{biomolecule}}}{(A_{260/280} - A_{\text{max}} \cdot \text{CF}) \cdot \varepsilon_{\text{dye}}}$$

Live formulas:
- **Corrected Biomolecule Absorbance (`B22`)**: `=B21-(B20*B18)`
- **Biomolecule Concentration (µM) (`B23`)**: `=(B22/B19)*1000000`
- **Dye Concentration (µM) (`B24`)**: `=(B20/B17)*1000000`
- **Degree of Labeling (DOL) (`B25`)**: `=B24/B23` (Optimal single-label oligo range: $0.8\text{--}1.2$).

---

### Sheet 7: `Ecoli_Growth_Optimization`

Models bacterial culture kinetics, generation times, induction planning, plasmid copy numbers, and recombinant protein yields.

#### 1. Growth Kinetics Formulas

- **Required Doublings ($n$) (`B13`)**: `=LOG(B6/B5, 2)` (where `B5` = Initial $\text{OD}_{600}$, `B6` = Target $\text{OD}_{600}$)
- **Time to Induction (Minutes) (`B14`)**: `=B13*B9` ($n \times \text{doubling time } t_d$)
- **Time to Induction (Hours) (`B15`)**: `=B14/60`
- **Cell Count at Induction (`B16`)**: `=B6*800000000` (based on $8.0 \times 10^8\text{ cells/mL per } 1.0\text{ }\text{OD}_{600}$)
- **Total Culture Biomass (`B17`)**: `=B16*B10` ($\text{cells/mL} \times \text{volume in mL}$)

#### 2. Yield Projections

- **Theoretical Plasmid Yield (µg) (`B22`)**:
  ```excel
  =(B17*B20*1853916)/(6.02214e23)*1e6
  ```
  Where `B17` = Total cells, `B20` = Copy number per cell (e.g., $600$ for pUC), and `1853916` is the molecular weight of a $3,000\text{ bp}$ plasmid.
- **Column Kit Recovery (µg) (`B23`)**: `=B22*0.55` (modeling 55% silica-membrane binding efficiency).
- **Recombinant Protein Yield (mg) (`B26`)**: `=(B10*B6*0.150)*(B25/100)` (based on $150\text{ mg/L total protein per } 1.0\text{ }\text{OD}_{600}$ and `B25` expression percentage).
- **Molar Quantity (nmol) (`B27`)**: `=(B26*1000/B24)*1000`

---

## 3. Batch Processing Sequence Tables (`batch_process_excel`)

The `batch_process_excel` engine processes multi-row sequence tables from `.xlsx` files without writing custom parsing scripts.

### Input File Specification

The input Excel sheet should organize sequence records starting at Row 2 (Row 1 reserved for headers):
- **Column A**: Identifier / Clone Name (e.g., `Oligo_Fwd_1`)
- **Column B**: Raw sequence string (DNA, RNA, or amino acids)
- **Column C**: Molecule Type (`dna`, `rna`, `protein`, or `ssdna`)

### CLI Execution

```bash
biolabcalc batch-excel -i input_sequences.xlsx -o analyzed_sequences.xlsx
```

### Python API Usage

```python
import biolabcalc as blc

output_workbook = blc.batch_process_excel(
    input_path="input_sequences.xlsx",
    output_path="analyzed_sequences.xlsx"
)
print(f"Batch processing complete: {output_workbook}")
```

### Output Columns Generated

| Col | Header Name | Computed Property |
| :--- | :--- | :--- |
| **A** | Row | Sequential index |
| **B** | Identifier | Sample or clone name |
| **C** | Type | Normalized molecule type (`DNA`, `RNA`, `Protein`) |
| **D** | Sequence | Validated uppercase sequence string |
| **E** | Length | Sequence length in nucleotides (nt) or residues (aa) |
| **F** | MW (Da) | Average molecular weight in Daltons |
| **G** | GC (%) | Guanine-Cytosine percentage (nucleic acids) |
| **H** | Extinction Coeff | Molar extinction coefficient $\varepsilon$ ($\text{M}^{-1}\text{cm}^{-1}$) |
| **I** | 100 ng Moles (pmol) | Molar quantity represented by 100 ng of sample |

---

## 4. Exporting Analysis Objects (`export_analysis_to_excel`)

Python calculation results can be exported directly into a multi-tab workbook using `export_analysis_to_excel`.

```python
import biolabcalc as blc

# 1. Run reactions
ivt_res = blc.calculate_ivt_yield(
    rna_seq="GGGAGACCCAAGCUGGCCUUGAUCCAG",
    reaction_volume_ul=20.0,
    measured_yield_ug=48.5
)

pcr_res = blc.calculate_pcr_kinetics(
    amplicon_len_bp=850,
    template_ng=10.0,
    cycles=30
)

prot_res = blc.quantify_protein_a280(
    seq="MKWVTFISLLLLFSSAYSRGVI",
    a280_absorbance=0.742,
    volume_ml=2.5
)

# 2. Export all results to a single styled workbook
blc.export_analysis_to_excel(
    output_path="Campaign_Summary.xlsx",
    ivt_results=[ivt_res],
    pcr_results=[pcr_res],
    protein_results=[prot_res]
)
```

Each analytical domain is written to its own worksheet (`IVT_Results`, `PCR_Results`, `Protein_Results`, `Designed_Primers`) with styled Navy-and-White table headers, borders, and automatic column widths.
