# Bacterial Growth Modeling & Yield Optimization

The `biolabcalc.ecoli_growth` module provides a biophysical and quantitative kinetic suite for modeling *Escherichia coli* batch culture dynamics. It models exponential growth kinetics, Monod substrate utilization, media-specific doubling times, Arrhenius temperature compensation ($Q_{10}$ scaling), starter culture inoculation scheduling, plasmid isolation yields, and recombinant protein expression optimization.

---

## 1. Exponential Kinetics & The Monod Growth Model

Under unconstrained nutrient conditions with adequate aeration, unicellular bacterial populations multiply exponentially via binary fission.

```
OD600 (Log Scale)
  ^
  |                     Stationary Phase
  |                 +----------------------
  |                /
  |               /  Exponential (Log) Phase: dN/dt = mu * N
  |              /
  |             /
  |            /
  |   +-------+  Lag Phase
  +---------------------------------------> Time (Hours)
```

### Exponential Kinetics Equations
The differential rate of biomass accumulation is proportional to the current population density:
$$\frac{dN}{dt} = \mu N$$
Integration yields the classical exponential population trajectory:
$$N(t) = N_0 \, e^{\mu t} = N_0 \cdot 2^{\frac{t}{g}}$$
Where:
* $N_0$ is initial cell density or optical density at 600 nm ($\text{OD}_{600}$).
* $N(t)$ is cell density at time $t$.
* $\mu$ is the specific growth rate constant ($\text{time}^{-1}$).
* $g$ is the generation or doubling time:
  $$g = \frac{\ln 2}{\mu} = \frac{0.69315}{\mu}$$
  $$\mu = \frac{\ln 2}{g} \quad \left(\text{in hr}^{-1}\text{ when } g \text{ is in hours}\right)$$

### Number of Generation Doublings ($n$)
The number of population doublings ($n$) required to transition from an initial optical density ($\text{OD}_{\text{initial}}$) to a target optical density ($\text{OD}_{\text{target}}$) is:
$$n = \log_2\left(\frac{\text{OD}_{\text{target}}}{\text{OD}_{\text{initial}}}\right) = \frac{\ln(\text{OD}_{\text{target}} / \text{OD}_{\text{initial}})}{\ln 2}$$
The total incubation time required ($t_{\text{target}}$) is:
$$t_{\text{target}} = n \times g$$

### Monod Substrate-Limited Kinetics
As nutrients deplete, the specific growth rate decreases following the empirical **Monod equation**:
$$\mu = \mu_{\max} \frac{[S]}{K_s + [S]}$$
Where $[S]$ is the limiting nutrient concentration (e.g., glucose) and $K_s$ is the half-velocity constant (substrate concentration at which $\mu = 0.5\,\mu_{\max}$).

---

## 2. Media-Specific Doubling Times ($g$)

Nutrient density, amino acid availability, and osmotic buffering dramatically impact bacterial replication rates.

### Empirical Doubling Times in Standard Aerated Media

| Growth Medium | Formulation Highlights | Doubling Time at 37°C ($g_{37}$) | Max Saturated $\text{OD}_{600}$ | Application Suitability |
| :--- | :--- | :---: | :---: | :--- |
| **2×YT** | 16 g/L Tryptone, 10 g/L Yeast Extract, 5 g/L NaCl | **18.0 min** | 6.0–8.0 AU | Rapid growth, M13 phage propagation, high-yield cloning |
| **Luria-Bertani (LB)** | 10 g/L Tryptone, 5 g/L Yeast Extract, 10 g/L NaCl | **20.0 min** | 2.5–3.5 AU | Routine molecular cloning, plasmid maintenance |
| **Terrific Broth (TB)** | 12 g/L Tryptone, 24 g/L Yeast Extract, 4 mL/L Glycerol, Potassium Phosphate buffer | **22.0 min** | 8.0–12.0 AU | **High-density protein expression**; phosphate buffer prevents media acidification |
| **M9 Minimal Media** | $M9\text{ salts} + 0.4\%\text{ Glucose} + 1\text{ mM }\text{MgSO}_4$ | **50.0 min** | 1.5–2.5 AU | Isotopic labeling ($^{15}\text{N}, ^{13}\text{C}$ for NMR), metabolic flux analysis |

---

## 3. Arrhenius Temperature Compensation ($Q_{10}$ Scaling)

Bacterial enzymatic reaction rates scale with temperature according to Arrhenius kinetics. The temperature sensitivity of the generation time is modeled using a modified $Q_{10}$ temperature coefficient ($Q_{10} \approx 2.1$):
$$g(T) = g_{37} \cdot Q_{10}^{\frac{37.0 - T}{10.0}}$$

```
Doubling Time (min)
 140 |
 120 |                                        + (18°C: ~120 min)
 100 |
  80 |
  60 |                         + (25°C: ~60 min)
  40 |            + (30°C: ~35 min)
  20 | + (37°C: 20 min)
   0 +--------------------------------------------------> Temperature (°C)
      37         30            25              18
```

### Empirical LB Doubling Times Across Temperatures
* **37°C (Physiological Optimum):** $g = 20.0\text{ minutes}$ ($\mu = 2.079\text{ hr}^{-1}$).
* **30°C (Permissive Induction):** $g = 35.0\text{ minutes}$ ($\mu = 1.188\text{ hr}^{-1}$).
* **25°C (Room Temperature):** $g = 60.0\text{ minutes}$ ($\mu = 0.693\text{ hr}^{-1}$).
* **18°C (Cold Solubility Induction):** $g = 120.0\text{ minutes}$ ($\mu = 0.347\text{ hr}^{-1}$).

### Biological Boundaries & Stress Regimes
1. **Psychro-Stress Regime ($8.0^\circ\text{C} \le T < 15.0^\circ\text{C}$):** Below 15°C, membrane lipid phase transitions (rigidification) and ribosome cold-shock arrests retard growth beyond standard Arrhenius predictions. The model applies an additional $2.8\times$ kinetic retardation factor.
2. **Thermal Cessation Boundary ($T \ge 44.5^\circ\text{C}$):** Exponential growth ceases completely due to widespread protein denaturation and membrane breakdown.
3. **Heat Shock Regime ($39.5^\circ\text{C} < T < 44.5^\circ\text{C}$):** Induces cellular heat shock proteases (Lon, ClpP). Doubling time increases according to:
   $$\text{Penalty Factor} = 1.0 + (T - 39.5) \times 0.35$$

---

## 4. Inoculation Scheduling & Spectrophotometric Linearity

### Starter Inoculation Volume ($C_1 V_1 = C_2 V_2$)
To schedule culture induction precisely during the workday, the volume of overnight starter culture required to achieve a specified initial density in fresh media is calculated as:
$$V_{\text{starter}} = \frac{\text{OD}_{\text{initial, target}} \times V_{\text{target}}}{\text{OD}_{\text{starter}}}$$
$$V_{\text{fresh media}} = V_{\text{target}} - V_{\text{starter}}$$

### Spectrophotometric Light Scattering Linearity Limit
Spectrophotometers do not measure light absorption in bacterial suspensions; rather, they quantify **turbidity** caused by Rayleigh-Gans-Debye light scattering.
* **The Linearity Ceiling ($\text{OD}_{600} \le 0.60\text{ AU}$):** Above $0.60\text{ AU}$, scattered light photons are scattered a second time back into the photodetector (multiple scattering events). This causes severe negative deviation from the Beer-Lambert law.
* **Dilution Rule:** Whenever a culture exceeds an apparent reading of $0.60\text{ AU}$, dilute the sample **1:5 or 1:10 in sterile media** before measuring, and multiply the reading by the dilution factor.
* **Cell Density Conversion:**
  $$1.0\text{ OD}_{600} \approx 8.0 \times 10^8\text{ bacterial cells/mL}$$

---

## 5. Plasmid Isolation Yield Estimator

The `estimate_plasmid_yield` function predicts theoretical and expected purified plasmid DNA yields from bacterial culture harvests.

### Replicon Copy Number Classification

| Plasmid Class | Origin of Replication (Ori) | Control Mechanism | Typical Copy Number | Representative Plasmids |
| :--- | :--- | :--- | :---: | :--- |
| **High Copy** | **pUC** (mutated pMB1) | RNA I / RNA II uninhibited | **500–700** | pUC19, pBluescript, pCR-Blunt |
| **Medium Copy** | **pBR322 / pET** | Rop ($rom$) protein regulated | **20–40** | pET-21, pET-28, pBR322 |
| **Low / Medium Copy** | **pACYC** (p15A) | Compatible with ColE1/pMB1 | **10–15** | pACYC184, pCDFDuet |
| **Low Copy** | **pSC101** | RepA dependent partition | **~5** | pSC101, recombineering vectors |
| **Single Copy** | **BAC** (F-plasmid *oriS*) | ParABC active partitioning | **1** | Bacterial Artificial Chromosomes |

### Mathematical Yield Model
1. **Total Biomass Harvest:**
   $$\text{Total Cells} = V_{\text{culture}} (\text{mL}) \times \text{OD}_{600} \times (8.0 \times 10^8\text{ cells/mL})$$
2. **Total Plasmid Copies:**
   $$\text{Total Copies} = \text{Total Cells} \times \text{Copy Number per Cell}$$
3. **Covalently Closed Circular Plasmid Molecular Weight:**
   $$\text{MW}_{\text{plasmid}} (\text{g/mol}) = \text{Length}_{\text{bp}} \times 617.96\text{ g/(mol}\cdot\text{bp)}$$
   *(Note: Circular plasmid DNA contains no terminal phosphate/hydroxyl modifications, omitting the +36.04 end group correction).*
4. **Theoretical Yield vs Typical Column Recovery:**
   $$\text{Theoretical Yield } (\mu\text{g}) = \left(\frac{\text{Total Copies}}{6.02214 \times 10^{23}}\right) \times \text{MW}_{\text{plasmid}} \times 10^6$$
   $$\text{Expected Miniprep Yield } (\mu\text{g}) = \text{Theoretical Yield} \times 0.55$$
   *(Silica spin-column recovery efficiency is typically ~50–60% due to incomplete silica membrane binding and elution retention).*

---

## 6. Recombinant Protein Expression Yield Advisor

Overexpression of heterologous proteins in *E. coli* using T7 lac promoters (e.g., BL21(DE3) with pET vectors) requires balancing protein translation rate against chaperone folding capacity.

### Total Biomass Protein Estimation
In wet bacterial paste, total cellular protein accounts for approximately **150 µg of protein per mL of culture per $\text{OD}_{600}$ unit**:
$$\text{Total Cellular Protein (mg)} = V_{\text{culture}} (\text{mL}) \times \text{Final OD}_{600} \times 0.150\text{ mg/mL}$$

### Target Protein Accumulation
Given recombinant expression level as a fraction of total cellular protein ($f_{\text{expression}}$, typically 5% to 30%):
$$\text{Recombinant Protein Yield (mg)} = \text{Total Cellular Protein (mg)} \times \left(\frac{f_{\text{expression}}}{100}\right)$$
$$\text{Molar Quantity (nmol)} = \left(\frac{\text{Yield (mg)} \times 10^{-3}}{\text{MW}_{\text{protein}} (\text{Da})}\right) \times 10^9$$

### Temperature vs Solubility Advisor
The `optimize_protein_induction` engine recommends specific temperature-IPTG schedules:
* **Cold Induction ($16^\circ\text{C}–20^\circ\text{C}$ Overnight, 0.1–0.2 mM IPTG):**
  * **Mechanism:** Slows ribosomal translation elongation by ~70%, giving newly synthesized nascent chains time to interact with molecular chaperones (DnaK-DnaJ-GrpE, GroEL-GroES) and undergo correct tertiary folding.
  * **Application:** Multi-domain eukaryotic proteins, enzymes with complex hydrophobic cores, and proteins prone to inclusion bodies.
* **Moderate Induction ($28^\circ\text{C}–30^\circ\text{C}$ for 5–6 hours, 0.4 mM IPTG):**
  * **Mechanism:** Balanced biomass accumulation and folding fidelity.
* **Standard Induction ($37^\circ\text{C}$ for 3–4 hours, 0.5–1.0 mM IPTG):**
  * **Mechanism:** Maximal transcription and translation velocity.
  * **Application:** Small, highly soluble, or intrinsically disordered proteins; or when intentional inclusion body isolation and refolding is desired.

---

## 7. Python API & CLI Integration

### Inoculation and Growth Time Planning

```python
from biolabcalc.ecoli_growth import calculate_ecoli_growth, calculate_inoculation_volume

# Calculate time to reach IPTG induction OD600 (0.60) from starter dilution (0.05) in LB at 37°C
growth = calculate_ecoli_growth(
    initial_od600=0.05,
    target_od600=0.60,
    temperature_celsius=37.0,
    media="LB",
)

print(f"Doubling Time: {growth.doubling_time_min} minutes (mu = {growth.growth_rate_per_hour:.2f} /hr)")
print(f"Number of Doublings: {growth.num_doublings:.2f}")
print(f"Time to Induction: {growth.formatted_time} ({growth.hours_to_target_od:.2f} hours)")

# Inoculation setup: Prepare 500 mL fresh culture at OD 0.05 using an overnight culture at OD 3.2
inoc = calculate_inoculation_volume(
    starter_od600=3.2,
    target_volume_ml=500.0,
    target_od600=0.05,
)
print(f"Add {inoc['starter_culture_volume_ml']:.2f} mL starter culture to {inoc['fresh_media_volume_ml']:.2f} mL fresh media.")
```

### Plasmid Prep and Protein Expression Yield Estimation

```python
from biolabcalc.ecoli_growth import estimate_plasmid_yield, optimize_protein_induction

# Estimate pUC19 plasmid miniprep yield from 4 mL LB culture at OD600 = 3.0
p_yield = estimate_plasmid_yield(
    culture_volume_ml=4.0,
    final_od600=3.0,
    plasmid_type="pUC",
    plasmid_length_bp=2686,
)
print(f"Theoretical Plasmid Yield: {p_yield.theoretical_yield_ug:.1f} µg")
print(f"Expected Miniprep Column Recovery: {p_yield.typical_miniprep_yield_ug:.1f} µg")

# Predict yield for a 45 kDa recombinant protein from 1 L culture induced at 18°C
prot = optimize_protein_induction(
    protein_mw_da=45000.0,
    culture_volume_ml=1000.0,
    final_od600=4.5,
    expression_percent_of_total=15.0,
    temperature_celsius=18.0,
)
print(f"Total Biomass Protein: {prot.total_cellular_protein_mg:.1f} mg")
print(f"Expected Recombinant Protein: {prot.recombinant_protein_yield_mg:.2f} mg ({prot.recombinant_protein_nmol:.1f} nmol)")
print(f"Protocol: {prot.recommended_conditions}")
```

### CLI Command Execution
```bash
# Model E. coli growth kinetics
biolabcalc ecoli --mode growth --od-start 0.05 --od-target 0.6 --temp 37 --media LB

# Calculate starter culture inoculation volume
biolabcalc ecoli --mode inoculate --od-start 3.5 --vol 500 --od-target 0.05

# Predict plasmid isolation yield
biolabcalc ecoli --mode plasmid --vol 5 --od 3.2 --plasmid pUC --length 3200

# Predict recombinant protein expression
biolabcalc ecoli --mode protein --mw 48000 --vol 1000 --od 4.0 --pct 20 --temp 18
```
