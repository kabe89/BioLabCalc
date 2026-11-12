# Gel Electrophoresis & Image Annotator

BioLabCalc provides a unified suite for modeling, simulating, and annotating macromolecular gel electrophoresis. The toolkit bridges theoretical migration kinetics with laboratory workflows through three integrated subsystems:

1. **Analytical Migration Modeling (`gels.py`)**: Logarithmic relative mobility ($R_f$) calculations and standardized ladder catalogs for DNA, RNA, and proteins, featuring terminal ASCII band simulation.
2. **Headless Figure Annotation Engine (`gel_annotator.py`)**: Matplotlib- and Pillow-based publication figure generation for synthetic gels or raw laboratory transilluminator images (TIFF, PNG, JPEG), with direct embedding into Excel workbooks.
3. **Interactive Drag-and-Drop Web Application (`interactive_gel.py`)**: A client-side HTML5 Canvas interface for interactive lane definition, contrast/brightness tuning, standard curve fitting ($R^2$), and unknown band molecular weight interpolation.

---

## 1. Biophysical Principles of Electrophoretic Mobility

Gel electrophoresis separates charged macromolecules (nucleic acids or SDS-denatured polypeptides) by driving them through a porous matrix under an electric field.

### Relative Mobility ($R_f$)

The relative mobility ($R_f$) of a migrating band is defined as the ratio of the distance migrated by the band ($d_x$) to the distance migrated by the tracking dye or electrophoresis front ($d_f$):

$$R_f = \frac{d_x}{d_f}$$

In a constant-percentage gel matrix operated within the linear sieving range, macromolecular migration velocity is inversely proportional to the logarithm of molecular weight or sequence length. BioLabCalc models this relationship via:

$$R_f = a - b \log_{10}(\text{MW})$$

Where:
- $\text{MW}$ is the molecular length in base pairs ($\text{bp}$) or nucleotides ($\text{nt}$) for nucleic acids, or molecular mass in kilodaltons ($\text{kDa}$) for proteins.
- $a$ and $b$ are matrix- and field-dependent constants determined by gel concentration, buffer ionic strength, and electric potential gradient.

In `calculate_rf(size, min_size, max_size)`, BioLabCalc normalizes band migration across a standard relative migration window from $R_f = 0.10$ (near the loading wells at the cathode) to $R_f = 0.90$ (near the gel bottom at the anode):

$$R_f = 0.10 + 0.80 \cdot \left( \frac{\log_{10}(\text{max\_size}) - \log_{10}(\text{size})}{\log_{10}(\text{max\_size}) - \log_{10}(\text{min\_size})} \right)$$

Values are bounded between $0.05$ and $0.95$ to account for edge compression and limiting mobility regimes.

### Matrix Selection Guide

| Biomolecule Type | Size Range | Recommended Gel Matrix | Running Buffer | Voltage Gradient |
| :--- | :--- | :--- | :--- | :--- |
| **Large dsDNA / Plasmids** | 1,000 – 15,000 bp | 0.8% – 1.0% Agarose | 1X TAE or 1X TBE | 4–6 V/cm |
| **Standard PCR Amplicons** | 100 – 2,000 bp | 1.5% – 2.0% Agarose | 1X TAE or 1X TBE | 5–8 V/cm |
| **Small DNA Fragments** | 20 – 500 bp | 3.0% – 4.0% Low-melt Agarose or 8% PAGE | 1X TBE | 8–10 V/cm |
| **Denatured Long ssRNA** | 500 – 10,000 nt | 1.2% Agarose with 2.2 M Formaldehyde | 1X MOPS | 4–5 V/cm |
| **Small RNA / Oligos** | 10 – 200 nt | 6% – 15% Urea-PAGE (7 M Urea) | 1X TBE | 15–20 V/cm |
| **High MW Proteins** | 50 – 250 kDa | 6% – 8% SDS-PAGE (Tris-Glycine) | 1X Laemmli Running Buffer | 100–120 V |
| **Medium MW Proteins** | 15 – 100 kDa | 10% – 12% SDS-PAGE (Tris-Glycine) | 1X Laemmli Running Buffer | 120–150 V |
| **Peptides / Small Proteins**| 2 – 20 kDa | 15% – 18% Tris-Tricine PAGE | 1X Tricine Buffer | 80–100 V |

---

## 2. Standard Molecular Weight Ladder Catalog

BioLabCalc includes a built-in catalog of standard molecular weight ladders (`LADDER_CATALOG`) covering nucleic acid and protein separations.

### Ladder Specifications Table

| Key | Catalog Name | Class | Units | Band Series | Reference Bands | Optimal Matrix |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `1kb_dna` | 1 kb DNA Ladder | dsDNA | bp | 10000, 8000, 6000, 5000, 4000, 3000, 2000, 1500, 1000, 500 | 3,000 bp | 1.0% Agarose |
| `100bp_dna` | 100 bp DNA Ladder | dsDNA | bp | 1517, 1200, 1000, 900, 800, 700, 600, 500, 400, 300, 200, 100 | 500 bp, 1,000 bp | 2.0% Agarose |
| `low_range_ssdna`| Low Range ssDNA/RNA Oligo | ssDNA/RNA | nt | 100, 80, 60, 50, 40, 30, 20, 10 | 50 nt | 12–15% PAGE |
| `protein_broad_range` | Broad Range Prestained Protein | Protein | kDa | 250, 150, 100, 75, 50, 37, 25, 20, 15, 10 | 75 kDa, 25 kDa | 10–12% SDS-PAGE |
| `ssrna_ladder` | ssRNA High Range Ladder | ssRNA | nt | 9000, 7000, 5000, 3000, 2000, 1500, 1000, 500 | 2,000 nt | 1.2% Formaldehyde/MOPS |
| `low_range_rna` | Low Range ssRNA Ladder | ssRNA | nt | 1000, 800, 600, 500, 400, 300, 200, 100, 50 | 500 nt | 6–8% Urea-PAGE (7M Urea) |
| `microrna_ladder` | microRNA / Small RNA Ladder | ssRNA | nt | 50, 40, 30, 20, 10 | 30 nt | 12–15% Urea-PAGE (7M Urea) |

Reference bands (indicated by an asterisk `*`) possess approximately double or triple the mass intensity of adjacent bands to enable orientation during imaging.

---

## 3. Terminal ASCII Gel Simulation

The `simulate_gel` function computes relative migration and renders an immediate ASCII representation directly in the terminal, allowing bench verification before running a physical gel.

### Python API Usage

```python
import biolabcalc as blc

# Simulate separation of a 850 bp PCR product and 3,200 bp vector backbone against 1 kb DNA ladder
simulation = blc.simulate_gel(
    sample_sizes=[850, 3200],
    ladder_key="1kb_dna"
)

# Access simulation data
print("Ladder:", simulation.ladder_name)
print("Recommended Gel Percentage:", simulation.recommended_gel_percentage)
for band in simulation.sample_bands:
    print(f"Sample Band: {band.size} {band.unit} | Rf: {band.relative_migration_rf:.3f}")

# Print ASCII visualization
print(simulation.ascii_visualization)
```

### CLI Execution

```bash
biolabcalc gel -s 850 3200 -l 1kb_dna
```

### ASCII Output Example

```text
┌─────────── Gel Migration Simulation (1 kb DNA Ladder) ───────────┐
│ Well │   Ladder Lane    │   Sample Lane(s)                     │
├──────┼──────────────────┼──────────────────────────────────────┤
│  00  │                  │                                      │
│  01  │== 10000 bp   ==  │                                      │
│  02  │== 8000 bp    ==  │                                      │
│  03  │== 6000 bp    ==  │                                      │
│  04  │== 5000 bp    ==  │                                      │
│  05  │== 4000 bp    ==  │                                      │
│  06  │== 3000 bp *  ==  │## 3200 bp                            ##│
│  07  │                  │                                      │
│  08  │== 2000 bp    ==  │                                      │
│  09  │== 1500 bp    ==  │                                      │
│  10  │                  │                                      │
│  11  │== 1000 bp    ==  │## 850 bp                             ##│
│  12  │                  │                                      │
│  13  │== 500 bp     ==  │                                      │
│  14  │                  │                                      │
│  15  │                  │                                      │
└──────┴──────────────────┴──────────────────────────────────────┘
Recommended Matrix: 1.0
```

---

## 4. Headless Image Annotation Engine (`GelAnnotator`)

The `GelAnnotator` class generates annotated gel figures suitable for publication, laboratory presentations, and notebook documentation. It operates in two modes:

1. **Synthetic Schematic Mode (`GelAnnotator.synthetic`)**: Generates an idealized gel layout with rounded well geometry, lane dividers, calibrated molecular weight ladder bands, and user-specified target bands.
2. **Experimental Image Mode (`GelAnnotator.from_image`)**: Ingests raw camera or transilluminator captures (TIFF, PNG, JPEG), applies optional contrast inversion (`invert_colors=True`), and overlays numbered lane pills, MW scale ticks, and arrow-linked annotation callouts.

### Python API Examples

#### 1. Generating a Synthetic Gel Schematic

```python
from biolabcalc import GelAnnotator

# Configure synthetic gel layout
annotator = GelAnnotator.synthetic(
    num_lanes=6,
    title="Restriction Digest & PCR Verification",
    gel_info="1.0% Agarose in 1X TAE | 100V, 45 min",
    invert_colors=True
)

# Label experimental lanes
annotator.set_lanes([
    "1 kb Ladder",
    "Undigested Vector",
    "EcoRI Digest",
    "EcoRI/BamHI Double Digest",
    "PCR Product (Clone 1)",
    "PCR Product (Clone 2)"
])

# Calibrate ladder lane
annotator.add_ladder(lane_index=1, ladder_type="1kb_dna", side="left")

# Annotate specific bands with callout arrows
annotator.add_band(lane_index=2, size_bp_or_kda=5400, label="Supercoiled Vector (5.4 kb)", color="#2563EB")
annotator.add_band(lane_index=3, size_bp_or_kda=5400, label="Linearized Vector (5.4 kb)", color="#1F4E79")
annotator.add_band(lane_index=4, size_bp_or_kda=4200, label="Vector Backbone (4.2 kb)", color="#059669")
annotator.add_band(lane_index=4, size_bp_or_kda=1200, label="Excised Insert (1.2 kb)", color="#D97706")
annotator.add_band(lane_index=5, size_bp_or_kda=1200, label="Amplicon (1.2 kb)", color="#D97706")
annotator.add_band(lane_index=6, size_bp_or_kda=1200, label="Amplicon (1.2 kb)", color="#D97706")

# Render high-resolution PNG figure
annotator.render("digest_gel_figure.png", dpi=300)
```

#### 2. Annotating an Existing Instrument Gel Image

```python
from biolabcalc import GelAnnotator

# Ingest raw transilluminator image
annotator = GelAnnotator.from_image(
    image_path="raw_gel_capture.tif",
    title="Colony PCR Screening (Clones 1–4)",
    gel_info="2.0% Agarose in 1X TBE | GelGreen Stain",
    invert_colors=False
)

annotator.set_lanes([
    "100 bp Ladder",
    "Negative Control",
    "Colony 1",
    "Colony 2",
    "Colony 3",
    "Colony 4"
])

annotator.add_ladder(lane_index=1, ladder_type="100bp_dna", side="left")
annotator.add_band(lane_index=3, size_bp_or_kda=650, label="Target Amplicon (650 bp)", color="#EF4444")
annotator.add_band(lane_index=5, size_bp_or_kda=650, label="Target Amplicon (650 bp)", color="#EF4444")

annotator.render("annotated_colony_pcr.png", dpi=300)
```

#### 3. Embedding Figures into an Excel Laboratory Workbook

```python
annotator.embed_in_excel(
    excel_path="experiment_results.xlsx",
    sheet_name="Gel_Electrophoresis"
)
```

This method creates or updates the designated worksheet, formats an authoritative Navy-and-White header table detailing lane indices, sample identities, sample types, observed bands, and notes, renders the gel image at 180 DPI, and anchors the graphic below the data table.

### CLI Execution

```bash
# Synthetic gel with target bands and callout arrows
biolabcalc annotate-gel \
  -l "Ladder,Uncut,EcoRI,BamHI,Double_Digest" \
  --ladder 1kb_dna \
  --ladder-lane 1 \
  -b "3:5400:Linear,4:5400:Linear,5:4200:Backbone,5:1200:Insert" \
  -t "Restriction Digest Analysis" \
  --info "1.0% Agarose | 100V, 50 min" \
  -o "annotated_digest.png" \
  --invert

# Annotating an existing lab image and embedding into Excel
biolabcalc annotate-gel \
  -i "raw_capture.png" \
  -l "MW,Ctrl-,Clone1,Clone2" \
  --ladder 100bp_dna \
  -b "3:450:Positive,4:450:Positive" \
  -o "labeled_gel.png" \
  --excel "Project_Notebook.xlsx"
```

---

## 5. Interactive Drag-and-Drop Gel Annotator Web Application

For graphical interaction, BioLabCalc includes a zero-dependency HTML5 Canvas application (`interactive_gel.py`). It runs locally without external web servers or cloud connectivity, ensuring data privacy for proprietary sequences and images.

```
+-----------------------------------------------------------------------------------------+
| BioLabCalc | Interactive Drag & Drop Gel Annotator                                      |
+--------------------------+--------------------------------------------------------------+
| 1. Gel Image Upload      | Canvas Viewport                                              |
|    [ Drag & Drop Zone ]  |                                                              |
|    Contrast Slider       |   Lane 1     Lane 2     Lane 3     Lane 4     Lane 5             |
|    Brightness Slider     |   (Ladder)   (Ctrl-)    (Clone 1)  (Clone 2)  (Digest)           |
|                          |   [Well]     [Well]     [Well]     [Well]     [Well]             |
| 2. Lanes & Samples       |                                                              |
|    Number of Lanes: [ 5] |   == 10 kb                                                       |
|    L1: 1 kb Ladder       |   == 8 kb                                                        |
|    L2: Ctrl-             |   == 6 kb                                                        |
|    L3: Clone 1           |   == 5 kb                                                        |
|    L4: Clone 2           |   == 4 kb                                                        |
|    L5: Digest            |   == 3 kb* -------------------------> [ 3.2 kb Vector Backbone ] |
|                          |   == 2 kb                                                        |
| 3. Ladder Calibration    |   == 1.5 kb                                                      |
|    Type: 1 kb DNA Ladder |   == 1.0 kb                                                      |
|    Ladder Lane: [Lane 1] |   == 500 bp ------------> [ 850 bp PCR Target ]                  |
|                          |                                                              |
| 4. Band Readout          |                                                              |
|    Selected MW: 852 bp   |                                                              |
|    Rf: 0.684             |                                                              |
|    Regression: R^2=0.998 |                                                              |
+--------------------------+--------------------------------------------------------------+
```

### Key Capabilities

1. **Client-Side Image Manipulation**:
   - Drag-and-drop ingestion of standard image formats (TIFF, PNG, JPEG).
   - Real-time adjustment of brightness (50%–200%) and contrast (50%–250%).
   - Monochromatic inversion toggle (`invertGelColors`) to alternate between UV transilluminator (white bands on dark background) and colorimetric/Coomassie (dark bands on clear background) modes.
2. **Interactive Lane Geometry**:
   - Dynamic lane division (2 to 24 lanes) mapped across the image width.
   - Per-lane sample name editing and automatic numbered lane pill placement.
3. **Logarithmic Standard Curve Calibration**:
   - Assigns any lane as the molecular weight ladder.
   - Computes standard curve regression parameters:
     $$\log_{10}(\text{size}) = m \cdot R_f + c$$
     $$R^2 = \frac{\left(\sum (R_f - \overline{R_f})(\log_{10}(\text{MW}) - \overline{\log_{10}(\text{MW})})\right)^2}{\sum (R_f - \overline{R_f})^2 \cdot \sum (\log_{10}(\text{MW}) - \overline{\log_{10}(\text{MW})})^2}$$
4. **Unknown Band Molecular Weight Estimation**:
   - Clicking any position on an experimental lane measures $R_f$ relative to the top well and dye front.
   - Solves for molecular weight using the fitted linear regression:
     $$\text{MW}_{\text{est}} = 10^{(m \cdot R_f + c)}$$
   - Displays calculated size and $R_f$ in the readout panel.
5. **Callout Tagging & Export**:
   - Renders draggable callout badges with connecting pointer arrows.
   - Double-click to rename or delete band tags.
   - Single-click export to high-resolution PNG (`exportGelPNG`) or structured CSV (`exportTableCSV`).

### Running the Interactive Web Application

#### Launching the Local HTTP Server

```bash
biolabcalc interactive-gel --port 8501
```

Or via Python:

```python
import biolabcalc as blc

# Starts server on http://127.0.0.1:8501 and opens default browser
blc.launch_interactive_annotator(port=8501, open_browser=True, blocking=True)
```

#### Saving a Standalone HTML Application

For offline use in biosafety cabinets or air-gapped lab computers, export the self-contained HTML file:

```bash
biolabcalc interactive-gel --save-html standalone_gel_annotator.html
```

Or via Python:

```python
import biolabcalc as blc

path = blc.save_interactive_app("my_annotator.html")
print(f"Standalone application exported to {path}")
```

The exported file contains all necessary HTML5 Canvas rendering code, CSS styling, and JavaScript calibration routines in a single document requiring no internet access.
