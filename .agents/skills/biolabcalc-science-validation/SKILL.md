---
name: biolabcalc-science-validation
description: Reference benchmarks, biochemical sanity checks, and numerical verification standards for BioLabCalc scientific calculation engines. Use when authoring or verifying in vitro transcription (IVT), PCR kinetics, SDS-PAGE migration, protease cleavage, or plasmid coordinate calculations.
---

# biolabcalc-science-validation

Enforce rigorous biochemical consistency and numerical validation across all BioLabCalc calculation engines. Never hallucinate kinetic rates, promoter motifs, or enzyme cleavage sites.

## Benchmark Reference Standards

### 1. In Vitro Transcription (IVT) Promoters & Kinetics
- **Promoter Consensuses**:
  - `T7 (WT)`: `TAATACGACTCACTATA GGG` (Class III promoter, +1 to +3 preferred `GGG` or `GGA`).
  - `T7_G47A`: Reduced dsRNA byproduct variant for therapeutic mRNA synthesis.
  - `T7_Thermo`: Engineered thermal stability up to 50°C.
  - `SP6`: `ATTTAGGTGACACTATA GAA` (+1 to +3 initiation `GAA`).
  - `T3`: `AATTAACCCTCACTAAA GGG` (+1 to +3 initiation `GGG`).
  - `Syn5`: `ATTGGGCACCCGTAA GG` (high halotolerance, marine cyanophage).
- **Yield Calculation**:
  - 1 µg DNA template (1 kb) produces ~100–180 µg RNA under standard IVT (5 mM each NTP, 20–30 mM MgCl2).
  - Cap analog incorporation (`CleanCap_AG`, `CleanCap_AU`, `ARCA`, `m7G`) must match the +1/+2 transcript initiation nucleotide.

### 2. PCR Kinetics & Cycle Trajectories
- **Polymerase Catalogs**:
  - `Q5`: High-fidelity, processing speed 20–30 s/kb, error rate ~ $5 \times 10^{-7}$, $t_{1/2} (95^\circ\text{C}) \approx 30\text{ min}$.
  - `Phusion`: Processing speed 15–30 s/kb, error rate ~ $4 \times 10^{-7}$, $t_{1/2} (95^\circ\text{C}) \approx 25\text{ min}$.
  - `Taq`: Processing speed 60 s/kb, error rate ~ $2 \times 10^{-4}$, $t_{1/2} (95^\circ\text{C}) \approx 40\text{ min}$.
- **Reaction Kinetic Stages**:
  - Exponential phase ($E \approx 0.95 - 1.0$).
  - Linear transition due to enzyme thermal inactivation and reagent depletion.
  - Plateau phase caused by product strand re-annealing competition ($K_I$ product inhibition) when amplicon concentrations reach $10^{-8} - 10^{-7}\text{ M}$.

### 3. Protease Cleavage & SDS-PAGE Gel Simulation
- **Recognition Motifs**:
  - `TEV`: `ENLYFQ|G` or `ENLYFQ|S` (cuts after Q).
  - `HRV_3C`: `LEVLFQ|GP` (PreScission protease, cuts after Q).
  - `Thrombin`: `LVPR|GS` (cuts after R).
  - `Factor_Xa`: `IEGR|` (cuts after R).
  - `Enterokinase`: `DDDDK|` (cuts after K).
  - `Ulp1_SUMO`: Cleaves tertiary structure at C-terminus of SUMO (`...G-G|`).
  - `Trypsin`: Cleaves C-terminal to `K` or `R` (except when followed by `P`).
- **SDS-PAGE Mobility ($R_f$)**:
  - Migration follows empirical Ferguson relation: $\log_{10}(\text{MW}) \propto -R_f$.
  - Reducing vs. Non-reducing: Disulfide-linked multimers shift to monomeric molecular weights under reducing conditions (+DTT / +$\beta$ME).

### 4. DNA Coordinates & Circular Plasmids
- Coordinates are strictly **1-based inclusive** `[start, end]` with $1 \le \text{start} \le \text{end} \le L$.
- For circular origins spanning the origin ($0 / L$), split into `[start, L]` and `[1, end]`.
