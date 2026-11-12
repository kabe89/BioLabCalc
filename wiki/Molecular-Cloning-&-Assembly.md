# Molecular Cloning & Assembly Suite

The `biolabcalc.cloning` module provides an in silico analytical and stoichiometric framework for recombinant DNA assembly workflows. It automates reagent calculations, enzyme and buffer compatibility audits, and stoichiometric balancing across conventional restriction digests, cohesive and blunt-end ligations, isothermal Gibson Assembly (NEBuilder HiFi), and Type IIS Golden Gate combinatorial assembly.

---

## 1. Restriction Endonuclease Digestion Planning

Restriction digestion utilizes Type II endonucleases to generate sequence-specific double-stranded DNA breaks. The `plan_restriction_digest` engine designs single and double digestion setups, evaluates buffer compatibility across New England Biolabs (NEB) buffer families, flags star activity risks, and determines heat inactivation or spin-column clean-up requirements.

### Enzymatic Mechanics & Overhang Generation
Type II restriction endonucleases recognize specific palindromic or interrupted sequences, hydrolyzing phosphodiester bonds on both strands to yield three possible terminus types:
1. **$5'$ Overhang (Cohesive/Sticky):** The enzyme cleaves upstream of the symmetry axis on the top strand, leaving protruding $5'$ single-stranded ends (e.g., EcoRI: $5'\text{-G}\downarrow\text{AATTC}-3'$, yielding $5'\text{-AATT}$ overhangs).
2. **$3'$ Overhang (Cohesive/Sticky):** The enzyme cleaves downstream of the symmetry axis, leaving protruding $3'$ single-stranded ends (e.g., PstI: $5'\text{-CTGCA}\downarrow\text{G}-3'$, yielding $3'\text{-TGCA}$ overhangs).
3. **Blunt Termini:** The enzyme hydrolyzes opposing phosphodiester bonds at the center of the dyad symmetry axis, generating flush double-stranded ends with no single-stranded overhang (e.g., EcoRV: $5'\text{-GAT}\downarrow\text{ATC}-3'$; SmaI: $5'\text{-CCC}\downarrow\text{GGG}-3'$).

### Buffer Systems & Activity Profiles
Modern restriction digests standardize on recombinant albumin-supplemented buffer formulations:
* **rCutSmart™ Buffer:** Standardizes digestion for over 210 restriction endonucleases at 100% relative activity. Formulated with recombinant albumin (rAlbumin) rather than animal-derived bovine serum albumin (BSA), eliminating trace animal pathogen and non-specific RNase/DNase contamination risks.
* **Legacy NEBuffers (1.1, 2.1, 3.1):** Utilized for non-CutSmart enzymes requiring distinct ionic strengths:
  * **NEBuffer r1.1:** Low salt (10 mM Bis-Tris-Propane-HCl, 10 mM $\text{MgCl}_2$, 100 µg/mL rAlbumin, pH 7.0 at 25°C).
  * **NEBuffer r2.1:** Medium salt (50 mM NaCl, 10 mM Tris-HCl, 10 mM $\text{MgCl}_2$, 100 µg/mL rAlbumin, pH 7.9 at 25°C).
  * **NEBuffer r3.1:** High salt (100 mM NaCl, 50 mM Tris-HCl, 10 mM $\text{MgCl}_2$, 100 µg/mL rAlbumin, pH 7.9 at 25°C); standard for BsmBI-v2.

### Buffer Selection & Double Digest Compatibility
When planning single or double digests, `plan_restriction_digest` dynamically evaluates buffer requirements:
* **Single Enzyme:** The reaction buffer is matched directly to the enzyme's optimal standard buffer (e.g., `1X rCutSmart Buffer` for EcoRI or `1X NEBuffer r3.1 Buffer` for BsmBI).
* **Double Digest Buffer Reconciliation:**
  * If both enzymes share the same buffer, that buffer is recommended.
  * If one enzyme requires high-salt `NEBuffer r3.1` (such as BsmBI) while the partner enzyme standardizes on `rCutSmart`, `NEBuffer r3.1` is recommended because CutSmart enzymes generally retain high activity in r3.1.
  * If two enzymes have conflicting or incompatible buffer requirements, the system issues a double digest advisory recommending sequential digestion with intermediate spin-column purification.

### Star Activity Safeguards
Star activity refers to relaxed or altered sequence specificity, where an endonuclease hydrolyzes sequences non-identical to its canonical recognition motif. The most critical operational parameter governing star activity is glycerol concentration:
$$\text{Glycerol Concentration (\% v/v)} = \frac{V_{\text{enzyme}} \times 50\%}{V_{\text{reaction}}}$$
Commercial enzymes are shipped in 50% glycerol storage buffer to prevent freezing at -20°C. To ensure fidelity:
* Total enzyme volume ($V_{\text{enzyme 1}} + V_{\text{enzyme 2}}$) must not exceed 10% of the total reaction volume ($V_{\text{reaction}}$), capping the final glycerol concentration at $\le 5.0\% \text{ v/v}$.
* Extended incubations ($>4\text{ hours}$) should utilize engineered High-Fidelity (HF®) enzyme variants (e.g., EcoRI-HF, BamHI-HF) characterized by lower star-to-canonical activity ratios.

### Thermal Inactivation and Clean-Up
Enzymes must be removed or inactivated prior to downstream ligation to prevent re-digestion of ligated junctions:
* **Heat Inactivatable:** Enzymes denatured by heating at $65^\circ\text{C}$ for 20 minutes (e.g., EcoRI, XhoI, NotI) or $80^\circ\text{C}$ for 20 minutes (e.g., HindIII, DpnI, BsaI-HFv2).
* **Heat Resistant:** Enzymes that resist thermal denaturation (e.g., BamHI, BglII) require silica spin-column clean-up or agarose gel extraction before ligation.

### Standard Enzyme Reference Catalog

| Enzyme | Recognition Site | Cut Type | Overhang | Incubation Temp | Heat Inactivation | Methylation Sensitivity | Buffer |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EcoRI** | `G^AATTC` | 5' overhang | `AATT` | 37°C | 65°C, 20 min | None | rCutSmart |
| **BamHI** | `G^GATCC` | 5' overhang | `GATC` | 37°C | None (Column) | None | rCutSmart |
| **HindIII** | `A^AGCTT` | 5' overhang | `AGCT` | 37°C | 80°C, 20 min | None | rCutSmart |
| **XhoI** | `C^TCGAG` | 5' overhang | `TCGA` | 37°C | 65°C, 20 min | None | rCutSmart |
| **NdeI** | `CA^TATG` | 5' overhang | `TA` | 37°C | 65°C, 20 min | None | rCutSmart |
| **NotI** | `GC^GGCCGC` | 5' overhang | `GGCC` | 37°C | 65°C, 20 min | CpG sensitive | rCutSmart |
| **SalI** | `G^TCGAC` | 5' overhang | `TCGA` | 37°C | 65°C, 20 min | CpG sensitive | rCutSmart |
| **NheI** | `G^CTAGC` | 5' overhang | `CTAG` | 37°C | 65°C, 20 min | None | rCutSmart |
| **BglII** | `A^GATCT` | 5' overhang | `GATC` | 37°C | None (Column) | dam sensitive | rCutSmart |
| **DpnI** | `GA^TC` | Blunt | — | 37°C | 80°C, 20 min | Requires $G^{m6}ATC$ | rCutSmart |
| **EcoRV** | `GAT^ATC` | Blunt | — | 37°C | 80°C, 20 min | None | rCutSmart |
| **SmaI** | `CCC^GGG` | Blunt | — | 25°C | 65°C, 20 min | CpG sensitive | rCutSmart |
| **XbaI** | `T^CTAGA` | 5' overhang | `CTAG` | 37°C | 65°C, 20 min | dam sensitive | rCutSmart |
| **BsaI-HFv2** | `GGTCTC(1/5)` | 5' overhang | `NNNN` | 37°C | 80°C, 20 min | None | rCutSmart |
| **BsmBI-v2** | `CGTCTC(1/5)` | 5' overhang | `NNNN` | 42°C | 80°C, 20 min | None | NEBuffer r3.1 |
| **Esp3I** | `CGTCTC(1/5)` | 5' overhang | `NNNN` | 37°C | 65°C, 20 min | dam/dcm sens. | rCutSmart |
| **BbsI-HF** | `GAAGAC(2/6)` | 5' overhang | `NNNN` | 37°C | 65°C, 20 min | None | rCutSmart |
| **PaqCI** | `CACCTGC(4/8)`| 5' overhang | `NNNN` | 37°C | 65°C, 20 min | None | rCutSmart |
| **SapI** | `GCTCTTC(1/4)`| 5' overhang | `NNN` | 37°C | 65°C, 20 min | CpG sensitive | rCutSmart |

### Python API Usage

```python
from biolabcalc.cloning import plan_restriction_digest, get_restriction_enzyme

# Plan a double digest for 1.5 µg plasmid DNA using EcoRI and XhoI
digest_plan = plan_restriction_digest(
    dna_mass_ug=1.5,
    reaction_volume_ul=50.0,
    enzyme_1="EcoRI",
    enzyme_2="XhoI",
    dna_conc_ng_ul=150.0,
)

print(f"Recommended Buffer: {digest_plan.recommended_buffer}")
print(f"Incubation Temperature: {digest_plan.incubation_temp_celsius}°C")
print(f"Heat Inactivation: {digest_plan.heat_inactivation}")
print("Reagent Setup Table:")
for reagent, volume in digest_plan.reagent_volumes.items():
    print(f"  {reagent}: {volume:.2f} µL")
```

### CLI Command
```bash
biolabcalc digest --dna-ug 1.5 --e1 EcoRI --e2 XhoI --dna-conc 150 --vol 50
```

---

## 2. T4 DNA Ligase Stoichiometry

T4 DNA ligase catalyzes phosphodiester bond formation between adjacent $5'$ phosphate and $3'$ hydroxyl termini in duplex DNA. Efficient bimolecular circularization requires optimizing the molar ratio between insert and linearized vector.

### Mass-to-Mole Conversion & Ratio Equations
The mass of insert DNA required for a defined molar ratio is calculated as:
$$\text{Mass}_{\text{insert}} (\text{ng}) = \text{Mass}_{\text{vector}} (\text{ng}) \times \left( \frac{\text{Length}_{\text{insert}} (\text{bp})}{\text{Length}_{\text{vector}} (\text{bp})} \right) \times R_{\text{molar}}$$
Where $R_{\text{molar}} = \frac{[\text{Insert}]}{[\text{Vector}]}$.

The absolute molar quantity in picomoles ($n_{\text{pmol}}$) for double-stranded DNA (dsDNA) is derived using the average molecular weight of a DNA base pair ($617.96\text{ g/mol}$) plus the two terminal phosphates/hydroxyls ($36.04\text{ g/mol}$):
$$\text{MW}_{\text{dsDNA}} (\text{g/mol}) = (\text{Length}_{\text{bp}} \times 617.96) + 36.04$$
$$n_{\text{pmol}} = \left( \frac{\text{Mass}_{\text{ng}} \times 10^{-9}\text{ g/ng}}{\text{MW}_{\text{dsDNA}}} \right) \times 10^{12}\text{ pmol/mol}$$

### Recommended Molar Ratios & Conditions
* **Cohesive-End Cloning (3:1 Ratio):** Standard for cohesive 2–4 bp overhangs. A three-fold molar excess of insert reduces self-ligation of non-dephosphorylated vector and promotes intermolecular circularization.
* **Blunt-End Cloning (5:1 to 10:1 Ratio):** Blunt ends lack base-pairing stability to align termini. Requires higher insert concentrations, incubation at $16^\circ\text{C}$ overnight, and the inclusion of macromolecular crowding agents such as 5% w/v Polyethylene Glycol (PEG-4000).
* **Equimolar Cloning (1:1 Ratio):** Utilized when the insert is exceptionally large ($>6\text{ kb}$) to avoid multimeric concatenation.

### Python API Usage

```python
from biolabcalc.cloning import calculate_ligation

# Calculate 3:1 ligation for a 4000 bp vector (50 ng) and 1200 bp insert
ligation = calculate_ligation(
    vector_length_bp=4000,
    insert_length_bp=1200,
    vector_mass_ng=50.0,
    molar_ratio=3.0,
    vector_conc_ng_ul=25.0,
    insert_conc_ng_ul=15.0,
    reaction_volume_ul=20.0,
)

print(f"Insert Mass Required: {ligation.insert_mass_ng:.1f} ng")
print(f"Vector Quantity: {ligation.vector_pmol:.3f} pmol")
print(f"Insert Quantity: {ligation.insert_pmol:.3f} pmol")
print(f"Protocol: {ligation.incubation_guidelines}")
```

### CLI Command
```bash
biolabcalc ligate --vector-bp 4000 --insert-bp 1200 --vector-ng 50 --ratio 3 --vector-conc 25 --insert-conc 15
```

---

## 3. Gibson Assembly & NEBuilder HiFi

Gibson Assembly is an isothermal, single-tube homologous recombination system operating at $50^\circ\text{C}$. It coordinates three enzymatic activities:
1. **$5'\to 3'$ Exonuclease (T5 Exonuclease):** Chews back the $5'$ ends of fragments sharing overlapping terminal sequence identity, exposing single-stranded $3'$ overhangs.
2. **High-Fidelity DNA Polymerase (Phusion):** Fills in gaps following annealing of the complementary $3'$ single-stranded overhangs.
3. **Thermostable DNA Ligase (Taq Ligase):** Covalently seals the remaining nicks.

```
Fragment A:  5'======[ Overlap ]======3'
                     |||||||||
Fragment B:          3'======[ Overlap ]======5'
                          |  50°C Isothermal
                          v
T5 Exonuclease chews 5' ends -> Annealing of 3' overhangs -> Phusion fills gaps -> Taq Ligase seals nicks
```

### Homology Overlap Guidelines
* **2–3 Fragments:** 20–25 bp homologous overlap sequence ($T_m \ge 48^\circ\text{C}$).
* **4–6 Fragments:** 30–40 bp homologous overlap sequence ($T_m \ge 60^\circ\text{C}$).

### Stoichiometry & Total DNA Constraints
* **2–3 Fragments (2:1 Insert:Vector Ratio):**
  $$\text{Mass}_{\text{insert}} (\text{ng}) = \text{Mass}_{\text{vector}} (\text{ng}) \times \left( \frac{\text{Length}_{\text{insert}}}{\text{Length}_{\text{vector}}} \right) \times 2.0$$
* **4–6 Fragments (1:1 Equimolar Ratio):** Higher-order assemblies require equimolar ratios ($1:1$) across all fragments to prevent one intermediate from out-competing others during annealing.
* **The 100 ng Linearized Vector Benchmark:** Assemblies typically start with 50–100 ng of linearized vector backbone.
* **Optimal Total DNA Window:** Total DNA in a 20 µL reaction must fall strictly within **0.02 to 0.50 pmol**:
  * $< 0.02\text{ pmol}$: Inefficient fragment collision rates reduce colony yield.
  * $> 0.50\text{ pmol}$: Excess DNA inhibits competent cell transformation and promotes non-specific recombination.

### Incubation Protocol
* **2–3 Fragments:** Incubate at $50^\circ\text{C}$ for 15 minutes.
* **4–6 Fragments:** Incubate at $50^\circ\text{C}$ for 60 minutes.

### Python API Usage

```python
from biolabcalc.cloning import calculate_gibson_assembly

# Assemble 1 vector (5000 bp, 100 ng) and 2 inserts (1500 bp, 800 bp)
gibson = calculate_gibson_assembly(
    vector_length_bp=5000,
    insert_lengths_bp=[1500, 800],
    vector_mass_ng=100.0,
    molar_ratio=2.0,
    vector_conc_ng_ul=50.0,
    insert_concs_ng_ul=[30.0, 20.0],
    reaction_volume_ul=20.0,
)

print(f"Total DNA Input: {gibson.total_dna_pmol:.3f} pmol")
print(f"Insert Masses: {gibson.insert_masses_ng} ng")
print(f"Incubation Protocol: {gibson.incubation_protocol}")
```

### CLI Command
```bash
biolabcalc gibson --vector-bp 5000 --insert-bp 1500 800 --vector-ng 100 --ratio 2
```

---

## 4. Golden Gate Assembly (Type IIS)

Golden Gate Assembly coordinates Type IIS restriction endonucleases and T4 DNA ligase in a single thermocycled reaction. Unlike Type II enzymes that cleave within their recognition site, Type IIS enzymes recognize asymmetric non-palindromic sequences and cleave outside their recognition site, leaving 3-bp or 4-bp customizable cohesive overhangs.

### Enzymatic Mechanism & Directionality
Because the cleavage site is separated from the recognition sequence, the recognition motif can be oriented toward the cleaved fragment. Upon ligation of complementary overhangs, the Type IIS recognition site is eliminated from the assembled construct. This prevents re-cleavage of correctly assembled products, driving the reaction toward completion.

```
Type IIS Recognition Site:  5'-G G T C T C N ^ N N N N -3'
                            3'-C C A G A G N N N N N ^ -5'
                                           | Cleavage
                                           v
                             Non-palindromic 4-nt Overhang (User Defined)
```

### Type IIS Enzyme Comparison

| Enzyme | Recognition Site | Cleavage Distance (Top/Bottom) | Incubation Temp | Buffer | Common Application |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **BsaI-HFv2** | `5'-GGTCTC-3'` | 1 / 5 nt downstream | 37°C | rCutSmart | MoClo Level 0/2, general assemblies |
| **BsmBI-v2** | `5'-CGTCTC-3'` | 1 / 5 nt downstream | 42°C | NEBuffer r3.1 | MoClo Level 1, mammalian vector cassettes |
| **Esp3I** | `5'-CGTCTC-3'` | 1 / 5 nt downstream | 37°C | rCutSmart | BsmBI isoschizomer (runs at 37°C) |
| **BbsI-HF** | `5'-GAAGAC-3'` | 2 / 6 nt downstream | 37°C | rCutSmart | CRISPR sgRNA cloning into pSpCas9 |
| **PaqCI** | `5'-CACCTGC-3'`| 4 / 8 nt downstream | 37°C | rCutSmart | 7-base rare cutter (requires PaqCI activator) |
| **SapI** | `5'-GCTCTTC-3'`| 1 / 4 nt downstream | 37°C | rCutSmart | 3-bp overhang assembly |

### Reaction Stoichiometry & Molar Calculations
Golden Gate Assembly targets 20 femtomoles (fmol) of destination vector and 40 fmol of each insert fragment (2:1 insert:vector molar ratio).
$$\text{Mass}_{\text{DNA}} (\text{ng}) = \frac{\text{Quantity}_{\text{fmol}} \times \text{Length}_{\text{bp}} \times 650.0\text{ g/(mol}\cdot\text{bp)}}{10^6}$$
$$\text{Quantity}_{\text{fmol}} = \frac{\text{Mass}_{\text{ng}} \times 10^6}{\text{Length}_{\text{bp}} \times 650.0}$$

### Thermocycling Schedule
The reaction alternates between endonuclease digestion and T4 DNA ligation:
1. **Assembly Cycling (30 cycles):**
   * **Digestion Phase:** $37^\circ\text{C}$ for 3 minutes (or $42^\circ\text{C}$ specifically for BsmBI-v2; note that Esp3I, an isoschizomer of BsmBI, operates at $37^\circ\text{C}$).
   * **Ligation Phase:** $16^\circ\text{C}$ for 4 minutes.
2. **Terminal Digestion:** $60^\circ\text{C}$ for 5 minutes. Selectively cleaves residual linear fragments and unreacted destination vector containing intact Type IIS sites.
3. **Heat Inactivation:** $80^\circ\text{C}$ for 10 minutes. Thermally denatures both enzymes prior to bacterial transformation.
4. **Transformation:** 2–5 µL into high-efficiency competent *E. coli*.

### Python API Usage

```python
from biolabcalc.cloning import calculate_golden_gate_assembly

# Assemble 1 vector (4000 bp, 20 fmol) and 2 inserts (1000 bp, 500 bp) with BsaI-HFv2
gg = calculate_golden_gate_assembly(
    vector_length_bp=4000,
    insert_lengths_bp=[1000, 500],
    target_vector_fmol=20.0,
    insert_to_vector_ratio=2.0,
    type_iis_enzyme="BsaI-HFv2",
    vector_conc_ng_ul=40.0,
    insert_concs_ng_ul=[25.0, 20.0],
    reaction_volume_ul=20.0,
)

print(f"Vector Mass: {gg.vector_mass_ng:.1f} ng ({gg.vector_fmol:.1f} fmol)")
for idx, (m, f) in enumerate(zip(gg.insert_masses_ng, gg.insert_fmols), 1):
    print(f"Insert #{idx}: {m:.1f} ng ({f:.1f} fmol)")

print("Thermocycling Protocol:")
for step in gg.thermocycling_protocol:
    print(f"  {step}")
```

### CLI Command
```bash
biolabcalc golden-gate --vector-bp 4000 --insert-bp 1000 500 --enzyme BsaI-HFv2 --vector-fmol 20 --ratio 2
```

---

## 5. Cohesive Overhang Compatibility

The `are_overhangs_compatible` function audits restriction enzyme pairs to verify whether their cut termini can ligate:
1. **Blunt Compatibility:** All blunt-end generators (e.g., EcoRV, SmaI, DpnI) are universally compatible with one another.
2. **Polarity Check:** Termini must match in overhang orientation ($5'$ with $5'$, or $3'$ with $3'$). A $5'$ overhang cannot anneal to a $3'$ overhang.
3. **Isocaudomer Compatibility:** Enzymes that generate identical single-stranded overhangs from distinct recognition sites (isocaudomers) produce ligatable junctions that often destroy both recognition sites upon circularization.
   * *Example:* **BamHI** ($5'\text{-G}\downarrow\text{GATCC}-3'$) and **BglII** ($5'\text{-A}\downarrow\text{GATCT}-3'$) both generate identical $5'\text{-GATC}$ overhangs. Ligation generates a non-cleavable $5'\text{-GGATCT}-3'$ hybrid scar.
   * *Example:* **NheI** ($G\downarrow CTAGC$), **SpeI** ($A\downarrow CTAGT$), and **XbaI** ($T\downarrow CTAGA$) all generate identical $5'\text{-CTAG}$ overhangs.

### Python API Usage

```python
from biolabcalc.cloning import are_overhangs_compatible

# Test compatibility between BamHI and BglII (Isocaudomers)
compatible, explanation = are_overhangs_compatible("BamHI", "BglII")
print(f"Compatible: {compatible} -> {explanation}")

# Test compatibility between EcoRI (5' overhang) and EcoRV (blunt)
compatible, explanation = are_overhangs_compatible("EcoRI", "EcoRV")
print(f"Compatible: {compatible} -> {explanation}")
```
