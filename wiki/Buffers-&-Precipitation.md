# Buffers & Precipitation

The **Buffers & Precipitation** module provides comprehensive formulations, temperature-compensation mechanics, stoichiometric neutralization protocols, and phase extraction workflows for laboratory reagents. It standardizes reagent preparation, prevents temperature-induced pH drift, guarantees RNA integrity during nucleoside triphosphate (NTP) neutralization, and optimizes nucleic acid recovery across diverse precipitation regimes.

---

## 1. Laboratory Buffer Catalog (`BUFFER_CATALOG`)

BioLabCalc maintains an authoritative catalog of standard molecular biology buffers. All baseline formulations are normalized to $1000\text{ mL}$ ($1.0\text{ L}$) and scale dynamically to any target volume.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BUFFER_CATALOG REGISTRY                         │
├─────────────────┬──────────────────┬─────────────────┬─────────────────┤
│ Electrophoresis │ Physiological    │ Stocks & TE     │ Cell & Enzymatic│
├─────────────────┼──────────────────┼─────────────────┼─────────────────┤
│ • 50X TAE       │ • 10X PBS        │ • 1 M Tris-HCl  │ • LB Broth      │
│ • 10X TBE       │                  │ • 0.5 M EDTA    │ • 10X HEPES IVT │
│ • 6X Loading Dye│                  │ • 1X TE Buffer  │                 │
└─────────────────┴──────────────────┴─────────────────┴─────────────────┘
```

### 1.1 Complete Buffer Formulations (per 1.0 L Batch)

| Buffer ID | Full Name | Target pH | Components (for 1000 mL) | Preparation & Bench Notes | Storage & Safety |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `50X_TAE` | 50X Tris-Acetate-EDTA | $\sim8.3$<br>*(Do not adjust)* | • Tris base: $242.0\text{ g}$ ($2.0\text{ M}$)<br>• Glacial acetic acid: $57.1\text{ mL}$ ($1.0\text{ M}$)<br>• $0.5\text{ M}$ EDTA (pH 8.0): $100.0\text{ mL}$ ($50\text{ mM}$) | Dissolve Tris in $\sim700\text{ mL}$ $\text{dH}_2\text{O}$. Add acetic acid and EDTA. Bring to $1000\text{ mL}$. Working buffer (1X) is $40\text{ mM}$ Tris, $20\text{ mM}$ Acetate, $1\text{ mM}$ EDTA. | **Storage:** Room temp ($>1\text{ yr}$).<br>**Safety:** Glacial acetic acid is corrosive. Handle in fume hood. |
| `10X_TBE` | 10X Tris-Borate-EDTA | $\sim8.3$<br>*(Do not adjust)* | • Tris base: $108.0\text{ g}$ ($890\text{ mM}$)<br>• Boric acid: $55.0\text{ g}$ ($890\text{ mM}$)<br>• $0.5\text{ M}$ EDTA (pH 8.0): $40.0\text{ mL}$ ($20\text{ mM}$) | Dissolve Tris and Boric acid in $\sim800\text{ mL}$ $\text{dH}_2\text{O}$ with vigorous stirring. Add EDTA. Bring to $1000\text{ mL}$. Preferred for polyacrylamide gels and high-voltage runs. | **Storage:** Room temp. Discard if white precipitate forms.<br>**Safety:** Boric acid is a reproductive toxicant. |
| `10X_PBS` | 10X Phosphate-Buffered Saline | $7.4 \pm 0.1$<br>*(at 1X)* | • $\text{NaCl}$: $80.0\text{ g}$ ($1.37\text{ M}$)<br>• $\text{KCl}$: $2.0\text{ g}$ ($27\text{ mM}$)<br>• $\text{Na}_2\text{HPO}_4$: $14.4\text{ g}$ ($100\text{ mM}$)<br>• $\text{KH}_2\text{PO}_4$: $2.4\text{ g}$ ($18\text{ mM}$) | Dissolve salts in $\sim800\text{ mL}$ $\text{dH}_2\text{O}$. Adjust pH to $7.4$ with concentrated $\text{HCl}$ ($\sim2-3\text{ mL}$). Bring to $1000\text{ mL}$. Dilutes to 1X: $137\text{ mM NaCl}$, $2.7\text{ mM KCl}$, $10\text{ mM Na}_2\text{HPO}_4$, $1.8\text{ mM KH}_2\text{PO}_4$. | **Storage:** Room temp or $4^\circ\text{C}$. Autoclave for cell culture sterility. |
| `1M_TRIS` | 1 M Tris-HCl Stock Solution | $8.0$ (or $7.5$) | • Tris base: $121.14\text{ g}$ ($1.0\text{ M}$)<br>• Concentrated $\text{HCl}$ ($\sim37\%$): $\sim42.0\text{ mL}$ (pH 8.0) or $\sim65.0\text{ mL}$ (pH 7.5) | Dissolve Tris in $\sim800\text{ mL}$ $\text{dH}_2\text{O}$. Equilibrate to $25^\circ\text{C}$ before final pH titration. Bring to $1000\text{ mL}$ and autoclave. | **Storage:** Room temp.<br>**Safety:** Highly exothermic upon $\text{HCl}$ addition. Handle on ice/fume hood. |
| `0.5M_EDTA` | 0.5 M EDTA Stock (pH 8.0) | $8.0 \pm 0.05$<br>*(Strict)* | • $\text{Na}_2\text{EDTA}\cdot2\text{H}_2\text{O}$: $186.1\text{ g}$ ($0.5\text{ M}$)<br>• $\text{NaOH}$ pellets: $\sim20.0\text{ g}$ ($\sim500\text{ mM}$) | Add $\text{Na}_2\text{EDTA}$ to $\sim700\text{ mL}$ $\text{dH}_2\text{O}$. **EDTA will not dissolve until pH reaches $\sim8.0$!** Add $\text{NaOH}$ pellets slowly; solution clarifies rapidly above pH 7.5. Fine-tune to $8.0$ with $5\text{ M NaOH}$. | **Storage:** Room temp (autoclaved).<br>**Safety:** Dissolving $\text{NaOH}$ pellets releases significant heat. |
| `1X_TE` | 1X TE Buffer (Tris-EDTA) | $8.0 \pm 0.1$ | • $1\text{ M}$ Tris-HCl (pH 8.0): $10.0\text{ mL}$ ($10\text{ mM}$)<br>• $0.5\text{ M}$ EDTA (pH 8.0): $2.0\text{ mL}$ ($1\text{ mM}$) | Add stocks to $\sim900\text{ mL}$ $\text{dH}_2\text{O}$. Bring volume to $1000\text{ mL}$. Filter sterilize ($0.22\text{ }\mu\text{m}$) or autoclave. Standard storage buffer for DNA/RNA. | **Storage:** Room temp or $4^\circ\text{C}$. Non-hazardous. |
| `6X_LOADING_DYE` | 6X DNA Gel Loading Dye | Neutral | • Bromophenol blue: $2.5\text{ g}$ ($0.25\%\text{ w/v}$)<br>• Xylene cyanol FF: $2.5\text{ g}$ ($0.25\%\text{ w/v}$)<br>• Glycerol ($100\%$): $300.0\text{ mL}$ ($30\%\text{ v/v}$) | Dissolve dyes in $\sim500\text{ mL}$ $\text{dH}_2\text{O}$. Add glycerol. Bring volume to $1000\text{ mL}$ with deionized water. Bromophenol blue migrates at $\sim300\text{ bp}$ in $1\%$ agarose; Xylene cyanol migrates at $\sim4000\text{ bp}$. | **Storage:** $4^\circ\text{C}$ or $-20^\circ\text{C}$.<br>**Safety:** Stains skin and clothing. |
| `LB_BROTH` | LB Broth (Miller Formulation) | $7.0 \pm 0.2$ | • Tryptone: $10.0\text{ g}$ ($1\%\text{ w/v}$)<br>• Yeast Extract: $5.0\text{ g}$ ($0.5\%\text{ w/v}$)<br>• $\text{NaCl}$: $10.0\text{ g}$ ($170\text{ mM}$) | Dissolve ingredients in $\sim900\text{ mL}$ $\text{dH}_2\text{O}$. Adjust pH to $7.0$ with $1\text{ M NaOH}$. Bring to $1000\text{ mL}$. Autoclave at $121^\circ\text{C}$ ($15\text{ psi}$) for $20\text{ min}$. | **Storage:** Room temp (autoclaved). Ensure caps loosened during autoclaving. |
| `10X_HEPES_IVT` | 10X HEPES-KOH IVT Reaction Buffer | $7.67$ at $25^\circ\text{C}$<br>($7.50$ at $37^\circ\text{C}$) | • HEPES free acid: $95.32\text{ g}$ ($400\text{ mM}$)<br>• $5\text{ M}$ KOH: $\sim45.5\text{ mL}$ ($\sim227\text{ mM}$)<br>• DTT: $15.42\text{ g}$ ($100\text{ mM}$)<br>• Spermidine-3HCl: $5.09\text{ g}$ ($20\text{ mM}$)<br>• Triton X-100: $1.0\text{ mL}$ ($0.1\%\text{ v/v}$) | Dissolve HEPES in $\sim700\text{ mL}$ nuclease-free water. Titrate with $5\text{ M KOH}$ to pH $7.67$ at $25^\circ\text{C}$. Add DTT, Spermidine, and Triton X-100. Bring to $1000\text{ mL}$. Filter sterilize ($0.22\text{ }\mu\text{m}$). | **Storage:** $-20^\circ\text{C}$ in single-use aliquots (protects DTT from oxidation).<br>**Safety:** KOH is caustic. |

---

## 2. Custom Buffer Builder API (`CustomBufferBuilder`)

To support proprietary laboratory protocols, BioLabCalc provides a fluent builder pattern for authoring, scaling, and persisting custom buffers.

### 2.1 Builder Architecture

`CustomBufferBuilder` decouples recipe declaration from target batch volume. Components can be added as:
- **Solids (`add_solid`):** Defined by target concentration in millimolar ($\text{mM}$) and molecular weight ($\text{g/mol}$).
- **Liquid Stock Dilutions (`add_liquid_stock`):** Defined by target concentration ($\text{mM}$) and stock concentration ($\text{mM}$).
- **Percentage Formulations (`add_percent`):** Weight/volume ($\%\text{ w/v}$) or volume/volume ($\%\text{ v/v}$).
- **Preparation Steps (`add_step`):** Step-by-step procedural directions.

Once configured, the builder can:
1. `register()`: Inserts the buffer directly into the runtime `BUFFER_CATALOG`.
2. `build(target_volume_ml)`: Generates fully scaled component masses and pipetting volumes.
3. `save()`: Serializes the recipe to persistent JSON storage (`~/.biolabcalc/custom_buffers.json`).

---

## 3. Buffer Temperature Physics: Tris vs. HEPES

A frequent bench pitfall in enzymatic assays and in vitro transcription (IVT) is ignoring buffer temperature coefficients ($d\text{p}K_a/dT$).

### 3.1 Temperature Shift Formulation (`calculate_tris_temperature_shift`)

The shifted pH at an operating temperature $T_{\text{target}}$ is calculated as:

$$\text{pH}(T_{\text{target}}) = \text{pH}(T_{\text{ref}}) + \left( \frac{d\text{p}K_a}{dT} \right) \cdot \left( T_{\text{target}} - T_{\text{ref}} \right)$$

where $T_{\text{ref}}$ (`measured_temp_c`) defaults to $25.0^\circ\text{C}$ (reference calibration temperature).

```python
from biolabcalc.buffers import calculate_tris_temperature_shift

# Calculate cold-room (4°C) shift from pH 8.00 at standard reference temp (25°C):
ph_cold = calculate_tris_temperature_shift(measured_ph=8.00, target_temp_c=4.0)
# Output: 8.63
```

### 3.2 Comparison: Tris vs. HEPES

| Parameter | Tris-HCl | HEPES-KOH | Biological Consequence |
| :--- | :---: | :---: | :--- |
| **pKa (at $25^\circ\text{C}$)** | $8.06$ | $7.55$ | HEPES centers buffer capacity directly at physiological pH $7.4–7.5$. |
| **$d\text{p}K_a/dT$** | $\mathbf{-0.028\text{ to } -0.031\text{ /}^\circ\text{C}}$ | $\mathbf{-0.014\text{ /}^\circ\text{C}}$ | **Tris is twice as sensitive to temperature shifts as HEPES.** |
| **pH at $25^\circ\text{C}$ (Room Temp)** | $8.00$ | $7.67$ | Preparation target. |
| **pH at $37^\circ\text{C}$ (IVT Incubation)** | $\mathbf{7.64}$ ($\Delta = -0.36$) | $\mathbf{7.50}$ ($\Delta = -0.17$) | Tris drops below its optimal buffering range during incubation. |
| **pH at $4^\circ\text{C}$ (Cold Room)** | $\mathbf{8.59}$ ($\Delta = +0.59$) | $\mathbf{7.79}$ ($\Delta = +0.12$) | Tris becomes alkaline in cold room storage. |
| **Counterion Effect on RNA Polymerase** | Typically $\text{Na}^+$ or $\text{Cl}^-$ | $\text{K}^+$ (via KOH titration) | High $\text{Na}^+$ inhibits T7 RNAP elongation; $\text{K}^+$ stimulates transcription rate. |

---

## 4. NTP Neutralization Stoichiometry (`calculate_ntp_ph_adjustment`)

Synthesizing high-yield RNA via T7 RNA polymerase requires millimolar concentrations of nucleoside triphosphates (ATP, CTP, GTP, UTP). Commercial NTPs are supplied in varying chemical forms that dictate neutralization requirements.

### 4.1 Protonation Chemistry of NTPs

An unneutralized nucleoside triphosphate possesses four ionizable phosphate protons:
- The first three protons (two on the $\alpha$- and $\beta$-phosphates, one on the $\gamma$-phosphate) are strong acids ($\text{p}K_a < 2.0$).
- The terminal secondary $\gamma$-phosphate proton has a weak acid $\text{p}K_a \approx 6.65$.

```
              O           O           O
              ║           ║           ║
Base ── Ribose ── O ── P ── O ── P ── O ── P ── OH  (pKa ~ 6.65)
              │           │           │
              O⁻          O⁻          O⁻
          (pKa < 2)   (pKa < 2)   (pKa < 2)
```

At a target pH of $7.50$, the degree of $\gamma$-phosphate deprotonation ($\alpha_\gamma$) is calculated via the Henderson-Hasselbalch equation:

$$\alpha_\gamma = \frac{10^{\text{pH} - \text{p}K_a}}{1 + 10^{\text{pH} - \text{p}K_a}} = \frac{10^{7.50 - 6.65}}{1 + 10^{7.50 - 6.65}} = \frac{7.079}{1 + 7.079} \approx 0.876$$

### 4.2 Starting Forms & Base Equivalents ($Eq_{\text{NaOH}}$)

| Starting Chemical Form | Initial pH | Base Equivalents Required per Mole NTP ($Eq_{\text{NaOH}}$) | Stoichiometric Mechanics |
| :--- | :---: | :---: | :--- |
| **Pre-Neutralized (`pre_neutralized`)** | $7.0 - 7.5$ | $\mathbf{0.000}$ | Commercial solutions (NEB, Promega, Thermo Fisher) are pre-titrated with $\text{NaOH}$ or $\text{Tris}$. **Never add NaOH!** |
| **Disodium Salt (`disodium_salt`)** | $3.0 - 3.5$ | $\alpha_\gamma + Eq_{\text{ring}}$<br>• ATP: $\alpha_\gamma + 0.88 = \mathbf{1.756}$<br>• CTP: $\alpha_\gamma + 0.95 = \mathbf{1.826}$<br>• GTP: $\alpha_\gamma + 0.07 = \mathbf{0.946}$<br>• UTP: $\alpha_\gamma + 0.02 = \mathbf{0.896}$<br>• Equimolar Mix: $\mathbf{1.356}$ | Two $\text{Na}^+$ ions neutralize the two primary phosphates; neutralization requires titrating the third phosphate proton and partially protonated heterocyclic ring nitrogens (adenine N1 $\text{p}K_a \approx 4.0$, cytosine N3 $\text{p}K_a \approx 4.2$). |
| **Free Acid (`free_acid`)** | $1.5 - 2.0$ | $3.0 + \alpha_\gamma = \mathbf{3.876}$ | Completely un-neutralized. Requires neutralizing all 3 strong acidic protons plus the weak $\gamma$-phosphate. |

### 4.3 The Over-Alkalization Hazard & Critical Pipetting Rules

1. **The Pre-Neutralized Catastrophe:** Adding $\text{NaOH}$ to pre-neutralized NTP stocks pushes the pH above $9.5$. At $\text{pH} > 9.0$:
   - Cytidine rapidly undergoes base-catalyzed **deamination to uridine**, introducing point mutations into transcribed RNA.
   - Ribose $2'\text{-OH}$ groups deprotonate to alkoxides, attacking the adjacent phosphodiester backbone and inducing rapid RNA fragmentation.
2. **Order of Addition (Preventing Volume Overshoot):**
   - **Never add full diluent water before pH adjustment.** For example, when diluting $4.0\text{ mL}$ of $100\text{ mM}$ NTPs to $16.0\text{ mL}$ of $25\text{ mM}$ working stock, adding $12.0\text{ mL}$ water immediately brings the volume to the $16.0\text{ mL}$ ceiling.
   - Any subsequent addition of $\text{NaOH}$ (or back-titration with $\text{HCl}$) overshoots the volume budget, permanently diluting the NTP stock below $25.0\text{ mM}$.
   - **Correct Protocol:** Add $8.0\text{ mL}$ water ($\sim65\%$ diluent), add $\sim80\%$ of theoretical $5\text{ M NaOH}$ under micro-pH monitoring, fine-tune dropwise with $0.5\text{ M NaOH}$ to $\text{pH } 7.50 \pm 0.05$, and bring to exactly $16.0\text{ mL}$ with water in a volumetric flask.

---

## 5. Precipitation Regimes & Carrier Physics (`calculate_precipitation`)

Precipitating nucleic acids requires counteracting electrostatic repulsion between negatively charged phosphate backbones and decreasing solvent dielectric permittivity.

```
       Polyphosphate Backbone
        (Negative Charges Repel)
       -O-P(=O)-O-CH2- ... -O-P(=O)-O-
          │                     │
          ▼                     ▼
     Add Monovalent Cations (Na+, Li+, NH4+)
        (Shields Negative Charges)
          ▼
     Add Alcohol (Ethanol / Isopropanol)
  (Lowers Solvent Dielectric Constant, ε)
          ▼
 Aggregation & Centrifugal Pellet Formation
```

### 5.1 Alcohol & Salt Selection Matrix

| Precipitation Regime | Alcohol Volume Ratio | Optimal Salt & Ratio | Target Nucleic Acid | Advantages & Laboratory Trade-offs |
| :--- | :---: | :--- | :--- | :--- |
| **Ethanol (Standard)** | **$2.5\text{X}$** (DNA)<br>**$3.0\text{X}$** (RNA) | $3\text{ M}$ Sodium Acetate (pH 5.2)<br>$\mathbf{0.10\text{ vol}}$ ($0.3\text{ M}$ final) | High/low MW DNA, Total RNA, Plasmids | Standard reference protocol. Efficient recovery of short oligos ($>20\text{ nt}$). High total volume requires larger vessels. |
| **Isopropanol** | **$0.7\text{X}$** (DNA)<br>**$1.0\text{X}$** (RNA) | $3\text{ M}$ Sodium Acetate (pH 5.2)<br>$\mathbf{0.10\text{ vol}}$ | High MW Genomic DNA, Large Plasmids, IVT RNA | Compact volume fits inside standard $1.5\text{ mL}$ tubes. **Must incubate at room temp**; chilling below $-20^\circ\text{C}$ co-precipitates inhibitory salts. Pellets are more loosely adhered to tube walls. |
| **Ammonium Acetate** | $2.5\text{X}$ Ethanol or $0.7\text{X}$ Isopropanol | $5\text{ M}$ Ammonium Acetate (pH 7.0)<br>$\mathbf{0.50\text{ vol}}$ ($2.0–2.5\text{ M}$ final) | Post-labeling cleanup, Post-PCR cleanup | Volatile salt that prevents co-precipitation of dNTPs and free NTPs. **Avoid if performing T4 PNK kinase phosphorylation** ($\text{NH}_4^+$ inhibits kinase activity). |
| **Selective LiCl (No Alcohol!)** | **$0.0\text{X}$**<br>*(Alcohol strictly omitted)* | $8\text{ M}$ Lithium Chloride<br>$\mathbf{0.50\text{ vol}}$ ($2.5–4.0\text{ M}$ final) | **Large ssRNA ($>200\text{ nt}$)**<br>mRNAs, Ribosomal RNA | **Selectively precipitates large single-stranded RNA.** Completely excludes free NTPs, dNTPs, plasmid DNA templates, and tRNAs/small RNAs. **Adding alcohol destroys selectivity** by crashing out free nucleotides and salts. |

---

### 5.2 Co-Precipitation Carrier Selection

When nucleic acid concentrations are low ($<10\text{ ng/}\mu\text{L}$ or $<1\text{ }\mu\text{g}$ total), pellets are invisible and diffuse, leading to sample loss during supernatant aspiration.

| Carrier Reagent | Working Stock | Volume / Reaction | Optical / Biochemical Interferences | Best Application |
| :--- | :---: | :---: | :--- | :--- |
| **GlycoBlue™** | $20\text{ mg/mL}$ | $1.0\text{ }\mu\text{L}$ | Covalently dyed glycogen. Absorbs at $620\text{ nm}$; zero absorbance at $260/280\text{ nm}$. | High-throughput bench recovery. Yields a bright blue pellet visible under room light down to $<5\text{ ng}$. |
| **Glycogen (Molecular Grade)** | $20\text{ mg/mL}$ | $1.0\text{ }\mu\text{L}$ | Purified mussel polysaccharide. Negligible $A_{260}$ absorbance. May interfere with DNA-protein binding assays. | General-purpose recovery of dilute PCR amplicons, cDNA, and small oligos. |
| **Linear Polyacrylamide (LPA)** | $5\text{ mg/mL}$ | $1.0–2.0\text{ }\mu\text{L}$ | Completely synthetic polymer. **Zero absorbance from $200–300\text{ nm}$.** Free of biological contaminants. | Downstream microvolume NanoDrop quantitation, RT-qPCR, and next-generation sequencing (NGS). |

---

## 6. Acid Phenol:Chloroform Phase Extraction (`calculate_phenol_chloroform_extraction`)

Phenol:Chloroform:Isoamyl alcohol (PCI) partitions cellular proteins, genomic DNA, and RNA across two immiscible liquid phases based on pH-dependent phosphate ionization.

```
┌────────────────────────────────────────────────────────┐
│                   AQUEOUS PHASE (Top)                  │
│  • pH 4.5: RNA ONLY (DNA partitioned out)             │
│  • pH 8.0: BOTH DNA and RNA                            │
├────────────────────────────────────────────────────────┤
│                  INTERPHASE (Middle)                   │
│  • Denatured proteins, genomic DNA fibers (at pH 4.5)  │
├────────────────────────────────────────────────────────┤
│                   ORGANIC PHASE (Bottom)               │
│  • Phenol + Chloroform + Lipids + Hydrophobic Proteins │
└────────────────────────────────────────────────────────┘
```

### 6.1 Phase Partitioning Mechanics: pH 4.5 vs. pH 8.0

1. **Acid Phenol (pH 4.5, 125:24:1 PCI):**
   - At $\text{pH } 4.5$, the phosphate groups of double-stranded DNA are partially neutralized ($-\text{O}^- \to -\text{OH}$), reducing electrostatic solubility in water. DNA denatures and partitions into the organic phenol phase or aggregates at the white interphase.
   - RNA possesses a solvent-exposed $2'\text{-OH}$ group and single-stranded regions that maintain sufficient aqueous solvation, remaining exclusively in the upper aqueous phase.
2. **Buffered Phenol (pH 8.0, 25:24:1 PCI):**
   - At $\text{pH } 8.0$, both DNA and RNA polyphosphate backbones are completely ionized into polyanions ($-\text{PO}_3^{2-}$).
   - Both DNA and RNA remain dissolved in the upper aqueous phase, while denatured proteins accumulate at the interphase.
3. **Role of Reagent Components:**
   - **Phenol:** Denatures secondary and tertiary protein structures, inactivating endogenous RNases and DNases.
   - **Chloroform ($\rho = 1.49\text{ g/cm}^3$):** Increases the density of the organic layer, ensuring sharp separation below the aqueous phase ($\rho \approx 1.0\text{ g/cm}^3$), and extracts residual lipids.
   - **Isoamyl Alcohol:** Reduces surface tension to act as an anti-foaming agent.

### 6.2 Back-Extraction Protocol (Phenol Desolvation)

Traces of dissolved phenol in the aqueous phase cause significant downstream enzyme inhibition and distort NanoDrop ratios ($A_{270}$ peak). Following the initial PCI extraction:
1. Pipette the upper aqueous phase into a clean tube.
2. Add an equal volume of **Chloroform:Isoamyl alcohol (24:1)**.
3. Vortex vigorously for $15\text{ seconds}$ and centrifuge at $14,000 \times g$ for $5\text{ minutes}$.
4. Collect the upper aqueous phase. Chloroform strips dissolved phenol from the water into the organic phase, ensuring high purity prior to alcohol precipitation.

---

## 7. Python API Reference

### 7.1 Scaling Buffer Recipes (`calculate_buffer_recipe`)

```python
from biolabcalc.buffers import calculate_buffer_recipe

# Calculate scaled chemicals for 500 mL of 10X TBE
recipe = calculate_buffer_recipe("10X_TBE", target_volume_ml=500.0)

print(f"Buffer: {recipe.name}")
print(f"Volume: {recipe.target_volume_ml} mL")
print(f"pH Specification: {recipe.ph_specification}")
for comp in recipe.components:
    print(f"• {comp.name}: {comp.amount} {comp.unit} ({comp.molar_concentration})")
```

### 7.2 Custom Buffer Builder Workflow (`CustomBufferBuilder`)

```python
from biolabcalc.buffers import CustomBufferBuilder

# Build a customized Western blot transfer buffer
builder = (
    CustomBufferBuilder(name="Towbin_Transfer_Buffer", ph="8.3", storage="Room temperature")
    .add_solid(name="Tris base", target_conc_mm=25.0, mw_g_mol=121.14)
    .add_solid(name="Glycine", target_conc_mm=192.0, mw_g_mol=75.07)
    .add_percent(name="Methanol", target_percent=20.0, is_volume=True, notes="Add chilled before use")
    .add_step("Dissolve Tris base and Glycine in 700 mL deionized water.")
    .add_step("Add 200 mL absolute methanol.")
    .add_step("Bring volume to 1000 mL with deionized water. Do not adjust pH.")
)

# Calculate scaled recipe for 2.0 L
scaled_recipe = builder.build(target_volume_ml=2000.0)
print(f"Tris Required: {scaled_recipe.components[0].amount} g")
print(f"Methanol Required: {scaled_recipe.components[2].amount} mL")
```

### 7.3 NTP Neutralization Protocol (`calculate_ntp_ph_adjustment`)

```python
from biolabcalc.buffers import calculate_ntp_ph_adjustment

# Neutralize 4.0 mL of 100 mM disodium NTP mix to 16.0 mL of 25 mM working stock at pH 7.5
ntp_plan = calculate_ntp_ph_adjustment(
    initial_volume_ml=4.0,
    initial_conc_mm=100.0,
    target_volume_ml=16.0,
    target_conc_mm=25.0,
    target_ph=7.5,
    starting_form="disodium_salt",
    ntp_species="equimolar_mix",
    naoh_stock_m=5.0,
)

print(f"Total NTP Moles: {ntp_plan.total_ntp_mmol:.2f} mmol")
print(f"NaOH Required: {ntp_plan.naoh_mmol:.3f} mmol")
print(f"5M NaOH Volume Needed: {ntp_plan.naoh_volume_ul['5M']} µL")
print(f"Water Diluent Budget: {ntp_plan.water_volume_ml:.2f} mL")
print("\nCritical Bench Steps:")
for step in ntp_plan.preparation_steps:
    print(step)
```

### 7.4 Nucleic Acid Precipitation & Phenol Extraction

```python
from biolabcalc.precipitation import calculate_precipitation, calculate_phenol_chloroform_extraction

# 1. Ethanol Precipitation of dilute RNA sample
precip = calculate_precipitation(
    sample_volume_ul=100.0,
    nucleic_acid="rna",
    alcohol="ethanol",
    salt="naoac",
    low_concentration_carrier=True,
    target_resuspension_conc_ng_ul=500.0,
    estimated_total_ng=15000.0,
)
print(f"Salt: {precip.salt_type} ({precip.salt_volume_ul} µL)")
print(f"Alcohol: {precip.alcohol_type} ({precip.alcohol_volume_ul} µL)")
print(f"Carrier: {precip.carrier_added}")
print(f"Centrifugation: {precip.centrifugation_speed} for {precip.centrifugation_time_min} min")
print(f"Resuspension: {precip.resuspension_guidelines}")

# 2. Acid Phenol:Chloroform Phase Extraction
pci_plan = calculate_phenol_chloroform_extraction(
    sample_volume_ul=200.0,
    nucleic_acid="rna",
    phenol_ph=4.5,
)
print(f"Reagent: {pci_plan.phenol_type}")
print(f"Aqueous Phase Behavior: {pci_plan.aqueous_phase_layer}")
```

---

## 8. Command-Line Interface (CLI)

### 8.1 Buffer Scaling CLI (`biolabcalc buffer`)

```bash
# Generate recipe for 500 mL of 50X TAE
biolabcalc buffer -b 50X_TAE -v 500

# Generate recipe for 2.0 L (2000 mL) of 1X TE buffer
biolabcalc buffer -b 1X_TE -v 2000
```

### 8.2 NTP pH Neutralization CLI (`biolabcalc ntp-ph`)

```bash
# Neutralize 4 mL of 100 mM disodium NTP mix to 16 mL of 25 mM stock at pH 7.5
biolabcalc ntp-ph -v1 4.0 -c1 100 -v2 16.0 -c2 25.0 --form disodium_salt --ph 7.5
```

### 8.3 Precipitation & Extraction CLI

```bash
# Calculate ethanol precipitation for 150 µL RNA
biolabcalc precipitate -v 150 -t rna -a ethanol -s naoac --carrier

# Calculate selective LiCl precipitation for 200 µL IVT transcript
biolabcalc precipitate -v 200 -t rna -a licl -s licl

# Calculate Acid Phenol-Chloroform extraction protocol
biolabcalc pci -v 200 -t rna --ph 4.5
```
