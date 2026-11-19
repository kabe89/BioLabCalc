---
name: biolabcalc-in-vivo-arrive
description: Standards, ethical compliance, and calculations for in vivo mouse models adhering to ARRIVE 2.0 Essential 10 guidelines, IACUC protocols, route volume safety limits, and humane endpoints. Use when recording animal studies, calculating dosing, evaluating animal welfare, or generating reports.
---

# biolabcalc-in-vivo-arrive

Govern in vivo animal study calculations, ethical compliance, and experimental reporting according to the ARRIVE 2.0 (Animal Research: Reporting of In Vivo Experiments) Essential 10 guidelines and IACUC welfare standards.

## Core Animal Welfare & Calculation Standards

### 1. Route Administration Volume Safety Limits (Mouse, adult ~20–30 g)
Exceeding physiological volume limits causes severe distress, tissue necrosis, or mortality. BioLabCalc enforces these maximum thresholds:
- **Intraperitoneal (IP)**: Max 20 mL/kg (recommended $\le 10\text{ mL/kg}$, max ~0.5 mL in a 25 g mouse).
- **Subcutaneous (SC)**: Max 20 mL/kg (recommended $\le 10\text{ mL/kg}$, max ~0.5 mL in a 25 g mouse).
- **Intravenous (IV)**: Max 5 mL/kg slow bolus (max ~0.1–0.125 mL in a 25 g mouse).
- **Oral Gavage (PO)**: Max 10 mL/kg (max ~0.25 mL in a 25 g mouse).

If a calculated injection volume exceeds the safe route threshold, flag an immediate volume overload warning.

### 2. Humane Endpoints & Welfare Scoring
Evaluate observations systematically:
- **Body Weight Loss**:
  - Loss $\ge 15\%$ from baseline indicates high severity; triggers immediate veterinary evaluation or euthanasia.
  - Loss $\ge 20\%$ is an automatic mandatory humane endpoint under standard IACUC guidelines.
- **Clinical Condition Scoring (0 to 3)**:
  - 0: Normal grooming, active, clear eyes.
  - 1: Mild piloerection (ruffled fur), slightly reduced exploration.
  - 2: Moderate hunched posture, squinting eyes, delayed movement.
  - 3: Severe lethargy, hypothermia, moribund state (triggers endpoint).
- **Tumor Burden & Welfare**:
  - Mean diameter $> 15\text{ mm}$ or ulceration triggers humane endpoint.

### 3. ARRIVE 2.0 Essential 10 Reporting Checklist
Every generated in vivo experiment report must address:
1. **Study Design**: Number of experimental and control groups, randomization unit.
2. **Sample Size**: Total number of animals per group with statistical power rationale.
3. **Inclusion & Exclusion Criteria**: Defined criteria for removing data points or outliers.
4. **Randomization**: Method used to allocate animals to groups (e.g., block randomization by weight).
5. **Blinding / Masking**: Whether operators and outcome assessors were blinded to group allocation.
6. **Outcome Measures**: Clearly defined primary and secondary endpoints.
7. **Statistical Methods**: Analytical methods and validation of normality/homoscedasticity.
8. **Experimental Animals**: Strain, sex, age, baseline body weight, health/immune status.
9. **Experimental Procedures**: Formulation, dose, route, frequency, duration, anesthesia/analgesia.
10. **Results**: Summary numbers, baseline animal counts, dropouts, and adverse events.
