# Core Calculators & Biophysics

The **Core Calculators & Biophysics** module forms the computational backbone of BioLabCalc. It provides high-precision biophysical calculations, sequence manipulation algorithms, robust unit parsing, and experimental quality-control (QC) reporting. Designed for molecular biology laboratories, genomic core facilities, and automated analytical pipelines, this engine guarantees physical mass balance, isotopic fidelity, and reproducibility across bench experiments.

---

## 1. Molecular Weight Determination

BioLabCalc implements rigorous, residue-level molecular weight calculations for deoxyribonucleic acid (DNA), ribonucleic acid (RNA), and polypeptides. In high-resolution mass spectrometry (LC-MS) and biochemical stoichiometry, confusing average isotopic mass with monoisotopic mass introduces significant mass errors ($>0.1\%$). BioLabCalc computes both metrics concurrently.

### 1.1 Fundamental Polymer Mass Physics

The molecular weight of a biological polymer is governed by the summation of its constituent monomeric residue masses plus terminal modifications:

$$MW_{\text{polymer}} = \sum_{i=1}^{k} \left( n_i \cdot MW_{\text{residue}, i} \right) + \Delta MW_{\text{termini}} + \Delta MW_{\text{backbone}}$$

where:
- $n_i$ is the count of residue species $i$.
- $MW_{\text{residue}, i}$ is the molecular weight of the nucleotide or amino acid monophosphate residue as incorporated within the chain (accounting for the condensation loss of $\text{H}_2\text{O}$).
- $\Delta MW_{\text{termini}}$ represents terminal groups (e.g., 5'-phosphorylation, caps, 3'-modifications, peptide N- and C-termini).
- $\Delta MW_{\text{backbone}}$ represents internucleotide or backbone alterations (e.g., phosphorothioate linkages).

---

### 1.2 DNA Molecular Weight (`calculate_dna_mw`)

Standard single-stranded DNA (ssDNA) synthesized via solid-phase phosphoramidite chemistry terminates with a 5'-hydroxyl ($\text{-OH}$) and a 3'-hydroxyl ($\text{-OH}$). Because nucleotide residue weights represent nucleoside monophosphates ($\text{C}_n\text{H}_m\text{N}_x\text{O}_y\text{P}$), a 5'-hydroxyl polymer lacks one phosphate group ($\text{-HPO}_3$, $-79.98\text{ g/mol}$) but gains a proton, yielding a net terminal adjustment of $-61.96\text{ g/mol}$ (monoisotopic: $-61.9558\text{ g/mol}$).

#### Nucleotide Residue Reference Masses

| Base | Residue | Average MW (g/mol) | Monoisotopic MW (g/mol) | Chemical Formula (in-chain) |
| :---: | :--- | :---: | :---: | :--- |
| **A** | 2'-deoxyadenosine-5'-monophosphate | $313.21$ | $313.0576$ | $\text{C}_{10}\text{H}_{12}\text{N}_5\text{O}_5\text{P}$ |
| **C** | 2'-deoxycytidine-5'-monophosphate | $289.18$ | $289.0464$ | $\text{C}_{9}\text{H}_{12}\text{N}_3\text{O}_6\text{P}$ |
| **G** | 2'-deoxyguanosine-5'-monophosphate | $329.21$ | $329.0525$ | $\text{C}_{10}\text{H}_{12}\text{N}_5\text{O}_6\text{P}$ |
| **T** | 2'-deoxythymidine-5'-monophosphate | $304.20$ | $304.0460$ | $\text{C}_{10}\text{H}_{13}\text{N}_2\text{O}_7\text{P}$ |

#### Degenerate IUPAC Deoxyribonucleotide Masses

When degenerate primers or wobble positions are evaluated, BioLabCalc models IUPAC ambiguity codes as the arithmetic mean of constituent bases:

| Code | Bases Represented | Average MW (g/mol) | Monoisotopic MW (g/mol) | Formulation Basis |
| :---: | :--- | :---: | :---: | :--- |
| **R** | A or G (Purine) | $321.21$ | $321.0551$ | $(MW_A + MW_G) / 2$ |
| **Y** | C or T (Pyrimidine) | $296.69$ | $296.5462$ | $(MW_C + MW_T) / 2$ |
| **S** | G or C (Strong) | $309.20$ | $309.0495$ | $(MW_G + MW_C) / 2$ |
| **W** | A or T (Weak) | $308.71$ | $308.5518$ | $(MW_A + MW_T) / 2$ |
| **K** | G or T (Keto) | $316.71$ | $316.5493$ | $(MW_G + MW_T) / 2$ |
| **M** | A or C (Amino) | $301.20$ | $301.0520$ | $(MW_A + MW_C) / 2$ |
| **B** | C, G, or T (not A) | $307.53$ | $307.3816$ | $(MW_C + MW_G + MW_T) / 3$ |
| **D** | A, G, or T (not C) | $315.54$ | $315.3854$ | $(MW_A + MW_G + MW_T) / 3$ |
| **H** | A, C, or T (not G) | $302.20$ | $302.0500$ | $(MW_A + MW_C + MW_T) / 3$ |
| **V** | A, C, or G (not T) | $310.53$ | $310.3855$ | $(MW_A + MW_C + MW_G) / 3$ |
| **N** | A, C, G, or T (Any) | $308.95$ | $308.8006$ | $(MW_A + MW_C + MW_G + MW_T) / 4$ |

#### Terminal & Structural Adjustments ($\Delta MW$)

| 5' Terminal Chemistry | $\Delta MW_{\text{avg}}$ (g/mol) | $\Delta MW_{\text{mono}}$ (g/mol) | Description |
| :--- | :---: | :---: | :--- |
| **Hydroxyl (`hydroxyl`)** | $-61.96$ | $-61.9558$ | Standard synthetic oligo (5'-OH, 3'-OH) |
| **Monophosphate (`monophosphate`)** | $+18.02$ | $+18.0106$ | Phosphorylated oligo / restriction fragment |
| **Triphosphate (`triphosphate`)** | $+177.98$ | $+177.9430$ | Initiated enzymatic transcript |
| **Circular (`circular=True`)** | $0.00$ | $0.0000$ | Closed circular plasmid DNA (no free ends) |

#### Double-Stranded DNA (dsDNA)

When `double_stranded=True`, BioLabCalc generates the complementary Watson-Crick reverse strand, calculates both single-strand weights independently with terminal state symmetry, and sums them:

$$MW_{\text{dsDNA}} = MW_{\text{sense}} + MW_{\text{antisense}}$$

$$\text{GC Content (\%)} = \frac{N_{\text{G, total}} + N_{\text{C, total}}}{2 \cdot L_{\text{duplex}}} \times 100$$

---

### 1.3 RNA Molecular Weight (`calculate_rna_mw`)

Ribonucleic acid exhibits greater structural complexity at its termini and internucleotide linkages. BioLabCalc natively models in vitro transcription (IVT) products, synthetic oligonucleotides, cap analogs, and phosphorothioate backbones.

#### Ribonucleotide Residue Reference Masses

| Base | Residue | Average MW (g/mol) | Monoisotopic MW (g/mol) | Chemical Formula (in-chain) |
| :---: | :--- | :---: | :---: | :--- |
| **A** | Adenosine-5'-monophosphate | $329.21$ | $329.0525$ | $\text{C}_{10}\text{H}_{12}\text{N}_5\text{O}_6\text{P}$ |
| **C** | Cytidine-5'-monophosphate | $305.18$ | $305.0413$ | $\text{C}_{9}\text{H}_{12}\text{N}_3\text{O}_7\text{P}$ |
| **G** | Guanosine-5'-monophosphate | $345.21$ | $345.0474$ | $\text{C}_{10}\text{H}_{12}\text{N}_5\text{O}_7\text{P}$ |
| **U** | Uridine-5'-monophosphate | $306.17$ | $306.0253$ | $\text{C}_{9}\text{H}_{11}\text{N}_2\text{O}_8\text{P}$ |

#### Degenerate IUPAC Ribonucleotide Masses

For RNA degenerate probes and combinatorial transcript libraries:

| Code | Bases Represented | Average MW (g/mol) | Monoisotopic MW (g/mol) | Formulation Basis |
| :---: | :--- | :---: | :---: | :--- |
| **R** | A or G (Purine) | $337.21$ | $337.0500$ | $(MW_A + MW_G) / 2$ |
| **Y** | C or U (Pyrimidine) | $305.68$ | $305.5333$ | $(MW_C + MW_U) / 2$ |
| **S** | G or C (Strong) | $325.20$ | $325.0444$ | $(MW_G + MW_C) / 2$ |
| **W** | A or U (Weak) | $317.69$ | $317.5389$ | $(MW_A + MW_U) / 2$ |
| **K** | G or U (Keto) | $325.69$ | $325.5364$ | $(MW_G + MW_U) / 2$ |
| **M** | A or C (Amino) | $317.20$ | $317.0469$ | $(MW_A + MW_C) / 2$ |
| **B** | C, G, or U (not A) | $318.85$ | $318.7047$ | $(MW_C + MW_G + MW_U) / 3$ |
| **D** | A, G, or U (not C) | $326.86$ | $326.7084$ | $(MW_A + MW_G + MW_U) / 3$ |
| **H** | A, C, or U (not G) | $313.52$ | $313.3730$ | $(MW_A + MW_C + MW_U) / 3$ |
| **V** | A, C, or G (not U) | $326.53$ | $326.3804$ | $(MW_A + MW_C + MW_G) / 3$ |
| **N** | A, C, G, or U (Any) | $321.44$ | $321.2916$ | $(MW_A + MW_C + MW_G + MW_U) / 4$ |

#### RNA Terminal Chemistries

1. **5' Modifications:**
   - **Triphosphate (`triphosphate`):** Standard IVT initiation ($\text{pppNp}\dots$), $+239.94\text{ Da}$ relative to 5'-hydroxyl ($+177.98\text{ Da}$ net).
   - **Monophosphate (`monophosphate`):** Processed or 5'-monophosphorylated RNA, $+79.98\text{ Da}$ relative to 5'-hydroxyl.
   - **Hydroxyl (`hydroxyl`):** Synthetic RNA, base net adjustment of $-61.96\text{ Da}$.
   - **Cap0 ($\text{m}^7\text{GpppN}$):** Clean eukaryotic cap structure, $+749.24\text{ Da}$ relative to 5'-hydroxyl.
   - **Cap1 ($\text{m}^7\text{GpppN}_{2'\text{-O-Me}}$):** Clean mammalian Cap1 with 2'-O-methylated first base, $+763.26\text{ Da}$ relative to 5'-hydroxyl.

2. **3' Modifications:**
   - **Hydroxyl (`hydroxyl`):** Standard canonical terminus ($0.0\text{ Da}$).
   - **Monophosphate (`monophosphate`):** $+79.98\text{ Da}$.
   - **Diphosphate (`diphosphate`):** $+159.96\text{ Da}$.
   - **Triphosphate (`triphosphate`):** $+239.94\text{ Da}$.
   - **Cyclic Phosphate (`cyclic_phosphate`):** $2',3'\text{-cyclic phosphate}$ resulting from ribozyme cleavage or RNase A digestion, $+61.96\text{ Da}$.

3. **Phosphorothioate (PS) Backbone:**
   - Each phosphorothioate internucleotide linkage replaces a non-bridging oxygen atom ($15.9994\text{ Da}$) with a sulfur atom ($32.065\text{ Da}$).
   - $\Delta MW_{\text{avg}} = +16.066\text{ Da}$ per linkage; $\Delta MW_{\text{mono}} = +15.9772\text{ Da}$ per linkage.
   - For fully phosphorothioated RNA, $N_{\text{linkages}} = L - 1$.

---

### 1.4 Protein Molecular Weight (`calculate_protein_mw`)

BioLabCalc calculates polypeptide molecular weights based on the 20 standard amino acid residues, including peptide bond condensation and disulfide bond oxidation states.

$$MW_{\text{protein}} = \sum_{j=1}^{20} \left( n_j \cdot MW_{\text{aa}, j} \right) + MW_{\text{terminal H}_2\text{O}} - \left( N_{\text{disulfide}} \cdot 2.016 \right)$$

where $MW_{\text{terminal H}_2\text{O}} = 18.015\text{ g/mol}$ (monoisotopic: $18.01056\text{ g/mol}$) represents the terminal free amine ($\text{-H}$) and carboxyl ($\text{-OH}$).

#### Amino Acid Residue Weight Table

| AA | 1-Letter | Name | Avg Residue MW (g/mol) | Monoisotopic MW (g/mol) | Side Chain Polarity |
| :---: | :---: | :--- | :---: | :---: | :--- |
| **Ala** | A | Alanine | $71.08$ | $71.03711$ | Non-polar, aliphatic |
| **Arg** | R | Arginine | $156.19$ | $156.10111$ | Positively charged (basic) |
| **Asn** | N | Asparagine | $114.10$ | $114.04293$ | Polar, uncharged |
| **Asp** | D | Aspartate | $115.09$ | $115.02694$ | Negatively charged (acidic) |
| **Cys** | C | Cysteine | $103.14$ | $103.00919$ | Polar, thiol-containing |
| **Glu** | E | Glutamate | $129.12$ | $129.04259$ | Negatively charged (acidic) |
| **Gln** | Q | Glutamine | $128.13$ | $128.05858$ | Polar, uncharged |
| **Gly** | G | Glycine | $57.05$ | $57.02146$ | Non-polar, achiral |
| **His** | H | Histidine | $137.14$ | $137.05891$ | Positively charged (aromatic) |
| **Ile** | I | Isoleucine | $131.17$ | $131.09463$ | Non-polar, branched aliphatic |
| **Leu** | L | Leucine | $131.17$ | $131.09463$ | Non-polar, branched aliphatic |
| **Lys** | K | Lysine | $128.17$ | $128.09496$ | Positively charged (basic) |
| **Met** | M | Methionine | $131.19$ | $131.04049$ | Non-polar, thioether |
| **Phe** | F | Phenylalanine | $147.18$ | $147.06841$ | Non-polar, aromatic |
| **Pro** | P | Proline | $97.12$ | $97.05276$ | Non-polar, cyclic imino |
| **Ser** | S | Serine | $87.08$ | $87.03203$ | Polar, hydroxyl |
| **Thr** | T | Threonine | $101.11$ | $101.04768$ | Polar, hydroxyl |
| **Trp** | W | Tryptophan | $186.21$ | $186.07931$ | Non-polar, aromatic indole |
| **Tyr** | Y | Tyrosine | $163.18$ | $163.06333$ | Polar, aromatic phenol |
| **Val** | V | Valine | $99.13$ | $99.06841$ | Non-polar, branched aliphatic |
| **Sec** | U | Selenocysteine | $150.04$ | $150.9536$ | Polar, catalytic selenium thiol analog ($\text{C}_3\text{H}_5\text{NOSe}$), 21st amino acid |
| **Pyl** | O | Pyrrolysine | $237.30$ | $237.1477$ | Basic, pyrroline-linked lysine derivative ($\text{C}_{12}\text{H}_{19}\text{N}_3\text{O}_2$), 22nd amino acid |

#### Non-Canonical Amino Acid Physics

BioLabCalc natively incorporates the 21st and 22nd genetically encoded amino acids into polypeptide stoichiometry:

1. **Selenocysteine (Sec, U):**
   - Encoded by the UGA stop codon in the presence of a downstream selenocysteine insertion sequence (SECIS) stem-loop element.
   - Replaces the sulfur atom in cysteine with selenium ($\text{Se}$, atomic mass $78.96\text{ Da}$), resulting in an in-chain chemical formula of $\text{C}_3\text{H}_5\text{NOSe}$ with average residue MW $150.04\text{ g/mol}$ and monoisotopic residue MW $150.9536\text{ g/mol}$.

2. **Pyrrolysine (Pyl, O):**
   - Encoded by the UAG stop codon in specific methanogenic archaea and methylotrophic bacteria via a specialized pyrrolysyl-tRNA synthetase.
   - Consists of a 4-methyl-pyrroline-5-carboxylate linked to the $\epsilon$-amine of lysine ($\text{C}_{12}\text{H}_{19}\text{N}_3\text{O}_2$) with average residue MW $237.30\text{ g/mol}$ and monoisotopic residue MW $237.1477\text{ g/mol}$.

#### Disulfide Bond Accounting

When cysteines oxidize into cystines ($\text{Cys-S-S-Cys}$), each pair releases two protons and two electrons:

$$2\text{ R-SH} \longrightarrow \text{R-S-S-R} + 2\text{H}^+ + 2\text{e}^-$$

To preserve physical mass balance, BioLabCalc clamps the count of oxidized cysteines so it cannot exceed the actual number of cysteine residues present in the sequence ($N_{\text{Cys}}$):

$$N_{\text{disulfide}} = \lfloor \max(0, \min(N_{\text{oxidized}}, N_{\text{Cys}})) / 2 \rfloor$$

Each formed disulfide bond subtracts $2.016\text{ g/mol}$ (average) or $2.01565\text{ g/mol}$ (monoisotopic).

---

## 2. Stoichiometry & Copy Number Physics

Laboratory nucleic acid manipulation frequently requires switching between physical mass, molar amount, concentration, and molecular copy number.

```
       Mass (g)
         ▲  │
m = n·MW │  │ n = m / MW
         │  ▼
      Moles (mol)
         ▲  │
N = n·N_A│  │ n = N / N_A
         │  ▼
   Copy Number (N)
```

### 2.1 Governing Equations

1. **Mass-to-Moles Conversion:**
   $$n = \frac{m}{MW}$$
   where $n$ is in moles ($\text{mol}$), $m$ is in grams ($\text{g}$), and $MW$ is in $\text{g/mol}$.

2. **Moles-to-Mass Conversion:**
   $$m = n \cdot MW$$

3. **Mass to Copy Number:**
   $$N = \left( \frac{m}{MW} \right) \cdot N_A$$
   where $N_A = 6.02214076 \times 10^{23}\text{ molecules/mol}$ (Avogadro's constant, CODATA 2018).

4. **Copy Number to Mass:**
   $$m = \frac{N \cdot MW}{N_A}$$

5. **Concentration to Molarity:**
   $$\text{Molarity } (M) = \frac{\text{Mass Concentration (g/L)}}{MW} = \frac{\text{Concentration (ng/\mu L)} \times 10^{-3}}{MW}$$

All stoichiometry solvers enforce strict physical bounds:
- Validates $MW > 0$ across `mass_to_copy_number()` and `concentration_to_molarity()` (as well as `mass_to_moles()` and `moles_to_mass()`), raising `ValueError` to prevent division-by-zero errors.
- Validates that `target_unit.lower()` exists in `MASS_TO_GRAMS` in `copy_number_to_mass()`, raising `ValueError` for unknown target units.

### 2.2 Dynamic Metric Unit Scaling

BioLabCalc features dynamic unit auto-ranging. Outputs are scaled to standard biological orders of magnitude to avoid truncation or scientific notation errors:

| Base Unit | Scale Range | Display Unit | Scaling Factor |
| :--- | :--- | :---: | :---: |
| **Molar ($n$)** | $< 10^{-12}\text{ mol}$ | $\text{fmol}$ | $\times 10^{15}$ |
| | $10^{-12} \le n < 10^{-9}\text{ mol}$ | $\text{pmol}$ | $\times 10^{12}$ |
| | $10^{-9} \le n < 10^{-6}\text{ mol}$ | $\text{nmol}$ | $\times 10^{9}$ |
| | $10^{-6} \le n < 10^{-3}\text{ mol}$ | $\mu\text{mol}$ | $\times 10^{6}$ |
| | $10^{-3} \le n < 1.0\text{ mol}$ | $\text{mmol}$ | $\times 10^{3}$ |
| | $\ge 1.0\text{ mol}$ | $\text{mol}$ | $\times 1.0$ |
| **Mass ($m$)** | $< 10^{-9}\text{ g}$ | $\text{pg}$ | $\times 10^{12}$ |
| | $10^{-9} \le m < 10^{-6}\text{ g}$ | $\text{ng}$ | $\times 10^{9}$ |
| | $10^{-6} \le m < 10^{-3}\text{ g}$ | $\mu\text{g}$ | $\times 10^{6}$ |
| | $10^{-3} \le m < 1.0\text{ g}$ | $\text{mg}$ | $\times 10^{3}$ |
| | $\ge 1.0\text{ g}$ | $\text{g}$ | $\times 1.0$ |

---

## 3. Sequence Utilities (`seq_utils.py`)

BioLabCalc contains a specialized sequence-processing pipeline designed to clean, validate, translate, and compute biophysical properties of raw FASTA sequences.

### 3.1 FASTA Cleansing & Validation

The `clean_sequence` function automatically:
1. Strips FASTA definition lines starting with `>`.
2. Removes all numbers, tabs, spaces, and carriage returns.
3. Removes termination asterisks (`*`) in nucleotide inputs.
4. Normalizes all remaining characters to uppercase.

The `validate_sequence` function validates strings against strict IUPAC degenerate alphabets:
- **DNA:** `[ACGTNRYWSKMBDHV]+`
- **RNA:** `[ACGUNRYWSKMBDHV]+`
- **Protein:** `[ACDEFGHIKLMNPQRSTVWY*]+`

### 3.2 IUPAC Degenerate Nucleotide Table & Complements

To support primer design, degenerate probe synthesis, and enzyme cleavage recognition sites, BioLabCalc supports the full IUPAC degenerate base code and provides exact reverse-complementation:

| IUPAC Code | Meaning | Bases Represented | DNA Complement | RNA Complement |
| :---: | :--- | :---: | :---: | :---: |
| **A** | Adenine | A | **T** | **U** |
| **C** | Cytosine | C | **G** | **G** |
| **G** | Guanine | G | **C** | **C** |
| **T** | Thymine (DNA) | T | **A** | **A** |
| **U** | Uracil (RNA) | U | **A** | **A** |
| **R** | Purine | A or G | **Y** (pYrimidine) | **Y** |
| **Y** | Pyrimidine | C or T/U | **R** (puRine) | **R** |
| **S** | Strong interaction | C or G | **S** (G or C) | **S** |
| **W** | Weak interaction | A or T/U | **W** (T/U or A) | **W** |
| **K** | Keto | G or T/U | **M** (aMino) | **M** |
| **M** | Amino | A or C | **K** (Keto) | **K** |
| **B** | Not A | C, G, or T/U | **V** (Not T/U) | **V** |
| **D** | Not C | A, G, or T/U | **H** (Not G) | **H** |
| **H** | Not G | A, C, or T/U | **D** (Not C) | **D** |
| **V** | Not T/U | A, C, or G | **B** (Not A) | **B** |
| **N** | Any nucleotide | A, C, G, or T/U | **N** | **N** |

### 3.3 Translation (`translate_dna`)

The in silico translation utility converts DNA sequences to amino acid chains across 6 possible reading frames:
- **Forward Frames:** $+1$, $+2$, $+3$.
- **Reverse Complement Frames:** $-1$, $-2$, $-3$.
- **Termination Control (`to_stop=True`):** Halts translation immediately upon reaching the first stop codon (`*`), mirroring in vivo ribosomal termination.

---

## 4. Universal Unit Parsing (`units.py`)

BioLabCalc features `UnitParser`, a static class that parses arbitrary human-written string representations into strictly normalized float values.

### 4.1 Parser Normalization Engine

`UnitParser` uses regex pattern matching to decouple magnitude from units:

```python
r"^([+-]?[0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)([a-zA-Zµ/]*)$"
```

Inputs such as `"500 uL"`, `"0.5 mL"`, `"1.25e-3 L"`, `"25 mM"`, `"10 µM"`, `"1.5 ug"`, or `"100 ng/ul"` are normalized into consistent base metrics.

### 4.2 Supported Metric Domains & Conversions

| Physical Dimension | Method | Default Target | Supported Units |
| :--- | :--- | :---: | :--- |
| **Volume** | `parse_volume` | $\mu\text{L}$ | `l`, `liter`, `ml`, `milliliter`, `ul`, `µl`, `microliter`, `nl`, `nanoliter`, `pl` |
| **Molar Concentration** | `parse_concentration` | $\text{mM}$ | `m`, `molar`, `mm`, `millimolar`, `um`, `µm`, `micromolar`, `nm`, `pm`, `fm` |
| **Mass Concentration** | `parse_concentration` | $\text{mg/mL}$ | `mg/ml`, `ug/ul`, `µg/µl`, `g/l`, `ug/ml`, `µg/ml`, `ng/ul`, `ng/ml` |
| **Mass** | `parse_mass` | $\mu\text{g}$ | `g`, `gram`, `mg`, `milligram`, `ug`, `µg`, `microgram`, `ng`, `nanogram`, `pg`, `fg` |
| **Moles** | `parse_moles` | $\text{nmol}$ | `mol`, `mole`, `mmol`, `umol`, `µmol`, `nmol`, `nanomole`, `pmol`, `fmol`, `amol` |

---

## 5. LabReport Measurement Tracking & QC Engine (`lab_report.py`)

Scientific reproducibility requires traceability. BioLabCalc includes an integrated electronic lab session manager (`LabReport`) that records replicate measurements, evaluates Quality Control (QC) status against specifications, computes sample statistics, and outputs publication-grade reports.

### 5.1 Measurement Tracking & Automated QC

Each measurement recorded by `add_record` encapsulates experimental metadata:
- **`sample_id`**: Sample identifier.
- **`parameter`**: Assay or parameter measured (e.g., $A_{260}$, Yield, Purity, MW).
- **`value`**: Observed numeric value.
- **`unit`**: Physical measurement unit.
- **`target_or_expected`**: Theoretical or specification target.
- **`tolerance_pct`**: Acceptable percentage deviation ($\pm\%$).
- **`percent_deviation`**:
  $$\text{Deviation (\%)} = \frac{\text{Value} - \text{Target}}{\text{Target}} \times 100$$
- **`status`**: Automated status assignment:
  - **`PASS`**: $|\text{Deviation}| \le \text{tolerance\_pct}$
  - **`FLAG`**: $\text{tolerance\_pct} < |\text{Deviation}| \le 1.5 \times \text{tolerance\_pct}$
  - **`FAIL`**: $|\text{Deviation}| > 1.5 \times \text{tolerance\_pct}$

### 5.2 Statistical Aggregation Across Replicates

When multiple experimental replicates ($N \ge 2$) are recorded for a given `(sample_id, parameter)` pair, `calculate_statistics()` computes summary statistics:

1. **Sample Mean ($\bar{x}$):**
   $$\bar{x} = \frac{1}{N} \sum_{i=1}^{N} x_i$$

2. **Sample Standard Deviation ($s$):**
   $$s = \sqrt{\frac{1}{N - 1} \sum_{i=1}^{N} (x_i - \bar{x})^2}$$

3. **Coefficient of Variation ($\%CV$):**
   $$\%CV = \left( \frac{s}{\bar{x}} \right) \times 100$$

4. **Range:**
   $$[\min(x_1, \dots, x_N), \max(x_1, \dots, x_N)]$$

### 5.3 Multi-Format Exporters

The report session can be exported to multiple formats:
- **Markdown (`to_markdown`):** Formatted tables and replicate summaries suitable for GitHub wikis or static documentation.
- **Excel (`to_excel`):** Professional multi-section spreadsheet styled with `openpyxl`. Includes embedded dynamic formulas for percent deviation, automated soft color-coding for QC statuses (green for PASS, yellow for FLAG, red for FAIL), and auto-fitted column dimensions.
- **CSV (`to_csv`):** Tidy-data tabular format compatible with R, Python (pandas), or LIMS databases.
- **JSON (`to_json`):** Structured hierarchical schema suitable for ELN REST APIs.

---

## 6. Python API Reference

### 6.1 Molecular Weight & Stoichiometry

```python
from biolabcalc.molecular_weight import (
    calculate_dna_mw,
    calculate_rna_mw,
    calculate_protein_mw,
    mass_to_moles,
    moles_to_mass,
    mass_to_copy_number,
    copy_number_to_mass,
    concentration_to_molarity,
)

# 1. dsDNA Molecular Weight (100 bp duplex with 5'-phosphate)
dna_res = calculate_dna_mw(
    seq="ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATC",
    double_stranded=True,
    end_5="monophosphate",
)
print(f"dsDNA Average MW: {dna_res.average_mw:.2f} Da")
print(f"dsDNA Monoisotopic MW: {dna_res.monoisotopic_mw:.4f} Da")
print(f"Duplex GC Content: {dna_res.gc_content:.2f}%")

# 2. Synthetic Modified mRNA (Cap1, fully phosphorothioate-linked)
rna_res = calculate_rna_mw(
    seq="AUGGUGAGCAAGGGCGAGGAGCUGUUCACCGGG",
    end_5="cap1",
    end_3="hydroxyl",
    backbone="phosphorothioate",
)
print(f"mRNA Average MW: {rna_res.average_mw:.2f} Da")
print(f"Backbone: {rna_res.backbone}")

# 3. Protein with Disulfide Bonds
prot_res = calculate_protein_mw(
    seq="MKWVTFISLLFLFSSAYSRGVFRRDTHKSEIAHRFKDLGEEHFKGLVLIAFSQYLQQCPFDEHVKLVNELTEFAKTCVADESHAGCEKSLHTLFGDELCKVASLRETYGDMADCCEKQEPERNECFLSHKDDSPDLPKLKPDPNTLCDEFKADEKKFWGKYLYEIARRHPYFYAPELLYYANKYNGVFQECCQAEDKGACLLPKIETMREKVLASSARQRLRCASIQKFGERALKAWSVARLSQKFPKAEFVEVTKLVTDLTKVHKECCHGDLLECADDRADLAKYICDNQDTISSKLKECCDKPLLEKSHCIAEVEKDAIPENLPPLTADFAEDKDVCKNYQEAKDAFLGSFLYEYSRRHPEYAVSVLLRLAKEYEATLEECCAKDDPHACYSTVFDKLKHLVDEPQNLIKQNCDQFEKLGEYGFQNALIVRYTRKVPQVSTPTLVEVSRSLGKVGTRCCTKPESERMPCTEDYLSLILNRLCVLHEKTPVSEKVTKCCTESLVNRRPCFSALTPDETYVPKAFDEKLFTFHADICTLPDTEKQIKKQTALVELLKHKPKATEEQLKTVMENFVAFVDKCCAADDKEACFAVEGPKLVVSTQTALA",
    oxidized_cysteines=34,  # Human Serum Albumin: 17 disulfide bonds
)
print(f"Protein MW: {prot_res.average_mw:.2f} Da")

# 4. Stoichiometry and Copy Number Calculations
val, unit = mass_to_moles(mass_val=2.5, mass_unit="ug", mw=dna_res.average_mw)
print(f"2.5 µg dsDNA = {val:.3f} {unit}")

copies = mass_to_copy_number(mass_val=10.0, mass_unit="ng", mw=dna_res.average_mw)
print(f"10 ng dsDNA = {copies:.3e} copies")

mass_needed = copy_number_to_mass(copies=1e9, mw=dna_res.average_mw, target_unit="ng")
print(f"10^9 copies requires {mass_needed:.4f} ng")
```

### 6.2 Sequence Manipulation

```python
from biolabcalc.seq_utils import (
    clean_sequence,
    validate_sequence,
    reverse_complement,
    translate_dna,
    calculate_gc_content,
)

raw_fasta = """
>ENA|A00001|A00001.1 Synthetic cloning vector pBR322
TTCTCATGTT TGACAGCTTA TCATCGATAA GCTTTAATGC GGTAGTTTAT
CACAGTTAAA TTGCTAACGC AGTCAGGCAC CGTGTATGAA ATCTAACAAT
"""

clean_dna = clean_sequence(raw_fasta)
assert validate_sequence(clean_dna, seq_type="dna")

rc_dna = reverse_complement(clean_dna, seq_type="dna")
gc = calculate_gc_content(clean_dna)

# Translate forward frame 1 to first stop codon
peptide = translate_dna(clean_dna, frame=1, to_stop=True)
print(f"Peptide (Frame +1): {peptide}")
```

### 6.3 LabReport QC Session

```python
from biolabcalc.lab_report import LabReport

report = LabReport(
    title="Plasmid Prep Quality Control",
    experimenter="Dr. J. Watson",
    project="pUC19 Core Validation",
    objective="Quantify yield, replicate consistency, and optical purity.",
)

# Record replicate concentration measurements
report.add_record(sample_id="Plasmid_P1", parameter="Concentration", value=152.4, unit="ng/uL", target=150.0, tolerance_pct=10.0)
report.add_record(sample_id="Plasmid_P1", parameter="Concentration", value=148.9, unit="ng/uL", target=150.0, tolerance_pct=10.0)
report.add_record(sample_id="Plasmid_P1", parameter="Concentration", value=151.0, unit="ng/uL", target=150.0, tolerance_pct=10.0)

# Record purity ratios
report.add_record(sample_id="Plasmid_P1", parameter="A260/A280", value=1.86, unit="ratio", target=1.80, tolerance_pct=5.0)
report.add_record(sample_id="Plasmid_P1", parameter="A260/A230", value=2.15, unit="ratio", target=2.10, tolerance_pct=10.0)

report.add_conclusion("Sample Plasmid_P1 meets all purity and concentration release specifications.")

# Export multi-format reports
report.to_markdown("pUC19_QC_Report.md")
report.to_excel("pUC19_QC_Report.xlsx")
report.to_csv("pUC19_QC_Report.csv")
```

---

## 7. Command-Line Interface (CLI)

BioLabCalc exposes CLI commands for direct terminal execution:

### 7.1 Molecular Weight CLI (`biolabcalc mw`)

```bash
# DNA single strand
biolabcalc mw -s "ATGCGATCGATCGATCGATC" -t dna

# dsDNA duplex with monophosphate 5' ends
biolabcalc mw -s "ATGCGATCGATCGATCGATC" -t dsdna --end5 monophosphate

# RNA transcript with 5'-triphosphate
biolabcalc mw -s "AUGCGAUCGAUCGAUCGAUC" -t rna --end5 triphosphate

# Protein sequence
biolabcalc mw -s "MKWVTFISLLFLFSSAYSRG" -t protein
```

### 7.2 LabReport Tracking CLI (`biolabcalc report`)

```bash
# Initialize a new report session and add a record
biolabcalc report add --sample "Sample_A" --param "Concentration" --val 245.8 --unit "ng/uL" --target 250.0 --tol 5.0

# Export active report session to Markdown or Excel
biolabcalc report export --format excel --out "Experiment_Run_101.xlsx"
biolabcalc report export --format md --out "Experiment_Run_101.md"
```
