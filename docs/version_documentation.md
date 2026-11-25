# BioLabCalc Version Documentation & Architecture Evolution

**Document Version:** 1.5.0  
**Latest Software Release:** `v1.5.0`  
**License:** MIT License  
**Maintainers:** BioLabCalc Contributors (`kabe89/BioLabCalc`)  

---

## 📑 Table of Contents

1. [Executive Summary & Core Philosophy](#1-executive-summary--core-philosophy)
2. [Version History Matrix](#2-version-history-matrix)
3. [v0.1.0 – v0.1.5: Biophysical Foundations & Core Stoichiometry](#3-v010--v015-biophysical-foundations--core-stoichiometry)
4. [v0.2.0: Enzymatic Systems, Electrophoresis & Kinetics](#4-v020-enzymatic-systems-electrophoresis--kinetics)
5. [v0.3.0 – v0.3.5: Enterprise Electronic Lab Notebook (ELN) & LIMS](#5-v030--v035-enterprise-electronic-lab-notebook-eln--lims)
6. [v0.4.0: Plasmid Engineering, Restriction Digestion & TEA State Machine](#6-v040-plasmid-engineering-restriction-digestion--tea-state-machine)
7. [Architectural Invariants & Engineering Constraints](#7-architectural-invariants--engineering-constraints)
8. [Upgrade & Migration Guide (v0.3.x → v0.4.0)](#8-upgrade--migration-guide-v03x--v040)
9. [Future Strategic Roadmap](#9-future-strategic-roadmap)

---

## 1. Executive Summary & Core Philosophy

**BioLabCalc** was created to resolve a ubiquitous failure mode in modern academic and industrial life-science laboratories: the fragmentation of daily benchtop stoichiometry across ad-hoc spreadsheets, error-prone manual calculations, and expensive, proprietary, cloud-locked Electronic Lab Notebooks (ELNs).

### Core Architectural Axioms
1. **Zero External Runtime Dependencies:** BioLabCalc requires no heavy bioinformatics frameworks (e.g. BioPython), external databases, or cloud servers. The entire core suite executes using Python's standard library, with optional standard visualization libraries (`openpyxl`, `matplotlib`, `Pillow`, `numpy`).
2. **100% Offline & Absolute Data Sovereignty:** Laboratory sequences, primer designs, experimental formulations, and proprietary cloning strategies never leave the local workstation or institutional intranet.
3. **Mathematical & Thermodynamic Rigor:** Every algorithm implements peer-reviewed physical chemistry derivations—such as SantaLucia (1998) unified nearest-neighbor thermodynamics, Pace (1995) extinction coefficients, and dynamic phosphodiester bond cleavage tracking.
4. **Cross-Platform Path & Environment Portability:** Seamless operation across Windows (PowerShell, UNC paths `\\server\share`, mapped drive letters), Linux, and macOS.
5. **Strict Immutability:** Data models utilize `@dataclass(frozen=True)` with immutable tuple collections to prevent state corruption during concurrent multi-user execution.

---

## 2. Version History Matrix

| Version | Release Date | Major Focus | Key Modules Added / Upgraded | Test Suite Pass Count |
| :--- | :--- | :--- | :--- | :--- |
| **`v0.1.0`** | Sep 2026 | Initial Stoichiometry Core | `units.py`, `molecular_weight.py`, `protein.py`, `spectroscopy.py` | 85 tests |
| **`v0.1.5`** | Oct 2026 | PCR & Primer Thermodynamics | `pcr.py`, `primers.py`, `buffers.py`, `cli.py` | 172 tests |
| **`v0.2.0`** | Oct 2026 | In Vitro Transcription & Gels | `transcription.py`, `gels.py`, `fluorescence.py`, `interactive_gel.py` | 260 tests |
| **`v0.3.0`** | Nov 2026 | Browser-Based Offline ELN | `eln/` (Server, CAS, Audit Logs, Storage, Services, Web UI) | 385 tests |
| **`v0.3.5`** | Nov 2026 | Multi-User Network Storage & LIMS | `network_storage.py`, `inventory_service.py`, `setup_wizard.py` | 415 tests |
| **`v0.4.0`** | Nov 2026 | Plasmid Engineering & TEA Engine | `tea_runtime.py`, `sequence_store.py`, `plasmid.py`, `restriction_engine.py`, `plasmid_engineering.py`, `interactive_plasmid.py`, `protocols.py` | 473 tests |
| **`v1.0.0–v1.1.2`** | Nov 2026 | Automation, Interop & Portability | `automation.py`, `allostery.py`, `aptamers.py`, `gel_annotator.py`, `printable_protocol.py`, `profile.py`, `sqlite_store.py` | 543 tests |
| **`v1.5.0`** | Nov 2026 | Minimalist UI, Science Expansions & ELN LIMS | `theme.py`, `plugins.py`, `protein_recommender.py`, `in_vivo.py`, multi-Pol IVT, PCR kinetics, enzyme SDS-PAGE, `progress_report_service.py`, `purchase_service.py` | **628 tests** |

---

## 3. v0.1.0 – v0.1.5: Biophysical Foundations & Core Stoichiometry

### 3.1 Dimensional Analysis & Solution Dilution (`units.py`, `easy.py`)
- Implemented robust unit parsing and conversion for mass (g, mg, µg, ng, pg, fmol), volume (L, mL, µL, nL, pL), and molarity (M, mM, µM, nM, pM).
- Universal dilution solver for $C_1 V_1 = C_2 V_2$ handling mixed mass/volume and molar concentrations with automatic diluent calculation.

### 3.2 Molecular Weight & Extinction Coefficients (`molecular_weight.py`, `protein.py`, `spectroscopy.py`)
- **Nucleic Acid MW:** Calculated exact molecular weight accounting for single-stranded and double-stranded DNA and RNA, 5' phosphorylation states (`hydroxyl`, `monophosphate`, `triphosphate`), and 3' terminal states.
- **Protein MW & Extinction ($\epsilon_{280}$):** Implemented Pace et al. (1995) formula:
  $$\epsilon_{280} = (\text{Trp} \times 5500) + (\text{Tyr} \times 1490) + (\text{Cystine} \times 125) \quad [\text{M}^{-1}\text{cm}^{-1}]$$
- **NanoDrop Purity Predictor:** Theoretical $A_{260}/A_{280}$ and $A_{260}/A_{230}$ ratio estimation based on nucleotide composition and contaminant detection (phenol, guanidine, EDTA).

### 3.3 Primer Design & SantaLucia Thermodynamics (`primers.py`, `pcr.py`)
- Implemented SantaLucia (1998) unified nearest-neighbor thermodynamic calculations for DNA duplex stability:
  $$T_m = \frac{\Delta H^\circ}{\Delta S^\circ + R \ln(C_T / 4)} - 273.15 + 16.6 \log_{10}[Na^+]$$
  with terminal initiation parameters, self-dimerization penalty scoring, and hair-pin loop detection.
- Master mix generation with user-configurable reaction excess overfill allowances.

---

## 4. v0.2.0: Enzymatic Systems, Electrophoresis & Kinetics

### 4.1 In Vitro Transcription (IVT) Stoichiometry (`transcription.py`)
- Capping efficiency modeling for co-transcriptional capping reagents:
  - CleanCap® Reagent AG (Trimer)
  - CleanCap® Reagent GG
  - Anti-Reverse Cap Analog (ARCA)
  - Standard $m^7G(5')ppp(5')G$
- Support for modified nucleotide replacements:
  - $N^1$-methylpseudouridine ($\text{m1}\Psi\text{TP}$)
  - Pseudouridine ($\Psi\text{TP}$)
  - 5-methoxyuridine ($5\text{moUTP}$)
  - 5-methylcytidine ($5\text{mCTP}$)
- Automatic promoter recognition (T7, T3, SP6) with automated 5'-overhang trimming.
- NTP depletion kinetics, magnesium consumption modeling, and stoichiometric transcript turnover ratios.

### 4.2 Gel Electrophoresis & Ladder Migration (`gels.py`, `interactive_gel.py`)
- Semi-logarithmic relative mobility model:
  $$R_f = a - b \cdot \log_{10}(\text{MW})$$
- 7 preloaded calibration ladders:
  - `1kb_dna`, `100bp_dna`, `low_mw_dna`, `high_mw_dna`
  - `ssdna_ladder`, `rna_millennium`, `low_range_ssrna`
- Pure-browser drag-and-drop interactive gel annotator with HTML5 canvas and PNG export.

### 4.3 Fluorophore Modifications (`fluorescence.py`)
- Degree of Labeling (DoL) calculation:
  $$\text{DoL} = \frac{A_{max} \cdot \epsilon_{prot}}{(A_{280} - (A_{max} \cdot CF_{280})) \cdot \epsilon_{dye}}$$
- Preloaded dye database (Alexa Fluor 488/568/647, Cy3, Cy5, FITC, FAM, Texas Red) with spectral correction factors.

---

## 5. v0.3.0 – v0.3.5: Enterprise Electronic Lab Notebook (ELN) & LIMS

### 5.1 Pure Standard Library Web Server & Content-Addressable Storage
- High-performance HTTP server (`src/biolabcalc/eln/server.py`) operating without Flask, Django, or FastAPI.
- Content-Addressable Storage (CAS) with SHA-256 content hashing to ensure zero duplicate file storage and absolute data integrity.
- In-memory and disk caching with thread-safe atomic writes.

### 5.2 21 CFR Part 11 Audit Trail & Non-PI Peer Review
- Append-only JSON Lines (`.jsonl`) immutable audit trail capturing timestamp, user ID, client IP, action, resource, and cryptographic hashes.
- Tamper-evident digital signatures sealing experiments upon completion.
- Flexible peer review governance supporting four approval policies:
  1. `open`: Self-signoff permitted for rapid academic exploratory workflows.
  2. `single_peer`: Requires signoff from at least one peer researcher.
  3. `dual_peer`: Requires two independent peer reviews.
  4. `consensus`: Requires full project team agreement.

### 5.3 Shared Network Concurrency & LIMS Freezer Grids
- File-locking synchronization engine (`network_storage.py`) using lockfiles, transactional write buffering, and randomized exponential backoff for high-concurrency SMB/UNC network shares.
- Cryogenic freezer inventory hierarchy:
  $$\text{Freezer} \longrightarrow \text{Shelf} \longrightarrow \text{Rack} \longrightarrow \text{Box} \longrightarrow \text{Grid } (9\times9 \text{ or } 10\times10)$$
- Real-time plate coordinate visualization and aliquot tracking.

### 5.4 Instrument Parsers & Declarative Safe AST Experiment Builder
- Native parsers for:
  - ÄKTA FPLC UV/Conductivity chromatographic traces (`.res`, `.csv`)
  - Molecular Devices pCLAMP electrophysiology recordings (`.abf`, `.atf`)
  - Thermo Fisher NanoDrop spectrophotometer reports (`.tsv`)
  - Bio-Rad Gel Doc densitometry files
- Safe AST formula calculation engine eliminating arbitrary code execution (`eval()`).

---

## 6. v0.4.0: Plasmid Engineering, Restriction Digestion & TEA State Machine

The `v0.4.0` release introduces a comprehensive plasmid engineering suite, an in-silico restriction digestion engine, and an Elm Architecture (TEA) state machine.

### 6.1 The Elm Architecture (TEA) State Runtime (`tea_runtime.py`)
- Pure functional unidirectional state container:
  $$\text{Msg} \times \text{Model} \xrightarrow{\quad\text{update}\quad} \text{Model}' \times \text{Cmd}$$
- Strict immutability using `@dataclass(frozen=True)` and immutable `Tuple[...]` collections.
- Model state updates executed purely via `dataclasses.replace()`.
- Thread-safe `TEAStore` with subscription callbacks and predictable message queues (`LoadPlasmidMsg`, `SelectEnzymesMsg`, `RunDigestMsg`, `AddFeatureMsg`, `SetHostMsg`).

### 6.2 Sequence Store & Catalog (`sequence_store.py`)
- Standardized `SequenceRecord` dataclass:
  - Automated 16-character SHA-256 checksums (`hashlib.sha256(clean_seq.encode()).hexdigest()[:16]`).
  - GC% calculation and sequence-specific molecular weight calculations.
- Preloaded catalog: T7, SP6, T3 promoters, amplicons, aptamers, His6-TEV tags, and antibiotic resistance genes.
- Atomic file persistence (`~/.biolabcalc/sequences.json`) with temporary file staging and atomic replacement.
- FASTA multi-record import and export.

### 6.3 Circular Modulo-$L$ Plasmid Storage & GenBank I/O (`plasmid.py`)
- **Coordinate System:** Strictly 1-based inclusive (`1 .. L`), matching GenBank and SnapGene standards.
- **Origin-Spanning Features:** Circular features crossing the vector origin have $start > end$, spanning $start \dots L$ and $1 \dots end$ with length $(L - start + 1) + end$.
- **Origin Rotation:** `rotate_origin(plasmid, new_origin_1based)` transforms all feature coordinates while maintaining complete vector sequence integrity.
- **Circular ORF Detection:** `find_orfs` scans across the origin boundary to identify proteins spanning the linear split.
- **Automated Feature Annotator:** Autonomous dual-strand motif scanner identifying promoters, operators, ribosome binding sites, epitope tags, terminators, plasmid origins, and resistance cassettes.
- **Standard Plasmid Vectors:** Preloaded valid sequences and annotations for `pUC19` (2,686 bp), `pET-28a(+)`, `pcDNA3.1(+)`, and `pGoldenGate-Dest`.
- **GenBank I/O:** Complete round-trip parser (`parse_genbank`) and formatter (`export_genbank`).

### 6.4 In-Silico Restriction Digestion Engine (`restriction_engine.py`)
- **Phosphodiester Cleavage Offsets:** Tracks cleavage positions independently on both the top ($5'\to 3'$) and bottom ($3'\to 5'$) strands.
- **Dynamic Overhang Extraction:** Overhang sequences are derived directly from the cleaved DNA sequence, properly handling degenerate IUPAC enzymes (`SfiI`, `XhoI`, etc.) and Type IIS enzymes (`BsaI-HFv2`, `BsmBI-v2`, `BbsI-HF`, `SapI`, `PaqCI`).
- **Fragment Stoichiometry:** Exact mass ($ng$), length ($bp$), molar concentration, and molecular weight for every digest fragment.
- **Virtual Gel Migration:** Direct simulation of digest banding patterns mapped against agarose calibration ladders.

### 6.5 Automated Gene Expression Plasmid Engineering (`plasmid_engineering.py`)
- Unified assembly pipeline for:
  - Standard restriction-ligation cloning
  - Golden Gate Type IIS assembly (BsaI, BsmBI, BbsI)
  - Gibson / HiFi isothermal assembly
- **7-Point Validation Checklist:**
  1. *Reading Frame Synchronization:* Verifies that inserted CDS remains in-frame with upstream initiation codons and downstream tags (e.g. 6xHis).
  2. *Internal Restriction Site Screening:* Detects and flags problematic internal cleavage sites for selected cloning enzymes.
  3. *Start & Stop Codon Integrity:* Validates canonical start (`ATG`, `GTG`, `TTG`) and stop (`TAA`, `TAG`, `TGA`) codons.
  4. *Colony PCR Screening Primers:* Computes flanking diagnostic primers and calculates anticipated positive vs. negative colony PCR amplicon sizes.
  5. *Recombinant Protein Properties:* Predicts translated amino acid sequence, full molecular weight (Da), and isoelectric point ($pI$).
  6. *Host Codon Usage Evaluation:* Analyzes codon adaptation and flags rare codons for *E. coli*, *H. sapiens*, and *S. cerevisiae*.
  7. *Codon Optimization Engine:* Performs synonymous substitution of rare codons to maximize recombinant expression.

### 6.6 Interactive HTML5/SVG Plasmid Workbench (`interactive_plasmid.py`)
- Pure Python SVG vector map generator producing publication-ready plasmid maps with proportional circular arcs, directional feature arrows, and restriction cut labels.
- Self-contained, single-file HTML5 plasmid workbench for interactive local exploration and vector manipulation.

### 6.7 Standard Laboratory Protocols (`protocols.py`)
- Catalog of peer-reviewed laboratory Standard Operating Procedures (SOPs):
  - Golden Gate Assembly
  - Gibson Isothermal Assembly
  - High-Fidelity Q5 PCR Amplification
  - Alkaline Lysis Plasmid Miniprep
  - Chemically Competent Cell Transformation
- Markdown formatting and checklist export.

---

## 7. Architectural Invariants & Engineering Constraints

When contributing to BioLabCalc or developing automated extensions, the following invariants are strictly enforced:

1. **Dataclass Immutability:**
   All domain models must be declared with `@dataclass(frozen=True)`. Never mutate an instance in-place. Use `dataclasses.replace(instance, ...)` to generate new state instances.
2. **Collection Types in Models:**
   Collections inside frozen dataclasses must be `Tuple[...]`, not `List[...]` or `Set[...]`, ensuring true immutability.
3. **1-Based Coordinates:**
   All genomic, vector, and feature coordinates are 1-based inclusive (`1 .. L`). Zero-based indexing is confined strictly to Python array slicing internally.
4. **Circular Topology Modulo Math:**
   For circular plasmids of length $L$:
   - Distance between two coordinates $p_1$ and $p_2$ in the forward direction is $(p_2 - p_1) \pmod L$.
   - Origin-spanning features have $start > end$, with length $(L - start + 1) + end$.
5. **No Direct System `/tmp` Hardcoding:**
   Always utilize `tempfile.TemporaryDirectory()` or `tempfile.NamedTemporaryFile()` with safe, explicit handle closure prior to unlinking.
6. **Zero External Dependencies:**
   No third-party packages beyond Python's standard library and the optional visualization libraries (`openpyxl`, `matplotlib`, `Pillow`, `numpy`).

---

## 8. Upgrade & Migration Guide (v0.3.x → v0.4.0)

### 8.1 API Compatibility
- `v0.4.0` is 100% backward compatible with existing `v0.3.x` scripts, ELN storage databases, and CLI workflows.
- All existing CLI commands remain functional with identical arguments.

### 8.2 New Module Imports
```python
# v0.4.0 New Modules:
from biolabcalc.tea_runtime import TEAStore, LoadPlasmidMsg, SelectEnzymesMsg, RunDigestMsg
from biolabcalc.sequence_store import save_sequence, get_sequence, list_sequences, SequenceRecord
from biolabcalc.plasmid import parse_genbank, export_genbank, auto_annotate_plasmid, STANDARD_PLASMID_CATALOG
from biolabcalc.restriction_engine import predict_restriction_digest, find_restriction_sites
from biolabcalc.plasmid_engineering import engineer_plasmid, evaluate_codon_usage, optimize_codons
from biolabcalc.interactive_plasmid import render_plasmid_map_svg, save_plasmid_workbench_html
from biolabcalc.protocols import list_protocols, get_protocol, format_protocol_markdown
```

### 8.3 Upgraded CLI Subcommands
- `biolabcalc seq {save,list,get,delete,import,export}`: Manage local sequence store.
- `biolabcalc plasmid {inspect,annotate,digest,list,export}`: Vector analysis and GenBank conversion.
- `biolabcalc clone-gene`: Automated gene expression plasmid engineering.
- `biolabcalc interactive-plasmid`: Standalone SVG plasmid map workbench.
- `biolabcalc digest --simulate-gel`: Virtual restriction digest electrophoresis.

---

## 9. Future Strategic Roadmap

The consolidated post-v1.5.0 roadmap spans four prioritized tracks (see [README.md](../README.md#-planned-features--strategic-roadmap) for full details):

1. **Immediate Hardening (`v1.5.x` Patch):** Fix ELN `/api/timepoints/timers` route shadowing, tighten RBAC decorators on `approvals.py` and `timepoints.py`, add 64-hex SHA-256 validation in `BlobStore`, enforce configured `cors_origins` in `api/app.py`, replace synthetic OCR fallback text with an explicit unavailable flag, and add Ruff/`pre-commit` + Playwright `[qa]` smoke tests.
2. **Next-Generation Scientific Modules (`v1.6.0+`):**
   - **NGS Library Prep:** Automated fragmentation sizing, adapter-to-insert molar ratios, and SPRI magnetic bead double-sided selection.
   - **CRISPR-Cas9 sgRNA Guide Design:** On-target and off-target scoring with Doench (2016) heuristics.
   - **Immunoassays & Cell Viability:** ELISA 4-Parameter Logistic (4PL) sigmoidal curve fitting ($EC_{50}$) and normalized $IC_{50}$ estimation (MTT, CCK-8, AlamarBlue).
   - **Isothermal Amplification & Proteomics:** LAMP/RT-LAMP/RCA calculators, quantitative Western blot densitometry, and Trypsin/Lys-C digestion scheduling with missed-cleavage tracking.
3. **Enterprise Authentication & ACLs:** Credential-based `/login`, full RBAC permission matrices, project-level ACLs, and lightweight LDAP/Active Directory SSO.
4. **Real-Time Collaboration & Hardware Integration:** WebRTC mobile 2D DataMatrix barcode scanning and WebSocket co-authoring presence/section locks.
