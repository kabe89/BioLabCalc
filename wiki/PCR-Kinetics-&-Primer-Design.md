# PCR Kinetics, Thermodynamics, & Primer Design

The `biolabcalc.pcr` and `biolabcalc.primers` modules provide an integrated biophysical and quantitative suite for modeling polymerase chain reaction (PCR) amplification kinetics, oligonucleotide melting thermodynamics, secondary structure risks, polymerase-specific thermal profiles, and quantitative PCR (qPCR) standard curve efficiencies.

---

## 1. SantaLucia (1998) Nearest-Neighbor Thermodynamic Model

Oligonucleotide hybridization stability is governed by nearest-neighbor interactions rather than base composition alone. Stacking interactions between adjacent dinucleotide pairs, hydrogen bonding geometries, and flanking terminal bases dictate the enthalpy ($\Delta H^\circ$) and entropy ($\Delta S^\circ$) of DNA duplex formation.

The module implements the unified nearest-neighbor thermodynamic parameters established by **SantaLucia (1998)** (*Proc. Natl. Acad. Sci. USA*, 95:1460–1465).

### Core Thermodynamic Equations
The total enthalpy ($\Delta H^\circ_{\text{total}}$) and total entropy ($\Delta S^\circ_{\text{total}}$) for a duplex of length $N$ are calculated by summing transition parameters:
$$\Delta H^\circ_{\text{total}} = \sum_{i=1}^{N-1} \Delta H^\circ_{\text{NN}}(i, i+1) + \Delta H^\circ_{\text{init (5')}} + \Delta H^\circ_{\text{init (3')}}$$
$$\Delta S^\circ_{\text{total}} = \sum_{i=1}^{N-1} \Delta S^\circ_{\text{NN}}(i, i+1) + \Delta S^\circ_{\text{init (5')}} + \Delta S^\circ_{\text{init (3')}} + \Delta S^\circ_{\text{symmetry}}$$

### Nearest-Neighbor Thermodynamic Parameter Table

| Dinucleotide Pair ($5'\to 3'$) | $\Delta H^\circ$ (kcal/mol) | $\Delta S^\circ$ (cal/(mol·K)) | Free Energy $\Delta G_{37}^\circ$ (kcal/mol) |
| :---: | :---: | :---: | :---: |
| **AA / TT** | -7.6 | -21.3 | -1.00 |
| **AT** | -7.2 | -20.4 | -0.88 |
| **TA** | -7.2 | -21.3 | -0.58 |
| **CA / TG** | -8.5 | -22.7 | -1.45 |
| **GT / AC** | -8.4 | -22.4 | -1.44 |
| **CT / AG** | -7.8 | -21.0 | -1.28 |
| **GA / TC** | -8.2 | -22.2 | -1.30 |
| **CG** | -10.6 | -27.2 | -2.17 |
| **GC** | -9.8 | -24.4 | -2.24 |
| **GG / CC** | -8.0 | -19.9 | -1.84 |
| **Terminal Initiation (A-T)** | +2.3 | +4.1 | +1.03 |
| **Terminal Initiation (G-C)** | +0.1 | -2.8 | +0.98 |
| **Symmetry Correction** | 0.0 | -1.4 | +0.43 |

*Note: The symmetry penalty ($\Delta S^\circ_{\text{symmetry}} = -1.4\text{ cal/(mol}\cdot\text{K)}$) is applied strictly to self-complementary duplex sequences.*

---

## 2. Salt and Divalent Cation Corrections

Monovalent cations ($\text{Na}^+, \text{K}^+$) and divalent cations ($\text{Mg}^{2+}$) neutralize negative charge repulsion along the phosphodiester backbone, stabilizing the duplex and raising the melting temperature. However, free deoxynucleotide triphosphates (dNTPs) chelate $\text{Mg}^{2+}$ in a 1:1 molar complex, reducing the biologically active free magnesium concentration.

### Free Magnesium & Monovalent Equivalence
The effective monovalent cation concentration ($[\text{Monovalent}]_{\text{eq}}$) is computed using the empirical relation derived by Owczarzy et al. (2008) and SantaLucia (1998):
$$[\text{Mg}^{2+}]_{\text{free}} = \max\left(0, \frac{[\text{Mg}^{2+}]_{\text{total}} - [\text{dNTP}]_{\text{total}}}{1000}\right) \quad (\text{in M})$$
$$[\text{Monovalent}]_{\text{eq}} = \left(\frac{[\text{Na}^+] + [\text{K}^+]}{1000}\right) + 3.795 \sqrt{[\text{Mg}^{2+}]_{\text{free}}} \quad (\text{in M})$$

### Entropy Salt Correction
Duplex entropy is corrected as a function of oligonucleotide length $N$ and equivalent monovalent ionic strength:
$$\Delta S^\circ_{\text{salt-corrected}} = \Delta S^\circ_{\text{total}} + 0.368 \cdot (N - 1) \cdot \ln([\text{Monovalent}]_{\text{eq}})$$

### Melting Temperature ($T_m$) and Gibbs Free Energy ($\Delta G_{37}^\circ$)
$$T_m (\text{Kelvin}) = \frac{\Delta H^\circ_{\text{total}} \times 1000}{\Delta S^\circ_{\text{salt-corrected}} + R \cdot \ln\left(\frac{C_t}{x}\right)}$$
$$T_m (^\circ\text{C}) = T_m (\text{Kelvin}) - 273.15$$
Where:
* $R = 1.9872\text{ cal/(mol}\cdot\text{K)}$ (ideal gas constant).
* $C_t$ is total single-strand primer concentration in molar units (e.g., $400\text{ nM} = 400 \times 10^{-9}\text{ M}$).
* $x = 1.0$ for non-symmetric primer excess (standard PCR condition, configured by default with `is_excess_primer=True`) or self-complementary oligonucleotides; $x = 4.0$ for non-symmetric equimolar complementary strands (`is_excess_primer=False`).

Gibbs free energy at physiological reaction temperature ($37^\circ\text{C} = 310.15\text{ K}$) indicates duplex hybridization stability:
$$\Delta G_{37}^\circ = \Delta H^\circ_{\text{total}} - \left(310.15 \times \frac{\Delta S^\circ_{\text{salt-corrected}}}{1000}\right) \quad (\text{kcal/mol})$$

---

## 3. Structural Features: GC Clamps, Homopolymers, and Dimers

Primer binding efficiency and enzymatic initiation by DNA polymerase depend critically on terminal structural motifs.

```
5'-----------------------------3'  <- Primer
                    | G | C | G |  <- 3' GC Clamp: 1-2 G/C in last 5 nt ensures stable anchoring
```

### 3' GC Clamp Dynamics
The $3'$ terminal region of a primer is where polymerase extension initiates.
* **Optimal GC Clamp:** 1 to 2 G or C bases within the last 5 nucleotides of the $3'$ terminus. This provides optimal thermal stability without inducing terminal mispriming.
* **Under-clamped ($0\text{ G/C}$):** Excessive A/T at the $3'$ terminus causes thermal fraying, leading to inefficient extension.
* **Over-clamped ($>3\text{ G/C}$):** Excessive terminal G/C content promotes non-specific priming at off-target GC-rich sites and increases primer-dimer formation.

### Homopolymer & Composition Penalties
* **Homopolymer Tracts:** Contiguous runs of $\ge 4$ identical nucleotides (e.g., `AAAA` or `GGGG`) induce replication slippage and secondary structure artifacts.
* **GC Content Window:** Optimal amplification occurs between 40% and 60% GC. Primers outside this window are penalized in quality scoring.

### Dimerization and Secondary Structure Algorithms
1. **Self-Dimer (3' Terminal Cross-Complementarity):** Measures the complementarity between the $3'$ terminal 6 bases of a primer and another molecule of the same primer. High scores indicate primer-dimer artifacts that consume reagents.
2. **Hairpin Loop (Intramolecular Inverted Repeats):** Identifies complementary stems separated by an intervening loop of $\ge 3$ nucleotides. Stems of $\ge 4\text{ bp}$ severely reduce the effective free primer pool.
3. **Heterodimer (Cross-Dimer between Forward and Reverse Primers):** Evaluates duplex formation between forward and reverse primers across sliding frames, with heavy weighting on $3'$ terminal pairings that allow mutual extension into primer-dimer amplicons.

---

## 4. Automated Primer Pair Design (`design_primers`)

The `design_primers` algorithm scans template sequences to identify forward and reverse primer pairs optimized for specific target $T_m$ and amplicon boundaries.

```
Template:  5'======[Fwd Primer ->]====================[<- Rev Primer]======3'
                      |                                       |
                      +------------ Amplicon Length ----------+
```

### Scanning Heuristics
1. **Forward Candidate Extraction:** Generates candidate primers (length 18–25 nt) across the $5'$ template boundary (up to 250 bp).
2. **Reverse Candidate Extraction:** Generates candidate primers from the downstream sense strand and computes their reverse complement.
3. **Filtering Thresholds:**
   * $T_m$ window: $57^\circ\text{C}$ to $64^\circ\text{C}$ (target $60^\circ\text{C}$).
   * GC range: 35% to 65%.
   * Homopolymer avoidance: Excludes sequences containing $\ge 4$ identical bases.
4. **Pair Compatibility Scoring:**
   * $\Delta T_m \le 3.0^\circ\text{C}$ between forward and reverse primers.
   * Cross-dimer exclusion: Penalizes heterodimerization, especially $3'$ terminal cross-matches.
   * Product size constraint: Filters within requested minimum and maximum amplicon length.

### Python API Usage

```python
from biolabcalc.primers import analyze_primer, design_primers, calculate_tm_santalucia

# Direct SantaLucia nearest-neighbor Tm calculation (with primer excess x=1.0 default)
tm, dh, ds, dg = calculate_tm_santalucia("ATGCGATCGATCGATCGCTA", primer_conc_nm=400.0)
# (calculate_tm_santaluicia is also available as an alias)

# Comprehensive thermodynamic analysis of a candidate primer
analysis = analyze_primer(
    seq="ATGCGATCGATCGATCGCTA",
    primer_conc_nm=400.0,
    na_conc_mm=50.0,
    mg_conc_mm=1.5,
    dntp_conc_mm=0.8,
)

print(f"Sequence: {analysis.sequence} ({analysis.length} nt)")
print(f"SantaLucia Tm: {analysis.tm_celsius:.2f}°C")
print(f"GC Content: {analysis.gc_percent:.1f}% (GC Clamp: {analysis.has_gc_clamp})")
print(f"Thermodynamics: dH = {analysis.delta_h_kcal} kcal/mol, dS = {analysis.delta_s_cal} cal/(K*mol)")
print(f"dG (37°C): {analysis.delta_g_37_kcal} kcal/mol")
print(f"Quality Score: {analysis.quality_score} / 100")
```

---

## 5. Polymerase Kinetics & Thermal Cycling Optimization

Different DNA polymerases possess distinct processivity, extension rates, thermal stabilities, and salt tolerances. The `optimize_pcr_protocol` function tailors annealing temperatures, extension times, and cycling profiles based on the selected polymerase.

### Polymerase Benchmark Comparison

| Polymerase | Fidelity vs Taq | Extension Rate (sec/kb) | Denaturation Temp | Annealing Temp ($T_a$) Rule | Recommended Extension Temp |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Q5® High-Fidelity** | $280\times$ | 20–30 s/kb | 98°C | $T_a = \min(T_m) + 1.0^\circ\text{C}$ | 72°C |
| **Phusion®** | $50\times$ | 15–30 s/kb | 98°C | $T_a = \min(T_m) + 1.0^\circ\text{C}$ | 72°C |
| **KAPA HiFi** | $100\times$ | 15–20 s/kb | 95°C | $T_a = \min(T_m) - 2.0^\circ\text{C}$ | 72°C |
| **OneTaq®** | $2\times$ | 60 s/kb | 94–95°C | $T_a = \min(T_m) - 3.0^\circ\text{C}$ | 68°C |
| **Standard Taq** | $1\times$ | 60 s/kb | 95°C | $T_a = \min(T_m) - 3.0^\circ\text{C}$ | 72°C |

### Extension Time Calculation
$$\text{Extension Time (seconds)} = \max\left(15, \left\lceil \frac{\text{Amplicon Length (bp)}}{1000} \times \text{Rate}_{\text{sec/kb}} \right\rceil\right)$$

### Touchdown PCR Architecture
Touchdown PCR prevents non-specific amplification and primer-dimer formation when primer $T_m$ values are mismatched ($\Delta T_m > 3.0^\circ\text{C}$) or templates contain complex secondary structures:
* **Initial Annealing:** Programmed at $\max(T_m) + 3.0^\circ\text{C}$.
* **Ramping Phase (10 cycles):** Decreases annealing temperature by $0.5^\circ\text{C}$ or $1.0^\circ\text{C}$ per cycle until reaching the optimal $T_a$. Early cycles favor specific primer-target duplexes over misprimed off-target sites.
* **Standard Phase (25 cycles):** Continues at constant optimal $T_a$ to exponentially amplify the specific product.

### GC-Rich Template Additives
* **$\ge 65\%$ GC:** Requires 3% to 5% Dimethyl Sulfoxide (DMSO) or 1.0 M Betaine to destabilize G-C base pairing and resolve secondary structures/hairpins in the denatured single strands.
* **$\le 35\%$ GC:** Annealing temperatures must be lowered or primer concentrations elevated to ensure adequate duplex stability.

---

## 6. Amplification Kinetics & Master Mix Formulation

The `calculate_pcr_kinetics` function models cycle-by-cycle product accumulation and tracks substrate depletion.

### Exponential Accumulation & Plateau Model
The theoretical accumulation of amplicon copies at cycle $c$ with amplification efficiency $E$ ($0 \le E \le 1.0$) is:
$$N(c) = N_0 \cdot (1 + E)^c$$
Where $N_0$ is the initial copy number of the target template derived from input mass:
$$N_0 = \frac{\text{Template Mass (g)} \times N_A}{\text{MW}_{\text{template}} (\text{g/mol})}$$
The reaction enters a plateau phase when one of two components is exhausted:
1. **dNTP Depletion:** Each double-stranded amplicon molecule consumes $L_{\text{amplicon}} \cdot (1 - \text{GC})$ of dATP and dTTP, and $L_{\text{amplicon}} \cdot \text{GC}$ of dCTP and dGTP.
2. **Primer Depletion:** Standard reactions contain $400\text{ nM}$ primer ($20\text{ pmol}$ in a 50 µL reaction).

### Master Mix Pipetting Table with Excess Allowance
To compensate for pipetting wall loss, master mix formulations scale reagents by an overage factor (typically 10% excess):
$$\text{Master Multiplier} = N_{\text{reactions}} \times \left(1 + \frac{\text{Excess \%}}{100}\right)$$

### Python API Usage

```python
from biolabcalc.pcr import calculate_pcr_kinetics, build_master_mix, optimize_pcr_protocol

# Model amplification kinetics for a 500 bp amplicon (10 ng plasmid, 30 cycles)
kinetics = calculate_pcr_kinetics(
    amplicon_len_bp=500,
    template_ng=10.0,
    cycles=30,
    efficiency=0.95,
    reaction_volume_ul=50.0,
    dntp_conc_mm=0.2,
    amplicon_gc_pct=52.0,
)

print(f"Amplicon Yield: {kinetics.amplicon_yield_ng:.2f} ng ({kinetics.amplicon_yield_pmol:.3f} pmol)")
print(f"Limiting Reagent: {kinetics.limiting_reagent} (Limiting dNTP: {kinetics.limiting_dntp})")
if kinetics.dntp_exhaustion_cycle:
    print(f"Reagents Exhausted at Cycle: {kinetics.dntp_exhaustion_cycle}")

# Generate Master Mix for 8 reactions with 10% excess
master_mix = build_master_mix(
    num_reactions=8,
    reaction_volume_ul=50.0,
    buffer_conc="5X",
    excess_percent=10.0,
)
for item in master_mix:
    print(f"{item.component}: {item.volume_per_reaction_ul:.1f} µL/rxn -> {item.total_volume_ul:.1f} µL total")
```

---

## 7. qPCR Standard Curve Amplification Efficiency

In quantitative real-time PCR (qPCR), amplification efficiency ($E$) is determined empirically from serial dilution standard curves plotting quantification cycle ($C_t$) against the logarithm of template copy number:
$$C_t = \text{slope} \cdot \log_{10}(\text{Copy Number}) + b$$

### Efficiency Derivation
From the exponential doubling relationship $2^n = 10^1$, a 10-fold dilution corresponds to $\log_2(10) \approx 3.3219$ cycles. The amplification efficiency fraction ($E$) and percentage are derived as:
$$E = 10^{-\frac{1}{\text{slope}}} - 1$$
$$\% \text{Efficiency} = \left(10^{-\frac{1}{\text{slope}}} - 1\right) \times 100\%$$

### Slope vs Efficiency Interpretation

| Standard Curve Slope | Amplification Efficiency ($E$) | Percent Efficiency | Quality Assessment |
| :---: | :---: | :---: | :--- |
| **-3.322** | **1.000** | **100.0%** | **Ideal biological doubling (2-fold increase per cycle)** |
| **-3.400** | 0.969 | 96.9% | Excellent assay performance |
| **-3.580** | 0.903 | 90.3% | Acceptable threshold for gene expression profiling |
| **< -3.600** | < 0.896 | < 89.6% | Suboptimal; check for reaction inhibitors or suboptimal $T_a$ |
| **> -3.100** | > 1.100 | > 110.0% | Non-specific amplification, primer-dimer, or pipetting error |

### Python API Usage

```python
from biolabcalc.pcr import calculate_qpcr_efficiency

# Calculate qPCR efficiency from an experimental standard curve slope
eff_frac, eff_pct = calculate_qpcr_efficiency(slope=-3.34)
print(f"qPCR Efficiency: {eff_frac:.4f} ({eff_pct:.2f}%)")
```

### CLI Command
```bash
biolabcalc pcr-opt --tm-fwd 61.2 --tm-rev 60.8 --length 650 --poly q5 --gc 55
```
