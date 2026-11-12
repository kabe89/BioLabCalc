# BioLabCalc Documentation Wiki

Welcome to the **BioLabCalc** technical documentation and computational biology reference guide. BioLabCalc is an integrated scientific computing suite and biophysical modeling engine designed for wet-lab molecular biologists, synthetic biologists, and protein biochemists.

---

## Core Documentation Modules

| Documentation Guide | Functional Modules | Core Topics Covered |
| :--- | :--- | :--- |
| **[Molecular Cloning & Assembly](Molecular-Cloning-&-Assembly.md)** | `biolabcalc.cloning` | Restriction enzyme digestion planning, NEB buffer compatibility (rCutSmart, Buffers 1.1–3.1), star activity mitigation, heat inactivation profiles; T4 DNA ligase stoichiometry (1:1, 3:1, 5:1 molar ratios); Isothermal Gibson Assembly / NEBuilder HiFi (fmol calculations, 2–3 vs 4–6 fragments, 100 ng vector rule); Golden Gate Type IIS assembly (BsaI, BsmBI, Esp3I, BbsI, PaqCI, SapI), cycling schedules (37°C/16°C), cohesive overhang compatibility checking. |
| **[PCR Kinetics & Primer Design](PCR-Kinetics-&-Primer-Design.md)** | `biolabcalc.pcr`, `biolabcalc.primers` | SantaLucia (1998) unified nearest-neighbor thermodynamic model, salt corrections ($\text{Na}^+, \text{K}^+, \text{Mg}^{2+}$, dNTPs); 3' GC clamp detection (1–2 G/C in last 5 nt); Hairpin, self-dimer, and heterodimer $\Delta G$ thermodynamic scoring; Automated primer pair design (`design_primers`); Polymerase extension rates and annealing temperatures (Q5, Phusion, Taq, OneTaq, KAPA); Touchdown PCR profiles; Master mix formulations with excess pipetting multipliers; qPCR amplification efficiency ($E = 10^{-1/\text{slope}} - 1$). |
| **[In Vitro Transcription (IVT)](In-Vitro-Transcription-(IVT).md)** | `biolabcalc.transcription`, `biolabcalc.buffers` | Bacteriophage T7/T3/SP6 promoter detection and automated trimming; Per-NTP stoichiometric consumption (ATP, CTP, GTP, UTP in pmol and mass) and residual pool projections; Modified ribonucleotides ($m^1\Psi$, $s^2\text{U}$, $5\text{moU}$, $m^5\text{C}$); Co-transcriptional capping analog chemistry (CleanCap AG, CleanCap GG, CleanCap AU/M6, ARCA); Magnesium depletion and pyrophosphate ($PP_i$) precipitation kinetics; Incubation timecourse optimization; 10X HEPES-KOH IVT buffer formulation with temperature compensation. |
| **[Western Blotting Suite](Western-Blotting-Suite.md)** | `biolabcalc.western_blot` | Quantitative electrotransfer condition calculator (wet tank vs semi-dry, target MW categories, voltage, current, duration, Towbin methanol/SDS formulations: 20% for small, 10% or 0% + 0.05% SDS for large $>100\text{ kDa}$); Membrane matrix selection (PVDF 0.2 µm vs 0.45 µm vs Nitrocellulose); Cell lysate loading calculation with Laemmli sample buffer ($4\times / 2\times$); Multi-pass transmembrane protein denaturation safeguards (avoiding 95°C boiling vs 65–70°C / 37°C non-boiling protocols); Comprehensive diagnostic troubleshooting matrix (`no_signal`, `high_background`, `ghost_bands`, `membrane_protein_aggregates`, `patchy_transfer`). |
| **[Bacterial Growth Modeling](Bacterial-Growth-Modeling.md)** | `biolabcalc.ecoli_growth` | Monod and exponential bacterial growth kinetics ($N(t) = N_0 \cdot 2^{t/g}$); Media-specific doubling times (LB, 2×YT, TB, M9 minimal); Arrhenius temperature compensation ($18^\circ\text{C}–37^\circ\text{C}$, $Q_{10} \approx 2.1$ scaling); Inoculation volume and time-to-induction $\text{OD}_{600}$ scheduling; Plasmid isolation yield estimator (pUC high copy, pBR322 medium copy, pET/low copy, BAC single copy); Recombinant protein expression yield advisor. |

---

## Installation & CLI Quickstart

Install the latest version of BioLabCalc via pip:
```bash
pip install biolabcalc
```

Launch the interactive benchtop calculation wizard:
```bash
biolabcalc wizard
```

Or query any module directly via the unified command-line interface:
```bash
# Restriction digest planning
biolabcalc digest --dna-ug 1.5 --e1 EcoRI --e2 XhoI

# PCR optimization
biolabcalc pcr-opt --tm-fwd 61.2 --tm-rev 60.8 --length 650 --poly q5

# In vitro transcription yield modeling
biolabcalc ivt --seq "TAATACGACTCACTATAAGGACUGCAUGC..." --vol 20 --cap cleancap_ag

# Western blot planning
biolabcalc western --target "GluK2" --mw 102.5 --conc 2.5 --ug 20 --membrane

# Bacterial growth modeling
biolabcalc ecoli --mode growth --od-start 0.05 --od-target 0.6 --temp 37
```
