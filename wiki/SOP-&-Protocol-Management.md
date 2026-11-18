# Standard Operating Procedure (SOP) & Protocol Management

In regulated wet-lab and bioprocessing environments (GLP, GMP, ISO 17025), experimental reproducibility requires strict separation between **Master Protocol Blueprints** and **Executed Experimental Instances**. The BioLabCalc SOP subsystem (`biolabcalc.eln.services.sop_service`, `biolabcalc.eln.api.routes.sops`) enforces GxP compliance through formal semantic versioning, electronic Principal Investigator (PI) sign-offs, immutable execution forking, interactive step checkoffs, and kinetic timer integration.

---

## 📋 Master SOP Architecture & Markdown Authoring

Master SOPs represent approved, standard protocols maintained in the master catalog. Each SOP combines high-level Markdown procedural documentation with machine-readable parameter definitions and sequential step checklists.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Master SOP Entity (`MasterSOP`)                 │
├─────────────────┬─────────────────┬──────────────────┬─────────────────┤
│ SOP ID          │ Title           │ Version          │ Status          │
│ (SOP-EXP-001)   │ T7RNAP Express  │ Semantic (1.2)   │ draft/approved  │
├─────────────────┴─────────────────┴──────────────────┴─────────────────┤
│ Description & Formatted Markdown Instructions                          │
├────────────────────────────────────────────────────────────────────────┤
│ Default Parameter Blueprint:                                           │
│ { "host_strain": "BL21(DE3)", "induction_temp_c": 18.0, ... }          │
├────────────────────────────────────────────────────────────────────────┤
│ Structured Step Pipeline (`List[SOPStep]`):                            │
│ ┌─────┬──────────────────────┬─────────────┬─────────────────────────┐ │
│ │ #   │ Step Name            │ Planned Min │ Checkpoint Parameters   │ │
│ ├─────┼──────────────────────┼─────────────┼─────────────────────────┤ │
│ │ 1   │ Seed Culture Inoc    │ 15.0 min    │ 50 mL LB + 50 µg/mL Kan │ │
│ │ 2   │ Bioreactor Scaling   │ 240.0 min   │ 37.0°C, 220 RPM, OD 0.6 │ │
│ │ 3   │ IPTG Induction       │ 10.0 min    │ 0.5 mM IPTG, cool to 18°│ │
│ │ 4   │ Overnight Expression │ 960.0 min   │ 18.0°C, 180 RPM         │ │
│ │ 5   │ Cell Harvest Centrif │ 30.0 min    │ 4°C, 6000 x g, 20 min   │ │
│ └─────┴──────────────────────┴─────────────┴─────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

### Python SOP Definition Example
```python
from biolabcalc.eln.services.sop_service import get_sop_service

sop_service = get_sop_service()

# Register a master protocol
sop = sop_service.create_sop(
    sop_id="SOP-EXP-T7RNAP-001",
    title="High-Density Recombinant T7 RNA Polymerase Expression",
    version="1.0",
    category="Expression",
    description="Standardized fed-batch protocol for pET-28a-T7RNAP in E. coli BL21(DE3).",
    parameters={
        "host_strain": "BL21(DE3)",
        "antibiotic": "Kanamycin 50 ug/mL",
        "target_induction_od600": 0.65,
        "iptg_concentration_mm": 0.5,
        "induction_temp_celsius": 18.0,
        "expression_duration_hours": 16.0,
    },
    steps=[
        {
            "step_index": 1,
            "name": "Primary Inoculation",
            "instruction": "Inoculate 50 mL sterile LB broth containing 50 ug/mL kanamycin with a single fresh colony.",
            "planned_duration_minutes": 15.0,
            "parameters": {"media": "LB", "volume_ml": 50},
        },
        {
            "step_index": 2,
            "name": "Biomass Growth to Mid-Log Phase",
            "instruction": "Incubate culture at 37.0°C, 220 RPM until OD600 reaches 0.60 - 0.70.",
            "planned_duration_minutes": 210.0,
            "parameters": {"temp_c": 37.0, "rpm": 220, "target_od": 0.65},
        },
        {
            "step_index": 3,
            "name": "Temperature Shift & IPTG Induction",
            "instruction": "Transfer flasks to 18°C shaker for 30 minutes to equilibrate, then add IPTG to 0.5 mM final.",
            "planned_duration_minutes": 40.0,
            "parameters": {"temp_c": 18.0, "iptg_mm": 0.5},
        },
        {
            "step_index": 4,
            "name": "Overnight Induction & Harvest",
            "instruction": "Express for 16 hours at 18°C. Pellet cells at 6,000 x g for 20 minutes at 4°C.",
            "planned_duration_minutes": 980.0,
            "parameters": {"centrifuge_rcf": 6000, "duration_min": 20},
        },
    ],
    created_by="researcher_alice",
)
```

---

## 🏷️ Semantic Versioning & PI Sign-Off Lifecycle

BioLabCalc enforces a formal governance lifecycle across all SOPs:

```
┌──────────────┐     PI Approval      ┌─────────────────┐    Deprecation    ┌────────────────┐
│    Draft     │ ───────────────────> │    Approved     │ ────────────────> │   Deprecated   │
│ (In Edit)    │   Electronic Sign    │ (Executable GxP)│   New Version     │ (Historical)   │
└──────────────┘                      └─────────────────┘                   └────────────────┘
```

1. **Semantic Versioning Semantics**:
   * **Patch Release (`1.0` $\rightarrow$ `1.0.1`)**: Clarifications, typographical corrections, safety equipment notes; does not alter chemical stoichiometry or execution steps.
   * **Minor Release (`1.0` $\rightarrow$ `1.1`)**: Additions of optional wash steps, non-critical buffer adjustments, or modified incubation temperature tolerances ($\pm 1.0^\circ\text{C}$).
   * **Major Release (`1.0` $\rightarrow$ `2.0`)**: Changes to host strain, column chromatography resin (e.g., Ni-NTA to Co-TALON), lysis mechanics, or reaction chemistry.
2. **Electronic PI Sign-Off**:
   Before an SOP can be instantiated into daily bench execution runs, a user holding the `principal_investigator` or `lab_manager` role must authorize it:
   ```python
   approved_sop = sop_service.approve_sop(
       sop_id="SOP-EXP-T7RNAP-001",
       approver_id="prof_franklin",
   )
   ```
   This operation transitions the SOP status from `draft` to `approved` and writes an immutable, timestamped event to the cryptographic audit trail recording the approver's identity and signed version.

---

## 🔒 GxP Immutable Execution Forks

In historical research notebooks, altering a master protocol after experiments have completed can retroactively falsify or obscure past methodology. BioLabCalc eliminates this risk through **Immutable Execution Forking**:

```
Master SOP: SOP-EXP-T7RNAP-001 (Version 1.0)
    │
    ├─► Execution Fork FORK-001 (Campaign CMP-2026-T7, Day 1) [FROZEN]
    │   ├── Locked Parameters: { "induction_temp_celsius": 18.0, ... }
    │   └── Execution Checklist: Steps 1..4 (Completed by Operator Alice)
    │
    ▼ (PI updates Master SOP to Version 2.0 with Cobalt resin)
Master SOP: SOP-EXP-T7RNAP-001 (Version 2.0)
    │
    └─► Execution Fork FORK-002 (Campaign CMP-2026-T7, Day 4) [FROZEN]
        ├── Locked Parameters: { "resin": "TALON-Cobalt", ... }
        └── Execution Checklist: Steps 1..4 (In Progress by Operator Bob)
```

### Fork Creation Mechanics
When an operator begins Day 1 of an experimental campaign, the ELN creates an isolated `SOPFork`:
```python
fork = sop_service.fork_sop_for_entry(
    sop_id="SOP-EXP-T7RNAP-001",
    entry_id="ENTRY-CAMP-T7-D1",
    forked_by="researcher_alice",
    parameter_overrides={
        "induction_temp_celsius": 16.0  # Approved run-specific optimization
    },
)
print(f"Created Execution Fork: {fork.fork_id} (Version {fork.sop_version})")
```
* **Approved Status Enforcement**: To enforce GxP compliance, `fork_sop_for_entry` validates that the target master SOP has `approved` status. Attempting to fork an SOP with `draft` or `deprecated` status raises `ValueError` (`Cannot fork SOP '{sop_id}' with status '{status}'. Only approved SOPs can be executed in experimental entries.`).
* **Parameter Snapshot**: Master default parameters are deep-copied and merged with any authorized parameter overrides. The resulting dictionary is permanently locked.
* **Independent Checklist**: The step definitions are deep-copied into individual `StepExecution` instances with pending statuses.

---

## ⏱️ Step Checkoffs, Operator Signatures & Deviations

During laboratory execution, operators check off steps in real time via the web interface or REST API.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  Step 2: Biomass Growth to Mid-Log Phase                                [ COMPLETED ]  │
│  Instruction: Incubate culture at 37.0°C, 220 RPM until OD600 reaches 0.60 - 0.70.    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Planned Duration: 210.0 min  │  Actual Duration: 235.0 min  (Deviation: +25.0 min)    │
│  Completed By:     alice_r    │  Timestamp:       2026-11-12T14:35:10Z                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  ⚠️ Protocol Deviation Logged:                                                         │
│  "Culture growth was slower than anticipated due to initial incubator lag at 35.5°C.   │
│   Induction delayed until target OD600 (0.64) was verified by spectrophotometer."      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Checkoff API Execution
```python
updated_fork = sop_service.checkoff_step(
    fork_id="FORK-SOP-EXP-T7RNAP-001-A48F91",
    step_index=2,
    completed_by="alice_r",
    actual_duration_minutes=235.0,
    deviation_notes="Incubator took 25 minutes longer to reach target OD600 of 0.64.",
)
```

### Protocol Deviation Logging
Regulatory guidelines mandate that any departure from written procedure must be documented, justified, and reviewed:
1. **Planned vs. Actual Delta**: The system automatically computes and displays the variance between `planned_duration_minutes` and `actual_duration_minutes`.
2. **Mandatory Deviation Rationale**: If actual duration or parameter measurements fall outside pre-configured tolerances, the UI requires the operator to provide an explanation before the checkoff is accepted.
3. **Audit Ledger Coupling**: Every checkoff event generates a `STEP_CHECKOFF` audit event containing the exact timestamp, actor ID, duration metrics, and deviation text.

---

## ⏲️ Real-Time Kinetic Timers & Audio Alerts

The ELN web interface features an integrated kinetic timer engine (`eln/web/static/timer_widget.js`) directly synchronized with SOP execution steps:

1. **Multi-Timer Parallel Tracking**: Run multiple incubation, digestion, and centrifuge countdowns simultaneously across different benches.
2. **Step Duration Pre-population**: Clicking a step's timer icon automatically initializes the timer to `planned_duration_minutes`.
3. **Elapsed Countup & Overtime Warning**: If an incubation timer expires, it immediately transitions to a flashing amber/red overtime countup, alerting the scientist to the exact duration of over-incubation.
4. **Web Audio Synthesis**: Built-in harmonic frequency beeps fire across standard computer or mobile speakers upon milestone completion without relying on external MP3 assets.

---

## 📡 REST API Reference

The SOP router (`biolabcalc.eln.api.routes.sops`) exposes the following endpoints:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/sops` | List all Master SOPs, filterable by `category` and `status`. |
| `POST` | `/api/sops` | Create a new master SOP blueprint (Draft status). |
| `GET` | `/api/sops/{sop_id}` | Retrieve complete master SOP details and step checklist. |
| `POST` | `/api/sops/{sop_id}/approve` | Principal Investigator authorization sign-off. |
| `POST` | `/api/sops/{sop_id}/fork` | Instantiate an immutable execution fork for an experiment. |
| `GET` | `/api/sops/forks/{fork_id}` | Retrieve real-time progress and checklist of an execution fork. |
| `POST` | `/api/sops/forks/{fork_id}/checkoff` | Record step completion, operator signature, duration, and deviation. |

---

## 🌐 Shared Protocol Repository & SOP Branching

In multi-user laboratory network environments, researchers often need to branch or customize standard laboratory protocols for specific research objectives without overwriting standard master blueprints.

### 1. Protocol Lineage & Forking
When a researcher customizes an existing SOP:
* **Lineage Preservation**: The branched SOP maintains a pointer to `parent_sop_id` and creates an incremental version (e.g. `1.0-fork.1`).
* **Custom Parameter Overrides**: The user can modify incubation times, buffer formulas, or antibiotic concentrations while inheriting all validated safety steps.
* **Shared Drive Storage**: Protocols are stored in the central database on the shared network drive, making new methods immediately accessible to all lab members.

### 2. Multi-User Protocol Synchronization
When multiple researchers access the protocol library over a shared network drive:
* Concurrency controls prevent simultaneous conflicting edits to master blueprints.
* Protocol revisions generate an audit trail event documenting who modified the protocol, when, and the rational diff between versions.

---

## 🖨️ Printable Benchtop Companion & Physical Lab Notebook Sheets

In wet-lab environments, biosafety cabinets, radioisotope suites, and cleanrooms, scientists frequently cannot operate laptops or touchscreens while wearing PPE. Furthermore, many academic, clinical, and industrial laboratories enforce physical paper laboratory notebooks (e.g., Boorum & Pease archival bound notebooks) for patent documentation and regulatory compliance.

BioLabCalc's `printable_protocol.py` engine generates standalone, print-optimized HTML5/CSS documents (`@media print`) that can be printed on benchtop laser printers and pasted directly into physical lab notebooks.

### 1. 7-Stage Thermodynamic Addition Priority (Enzyme-Last Hierarchy)

Master mixes are automatically structured following the thermodynamic order of addition to prevent osmotic shock, buffer precipitation, or premature enzymatic degradation:

| Stage | Component Category | Examples | Bench Directive & Handling |
| :---: | :--- | :--- | :--- |
| **1** | **Water & Solvents** | Nuclease-free $\text{ddH}_2\text{O}$, DEPC water | Ambient; provides bulk thermal and ionic dilution buffer |
| **2** | **Salts & Reaction Buffers** | 10X Taq Buffer, 5X Q5 Buffer, $\text{MgCl}_2$ | Vortex and thaw completely before adding |
| **3** | **Reaction Additives & Enhancers** | DMSO, Betaine, Glycerol, BSA, DTT | Thaw gently; mix thoroughly |
| **4** | **Nucleotides** | dNTP mix (10 mM each), rNTPs | Keep chilled; avoid freeze-thaw cycles |
| **5** | **Oligos & Primers** | Forward / Reverse PCR primers, probes | Pulse spin before opening caps |
| **6** | **Template DNA / RNA** | Plasmid DNA, cDNA, gDNA | Added individually to reaction wells (separate addition) |
| **7** | **Active Enzymes** | DNA Polymerase, Reverse Transcriptase, Ligase | **[❄️ 4°C ICE]** Keep on ice; add last; flick/invert gently to mix |

### 2. Overage Calculations & Pipette Tool Sizing

Formulations automatically compute surplus reaction volume to absorb pipetting loss across viscous components:

$$\text{Total Multiplier} = N_{\text{rxn}} \cdot \left(1 + \frac{\text{Overage \%}}{100}\right)$$

Every component line item displays:
- Stock concentration and desired final reaction concentration.
- Single reaction volume ($\mu\text{L}$) and total master mix volume ($\mu\text{L}$).
- Recommended calibrated air-displacement pipette tool:
  - $\le 2.0\,\mu\text{L} \rightarrow \mathbf{P2}$
  - $2.1 - 10.0\,\mu\text{L} \rightarrow \mathbf{P10}$
  - $10.1 - 20.0\,\mu\text{L} \rightarrow \mathbf{P20}$
  - $20.1 - 200.0\,\mu\text{L} \rightarrow \mathbf{P200}$
  - $> 200.0\,\mu\text{L} \rightarrow \mathbf{P1000}$

### 3. Visual Benchware Plate & Tube Maps

The printable sheet formats visual loading maps with physical orientation indicators:
- **96-Well & 384-Well Grids**: Features a high-contrast chamfer notch indicator at coordinate **A1** matching physical microplate geometry.
- **Tube & Strip Racks**: Formatted for 24-tube bench racks or 8-strip PCR tubes.
- **Benchtop Well Checkboxes**: Each well contains a circular checkbox allowing operators to physically check off wells as samples or master mix aliquots are dispensed.

### 4. Physical Lab Notebook Trim Guides & Archival Sign-Off

The output CSS renders cutting and pasting guides designed specifically for physical laboratory notebook tape-ins:
- **Notebook Trim Guides**: Pre-calibrated margins for $8'' \times 10''$ standard notebooks or $7.5'' \times 9.5''$ composition notebooks.
- **Tamper-Evident Paste Seams**: Corner tabs and cross-boundary witness lines across the paper margin (`[Initials / Date Across Seam]`) ensuring compliance with intellectual property and legal patent filing guidelines.
- **GLP/GMP Archival Sign-Off Block**: Pre-formatted tables capturing Operator Name, Signature, Date Executed, Project ID, SOP ID, Notebook & Page Number, and Witness/PI Counter-Signature.

### 5. Python API & CLI Generation

```bash
# Generate a 24-reaction PCR bench sheet with 10% overage and 96-well plate map
biolabcalc print-protocol \
  --title "Q5 Colony PCR Screening" \
  --reactions 24 \
  --overage 10 \
  --template pcr \
  --plate-type 96-well \
  --trim-size 8x10 \
  --output "colony_pcr_protocol.html"
```

Via Python:

```python
import biolabcalc as blc
from biolabcalc.printable_protocol import (
    build_bench_master_mix,
    generate_plate_bench_sheet,
    render_bench_companion_html,
    GLPSignOffBlock,
)

# 1. Formulate master mix with 10% overage
mix = build_bench_master_mix(
    num_reactions=16,
    excess_percent=10.0,
    reagents_per_rxn=[
        {"name": "Nuclease-Free Water", "stock": "-", "final": "-", "volume_ul": 14.5, "category": "water"},
        {"name": "5X Q5 Reaction Buffer", "stock": "5X", "final": "1X", "volume_ul": 5.0, "category": "buffer"},
        {"name": "10 mM dNTPs", "stock": "10 mM", "final": "200 µM", "volume_ul": 0.5, "category": "dntp"},
        {"name": "Fwd Primer (10 µM)", "stock": "10 µM", "final": "0.5 µM", "volume_ul": 1.25, "category": "primer"},
        {"name": "Rev Primer (10 µM)", "stock": "10 µM", "final": "0.5 µM", "volume_ul": 1.25, "category": "primer"},
        {"name": "Plasmid DNA", "stock": "50 ng/µL", "final": "50 ng", "volume_ul": 2.0, "category": "template", "is_separate": True},
        {"name": "Q5 High-Fidelity DNA Polymerase", "stock": "2 U/µL", "final": "0.02 U/µL", "volume_ul": 0.5, "category": "enzyme"},
    ],
    single_rxn_total_vol_ul=25.0,
    aliquot_per_well_ul=23.0,
)

# 2. Map samples across a 96-well plate
plate = generate_plate_bench_sheet(
    sample_names=[f"Colony-{i+1}" for i in range(16)],
    plate_type="96-well",
)

# 3. Render HTML document
html_doc = render_bench_companion_html(
    title="pUC19 Insert Verification Colony PCR",
    master_mix=mix,
    plate_map=plate,
    sign_off=GLPSignOffBlock(operator_name="Dr. Jane Smith", project_id="PRJ-SYNTH-04"),
    page_trim="8x10",
)

with open("bench_protocol.html", "w", encoding="utf-8") as f:
    f.write(html_doc)
```

---

## 🔗 Related Documentation
* [Electronic Lab Notebook (ELN)](Electronic-Lab-Notebook-(ELN)) — System architecture and web SPA overview.
* [GxP Compliance & Audit Trails](GxP-Compliance-&-Audit-Trails) — Audit ledger hashing, 21 CFR Part 11, and electronic signatures.
* [Inventory & Freezer LIMS](Inventory-&-Freezer-LIMS) — Linking SOP execution yields to freezer tubes and aliquots.
