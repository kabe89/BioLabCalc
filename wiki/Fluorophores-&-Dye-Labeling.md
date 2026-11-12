# Fluorophores & Dye Labeling

The **Fluorophores & Dye Labeling** module provides rigorous biochemical calculations for modified oligonucleotides, fluorescently conjugated proteins, and dual-labeled fluorophore-quencher probes (e.g., TaqMan™ and molecular beacons). It models mass shifts, accounts for dye-induced UV absorbance cross-talk, determines the spectrophotometric Degree of Labeling (DOL), and diagnoses labeling anomalies.

---

## 1. Fluorophore & Quencher Database (`FLUOROPHORE_DATABASE`)

BioLabCalc incorporates physical, spectroscopic, and mass parameters for leading commercial fluorescent dyes, cyanines, Alexa Fluors, ATTO dyes, and dark quenchers.

```
                    Absorption / Emission Spectrum
   Absorbance /
   Fluorescence
        ▲
        │         Ex Max             Em Max
        │       (λ_ex, nm)         (λ_em, nm)
        │          ╭───╮              ╭───╮
        │         │     │            │     │
        │        │       │          │       │
        │       │         │        │         │
    ────┴───────┴─────────┴────────┴─────────┴──────► Wavelength (nm)
                ◄─────── Stokes Shift ───────►
```

### 1.1 Physical & Optical Parameters

| Identifier | Full Chemical Name | Added Avg MW (g/mol) | Added Monoisotopic MW (g/mol) | $\lambda_{\text{ex}}$ (nm) | $\lambda_{\text{em}}$ (nm) | $\epsilon_{\text{dye}}$ ($\text{M}^{-1}\text{ cm}^{-1}$) | $CF_{260}$ | $CF_{280}$ | Optical Class / Color |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `FAM` | 6-Carboxyfluorescein (6-FAM) | $537.50$ | $537.11$ | $495$ | $520$ | $75,000$ | $0.30$ | $0.17$ | Green Fluorescein |
| `TET` | Tetrachlorofluorescein | $675.30$ | $674.96$ | $522$ | $539$ | $73,000$ | $0.58$ | $0.20$ | Yellow-Green |
| `HEX` | Hexachlorofluorescein | $744.10$ | $743.88$ | $535$ | $556$ | $73,000$ | $0.30$ | $0.16$ | Yellow-Orange |
| `CY3` | Cyanine 3 (Cy3) | $767.00$ | $766.36$ | $550$ | $570$ | $150,000$ | $0.08$ | $0.05$ | Orange-Red Cyanine |
| `CY5` | Cyanine 5 (Cy5) | $793.00$ | $792.38$ | $650$ | $670$ | $250,000$ | $0.05$ | $0.05$ | Far-Red Cyanine |
| `ALEXA488` | Alexa Fluor 488 | $643.40$ | $642.99$ | $495$ | $519$ | $73,000$ | $0.30$ | $0.11$ | Bright Green |
| `ALEXA546` | Alexa Fluor 546 | $1079.00$ | $1078.20$ | $556$ | $573$ | $112,000$ | $0.21$ | $0.12$ | Orange Rhodamine |
| `ALEXA594` | Alexa Fluor 594 | $820.00$ | $819.12$ | $590$ | $617$ | $92,000$ | $0.43$ | $0.56$ | Red Rhodamine |
| `ALEXA647` | Alexa Fluor 647 | $1250.00$ | $1249.20$ | $650$ | $665$ | $270,000$ | $0.03$ | $0.03$ | Far-Red Cyanine |
| `TEXAS_RED` | Texas Red-X | $816.90$ | $816.28$ | $596$ | $620$ | $85,000$ | $0.23$ | $0.18$ | Deep Red Sulforhodamine |
| `TAMRA` | Carboxytetramethylrhodamine | $527.50$ | $527.20$ | $557$ | $583$ | $65,000$ | $0.32$ | $0.36$ | Rose Rhodamine |
| `ROX` | Carboxy-X-rhodamine | $635.70$ | $635.26$ | $588$ | $608$ | $82,000$ | $0.27$ | $0.30$ | Red-Orange |
| `ATTO488` | ATTO 488 | $804.00$ | $803.22$ | $501$ | $523$ | $90,000$ | $0.24$ | $0.10$ | Green Photostable |
| `ATTO647N` | ATTO 647N | $843.50$ | $842.43$ | $644$ | $669$ | $150,000$ | $0.06$ | $0.05$ | Far-Red Lipophilic |
| `BHQ1` | Black Hole Quencher 1 | $518.50$ | $518.20$ | $534$ | — *(Dark)* | $34,000$ | $0.35$ | $0.25$ | Dark Azo Quencher (480–580 nm) |
| `BHQ2` | Black Hole Quencher 2 | $562.60$ | $562.19$ | $579$ | — *(Dark)* | $38,000$ | $0.28$ | $0.22$ | Dark Azo Quencher (550–650 nm) |

---

## 2. Molecular Weight Increments & Mass Spectrometry

Conjugating a fluorophore or quencher to an oligonucleotide or protein increases its total molecular mass. In high-resolution mass spectrometry (LC-MS electrospray ionization or MALDI-TOF), confirming conjugate purity requires matching the observed mass envelope to the theoretical sum of the unmodified biomolecule and the modifier:

$$MW_{\text{modified}} = MW_{\text{original}} + \sum_{k=1}^{M} \Delta MW_{\text{fluorophore}, k}$$

$$MW_{\text{mono, modified}} = MW_{\text{mono, original}} + \sum_{k=1}^{M} \Delta MW_{\text{mono, fluorophore}, k}$$

### 2.1 Oligonucleotide Labeling Chemistries

1. **5' Terminal Labeling:**
   - Synthesized using fluorophore phosphoramidite reagents during automated solid-phase synthesis.
   - The phosphoramidite dye couples directly to the 5'-hydroxyl of the nascent oligonucleotide chain, introducing a phosphodiester linkage. The values in `FLUOROPHORE_DATABASE` incorporate the net weight of the fluorophore core plus linker arm and terminal phosphate.
2. **3' Terminal Labeling:**
   - Synthesized using solid supports (CPG) functionalized with the fluorophore or quencher (e.g., 3'-BHQ1 CPG or 3'-TAMRA CPG).
   - Alternatively, introduced enzymatically via terminal deoxynucleotidyl transferase (TdT) and fluorophore-conjugated dideoxynucleotides (ddNTPs).
3. **Internal Base Labeling:**
   - Introduced via amino-modified bases, such as **Amino-Modifier C6 dT** (5-[3-(6-aminohexylamino)allyl]-2'-deoxyuridine), followed by post-synthetic conjugation with an amine-reactive dye (NHS ester).
   - Each internal addition preserves the base's pairing capability while extending the dye into the major groove of the DNA duplex.

---

## 3. Spectrophotometric Degree of Labeling (DOL)

Accurately quantifying fluorescently labeled conjugates via UV-Vis absorption is complicated by **spectral overlap**: almost all fluorophores absorb light in the ultraviolet region ($260\text{ nm}$ and $280\text{ nm}$). Uncorrected absorbance measurements overestimate biomolecule concentrations, resulting in incorrect stoichiometry and failed assays.

```
 Absorbance
   ▲
   │        Biomolecule Peak
   │          (260 / 280 nm)
   │               ╭───╮
   │    Dye Cross- │   │                 Fluorophore Peak
   │    Absorption │   │                    (λ_max)
   │        ╭──╮  │   │                      ╭───╮
   │        │  │  │   │                      │   │
───┴────────┴──┴──┴───┴──────────────────────┴───┴───► Wavelength (nm)
           260 / 280                         λ_max
```

### 3.1 Spectral Correction Factors ($CF_{260}$ and $CF_{280}$)

The correction factor ($CF$) represents the intrinsic ratio of dye absorbance at the biomolecule reference wavelength ($260\text{ nm}$ for nucleic acids, $280\text{ nm}$ for proteins) to dye absorbance at its visible absorption maximum ($\lambda_{\text{max}}$):

$$CF_{260} = \frac{A_{260, \text{dye}}}{A_{\text{max, dye}}} \qquad CF_{280} = \frac{A_{280, \text{dye}}}{A_{\text{max, dye}}}$$

### 3.2 Corrected Biomolecule Absorbance ($A_{\text{corrected}}$)

The true absorbance of the biomolecule is isolated by subtracting the dye's UV contribution:

#### For Proteins:
$$A_{280, \text{corrected}} = A_{280, \text{measured}} - \left( A_{\text{max, dye}} \times CF_{280} \right)$$

#### For Oligonucleotides:
$$A_{260, \text{corrected}} = A_{260, \text{measured}} - \left( A_{\text{max, dye}} \times CF_{260} \right)$$

### 3.3 Concentration & Stoichiometry Derivations

Applying the Beer-Lambert Law across a pathlength $l$ ($\text{cm}$):

1. **Biomolecule Molar Concentration ($c_{\text{biomol}}$):**
   $$c_{\text{biomol}}\text{ (M)} = \frac{A_{\text{corrected}}}{\epsilon_{\text{biomol}} \times l}$$

2. **Dye Molar Concentration ($c_{\text{dye}}$):**
   $$c_{\text{dye}}\text{ (M)} = \frac{A_{\text{max, dye}}}{\epsilon_{\text{dye}} \times l}$$

3. **Degree of Labeling (DOL):**
   The Degree of Labeling represents the average stoichiometric ratio of dye molecules covalently conjugated per biomolecule:

   $$\text{DOL} = \frac{c_{\text{dye}}}{c_{\text{biomol}}} = \frac{A_{\text{max, dye}} \cdot \epsilon_{\text{biomol}}}{A_{\text{corrected}} \cdot \epsilon_{\text{dye}}}$$

4. **Labeling Efficiency Percentage:**
   $$\text{Labeling Efficiency (\%)} = \min\left(100.0, \text{DOL} \times 100\right)$$

---

## 4. Target DOL Ranges & Biological Interpretations

| DOL Metric | Classification | Biochemical Interpretation & Functional Consequence |
| :---: | :--- | :--- |
| **$< 0.80$** | **Under-Labeled** | Significant fraction of the biomolecule population remains unconjugated. Yields low fluorescence intensity in imaging, flow cytometry, or qPCR assays. |
| **$0.80 - 1.20$** | **Optimally Labeled (1:1)** | Ideal stoichiometric ratio for oligonucleotides, qPCR hydrolysis probes, and single-domain binders. Maximizes signal without perturbing hybridization kinetics or inducing steric hindrance. |
| **$1.20 - 2.50$** | **Multi-Labeled** | Ideal target range for **whole IgG antibodies** ($150\text{ kDa}$) and large globular proteins labeled via solvent-exposed lysine side chains. Enhances detection sensitivity in immunofluorescence (IF) and Western blotting. |
| **$> 2.50$** | **Over-Labeled** | Excessive fluorophore density. Induces severe **fluorophore self-quenching**, antibody precipitation, and loss of antigen-binding specificity. |

---

## 5. Troubleshooting Over- and Under-Labeling

```
┌────────────────────────────────────────────────────────────────────────┐
│                   LABELING REACTION DIAGNOSTICS                        │
├───────────────────────────────────┬────────────────────────────────────┤
│ Over-Labeling (DOL > 2.5)         │ Under-Labeling (DOL < 0.8)         │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Fluorophore self-quenching      │ • Low fluorescence signal          │
│ • Hydrophobic precipitation       │ • Quenched NHS ester (Tris buffer) │
│ • Non-specific binding / stickiness│ • Inactive maleimides (oxidized-SH)│
│ • Loss of antibody binding affinity│ • Hydrolyzed dye stock            │
└───────────────────────────────────┴────────────────────────────────────┘
```

### 5.1 The Physics of Over-Labeling: Self-Quenching & Aggregation

When fluorophores are packed closely together on a protein or nucleic acid scaffold, their electronic excitation energy dissipates non-radiatively rather than via photon emission:

1. **Förster Resonance Energy Transfer (Homotypic FRET):** Exciton hopping between identical fluorophores increases the probability that energy will be trapped by a non-fluorescent ground-state dimer.
2. **Ground-State Static Dimerization:** Aromatic, hydrophobic dyes (such as Cy5, Texas Red, and rhodamines) stack via planar $\pi-\pi$ interactions in aqueous solutions, forming non-fluorescent ground-state dimers with shifted absorption peaks (H-aggregates).
3. **Loss of Biological Activity:** Hydrophobic dye accumulation masks paratopes on antibodies and induces protein aggregation and precipitation out of solution.
4. **Corrective Countermeasures:**
   - Reduce the molar excess of reactive dye (e.g., reduce NHS ester from $15\text{X}$ down to $3\text{X}–5\text{X}$).
   - Shorten reaction incubation time from $2\text{ hours}$ to $45\text{ minutes}$.
   - Add a hydrophilic PEG spacer linker ($\text{PEG}_4$) between the dye core and the reactive group.

### 5.2 Root Causes & Solutions for Under-Labeling

1. **Amine Buffer Contamination (The Tris / Glycine Trap):**
   - **Problem:** NHS ester and sulfo-NHS ester crosslinkers react with primary amines ($-\text{NH}_2$). If the protein is formulated in **Tris-HCl**, glycine, or ammonium sulfate, the buffer amines outnumber the protein lysines by $>10,000:1$, immediately quenching the reactive dye.
   - **Fix:** Buffer exchange the protein into amine-free buffer ($100\text{ mM}$ Sodium Bicarbonate, $\text{pH } 8.3–8.5$, or $1\text{X PBS}$, $\text{pH } 7.4$) using a desalting spin column (e.g., Zeba™ or Sephadex G-25) prior to reaction.
2. **Suboptimal Reaction pH:**
   - **Problem:** Conjugation of NHS esters targets unprotonated $\epsilon$-amino groups of lysines ($\text{p}K_a \approx 10.5$). Performing reactions at $\text{pH} < 7.2$ leaves lysines protonated ($-\text{NH}_3^+$), eliminating nucleophilic attack.
   - **Fix:** Conduct NHS ester conjugations at $\text{pH } 8.2–8.6$ using sodium bicarbonate buffer.
3. **Thiol Oxidation in Maleimide Labeling:**
   - **Problem:** Maleimide-activated fluorophores target reduced sulfhydryls ($-\text{SH}$) on cysteines. Air oxidation readily forms intra- or intermolecular disulfide bonds ($\text{Cys-S-S-Cys}$), preventing conjugation.
   - **Fix:** Pre-incubate the sample with a $10\text{-fold}$ molar excess of **TCEP** (tris(2-carboxyethyl)phosphine) for $20\text{ minutes}$ at room temperature. TCEP does not contain thiols (unlike DTT or $\beta$-ME) and does not need to be removed prior to maleimide addition.
4. **Moisture-Induced Dye Hydrolysis:**
   - **Problem:** NHS ester dry powder and DMSO stock solutions rapidly hydrolyze into non-reactive carboxylates upon exposure to atmospheric moisture.
   - **Fix:** Equilibrate lyophilized dye vials to room temperature before opening. Reconstitute in anhydrous, molecular-sieve-stored DMSO or DMF immediately prior to use; discard unused aliquots.

### 5.3 The Over-Correction Error

If BioLabCalc raises an `Over-correction error`, the dye absorbance contribution ($A_{\text{max, dye}} \times CF$) exceeds the total measured absorbance ($A_{280}$ or $A_{260}$), resulting in a negative corrected absorbance ($A_{\text{corrected}} \le 0$).

**Diagnostic Causes:**
1. **Unincorporated Free Dye Carryover:** The sample was not sufficiently separated from unreacted dye after the labeling reaction. Free dye absorbs heavily at $\lambda_{\text{max}}$, falsely inflating the calculated dye correction.
2. **Protein Concentration Below Limit of Detection:** The protein concentration is too low ($< 0.05\text{ mg/mL}$) relative to the dye absorbance.
3. **Corrective Action:** Re-purify the conjugate through a desalting resin, perform centrifugal ultrafiltration (washing $3\text{X}$ with buffer until filtrate is colorless), or run extensive dialysis.

---

## 6. Python API Reference

### 6.1 Inspecting Fluorophore Properties (`get_fluorophore`)

`get_fluorophore` normalizes queries by stripping whitespace, hyphens, and underscores, matching against dictionary keys, formal names, and common aliases. It seamlessly supports multi-word names like `"Alexa Fluor 488"`, `"Texas Red"`, and `"Black Hole Quencher 1"`.

```python
from biolabcalc.fluorescence import get_fluorophore

# Retrieve metadata for Cy5 or multi-word fluorophores
cy5 = get_fluorophore("Cy5")
af488 = get_fluorophore("Alexa Fluor 488")
texas_red = get_fluorophore("Texas Red")
bhq1 = get_fluorophore("Black Hole Quencher 1")

print(f"Name: {af488.name} (Alias: {af488.common_name})")
print(f"Added MW: {af488.added_mw} Da (Monoisotopic: {af488.added_monoisotopic} Da)")
print(f"Excitation / Emission: {af488.excitation_max_nm} nm / {af488.emission_max_nm} nm")
print(f"Extinction Coefficient: {af488.extinction_coeff_m_cm:,} M^-1 cm^-1")
print(f"Correction Factors: CF260 = {af488.cf260}, CF280 = {af488.cf280}")
```

### 6.2 Applying Modifications to Oligonucleotides (`apply_fluorophore_modification`)

```python
from biolabcalc.molecular_weight import calculate_dna_mw
from biolabcalc.fluorescence import apply_fluorophore_modification

# 1. Calculate Unmodified 20-nt DNA Primer
dna_base = calculate_dna_mw("GACTACAGCTAGCTAGCTAG", double_stranded=False, end_5="hydroxyl")
print(f"Unmodified ssDNA MW: {dna_base.average_mw:.2f} Da")

# 2. Add Dual Modifications: 5'-FAM and 3'-BHQ1 (TaqMan Probe)
labeled_probe = apply_fluorophore_modification(
    base_result=dna_base,
    modifications=["FAM", "BHQ1"],
)

print(f"Dual-Labeled Probe Average MW: {labeled_probe.total_modified_mw:.2f} Da")
print(f"Dual-Labeled Probe Monoisotopic MW: {labeled_probe.total_modified_monoisotopic:.4f} Da")
print(f"Net Added Mass: +{labeled_probe.total_added_mw:.2f} Da")
print(f"Applied Modifiers: {labeled_probe.modifications}")
```

### 6.3 Calculating Degree of Labeling (DOL) (`calculate_degree_of_labeling`)

#### Example A: Fluorescently Labeled Antibody (Protein)

```python
from biolabcalc.fluorescence import calculate_degree_of_labeling

# Quantify an Alexa Fluor 488-conjugated IgG antibody (MW ~150 kDa, e280 ~210,000 M^-1 cm^-1)
dol_antibody = calculate_degree_of_labeling(
    absorbance_max_dye=0.820,           # Absorbance at 495 nm
    absorbance_280=0.640,               # Measured total A280
    fluorophore_name="Alexa Fluor 488",
    protein_extinction_coeff=210000.0,
    pathlength_cm=1.0,
)

print(f"Molecule Type: {dol_antibody.molecule_type}")
print(f"Fluorophore: {dol_antibody.fluorophore_name}")
print(f"Corrected Protein A280: {dol_antibody.absorbance_corrected_biomolecule:.4f} AU")
print(f"Protein Concentration: {dol_antibody.biomolecule_concentration_um:.2f} µM")
print(f"Dye Concentration: {dol_antibody.dye_concentration_um:.2f} µM")
print(f"Degree of Labeling (DOL): {dol_antibody.degree_of_labeling:.2f} dyes / antibody")
print(f"Interpretation: {dol_antibody.interpretation}")
```

#### Example B: Fluorescently Labeled Oligonucleotide (DNA)

```python
from biolabcalc.fluorescence import calculate_degree_of_labeling

# Quantify a Cy3-labeled synthetic oligo (e260 ~195,000 M^-1 cm^-1)
dol_oligo = calculate_degree_of_labeling(
    absorbance_max_dye=1.150,           # Absorbance at 550 nm
    absorbance_260=0.980,               # Measured total A260
    fluorophore_name="Cy3",
    oligo_extinction_coeff=195000.0,
    pathlength_cm=1.0,
)

print(f"Molecule Type: {dol_oligo.molecule_type}")
print(f"Corrected Oligo A260: {dol_oligo.absorbance_corrected_biomolecule:.4f} AU")
print(f"Oligo Concentration: {dol_oligo.biomolecule_concentration_um:.2f} µM")
print(f"Degree of Labeling (DOL): {dol_oligo.degree_of_labeling:.2f} dyes / oligo")
print(f"Efficiency: {dol_oligo.labeling_efficiency_percent:.1f}%")
print(f"Interpretation: {dol_oligo.interpretation}")
```

---

## 7. Command-Line Interface (CLI)

The `biolabcalc fluo` command provides instant terminal access to fluorophore modifications and DOL calculations:

### 7.1 Inspect Fluorophore Database via CLI

```bash
# Query fluorophore parameters
biolabcalc fluo --info FAM
biolabcalc fluo --info Cy5
biolabcalc fluo --info AlexaFluor647
```

### 7.2 Degree of Labeling (DOL) Calculations via CLI

```bash
# Protein Conjugate (Alexa Fluor 488 labeled IgG)
biolabcalc fluo --dol \
                --dye ALEXA488 \
                --a-dye 0.820 \
                --a280 0.640 \
                --prot-e280 210000

# Oligonucleotide Conjugate (Cy3 labeled probe)
biolabcalc fluo --dol \
                --dye CY3 \
                --a-dye 1.150 \
                --a260 0.980 \
                --dna-e260 195000
```
