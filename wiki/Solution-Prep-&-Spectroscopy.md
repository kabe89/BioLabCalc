# Solution Preparation & Spectroscopy

The **Solution Preparation & Spectroscopy** module delivers high-accuracy spectrophotometric modeling, automated standard solution formulations, and diagnostic impurity assessments. It bridges theoretical quantum biochemistry with everyday bench pipetting, empowering researchers to prepare micro-molar standardized stocks, predict optical density (OD) across multiple optical pathlengths, and diagnose chemical contaminants in UV-Vis absorption spectra.

---

## 1. Dilution Calculations ($C_1 V_1 = C_2 V_2$)

At the bench, stock solutions must frequently be diluted to precise operational concentrations. BioLabCalc provides a unit-aware, multi-variable solver for the classic conservation-of-mass dilution law:

$$C_1 \cdot V_1 = C_2 \cdot V_2$$

where:
- $C_1$: Initial stock concentration.
- $V_1$: Volume of initial stock required.
- $C_2$: Target final working concentration.
- $V_2$: Target final total volume.

### 1.1 Solving for Missing Variables

Given any three parameters, BioLabCalc algebraically determines the fourth variable and computes the exact volume of diluent buffer required:

$$V_{\text{diluent}} = V_2 - V_1$$

$$\begin{aligned}
C_1 &= \frac{C_2 \cdot V_2}{V_1} &\quad V_1 &= \frac{C_2 \cdot V_2}{C_1} \\
C_2 &= \frac{C_1 \cdot V_1}{V_2} &\quad V_2 &= \frac{C_1 \cdot V_1}{C_2}
\end{aligned}$$

The solver automatically parses human-readable metric strings across volume dimensions ($\text{L}$, $\text{mL}$, $\mu\text{L}$, $\text{nL}$) and concentration dimensions ($\text{M}$, $\text{mM}$, $\mu\text{M}$, $\text{nM}$, $\text{pM}$, or $\text{mg/mL}$, $\mu\text{g/}\mu\text{L}$, $\text{ng/}\mu\text{L}$), normalizing all terms before computation.

---

## 2. Theoretical Absorbance & Beer-Lambert Physics

Ultraviolet-visible (UV-Vis) quantification of biomolecules is governed by the Beer-Lambert Law:

$$A_{\lambda} = \epsilon_{\lambda} \cdot c \cdot l$$

where:
- $A_{\lambda}$: Absorbance (optical density, OD) at wavelength $\lambda$ (unitless or Absorbance Units, $\text{AU}$).
- $\epsilon_{\lambda}$: Molar absorption coefficient (molar extinction coefficient) in $\text{M}^{-1}\text{ cm}^{-1}$.
- $c$: Molar concentration of the analyte ($\text{mol/L}$).
- $l$: Optical pathlength of the sample cell ($\text{cm}$).

### 2.1 Microvolume Spectrophotometry Pathlength Scaling

Standard transmission cuvettes feature an internal pathlength of $l = 1.0\text{ cm}$ ($10\text{ mm}$). Modern microvolume instruments (e.g., Thermo Fisher NanoDrop™) utilize liquid surface tension to draw a liquid column across pathlengths of $1.0\text{ mm}$ ($0.1\text{ cm}$) or $0.2\text{ mm}$ ($0.02\text{ cm}$).

The physical absorbance measured across a $1\text{ mm}$ pathlength is one-tenth of the normalized $10\text{ mm}$ absorbance:

$$A_{10\text{mm}} = 10 \times A_{1\text{mm}}$$

BioLabCalc reports both the standard $10\text{ mm}$-normalized absorbance and the raw $1\text{ mm}$ instrument absorbance to prevent confusion when verifying instrument performance.

---

## 3. Nearest-Neighbor Extinction Coefficients

A common source of error in nucleic acid quantification is relying on static conversion factors (e.g., $1\text{ OD}_{260} = 40\text{ }\mu\text{g/mL}$ for RNA or $33\text{ }\mu\text{g/mL}$ for ssDNA). The actual molar absorptivity at $260\text{ nm}$ ($\epsilon_{260}$) depends on base composition and base-stacking interactions (hypochromicity).

BioLabCalc computes sequence-specific extinction coefficients using the **Nearest-Neighbor (NN) Model**:

$$\epsilon_{260} = \sum_{i=1}^{N-1} \epsilon_{\text{NN}}(b_i b_{i+1}) - \sum_{i=2}^{N-1} \epsilon_{\text{mono}}(b_i)$$

where:
- $\epsilon_{\text{NN}}(b_i b_{i+1})$ is the extinction coefficient of the dinucleotide pair at positions $i$ and $i+1$.
- $\epsilon_{\text{mono}}(b_i)$ is the individual monomer extinction coefficient subtracted for internal bases to correct for double-counting.

### 3.1 RNA Nearest-Neighbor Parameters (Puglisi & Tinoco, 1989)

Reference: *Puglisi, J. D., & Tinoco, I. (1989). Absorbance properties for calculating RNA concentration. Methods in Enzymology, 180, 304–325.*

#### Dinucleotide Extinction Coefficients ($\text{M}^{-1}\text{ cm}^{-1}$ at $260\text{ nm}$)

| 5' \ 3' | A | C | G | U |
| :---: | :---: | :---: | :---: | :---: |
| **A** | $27,400$ | $21,000$ | $25,000$ | $24,000$ |
| **C** | $21,000$ | $14,200$ | $17,800$ | $16,200$ |
| **G** | $25,200$ | $17,400$ | $21,600$ | $21,200$ |
| **U** | $24,600$ | $17,200$ | $20,000$ | $19,600$ |

#### Monomer Extinction Coefficients ($\text{M}^{-1}\text{ cm}^{-1}$)

$$\epsilon_{\text{A}} = 15,400 \quad \epsilon_{\text{C}} = 7,200 \quad \epsilon_{\text{G}} = 11,500 \quad \epsilon_{\text{U}} = 9,900$$

---

### 3.2 DNA Nearest-Neighbor Parameters (Cavaluzzi & Borer, 2004)

Reference: *Cavaluzzi, M. J., & Borer, P. N. (2004). Revised UV extinction coefficients for nucleoside-5'-monophosphates and unpaired DNA species. Nucleic Acids Research, 32(1), e13.*

#### Dinucleotide Extinction Coefficients ($\text{M}^{-1}\text{ cm}^{-1}$ at $260\text{ nm}$)

| 5' \ 3' | A | C | G | T |
| :---: | :---: | :---: | :---: | :---: |
| **A** | $27,400$ | $21,200$ | $25,000$ | $22,800$ |
| **C** | $21,200$ | $14,600$ | $18,000$ | $15,200$ |
| **G** | $25,200$ | $17,600$ | $21,600$ | $20,000$ |
| **T** | $23,400$ | $16,200$ | $19,000$ | $16,800$ |

#### Monomer Extinction Coefficients ($\text{M}^{-1}\text{ cm}^{-1}$)

$$\epsilon_{\text{A}} = 15,400 \quad \epsilon_{\text{C}} = 7,300 \quad \epsilon_{\text{G}} = 11,700 \quad \epsilon_{\text{T}} = 8,800$$

---

### 3.3 Double-Stranded DNA (dsDNA) Duplex Hypochromicity

When complementary single strands anneal to form a Watson-Crick B-DNA double helix, $\pi-\pi$ orbital overlap between stacked base pairs restricts electronic transitions, inducing **hypochromism** (a $\sim20\%$ decrease in UV absorbance). BioLabCalc models duplex extinction as:

$$\epsilon_{260, \text{dsDNA}} = 0.80 \times \left( \epsilon_{260, \text{sense}} + \epsilon_{260, \text{antisense}} \right)$$

where $\epsilon_{260, \text{sense}}$ and $\epsilon_{260, \text{antisense}}$ are calculated via the single-strand nearest-neighbor parameters.

---

## 4. Standardized Solution Formulation (`prepare_standard_solution`)

Preparing working stocks of synthetic oligos, sgRNAs, or mRNA standards requires aligning target molarity ($\mu\text{M}$), target volume ($\mu\text{L}$), and sequence-specific extinction properties.

### 4.1 Mass and Pipetting Derivations

1. **Total Moles Required ($n$):**
   $$n\text{ (nmol)} = C_{\text{target}}\text{ (}\mu\text{M)} \times V_{\text{target}}\text{ (}\mu\text{L)} \times 10^{-3}$$

2. **Total Mass Required ($m$):**
   $$m\text{ (}\mu\text{g)} = n\text{ (nmol)} \times MW\text{ (g/mol)} \times 10^{-3}$$
   $$m\text{ (ng)} = m\text{ (}\mu\text{g)} \times 10^{3}$$

3. **Physical Mass Concentration ($C_{\text{actual}}$):**
   $$C_{\text{actual}}\text{ (ng/}\mu\text{L)} = \frac{m\text{ (ng)}}{V_{\text{target}}\text{ (}\mu\text{L)}}$$

4. **Sequence-Specific Conversion Factor:**
   $$\text{Factor}_{\text{seq}}\text{ (}\mu\text{g/mL per OD}_{260}\text{)} = \frac{MW}{\epsilon_{260}} \times 1000$$

5. **Expected Sequence-Specific NanoDrop $A_{260}$:**
   $$A_{260, \text{seq}} = \epsilon_{260} \times \left( C_{\text{target}} \times 10^{-6} \right) \times 1.0\text{ cm}$$

6. **Generic Instrument Discrepancy:**
   Standard spectrophotometer software applies a static factor ($\text{Factor}_{\text{generic}} = 40.0\text{ }\mu\text{g/mL}$ for RNA, $50.0\text{ }\mu\text{g/mL}$ for dsDNA). The value displayed on the instrument screen will be:
   $$C_{\text{displayed}}\text{ (ng/}\mu\text{L)} = A_{260, \text{seq}} \times \text{Factor}_{\text{generic}}$$
   BioLabCalc explicitly predicts this discrepancy, allowing researchers to verify sample concentrations without misattributing sequence-specific hypochromicity to pipetting error.

7. **Dilution from Concentrated Stock:**
   When `stock_conc_ng_ul` is supplied:
   $$V_{\text{stock}} = \frac{m\text{ (ng)}}{C_{\text{stock}}\text{ (ng/}\mu\text{L)}} \qquad V_{\text{buffer}} = V_{\text{target}} - V_{\text{stock}}$$

---

## 5. Purity Ratios & Contaminant Diagnostics (`assess_nanodrop_purity`)

NanoDrop UV-Vis spectra provide qualitative and quantitative insight into sample purity via the $A_{260}/A_{280}$ and $A_{260}/A_{230}$ absorbance ratios.

```
 Absorbance
   ▲
   │        Nucleic Acid Peak (260 nm)
   │               ╭───╮
   │      Phenol   │   │
   │      (270nm)  │   │
   │        ╭──╮  │   │
   │  Salts │  │  │   │   Aromatic Proteins (280 nm)
   │ (230nm)│  │  │   │        ╭──╮
   │   ╭─╮  │  │  │   │        │  │
───┴───┴─┴──┴──┴──┴───┴────────┴──┴────────► Wavelength (nm)
      230        260   270    280
```

### 5.1 Canonical Benchmark Purity Ratios

| Sample Type | Canonical $A_{260}/A_{280}$ | Canonical $A_{260}/A_{230}$ | Primary Molecular Basis |
| :--- | :---: | :---: | :--- |
| **Pure RNA** | $\mathbf{2.00 \pm 0.10}$ | $\mathbf{2.00 - 2.20}$ | Higher ratio than DNA due to higher uracil/guanine extinction at $260\text{ nm}$ |
| **Pure DNA** | $\mathbf{1.80 \pm 0.10}$ | $\mathbf{2.00 - 2.20}$ | Lower ratio due to thymine absorbance spectrum |

---

### 5.2 Contaminant Diagnostic Matrix

BioLabCalc classifies spectral anomalies into actionable diagnoses using an automated rules engine:

| Contaminant Species | Spectral Signature | Ratio Impact | Biochemical Consequence | Corrective Action |
| :--- | :--- | :--- | :--- | :--- |
| **Aromatic Proteins** (BSA, Cellular Lysate, RNase A) | Absorbance peak at $280\text{ nm}$ due to Trp, Tyr, and cystine | $A_{260}/A_{280} < 1.70$ (RNA)<br>$A_{260}/A_{280} < 1.60$ (DNA) | Nuclease degradation risk; inhibits RT-PCR and cDNA synthesis | Digest with Proteinase K ($55^\circ\text{C}$), followed by acid phenol-chloroform or silica column re-isolation. |
| **Phenol** (TRIzol®, QIAzol®, PCI) | Absorbance maximum at $270\text{ nm}$ with significant $230\text{ nm}$ shoulder | **Severe depression:**<br>$A_{260}/A_{280} < 1.60$<br>$A_{260}/A_{230} < 1.40$ | Falsely elevates apparent $A_{260}$; completely inhibits polymerases and cell culture transfection | Perform chloroform:isoamyl alcohol back-extraction to strip phenol, followed by ethanol or LiCl precipitation. |
| **Chaotropic Salts** (Guanidinium HCl, Guanidinium Thiocyanate) | High absorption below $240\text{ nm}$, peaking at $\sim230\text{ nm}$ | Normal $A_{260}/A_{280}$ ($1.8–2.0$)<br>**Severely low:**<br>$A_{260}/A_{230} < 1.50$ | Denatures enzymes; inhibits RT-qPCR enzymes and T7 transcription | Wash silica spin column with additional $80\%$ ethanol wash buffer; wash precipitation pellets thoroughly with $70\%$ ethanol. |
| **EDTA** (Chelating Agent) | Broad UV absorption at $220–235\text{ nm}$ | $A_{260}/A_{230} < 1.80$ | Chelates required divalent cations ($\text{Mg}^{2+}$, $\text{Mn}^{2+}$), shutting down downstream enzymatic reactions | Desalt via centrifugal dialysis (Amicon, Microcon) or ethanol-salt precipitation. |
| **Polysaccharides / Glycogen / Carbohydrates** | Turbidity and light scattering across $220–240\text{ nm}$ | $A_{260}/A_{230} < 1.70$ | Interferes with pipetting viscosity and non-specifically inhibits ligations and PCR | Perform CTAB/NaCl extraction or selective lithium chloride ($\text{LiCl}$) precipitation. |
| **Buffer Drift / Acidic pH Shift** | Hypochromic shift in nucleic acid absorbance | $A_{260}/A_{280}$ shifts down by $\sim0.2$ in acidic pure $\text{H}_2\text{O}$ | Falsely indicates protein contamination due to unbuffered solvent | Blank and measure samples in $1\text{X TE}$ buffer ($\text{pH } 7.5–8.0$) or $10\text{ mM Tris-HCl}$. |

---

### 5.3 Corrected Concentration Estimation

When protein carryover is detected ($A_{260}/A_{280} < 1.75$ for RNA), BioLabCalc estimates the true nucleic acid absorbance by adjusting for aromatic protein absorption at $260\text{ nm}$:

$$A_{260, \text{corrected}} = \max\left(0, A_{260} - 0.15 \cdot A_{280}\right)$$

$$C_{\text{corrected}}\text{ (ng/}\mu\text{L)} = A_{260, \text{corrected}} \times \text{Factor}_{\text{generic}}$$

This correction provides researchers with a more realistic yield estimate prior to re-purification.

---

### 5.4 Below Detection Limit & Water Blank Safeguard

When $A_{260} < 0.02\text{ AU}$ (representing a water blank, buffer reference, or sample below reliable spectrophotometric detection limits), `assess_nanodrop_purity` classifies the sample as `purity_status = "Below Detection Limit"`. It prevents false chemical contamination alarms by setting:
- `protein_contamination = False` (and `protein_contamination_risk = False`)
- `salt_or_solvent_contamination = False`
- `phenol_contamination_risk = False`

It returns a clean diagnostic message explaining that absorbance ratios are not statistically or biochemically meaningful at baseline noise levels.

---

## 6. Python API Reference

### 6.1 Dilution Calculations (`dilute`)

```python
from biolabcalc.easy import dilute

# Solve for required stock volume (V1)
result = dilute(
    c1="100 mM",      # Stock NTP concentration
    c2="25 mM",       # Desired working concentration
    v2="16 mL",       # Desired final volume
)
print(f"Stock Volume Needed (V1): {result['v1']} uL ({result['v1']/1000} mL)")
print(f"Diluent Needed: {result['diluent_needed']} uL ({result['diluent_needed']/1000} mL)")

# Solve for working concentration (C2)
res2 = dilute(c1="50X", v1="20 mL", v2="1000 mL")
print(f"Working Buffer Strength (C2): {res2['c2']}X")
```

### 6.2 Standardized Solution Formulation (`prepare_standard_solution`)

```python
from biolabcalc.spectroscopy import prepare_standard_solution

# Formulate a 4.0 µM standard solution of a 50-nt ssRNA in 500 µL
recipe = prepare_standard_solution(
    target_molarity_um=4.0,
    target_volume_ul=500.0,
    sequence="AUGGUGAGCAAGGGCGAGGAGCUGUUCACCGGGGUGGUGCCCAUCCUGGU",
    seq_type="rna",
    end_5="hydroxyl",
    stock_conc_ng_ul=850.0,  # Starting stock concentration
)

print(f"Molecular Weight: {recipe.molecular_weight:.2f} g/mol")
print(f"Nearest-Neighbor Extinction Coeff (e260): {recipe.sequence_extinction_coeff_260:,} M^-1 cm^-1")
print(f"Sequence-Specific Conversion Factor: {recipe.sequence_specific_conversion_factor:.2f} ug/mL per OD260")
print(f"Required Mass: {recipe.required_mass_ug:.3f} µg ({recipe.required_mass_ng:.1f} ng)")
print(f"Stock Volume Needed: {recipe.stock_volume_needed_ul:.2f} µL")
print(f"Buffer Volume Needed: {recipe.buffer_volume_needed_ul:.2f} µL")
print(f"Expected NanoDrop A260 (10 mm path): {recipe.expected_nanodrop_a260_sequence_specific:.3f} AU")
print(f"Expected NanoDrop A260 (1 mm path): {recipe.expected_nanodrop_a260_1mm:.4f} AU")
print(f"Expected Displayed Conc (Generic Mode): {recipe.expected_nanodrop_display_ng_ul_generic_mode:.2f} ng/µL")
```

### 6.3 NanoDrop Purity Assessment (`assess_nanodrop_purity`)

```python
from biolabcalc.spectroscopy import assess_nanodrop_purity

# Evaluate an RNA sample exhibiting phenol carryover
purity = assess_nanodrop_purity(
    a260=1.450,
    a280=0.980,
    a230=1.120,
    sample_type="rna",
)

print(f"Purity Status: {purity.purity_status}")
print(f"A260/A280 Ratio: {purity.a260_a280_ratio:.2f} (Target ~2.00)")
print(f"A260/A230 Ratio: {purity.a260_a230_ratio:.2f} (Target 2.00–2.20)")
print(f"Protein Contamination Detected: {purity.protein_contamination}")
print(f"Phenol Risk Detected: {purity.phenol_contamination_risk}")
print(f"Corrected A260: {purity.corrected_a260:.3f} AU")
print(f"Corrected Concentration: {purity.corrected_concentration_ng_ul:.1f} ng/µL")
print("\nDiagnostics:")
for diag in purity.diagnostic_feedback:
    print(f"- {diag}")
```

---

## 7. Command-Line Interface (CLI)

### 7.1 Dilution Calculator CLI (`biolabcalc dilute`)

```bash
# Calculate stock volume required to prepare 16 mL of 25 mM working stock from 100 mM
biolabcalc dilute -c1 "100 mM" -c2 "25 mM" -v2 "16 mL"

# Calculate target concentration after diluting 50 uL of 10 mg/mL BSA into 950 uL buffer
biolabcalc dilute -c1 "10 mg/ml" -v1 "50 uL" -v2 "1000 uL"
```

### 7.2 Solution Preparation CLI (`biolabcalc nanodrop`)

```bash
# Prepare a 2.5 µM solution of a synthetic DNA probe in 200 µL from a 500 ng/µL stock
biolabcalc nanodrop -m 2.5 -v 200 -s "GACTACAGCTAGCTAGCTAG" -t dna --stock 500.0

# Prepare 10 µM mRNA in 100 µL without a sequence (using estimated length of 1200 nt)
biolabcalc nanodrop -m 10.0 -v 100 -l 1200 -t rna --end5 triphosphate
```

### 7.3 NanoDrop Purity Assessment CLI (`biolabcalc purity`)

```bash
# Evaluate RNA absorbance readings
biolabcalc purity --a260 2.15 --a280 1.08 --a230 1.02 --type rna

# Evaluate plasmid DNA absorbance readings
biolabcalc purity --a260 0.85 --a280 0.46 --a230 0.41 --type dna
```
