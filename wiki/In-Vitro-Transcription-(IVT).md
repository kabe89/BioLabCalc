# In Vitro Transcription (IVT) Stoichiometry & Reaction Engineering

The `biolabcalc.transcription` module provides an analytical and biophysical reaction engineering suite for cell-free in vitro transcription (IVT) driven by bacteriophage RNA polymerases (T7, SP6, T3). It models promoter clearance, 5' initiation kinetics, stoichiometric ribonucleotide triphosphate (NTP) consumption, modified nucleotide mass deviations, co-transcriptional capping analog efficiencies, magnesium-pyrophosphate precipitation dynamics, and temperature-compensated reaction buffer formulations.

---

## 1. Promoter Architecture & Automated Cleavage Trimming

Bacteriophage RNA polymerases recognize highly conserved 17-base-pair double-stranded DNA promoter sequences situated immediately upstream of the transcription initiation site ($+1$).

```
                      -17               -1 | +1
Promoter Consensus:  5'- T A A T A C G A C T C A C T A T A G G G -3'
Template Strand:     3'- A T T A T G C T G A G T G A T A T C C C -5'
                                                   ^
                                            Initiation Site (+1)
```

### Consensus Promoters
* **T7 Class III Promoter:** $5'\text{-TAATACGACTCACTATA}\downarrow\text{GGG}-3'$ ($-17$ to $-1$).
* **SP6 Promoter:** $5'\text{-ATTTAGGTGACACTATA}\downarrow\text{G}-3'$ ($-17$ to $-1$).
* **T3 Promoter:** $5'\text{-AATTAACCCTCACTAAA}\downarrow\text{G}-3'$ ($-17$ to $-1$).

### Sense & Antisense Template Auto-Detection (`detect_and_trim_promoter`)
The `detect_and_trim_promoter` engine inspects input sequences for forward sense promoters as well as their reverse complements on the non-coding template strand. When a promoter is identified, the upstream promoter region is automatically excised, setting the transcript $+1$ start site precisely at the first transcribed nucleotide.

### 5' Initiation Kinetics & Abortive Cycling
T7 RNA polymerase initiates transcription via a rigid structural transition. The enzyme exhibits strict nucleotide preferences at the $+1, +2,$ and $+3$ positions:
* **Optimal Initiation ($5'\text{-GGG}\dots$):** 100% relative initiation efficiency. Enables rapid promoter clearance, transitioning from unstable abortive initiation (synthesizing 2–8 nt abortive transcripts) into a stable, processive elongation complex.
* **High Efficiency ($5'\text{-GG}\dots$):** ~85% relative efficiency. Standard for Cas9 guide RNAs (sgRNAs) and synthetic riboswitches.
* **Moderate Efficiency ($5'\text{-G}\dots$):** ~60% relative efficiency. High frequency of abortive cycling.
* **Low Efficiency ($5'\text{-A}\dots$):** ~25% relative efficiency. Requires higher starting ATP concentrations.
* **Severe Impairment ($5'\text{-C}$ or $5'\text{-U}$):** $<10\%$ yield. Pyrimidines at $+1$ induce conformational instability in the catalytic center. Prepending $5'\text{-GG}$ residues is strongly advised.

---

## 2. Per-NTP Stoichiometry & Yield Modeling

Transcription is an irreversible condensation polymerization where one molecule of ribonucleotide triphosphate is incorporated per template base, releasing inorganic pyrophosphate ($PP_i$) and a hydronium ion ($\text{H}^+$).

$$\text{RNA Synthesis (mol)} = \frac{\text{Yield} (\mu\text{g}) \times 10^{-6}\text{ g/\mu g}}{\text{MW}_{\text{RNA}} (\text{g/mol})}$$

### Stoichiometric NTP Consumption
For a transcript of length $L$ with base composition counts $n_A, n_C, n_G, n_U$:
$$\text{Consumed NTP}_i (\text{nmol}) = n_i \times \text{RNA Synthesized (nmol)}$$
$$\text{Residual NTP}_i (\text{mM}) = \frac{\text{Initial NTP}_i (\text{nmol}) - \text{Consumed NTP}_i (\text{nmol})}{V_{\text{reaction}} (\mu\text{L})}$$

### Limiting Ribonucleotide & Theoretical Maximum Yield
The theoretical yield ceiling is dictated by whichever NTP pool is depleted first:
$$\text{Max Transcripts (nmol)} = \min_{i \in \{A,C,G,U\}} \left( \frac{\text{Initial NTP}_i (\text{nmol})}{n_i} \right)$$
$$\text{Theoretical Max Yield} (\mu\text{g}) = (\text{Max Transcripts (nmol)} \times 10^{-9}) \times \text{MW}_{\text{RNA}} \times 10^6$$
$$\text{Reaction Efficiency (\%)} = \left(\frac{\text{Actual Yield} (\mu\text{g})}{\text{Theoretical Max Yield} (\mu\text{g})}\right) \times 100\%$$

### Template DNA Turnover
The molar turnover ratio indicates how many full-length RNA transcripts are produced per input DNA template molecule:
$$\text{Turnover Ratio} = \frac{\text{RNA Produced (nmol)}}{\text{DNA Template Input (nmol)}}$$
Industrial mRNA IVT reactions typically achieve turnover ratios between **200 and 800 transcripts per DNA template**.

---

## 3. Chemically Modified Nucleotides

Therapeutic mRNAs (e.g., vaccine antigens, gene editing cassettes) incorporate modified ribonucleotides to evade innate pattern recognition receptors (TLR3, TLR7, TLR8, and RIG-I) and boost translation capacity.

```
       O                      O                      O
     //                     //                     //
  HN   \                 HN   \                 HN   \
   |    CH3               |    O-CH3             |    S
   O=C  CH                O=C  CH                O=C  CH
     \ /                    \ /                    \ /
      N                      N                      N
      |                      |                      |
   m1Psi (m1Ψ)            5moU                   s2U
  (+14.027 Da)           (+30.026 Da)           (+16.060 Da)
```

The module automatically recalculates the transcript's average molecular weight, theoretical mass yield, and extinction coefficient when modified nucleotides are specified (e.g., `m1psi`, `5mou`, `m5c`, `s2u`, `psi`):

| Modified Nucleotide | Abbreviation | Replaces | $\Delta\text{MW}$ per Base | Biological & Immunological Mechanism |
| :--- | :---: | :---: | :---: | :--- |
| **$N^1$-Methylpseudouridine** | **m1Psi (m1Ψ)** | UTP | +14.027 Da | Completely abolishes TLR7/TLR8 activation; enhances ribosomal translation elongation; clinical standard for COVID-19 mRNA vaccines. |
| **5-Methoxyuridine** | **5moU** | UTP | +30.026 Da | Suppresses immune activation; enhances mRNA half-life. |
| **5-Methylcytidine** | **m5C** | CTP | +14.027 Da | Reduces cellular immunogenicity; frequently combined with pseudouridine. |
| **Pseudouridine** | **Psi (Ψ)** | UTP | 0.000 Da | C-glycoside isomer of uridine; stabilizes tertiary RNA structure through enhanced base-stacking and water bridging. |
| **2-Thiouridine** | **s2U** | UTP | +16.060 Da | Reduces non-specific protein binding and cytokine induction. |

---

## 4. Co-Transcriptional Capping Analog Chemistry

Eukaryotic translation requires a 7-methylguanosine ($m^7\text{G}$) cap structure at the $5'$ terminus to recruit eukaryotic initiation factor 4E (eIF4E) and protect against $5'\to 3'$ exoribonucleases (Xrn1).

### Cap Structures & Comparison

| Cap Analog | Structural Class | Cap Structure | Capping Efficiency | Initiation Sequence | Mass Delta ($\Delta\text{MW}$) | Chemical & Operational Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **CleanCap® AG** | Cap-1 | $m^7\text{G}(5')\text{ppp}(5')(2'O\text{Me})\text{ApG}$ | **~95%** | $5'\text{-AG}\dots$ | +696.5 Da | Co-transcriptional trimer; enzymatic Cap-1 structure; eliminates double-stranded RNA (dsRNA) byproducts. |
| **CleanCap® GG** | Cap-1 | $m^7\text{G}(5')\text{ppp}(5')(2'O\text{Me})\text{GpG}$ | **~95%** | $5'\text{-GG}\dots$ | +696.5 Da | Designed for templates starting with canonical $5'\text{-GG}\dots$ without modifying promoter. |
| **CleanCap® AU / M6**| Cap-1 | Modified trimers | **~95%** | $5'\text{-AU}\dots$ | Variable | Specialty Cap-1 analogs for non-canonical initiation sequences. |
| **ARCA** | Cap-0 | $m_2^{7,3'-O}\text{GpppG}$ | **~75%** | $5'\text{-G}\dots$ | +509.3 Da | Methylated at $3'\text{-OH}$ of $m^7\text{G}$ to force correct orientation. **Requires lowering GTP to 1.0 mM vs 4.0 mM ARCA (4:1 ratio)**. |
| **Standard $m^7\text{G}$** | Cap-0 | $m^7\text{GpppG}$ | **~70%** | $5'\text{-G}\dots$ | +525.3 Da | Incorporates in reverse orientation ~50% of the time, producing non-translatable $G\text{pppm}^7G$ transcripts. |

---

## 5. Magnesium Chelation & Pyrophosphate ($PP_i$) Dynamics

Every nucleotide incorporation event yields one molecule of inorganic pyrophosphate ($PP_i$):
$$\text{RNA}_n + \text{NTP} \xrightarrow{\text{T7 RNAP}} \text{RNA}_{n+1} + PP_i^{4-} + \text{H}^+$$
$$\text{Total } PP_i\text{ Released (nmol)} = (L_{\text{transcript}} - 1) \times \text{RNA Produced (nmol)}$$

### Magnesium Chelation & Catalytic Inactivation
T7 RNA polymerase requires free, unchelated $\text{Mg}^{2+}$ (typically 4–10 mM) to coordinate the active-site carboxylate triad (Asp537, Asp812) and facilitate phosphodiester bond transfer.
1. **Initial Chelation:** Each NTP binds $\text{Mg}^{2+}$ with high affinity ($K_d \approx 0.05\text{ mM}$):
   $$[\text{Mg}^{2+}]_{\text{free, initial}} = [\text{Mg}^{2+}]_{\text{total}} - \sum [\text{NTP}]_{\text{initial}}$$
2. **Pyrophosphate Precipitation Hazard:** As transcription proceeds, accumulation of $PP_i^{4-}$ chelates free $\text{Mg}^{2+}$, rapidly forming an insoluble white crystalline precipitate of magnesium pyrophosphate ($\text{Mg}_2P_2O_7$):
   $$2\,\text{Mg}^{2+} + PP_i^{4-} \longrightarrow \text{Mg}_2P_2O_7 \downarrow$$
   This precipitation strips catalytic $\text{Mg}^{2+}$ from the reaction, causing early elongation arrest and truncated transcripts.

### Mitigation via Inorganic Pyrophosphatase (IPP)
Inclusion of thermostable yeast **Inorganic Pyrophosphatase** (IPP, 0.05–0.1 U/µL) enzymatically hydrolyzes pyrophosphate into orthophosphate:
$$PP_i^{4-} + \text{H}_2\text{O} \xrightarrow{\text{IPP}} 2\,\text{HPO}_4^{2-} + \text{H}^+$$
Orthophosphate forms a soluble magnesium complex, maintaining catalytic $\text{Mg}^{2+}$ availability and sustaining transcription velocity.

---

## 6. Kinetic Incubation Timecourse Optimization

The `optimize_transcription_time` algorithm balances run-off yield against enzyme decay, thermal degradation, and $3'$ non-templated additions ($N+1/N+2$).

```
Yield (%)
100 |                             +----------------- Plateau (Optimal Stop)
 80 |                    +--------+
 60 |              +-----+
 40 |        +-----+
 20 |   +----+
  0 +----------------------------------------------
     0.5    1.0    1.5    2.0    2.5    3.0    4.0   Incubation (Hours)
```

### Transcript Length Classes
* **Small Transcripts ($<120\text{ nt}$; sgRNAs, aptamers):** Optimal incubation: **1.5 to 2.0 hours**. Small RNAs undergo rapid elongation. Prolonged incubation ($>2.5\text{ hours}$) results in severe untemplated nucleotide addition ($3'$ terminal heterogeneity) as the polymerase re-binds blunt RNA ends.
* **Intermediate Transcripts ($120–1000\text{ nt}$):** Optimal incubation: **2.0 to 2.5 hours**.
* **Long Transcripts ($>1000\text{ nt}$; mRNAs):** Optimal incubation: **2.5 to 3.5 hours** in the presence of IPP and RNase inhibitor (40 U per 20 µL reaction).

### Thermal Mode Adaptations
* **Elevated Temperature ($42^\circ\text{C}$):** Resolves stubborn RNA secondary structures, G-quadruplexes, and hairpins. However, T7 RNAP half-life drops to ~50 minutes at 42°C; reactions must be terminated at **1.0 to 1.5 hours**.
* **Reduced Temperature ($30^\circ\text{C}$):** Employed for structurally fragile ribozymes. Elongation velocity drops to ~40% of standard; reactions require **4.0 to 5.0 hours**.

---

## 7. 10X HEPES-KOH IVT Reaction Buffer Formulation

High-yield IVT reactions generate significant hydronium ion loads. For every incorporated NTP, one proton is released; if inorganic pyrophosphatase is active, an additional proton is generated per hydrolyzed $PP_i$:
$$\text{Total Protons (nmol)} = \text{Consumed NTPs (nmol)} + PP_i\text{ Hydrolyzed (nmol)}$$

### The Failure of Tris-HCl in High-Yield IVT
Conventional 40 mM Tris-HCl buffer possesses a steep negative temperature coefficient ($d\text{p}K_a/dT = -0.028\text{ pH}/^\circ\text{C}$). When warmed from 25°C to 37°C, Tris pH drops by **~0.34 units**. Furthermore, Tris buffering capacity collapses below pH 7.5. As millimolar quantities of protons accumulate, the pH rapidly crashes below 7.0, denaturing T7 RNA polymerase.

### The HEPES-KOH Buffer Solution
HEPES (4-(2-hydroxyethyl)-1-piperazineethanesulfonic acid) has half the temperature sensitivity of Tris ($d\text{p}K_a/dT = -0.014\text{ pH}/^\circ\text{C}$) and an optimal $pK_a$ of **7.38 at 37°C**. Potassium counterions ($\text{K}^+$ from KOH) also stimulate T7 RNAP processivity compared to $\text{Na}^+$ or $\text{Cl}^-$.

### Temperature-Compensated pH Titration Equation
To achieve precisely $\text{pH } 7.50$ at the $37^\circ\text{C}$ reaction temperature, the buffer must be titrated at room temperature ($25^\circ\text{C}$) to:
$$\text{pH}_{\text{target, 25°C}} = \text{pH}_{\text{target, 37°C}} - \left(\frac{d\text{p}K_a}{dT}\right) \times (37 - 25) = 7.50 - (-0.014 \times 12) = \mathbf{7.67}$$

### Standard 10X HEPES-KOH IVT Buffer Recipe (for 50 mL stock)

| Component | 1X Final Concentration | 10X Stock Concentration | Mass / Volume (50 mL 10X Stock) |
| :--- | :---: | :---: | :---: |
| **HEPES (free acid, MW 238.30)** | 40 mM | 400 mM | 4.766 g |
| **DTT (Dithiothreitol, MW 154.25)** | 10 mM | 100 mM | 0.771 g |
| **Spermidine (free base, MW 145.25 / Trihydrochloride MW 254.63)** | 2 mM | 20 mM | 0.255 g (Trihydrochloride) |
| **Triton™ X-100 (Surfactant)** | 0.01% v/v | 0.10% v/v | 50.0 µL |
| **5.0 M KOH (Titrant)** | — | — | ~3.0–3.6 mL (titrate to pH 7.67 at 25°C) |
| **Nuclease-Free Water** | — | — | Bring to 50.0 mL final volume |

---

## 8. Python API & CLI Integration

### Full Reaction Calculation (with CleanCap AG and m1Psi)

```python
from biolabcalc.transcription import calculate_ivt_yield

# mRNA transcription: 1200 nt transcript, CleanCap AG, m1Psi modified UTP
result = calculate_ivt_yield(
    rna_seq="TAATACGACTCACTATAAGGACUGCAUGCGACU..." + "A"*50,
    reaction_volume_ul=20.0,
    measured_yield_ug=45.0,
    atp_mm=5.0,
    ctp_mm=5.0,
    gtp_mm=5.0,
    utp_mm=5.0,
    mg_conc_mm=24.0,
    use_pyrophosphatase=True,
    cap_analog="cleancap_ag",
    modified_ntp="m1psi",
    buffer_type="hepes",
)

print(f"Transcript Length: {result.rna_length} nt (MW: {result.rna_mw:,.2f} Da)")
print(f"Actual Yield: {result.rna_yield_ug:.1f} µg ({result.rna_yield_pmol:.2f} pmol)")
print(f"Theoretical Max Yield: {result.theoretical_max_yield_ug:.1f} µg")
print(f"Limiting NTP: {result.limiting_ntp} (Overall Efficiency: {result.overall_efficiency_percent}%)")
print(f"Capping Efficiency: {result.predicted_capping_efficiency_percent}% ({result.cap_analog})")
print(f"PPi Released: {result.pyrophosphate_released_nmol:.2f} nmol ({result.pyrophosphate_released_ug:.1f} µg)")
print(f"Buffer Recommendation: {result.buffer_recommendation}")
```

### Buffer Preparation Recipe Calculation

```python
from biolabcalc.buffers import calculate_hepes_ivt_buffer

# Calculate recipe for 100 mL of 10X HEPES-KOH IVT buffer
buf = calculate_hepes_ivt_buffer(
    target_volume_ml=100.0,
    stock_multiplier=10,
    target_ph_37c=7.50,
    koh_stock_m=5.0,
)

print(f"Titrate to pH {buf.titration_ph_at_25c:.2f} at 25°C with ~{buf.estimated_koh_volume_ml:.2f} mL of 5M KOH.")
for comp in buf.components:
    print(f"  {comp.name}: {comp.amount} {comp.unit} ({comp.final_concentration})")
```

### CLI Command Execution
```bash
# Calculate IVT yield with promoter detection
biolabcalc ivt --seq "TAATACGACTCACTATAAGGACUGCAUGC..." --vol 20 --yield-ug 40 --cap cleancap_ag --mod m1psi

# Optimize incubation timecourse
biolabcalc ivt-time --length 1500 --temp 37 --ipp

# Formulate 10X HEPES-KOH buffer
biolabcalc hepes --vol 100 --mult 10 --ph 7.50
```
