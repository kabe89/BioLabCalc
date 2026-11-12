# Protein Quantification

The **Protein Quantification** module provides comprehensive analytical tools for determining protein concentration, calculating sequence-derived extinction coefficients, modeling direct UV absorbance at $280\text{ nm}$ and $205\text{ nm}$, and fitting colorimetric standard curves (BCA, Bradford, Lowry) with statistical regression.

---

## 1. Sequence-Based Extinction Coefficients ($\epsilon_{280}$)

Direct spectrophotometric quantification of proteins at $280\text{ nm}$ ($A_{280}$) is non-destructive, rapid, and does not consume standard curve reagents. However, its accuracy hinges upon knowing the protein's molar absorption coefficient ($\epsilon_{280}$), which is dictated by its aromatic amino acid composition.

### 1.1 The Pace & Gill/von Hippel Formulations

BioLabCalc calculates theoretical extinction coefficients using the consensus model established by Gill & von Hippel (1989) and refined by Pace et al. (1995):

$$\epsilon_{280} = \left( N_{\text{Trp}} \times 5500 \right) + \left( N_{\text{Tyr}} \times 1490 \right) + \left( N_{\text{cystine}} \times 125 \right) \quad (\text{M}^{-1}\text{ cm}^{-1})$$

where:
- $N_{\text{Trp}}$ is the number of tryptophan residues.
- $N_{\text{Tyr}}$ is the number of tyrosine residues.
- $N_{\text{cystine}}$ is the number of disulfide-bonded cystine pairs ($N_{\text{cystine}} = \lfloor N_{\text{oxidized Cys}} / 2 \rfloor$).

#### Physical Basis of Residue Absorptivity

| Residue | Structure / Chromophore | $\epsilon_{280}$ ($\text{M}^{-1}\text{ cm}^{-1}$) | Peak Wavelength ($\lambda_{\text{max}}$) | Biochemical Mechanism |
| :--- | :--- | :---: | :---: | :--- |
| **Tryptophan (Trp, W)** | Indole bicyclic ring | $\mathbf{5,500}$ | $280\text{ nm}$ | Dominant UV chromophore; sensitive to solvent polarity and local hydrophobic burial. |
| **Tyrosine (Tyr, Y)** | Phenolic ring | $\mathbf{1,490}$ | $274\text{ nm}$ | Significant absorption at $280\text{ nm}$; ionizes to phenolate at alkaline pH ($\text{pH} > 10$), shifting peak to $295\text{ nm}$. |
| **Cystine (Cys-S-S-Cys)** | Disulfide bridge | $\mathbf{125}$ | $250\text{ nm}$ | Disulfide bond orbital transitions exhibit a broad tail extending into $280\text{ nm}$. |
| **Free Cysteine (Cys, C)** | Thiol ($-\text{SH}$) | $\mathbf{0}$ | $< 230\text{ nm}$ | Negligible contribution at $280\text{ nm}$. |
| **Phenylalanine (Phe, F)** | Benzene ring | $\sim0$ | $257\text{ nm}$ | Fine vibrational structure in far-UV; negligible contribution at $280\text{ nm}$ ($\epsilon_{280} < 10\text{ M}^{-1}\text{ cm}^{-1}$). |

### 1.2 Native vs. Denatured State Behavior

The Pace parameters are empirically calibrated in $6.0\text{ M}$ guanidine hydrochloride ($\text{GdnHCl}$), where the polypeptide chain is completely unfolded and all chromophores are uniformly exposed to solvent. 

In native folded proteins:
- Chromophores buried inside a hydrophobic core experience local refractive index shifts that can alter $\epsilon_{280}$ by $\pm 5–10\%$.
- For most folded globular proteins, the unfolded prediction remains accurate within $\pm 5\%$.
- If a protein lacks Trp and Tyr residues ($\epsilon_{280} = 0$), $A_{280}$ quantification cannot be used; the sample must be quantified via far-UV peptide backbone absorbance ($A_{205}$) or colorimetric assays.

### 1.3 Mass Extinction Coefficient ($A_{280}^{1\text{ mg/mL}}$)

In laboratory practice, extinction is often reported as the absorbance of a $0.1\%\text{ w/v}$ ($1.0\text{ mg/mL}$) solution across a $1.0\text{ cm}$ pathlength:

$$A_{280}^{1\text{ mg/mL}} = \frac{\epsilon_{280}}{MW} \quad \left(\text{AU}\cdot\text{mL}\cdot\text{mg}^{-1}\cdot\text{cm}^{-1}\right)$$

---

## 2. Direct $A_{280}$ Beer-Lambert Quantification

Once $\epsilon_{280}$ and $MW$ are established, sample concentration and total yield are computed directly from measured absorbance:

### 2.1 Governing Equations

1. **Molar Concentration ($c_{\text{molar}}$):**
   $$c_{\text{molar}}\text{ (M)} = \frac{A_{280} \times \text{Dilution Factor}}{\epsilon_{280} \times l\text{ (cm)}}$$

2. **Mass Concentration ($c_{\text{mass}}$):**
   $$c_{\text{mass}}\text{ (mg/mL)} = c_{\text{molar}}\text{ (M)} \times MW\text{ (g/mol)} = \frac{A_{280} \times \text{Dilution Factor}}{A_{280}^{1\text{ mg/mL}} \times l\text{ (cm)}}$$
   $$c_{\text{mass}}\text{ (}\mu\text{g/mL)} = c_{\text{mass}}\text{ (mg/mL)} \times 1000$$

3. **Total Absolute Yield:**
   $$\text{Yield (mg)} = c_{\text{mass}}\text{ (mg/mL)} \times V_{\text{sample}}\text{ (mL)}$$
   $$\text{Yield (}\mu\text{g)} = \text{Yield (mg)} \times 1000 \qquad \text{Yield (ng)} = \text{Yield (}\mu\text{g)} \times 1000$$

---

## 3. Far-UV Peptide Backbone Quantification ($A_{205}$)

When proteins or synthetic peptides contain few or no aromatic residues (e.g., collagen fragments, actin-binding peptides, recombinant tags), $A_{280}$ measurements fail. In these scenarios, BioLabCalc models far-UV absorption at $205\text{ nm}$ ($A_{205}$).

### 3.1 Physical Basis & The Anthis-Clore Model

At $205\text{ nm}$, absorption is dominated by the repeating **peptide bonds** ($-\text{CO}-\text{NH}-$) of the polypeptide backbone, with minor contributions from amino acid side chains.

BioLabCalc implements the sequence-specific model of **Anthis & Clore (2013)** (*Protein Science, 22*(6), 851–858):

$$\epsilon_{205} = (N - 1) \cdot \epsilon_{\text{backbone}} + \sum_{j=1}^{20} \left( n_j \cdot \epsilon_{205, \text{side-chain}, j} \right) \quad (\text{M}^{-1}\text{ cm}^{-1})$$

where:
- $N$ is total amino acid residue length (so $N-1$ is the number of peptide bonds).
- $\epsilon_{\text{backbone}} = 2,780\text{ M}^{-1}\text{ cm}^{-1}$ per peptide linkage.

#### Side-Chain Extinction Coefficients at $205\text{ nm}$ ($\epsilon_{205}$)

| Residue | Side Chain Contribution ($\text{M}^{-1}\text{ cm}^{-1}$) | Residue | Side Chain Contribution ($\text{M}^{-1}\text{ cm}^{-1}$) |
| :---: | :---: | :---: | :---: |
| **Trp (W)** | $20,400$ | **Cys (C)** | $690$ |
| **Phe (F)** | $8,600$ | **Lys (K)** | $110$ |
| **Tyr (Y)** | $5,400$ | **Glu (E)** | $80$ |
| **His (H)** | $5,200$ | **Asp (D)** | $58$ |
| **Met (M)** | $1,830$ | **Gln (Q)** | $30$ |
| **Arg (R)** | $1,350$ | **Asn (N)** | $30$ |
| **All Others (A, G, I, L, P, S, T, V)** | $0$ | | |

### 3.2 Comparison: Anthis-Clore vs. Scopes Empirical Approximation

Before sequence-specific algorithms, Scopes (1974) proposed an empirical relationship for generic mixed proteins:

$$c\text{ (mg/mL)} \approx \frac{A_{205}}{31}$$

The Anthis-Clore sequence-specific algorithm replaces this rough approximation, reducing quantification errors from $>30\%$ down to $<2\%$.

### 3.3 Critical Buffer Compatibility Warnings for $A_{205}$

Because $205\text{ nm}$ lies in the deep ultraviolet spectrum, many common biochemical buffer components absorb strongly, generating severe background noise:

| Buffer / Additive | Compatibility at $205\text{ nm}$ | Recommendation |
| :--- | :---: | :--- |
| **Potassium / Sodium Phosphate** ($10–50\text{ mM}$) | **Excellent** | Ideal quantification buffer. Near-zero UV absorbance at $205\text{ nm}$. |
| **Water ($\text{ddH}_2\text{O}$)** | **Excellent** | Ideal for purified synthetic peptides. |
| **Tris-HCl** | **Poor** | Tris absorbs significantly at $< 215\text{ nm}$. Keep $\le 10\text{ mM}$ or blank carefully. |
| **DTT / $\beta$-Mercaptoethanol** | **Incompatible** | Thiol reducing agents absorb heavily at $205\text{ nm}$. Use TCEP ($\le 0.5\text{ mM}$) instead. |
| **Detergents (Triton X-100, NP-40)** | **Incompatible** | Aromatic rings saturate the detector. Switch to octyl glucoside or polysorbate. |

---

## 4. Colorimetric Assay Standard Curves (BCA, Bradford, Lowry)

When samples contain interfering buffer components, colorimetric assays are the standard method for quantification. BioLabCalc features a standard curve fitting engine that performs regression analysis, calculates coefficients of determination ($R^2$), and interpolates unknown sample concentrations.

```
 Absorbance
   ▲
   │                           ╭── Standard Points
   │                     *    /
   │                 *   ┌───┘
   │             *       │   Interpolated Unknown
   │         *           ▼
   │     *          [Sample A]
   │  *   
───┴─────────────────────────────► Concentration (µg/mL)
```

### 4.1 Assay Mechanism Comparison

| Feature | Bicinchoninic Acid (BCA) | Bradford Assay | Lowry Assay |
| :--- | :--- | :--- | :--- |
| **Reaction Mechanism** | Biuret reduction ($\text{Cu}^{2+} \to \text{Cu}^+$) by peptide bonds, followed by $\text{Cu}^+$ chelation with BCA. | Coomassie Brilliant Blue G-250 binds basic (Arg, Lys) and aromatic residues, shifting dye absorbance. | Biuret reaction followed by reduction of Folin-Ciocalteu phosphomolybdic/tungstic acid. |
| **Detection Wavelength** | $\mathbf{562\text{ nm}}$ (Purple complex) | $\mathbf{595\text{ nm}}$ (Blue complex) | $\mathbf{750\text{ nm}}$ (Blue complex) |
| **Dynamic Range** | $20 - 2,000\text{ }\mu\text{g/mL}$ (Micro: $5 - 250\text{ }\mu\text{g/mL}$) | $100 - 1,500\text{ }\mu\text{g/mL}$ (Micro: $1 - 25\text{ }\mu\text{g/mL}$) | $10 - 1,000\text{ }\mu\text{g/mL}$ |
| **Detergent Tolerance** | **High** (Compatible with up to $5\%$ SDS, Triton X-100, NP-40) | **Zero** (Incompatible with detergents; precipitates dye) | **Moderate** (Tolerates low detergents) |
| **Reducing Agent Tolerance** | **Incompatible** (DTT, $\beta$-ME reduce $\text{Cu}^{2+}$ directly, yielding false positives) | **High** (Compatible with $5\text{ mM}$ DTT, $\beta$-ME) | **Incompatible** (Reducing agents reduce Folin reagent) |
| **Incubation Time** | $30\text{ min}$ at $37^\circ\text{C}$ (or $60^\circ\text{C}$ for sensitivity) | $5\text{ min}$ at room temperature | $30\text{ min}$ at room temperature |

---

### 4.2 Linear Regression Formulation

Standard concentration ($x_i$) and measured absorbance ($y_i$) pairs are modeled via ordinary least-squares:

$$y = m \cdot x + b$$

where:
- $m$: Slope of the standard curve ($\text{AU}\cdot\mu\text{g}^{-1}\cdot\text{mL}$).
- $b$: Y-intercept (reagent blank absorbance).

#### Parameter Estimation

$$\bar{x} = \frac{1}{n} \sum_{i=1}^{n} x_i \qquad \bar{y} = \frac{1}{n} \sum_{i=1}^{n} y_i$$

$$SS_{xx} = \sum_{i=1}^{n} (x_i - \bar{x})^2 \qquad SS_{xy} = \sum_{i=1}^{n} (x_i - \bar{x})(y_i - \bar{y}) \qquad SS_{yy} = \sum_{i=1}^{n} (y_i - \bar{y})^2$$

$$m = \frac{SS_{xy}}{SS_{xx}} \qquad b = \bar{y} - m \cdot \bar{x}$$

#### Goodness of Fit ($R^2$)

$$R^2 = \frac{(SS_{xy})^2}{SS_{xx} \cdot SS_{yy}}$$

A valid standard curve requires $R^2 \ge 0.990$ for quantitative biological assays.

---

### 4.3 Quadratic Polynomial Modeling (Non-Linear Curves)

At concentrations $>1,000\text{ }\mu\text{g/mL}$, both BCA and Bradford assays experience dye or copper depletion, leading to curve flattening. BioLabCalc models non-linear responses using a second-order polynomial:

$$y = a \cdot x^2 + b \cdot x + c$$

When interpolating unknown samples, the concentration $x$ is extracted via the positive quadratic root:

$$x = \frac{-b + \sqrt{b^2 - 4a(c - y)}}{2a}$$

---

### 4.4 Unknown Sample Interpolation & Dilution Scaling

Given an unknown sample absorbance $y_{\text{obs}}$, concentration is calculated by solving the inverse calibration function:

$$c_{\text{apparent}}\text{ (}\mu\text{g/mL)} = \max\left(0, \frac{y_{\text{obs}} - b}{m}\right)$$

$$c_{\text{actual}}\text{ (}\mu\text{g/mL)} = c_{\text{apparent}} \times \text{Dilution Factor}$$

$$c_{\text{actual}}\text{ (mg/mL)} = \frac{c_{\text{actual}}\text{ (}\mu\text{g/mL)}}{1000}$$

$$\text{Molarity } (\mu\text{M}) = \left( \frac{c_{\text{actual}}\text{ (mg/mL)}}{MW\text{ (g/mol)}} \right) \times 10^6$$

---

## 5. Python API Reference

### 5.1 Direct $A_{280}$ Quantification (`quantify_protein_a280`)

```python
from biolabcalc.protein import (
    calculate_extinction_coefficient,
    quantify_protein_a280,
)

# Bovine Serum Albumin (BSA) precursor sequence
bsa_seq = (
    "MKWVTFISLLLLFSSAYSRGVFRRDTHKSEIAHRFKDLGEEHFKGLVLIAFSQYLQQCPFDEHVKLVNELTEFAKTC"
    "VADESHAGCEKSLHTLFGDELCKVASLRETYGDMADCCEKQEPERNECFLSHKDDSPDLPKLKPDPNTLCDEFKADEK"
    "KFWGKYLYEIARRHPYFYAPELLYYANKYNGVFQECCQAEDKGACLLPKIETMREKVLASSARQRLRCASIQKFGERA"
    "LKAWSVARLSQKFPKAEFVEVTKLVTDLTKVHKECCHGDLLECADDRADLAKYICDNQDTISSKLKECCDKPLLEKSH"
    "CIAEVEKDAIPENLPPLTADFAEDKDVCKNYQEAKDAFLGSFLYEYSRRHPEYAVSVLLRLAKEYEATLEECCAKDDP"
    "HACYSTVFDKLKHLVDEPQNLIKQNCDQFEKLGEYGFQNALIVRYTRKVPQVSTPTLVEVSRSLGKVGTRCCTKPESE"
    "RMPCTEDYLSLILNRLCVLHEKTPVSEKVTKCCTESLVNRRPCFSALTPDETYVPKAFDEKLFTFHADICTLPDTEKQ"
    "IKKQTALVELLKHKPKATEEQLKTVMENFVAFVDKCCAADDKEACFAVEGPKLVVSTQTALA"
)

# 1. Calculate Sequence Extinction Coefficient
coeff = calculate_extinction_coefficient(bsa_seq, oxidized_cysteines=34)
print(f"Molecular Weight: {coeff.molecular_weight:.2f} Da")
print(f"Extinction Coefficient (e280): {coeff.extinction_coeff_m_cm:,} M^-1 cm^-1")
print(f"A280 for 1 mg/mL: {coeff.a280_1mg_ml:.3f} AU")
print(f"Tryptophans: {coeff.tryptophan_count}, Tyrosines: {coeff.tyrosine_count}, Disulfides: {coeff.cystine_pairs}")

# 2. Quantify Protein Sample from A280
yield_res = quantify_protein_a280(
    seq=bsa_seq,
    a280_absorbance=0.667,
    volume_ml=5.0,
    pathlength_cm=1.0,
    dilution_factor=2.0,  # 1:2 dilution prior to measurement
    oxidized_cysteines=34,
    sample_name="Purified_BSA_Batch_4",
)

print(f"\nSample: {yield_res.sample_name}")
print(f"Concentration: {yield_res.concentration_mg_ml:.3f} mg/mL ({yield_res.concentration_ug_ml:.1f} µg/mL)")
print(f"Molarity: {yield_res.molarity_um:.2f} µM")
print(f"Total Yield: {yield_res.total_yield_mg:.3f} mg ({yield_res.total_yield_ug:.1f} µg)")
```

### 5.2 Far-UV $A_{205}$ Peptide Backbone Quantification (`quantify_protein_a205`)

```python
from biolabcalc.protein import quantify_protein_a205, calculate_protein_e205

# Synthetic peptide lacking aromatic residues (No Trp, No Tyr)
peptide_seq = "MAGKSSDSEENKKVIVVK"

e205 = calculate_protein_e205(peptide_seq)
print(f"Calculated e205: {e205:,} M^-1 cm^-1")

pep_res = quantify_protein_a205(
    seq=peptide_seq,
    a205_absorbance=0.450,
    volume_ml=1.5,
    pathlength_cm=1.0,
    dilution_factor=1.0,
    sample_name="Synthetic_Peptide_P1",
)

print(f"Concentration: {pep_res.concentration_mg_ml:.4f} mg/mL")
print(f"Total Yield: {pep_res.total_yield_ug:.2f} µg")
```

### 5.3 Colorimetric Standard Curve Fitting (`fit_standard_curve`)

```python
from biolabcalc.protein import fit_standard_curve

# BCA Assay BSA Standard Curve (Concentration in µg/mL vs A562)
standards = [
    (0.0, 0.045),     # Blank
    (125.0, 0.142),
    (250.0, 0.239),
    (500.0, 0.435),
    (750.0, 0.628),
    (1000.0, 0.812),
    (1500.0, 1.175),
    (2000.0, 1.510),
]

curve = fit_standard_curve(standards, assay_type="BCA")
print(f"Assay: {curve.assay_type}")
print(f"Fit Formula: {curve.formula_str}")
print(f"R² Goodness of Fit: {curve.r_squared:.4f}")

# Predict concentration of an unknown sample
unknown = curve.predict(
    absorbance=0.554,
    dilution_factor=5.0,   # Sample was diluted 1:5 before assay
    volume_ml=2.5,
    sample_name="Cell_Lysate_Fraction_3",
    protein_mw=66430.0,
)

print(f"\nSample: {unknown.sample_name}")
print(f"Interpolated Concentration: {unknown.concentration_ug_ml:.1f} µg/mL ({unknown.concentration_mg_ml:.3f} mg/mL)")
print(f"Total Protein in Fraction: {unknown.total_yield_mg:.3f} mg")
print(f"Estimated Molarity: {unknown.molarity_um:.2f} µM")
```

---

## 6. Command-Line Interface (CLI)

BioLabCalc provides terminal commands for protein quantification and standard curve modeling:

### 6.1 Direct $A_{280}$ CLI (`biolabcalc protein`)

```bash
# Quantify protein concentration and yield from FASTA sequence and A280
biolabcalc protein -s "MKWVTFISLLLLFSSAYSRGVFRRDTHKSEIAHRFKDLGEEHFKGLVLIAFSQYLQQCPFDEHVKLVNELTEFAKTC" \
                   -a 0.852 \
                   -v 2.5 \
                   --dilution 2.0 \
                   --oxidized-cys 2

# Inspect sequence-only extinction coefficient and 1 mg/mL absorbance
biolabcalc protein -s "MKWVTFISLLLLFSSAYSRGVFRRDTHKSEIAHRFKDLGEEHFKGLVLIAFSQYLQQCPFDEHVKLVNELTEFAKTC" \
                   --oxidized-cys 2
```
