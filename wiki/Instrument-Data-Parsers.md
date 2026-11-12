# Analytical Instrument Data Parsers

Modern bioprocess and molecular biology workflows generate high-dimensional datasets across heterogeneous, vendor-locked proprietary file formats. The BioLabCalc analytical parser suite (`biolabcalc.eln.parsers`) provides zero-dependency, pure-Python ingestion engines that decode raw instrument outputs, normalize units, extract acquisition metadata, and index scientific data into the ELN and CAS blob store.

---

## 📊 ÄKTA & Bio-Rad FPLC Chromatograms (`fplc_parser.py`)

Fast Protein Liquid Chromatography (FPLC) is the primary technique for purifying recombinant proteins, enzymes, and therapeutic monoclonal antibodies. `biolabcalc.eln.parsers.fplc_parser` natively ingests Cytiva / GE Healthcare ÄKTA UNICORN and Bio-Rad NGC outputs across `.res`, `.zip`, `.csv`, and `.asc` formats.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        FPLC Multi-Channel Chromatogram                                 │
│  400 ┬ mAU                                                            Conductivity ┬ 50│
│      │                                  Peak 2 (Target T7RNAP)                     │   │
│  300 ┼                                         ╭─╮                                 ┼ 40│
│      │                                        ╭╯ ╰╮                                │mS │
│  200 ┼             Peak 1 (Contaminant)      ╭╯   ╰╮            Gradient %B        ┼ 30│
│      │                    ╭─╮               ╭╯     ╰╮          ┌───────────────────┤   │
│  100 ┼                   ╭╯ ╰╮             ╭╯       ╰╮        ╭╯                   ┼ 20│
│      │   Flow-Through   ╭╯   ╰╮           ╭╯         ╰╮      ╭╯                    │   │
│    0 ┴─────────────────┴───────┴─────────┴─────────────┴────┴──────────────────────┴──0│
│      0                10                20                30                40   mL    │
│  Fractions: [ A1 ][ A2 ][ A3 ][ A4 ][ B1 ][ B2 ][ B3 ][ B4 ][ B5 ][ C1 ][ C2 ]         │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Extraction Capabilities:
* **Multi-Wavelength Optical Detection**: Simultaneous extraction of $UV_{280}$ (tryptophan/tyrosine absorbance), $UV_{260}$ (nucleic acid co-elution check), and $UV_{215}$ (peptide backbone).
* **Physicochemical Traces**: Conductivity (mS/cm), buffer gradient composition (%B), system pre-column pressure (MPa), and volumetric pump flow rate (mL/min).
* **Automated Fraction Mapping**: Maps retention volume intervals to discrete fraction collector rack tube labels (`FractionEvent`: ID, start volume, end volume, peak $UV_{280}$).
* **Hardware & Column Metadata**: Detects column bed volume ($V_c$), void volume ($V_0$), pressure limits, and chemical mode (IMAC, SEC, IEX, HIC).
* **Strict Scientific Data Integrity**: Binary `.res` streams require embedded ASCII curve data. If unparseable binary streams are encountered, `FPLCParser` raises an explicit `ValueError` requesting the user export curves as CSV or ASC from UNICORN software rather than generating synthetic mock data.

### Python Usage Example
```python
from biolabcalc.eln.parsers.fplc_parser import FPLCParser

# Ingest an ÄKTA UNICORN run export (.res, .csv, or .zip)
result = FPLCParser.parse("run_T7RNAP_HisTrap_04.res")

print(f"Format: {result.file_format} | Data Points: {len(result.volume_ml)}")
print(f"Max UV280: {max(result.uv280_mau):.2f} mAU")
print(f"Fractions Collected: {len(result.fractions)}")

# Query target peak fraction
for frac in result.fractions:
    if frac.peak_uv280_mau and frac.peak_uv280_mau > 150.0:
        print(f"Target Tube {frac.fraction_id}: {frac.start_volume_ml:.2f}-{frac.end_volume_ml:.2f} mL (Peak: {frac.peak_uv280_mau:.1f} mAU)")
```

---

## 🔬 Thermo Scientific NanoDrop Spectrophotometry (`nanodrop_parser.py`)

Microvolume UV-Vis spectrophotometry provides rapid concentration and purity metrics for extracted nucleic acids and purified proteins. `biolabcalc.eln.parsers.nanodrop_parser` ingests exports from NanoDrop One, NanoDrop 2000, and NanoDrop Eight across `.ndv`, `.tsv`, `.csv`, and `.xlsx` formats.

### Analytical Extraction & Diagnostic Purity Logic:
1. **Photometric Absorbance**: $A_{260}$, $A_{280}$, $A_{230}$, and $A_{340}$ (turbidity/scatter baseline).
2. **Purity Ratios**:
   * **$A_{260}/A_{280}$ Ratio**: Standard purity threshold (~1.80 for pure dsDNA, ~2.00 for pure RNA). Values $<1.65$ indicate protein contamination.
   * **$A_{260}/A_{230}$ Ratio**: Assessment of organic contaminants. Values $<1.80$ flag residual guanidine thiocyanate, TRIzol reagents, or EDTA.
3. **High-Resolution Spectral Curve**: Ingests continuous 220–350 nm UV spectra at 1 nm increments for publication-grade visualization.
4. **Automatic Contaminant Diagnostics**: Identifies spectral shoulders characteristic of phenol (270 nm peak) or guanidine salts (intense absorbance below 240 nm).

```python
from biolabcalc.eln.parsers.nanodrop_parser import NanoDropParser

# Ingest NanoDrop run export (returns NanoDropExperiment, which is directly iterable)
experiment = NanoDropParser.parse("nanodrop_plasmid_prep.tsv")
for s in experiment:
    print(f"Sample: {s.sample_name} | Type: {s.sample_type}")
    print(f"  Concentration: {s.concentration:.2f} {s.concentration_units}")
    print(f"  A260/A280: {s.ratio_260_280:.2f} | A260/A230: {s.ratio_260_230:.2f}")
    print(f"  Diagnostic Assessment: {s.quality_assessment}")
```

---

## 🧬 Bio-Rad Gel Documentation & Densitometry (`biorad_parser.py`)

Ingests Bio-Rad Image Lab format (`.scn`) and 16-bit scientific TIFF files (`.tif`, `.tiff`) generated by ChemiDoc MP, GelDoc Go, and Odyssey imaging systems.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SDS-PAGE Lane Densitometry                      │
│   Lane 1: Marker   Lane 2: Lysate   Lane 3: Flow-Thru   Lane 4: Eluate │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     ┌─────────────┐│
│   │ ─── 180 kDa │  │ ≡≡≡≡≡≡≡≡≡≡≡ │  │ ≡≡≡≡≡≡≡≡≡≡≡ │     │             ││
│   │ ─── 130 kDa │  │ ≡≡≡≡≡≡≡≡≡≡≡ │  │ ≡≡≡≡≡≡≡≡≡≡≡ │     │             ││
│   │ ─── 100 kDa │  │ ≡≡≡≡≡≡≡≡≡≡≡ │  │ ≡≡≡≡≡≡≡≡≡≡≡ │     │ ═══════════ ││ ◄ Target T7RNAP
│   │ ───  70 kDa │  │ ≡≡≡≡≡≡≡≡≡≡≡ │  │ ≡≡≡≡≡≡≡≡≡≡≡ │     │ (98.9 kDa)  ││   (94.2% Purity)
│   │ ───  55 kDa │  │ ≡≡≡≡≡≡≡≡≡≡≡ │  │ ≡≡≡≡≡≡≡≡≡≡≡ │     │             ││
│   └─────────────┘  └─────────────┘  └─────────────┘     └─────────────┘│
└────────────────────────────────────────────────────────────────────────┘
```

### Core Capabilities:
* **Exposure Metadata Extraction**: Ingests sensor integration time, binning mode (`1x1`, `2x2`), illumination chemistry (UV, Epi-White, Chemiluminescence, Stain-Free), and optical emission filter.
* **16-Bit Dynamic Range Preservation**: Avoids lossy 8-bit clipping. Linear intensity matrices ($0 - 65,535$ arbitrary units) are preserved for true scientific densitometry.
* **Logarithmic Molecular Weight Calibration**: Fits relative migration distances ($R_f$) of standard ladder rungs against known molecular weights:
  $$\log_{10}(\text{MW}) = a \cdot R_f + b$$
* **Purity Densitometry**: Calculates target band area relative to the integrated intensity of all lane contaminants:
  $$\text{Purity } (\%) = \left(\frac{I_{\text{target}}}{\sum I_{\text{lane}}}\right) \times 100$$

---

## ⚡ Axon Electrophysiology Formats (`abf_parser.py`)

Electrophysiology patch-clamp and voltage-clamp experiments recorded via Axon Instruments / Molecular Devices pCLAMP software produce Axon Binary Format (`.abf`) and Axon Text Format (`.atf`) files.

`biolabcalc.eln.parsers.abf_parser` provides a **100% pure-Python reader** for both legacy ABF v1 (used in pCLAMP 6–9) and modern ABF v2 (pCLAMP 10+) without requiring compiled DLLs or non-standard C-extensions:
* **Supported Modes**: Gap-free continuous recording, episodic variable-loop stimulation, and event-driven sweeps.
* **Header & Protocol Decoding**: Decodes sampling rate ($Hz$), analog-to-digital converter (ADC) channels, holding potentials ($mV$), amplifier gain, and filter cutoff frequencies ($kHz$).
* **Micro-Second Sweep Arrays**: Extracts raw time-series arrays ($pA$, $mV$) for every individual sweep episode.
* **Thumbnail Generation**: Downsamples massive multi-gigabyte recordings into lightweight SVG / canvas coordinates for rapid web browser rendering.

---

## 📄 Protocol Document Parser (`doc_parser.py`)

Parses unstructured or semi-structured laboratory Markdown files, laboratory logs, and plain text bench files into structured protocol entities:
* **Section Chunking**: Detects standard header sections (Materials, Reagents, Setup, Reaction Mixture, Step-by-Step Procedure, Troubleshooting).
* **Table Extraction**: Automatically transforms ASCII and Markdown tables into structured dictionaries and Pandas-compatible dataframes.
* **Reagent Parameter Extraction**: Uses regular expressions to extract incubation temperatures, shaker velocities ($RPM$), centrifugal forces ($\times g$), and incubation times.

---

## 👁️ Human-in-the-Loop Vision-OCR Engine (`ocr_engine.py`)

Laboratory scientists frequently take quick handwritten bench notes, hand-label microfuge tubes, or print thermal plate reader receipts. `ocr_engine.py` couples optical character recognition with domain-specific biochemical validation rules.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Human-in-the-Loop (HITL) OCR Verification                       │
├──────────────────────────────────────────┬─────────────────────────────────────────────┤
│ Scanned Image Region                     │ Extracted Token & Verification              │
├──────────────────────────────────────────┼─────────────────────────────────────────────┤
│ ┌──────────────────────────────────────┐ │ Token:     50 mM Tris-HCI, pH 7.5           │
│ │ 50 mM Tris-HCl, pH 7.5               │ │ Confidence: 0.74 (Ambiguous Character)     │
│ └──────────────────────────────────────┘ │ BBox:       [120, 45, 180, 24]              │
│                                          │ Candidates: ["Tris-HCl", "Tris-HCI", "Tris"]│
│                                          │                                             │
│                                          │ [ Accept "Tris-HCl" ]  [ Edit Value ]       │
└──────────────────────────────────────────┴─────────────────────────────────────────────┘
```

### Biochemical Disambiguation Logic:
Standard OCR engines frequently misinterpret biochemical strings due to shared character glyphs. The BioLabCalc engine applies automated contextual heuristics:
* **$O$ vs. $0$**: Distinguishes numeric concentrations (`0.5 M`) from chemical names (`$O$-acetyl`).
* **$l$ vs. $1$ vs. $I$**: Differentiates volume units (`10 µL`) from Roman numerals (`Complex I`) and numbers (`10 mM`).
* **Micro-Sign ($\mu$) Restoration**: Normalizes `uL`, `ug`, and `uM` into standard SI symbols (`µL`, `µg`, `µM`).

### Structured Uncertain Token Format
When token confidence falls below 0.85, the engine flags the entity for operator inspection using standardized markup:
```
[[UNCERTAIN:id="tok_42" text="Tris-HCI" conf=0.74 bbox="[120, 45, 180, 24]" candidates="['Tris-HCl', 'Tris-HCI']"]]
```
This token is rendered in `ocr_corrector.js` as an interactive, highlightable form element where the scientist can confirm or edit the transcription with a single keystroke.

---

## 🔗 Related Documentation
* [Electronic Lab Notebook (ELN)](Electronic-Lab-Notebook-(ELN)) — Web interface canvases for displaying parsed traces.
* [SOP & Protocol Management](SOP-&-Protocol-Management) — Instantiating parsed data into experimental checkoffs.
* [RAG & Local AI Assistant](RAG-&-Local-AI-Assistant) — Indexing parsed analytical outputs into the hybrid search engine.
