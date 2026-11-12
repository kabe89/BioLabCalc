# Laboratory Inventory & Freezer LIMS

Cryogenic and cold-chain sample management is a critical requirement for research integrity. Lost aliquots, unrecorded freeze-thaw degradation, and ambiguous tube labels can compromise months of laboratory investigation. The BioLabCalc Inventory & Freezer LIMS subsystem (`biolabcalc.eln.services.inventory_service`, `biolabcalc.eln.web.static.freezer_grid.js`) delivers a comprehensive cold-chain tracking platform featuring a 6-tier spatial hierarchy, interactive 2D box grid visualizers, barcode tracking, and end-to-end biological lineage resolution.

---

## ❄️ 6-Tier Hierarchical Storage Architecture

Biological samples are mapped to physical locations through a strict 6-tier relational hierarchy:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Level 1: Facility / Campus      (e.g., Main Research Campus)           │
├────────────────────────────────────────────────────────────────────────┤
│ Level 2: Laboratory Room        (e.g., Bioprocessing Suite 402)        │
├────────────────────────────────────────────────────────────────────────┤
│ Level 3: Cold Storage Unit      (e.g., -80°C Ultra-Low Freezer #1)     │
├────────────────────────────────────────────────────────────────────────┤
│ Level 4: Shelf / Metal Rack     (e.g., Rack Alpha - Shelf Level 2)     │
├────────────────────────────────────────────────────────────────────────┤
│ Level 5: Storage Box / Plate    (e.g., Box T7RNAP-01 [9x9 Grid])       │
├────────────────────────────────────────────────────────────────────────┤
│ Level 6: Tube Slot / Well       (e.g., Slot B4 -> BC-T7-0042 Aliquot)  │
└────────────────────────────────────────────────────────────────────────┘
```

### Supported Storage Unit Types
* **Ultra-Low Freezers ($-80^\circ\text{C}$)**: Purified protein stocks, competent cell aliquots, virus stocks, and archival DNA/RNA.
* **Standard Freezers ($-20^\circ\text{C}$)**: Restriction enzymes, PCR master mixes, primers, and daily plasmid aliquots.
* **Refrigeration ($+4^\circ\text{C}$)**: Chromatography buffers, agar plates, antibiotics, and protease inhibitor cocktails.
* **Liquid Nitrogen ($LN_2$, $-196^\circ\text{C}$)**: Primary mammalian and insect cell seed stocks.
* **Ambient ($+20^\circ\text{C}$)**: Desiccated powders, fine chemicals, chromatography resins, and plastic consumables.

---

## 🧮 Interactive 2D Freezer Box Visualizer

The web frontend (`eln/web/static/freezer_grid.js`) renders cryogenic storage boxes as interactive 2D grid matrices. The visualizer supports standard laboratory layouts:
* **$8 \times 8$ Grid**: 64-well cryogenic tube storage boxes.
* **$9 \times 9$ Grid**: 81-slot standard microcentrifuge box (Rows A–I, Columns 1–9).
* **$10 \times 10$ Grid**: 100-slot high-density freezer box (Rows A–J, Columns 1–10).
* **$8 \times 12$ Format**: Standard 96-well format for PCR plates, deep-well blocks, and sample eluates.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Box: T7RNAP-01 (9x9 Grid, -80°C)                      Occupancy: 42 / 81 slots (51.9%) │
├────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬──────────────────────────────────────┤
│    │ 1  │ 2  │ 3  │ 4  │ 5  │ 6  │ 7  │ 8  │ 9  │ Selected Slot: B4                    │
├────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤ Sample: T7RNAP Pool Eluate           │
│ A  │ █  │ █  │ █  │ █  │ █  │ █  │ █  │ █  │ █  │ Barcode: BC-T7-0042                  │
│ B  │ █  │ █  │ █  │[█] │ ░  │ ░  │ ░  │ ░  │ ░  │ Concentration: 2.85 mg/mL           │
│ C  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ Volume: 1000 µL                     │
│ D  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ Buffer: 50% Glycerol, 100 mM NaCl   │
│ E  │ █  │ █  │ █  │ █  │ ░  │ ░  │ ░  │ ░  │ ░  │ Upstream Lineage:                   │
│ F  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │   CMP-2026-T7 > Day 4 > HisTrap     │
│ G  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │   Fraction Pool B4-B8               │
│ H  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │                                      │
│ I  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ ░  │ [ Relocate Tube ]   [ Log Aliquot ] │
└────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴──────────────────────────────────────┘
Legend: █ Occupied Slot   ░ Empty Available Slot   [█] Active Selection
```

### Grid Matrix Features:
1. **Dynamic Color-Coding**: Cells are color-coded based on sample category (e.g., blue for recombinant protein, green for plasmids, amber for primary cell lines).
2. **Hover Tooltips**: Instant hover inspects sample name, barcode, remaining volume ($\mu\text{L}$), concentration ($mg/mL$), and recording scientist.
3. **Collision Detection**: The backend prevents duplicate placement. Attempting to place a tube into an occupied coordinate raises a `ValueError` with details of the current occupant.

---

## 🧬 Aliquot Tracking, Freeze-Thaw Cycles & Depletion

Managing sample integrity requires rigorous tracking of physical consumption and thermal cycling:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Aliquot Consumption Ledger                      │
├────────────┬─────────────┬──────────────┬─────────────┬────────────────┤
│ Date       │ Event       │ Delta Volume │ Remaining   │ Operator       │
├────────────┼─────────────┼──────────────┼─────────────┼────────────────┤
│ 2026-11-10 │ Stock Ingest│ +1000 µL     │ 1000 µL     │ alice_r        │
│ 2026-11-11 │ IVT Assay #1│ -50 µL       │ 950 µL      │ bob_k          │
│ 2026-11-12 │ IVT Assay #2│ -100 µL      │ 850 µL      │ alice_r        │
└────────────┴─────────────┴──────────────┴─────────────┴────────────────┘
Freeze-Thaw Counter: 2 Cycles  |  Depletion Status: 85.0% Available
```

* **Freeze-Thaw Cycle Monitoring**: Every removal and return from sub-zero storage increments an automated freeze-thaw counter. Warning flags trigger when delicate enzymes exceed recommended thresholds (e.g., $>3$ cycles).
* **Automated Depletion Alerts**: When remaining volume drops below $10\%$, the ELN flags the tube as "Low Stock" and notifies the project owner to schedule a re-expression or purification campaign.
* **Expiration Date Tracking**: Reagents and buffers with defined shelf lives (e.g., DTT solutions, antibiotic stocks) trigger visual alerts upon reaching expiration dates.

---

## 🏷️ Barcode Generation & Scanning

BioLabCalc supports physical laboratory identification standards:
* **Code-128 & DataMatrix 2D Barcodes**: Generates high-density 2D barcodes optimized for cryogenic vial labels and tube caps.
* **Automated Unique Identifiers**: Standardized format `BC-{CATEGORY}-{UUID8}`, e.g., `BC-T7-A4F89D12`.
* **Hardware Scanner Compatibility**: USB and Bluetooth barcode scanners operating in keyboard-wedge mode can directly scan tube labels into search bars or relocation dialogs.

---

## 🔄 Audited Tube Relocation & Spatial Transfer

Moving a tube between boxes or slots is fully audited under 21 CFR Part 11 requirements:
```python
from biolabcalc.eln.services.inventory_service import get_inventory_service

inv = get_inventory_service()

# Relocate tube from Box 1 (A1) to Box 2 (C4)
transfer = inv.move_tube(
    tube_id="TUBE-T7RNAP-001",
    target_box_id="BOX-T7RNAP-02",
    target_slot="C4",
    user_id="alice_r",
    reason="Consolidating active working stocks into benchtop working box.",
)

print(f"Transferred Tube: {transfer['tube_id']}")
print(f"Location: {transfer['from_box']}:{transfer['from_slot']} -> {transfer['to_box']}:{transfer['to_slot']}")
print(f"Audit Trail Hash Link: {transfer['audit_event_id']}")
```
The movement generates a cryptographically hashed `TUBE_MOVE` record capturing the source coordinates, destination coordinates, timestamp, operator signature, and operational justification.

---

## 🌳 End-to-End Sample Lineage Graph

One of the most powerful capabilities of the BioLabCalc LIMS is **Upstream Sample Lineage Resolution** (`resolve_lineage`). Starting from a physical tube in a cryogenic box, the system traverses all parent relationships backwards through the scientific workflow:

```
Physical Tube: TUBE-T7RNAP-001 (Box T7RNAP-01, Slot A1)
    │
    ├── 1. Spatial Cold Chain
    │      Building: BioSciences South > Room: 402 > Unit: -80°C Freezer #1 > Rack Alpha > Box T7RNAP-01
    │
    ├── 2. FPLC Purification Run
    │      Run: HisTrap HP 5 mL (2026-11-10) > Fraction Pool: POOL-RUN-01-B4-B8
    │      Yield: 19.25 mg Total Protein | Mean UV280: 2.85 mAU | Buffer: 500 mM Imidazole
    │
    ├── 3. Daily Notebook Entry
    │      Campaign: CMP-2026-T7RNAP > Day 4: IMAC Purification
    │      Executed SOP: SOP-EXP-T7RNAP-001 (Fork FORK-001) > Operator: alice_r
    │
    └── 4. Genetic Construct & Sequence
           Plasmid: pET-28a-T7RNAP (KanR) > Target MW: 98.9 kDa | pI: 6.24 | Ext. Coeff: 140,050 M^-1 cm^-1
```

```python
lineage = inv.resolve_lineage("TUBE-T7RNAP-001")
print(f"Sample: {lineage['sample_name']} ({lineage['barcode']})")
print(f"Spatial Path: {lineage['location']['full_path']}")
if lineage.get("fraction_pool"):
    print(f"Purification Source: {lineage['fraction_pool']['pool_id']}")
if lineage.get("construct"):
    print(f"Genetic Construct: {lineage['construct']['name']} (MW: {lineage['construct']['mw_da']} Da)")
```

---

## 🔗 Related Documentation
* [Electronic Lab Notebook (ELN)](Electronic-Lab-Notebook-(ELN)) — Web interface overview and freezer tab navigation.
* [SOP & Protocol Management](SOP-&-Protocol-Management) — Generating sample tubes from completed experimental forks.
* [GxP Compliance & Audit Trails](GxP-Compliance-&-Audit-Trails) — Audit trail specifications for tube movements and inventory updates.
