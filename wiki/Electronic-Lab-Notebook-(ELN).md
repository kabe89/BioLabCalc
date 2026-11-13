# Electronic Lab Notebook (ELN) & Multi-Modal LIMS

The **BioLabCalc Electronic Lab Notebook (ELN) and Multi-Modal Laboratory Information Management System (LIMS)** is an enterprise-grade digital laboratory platform engineered specifically for biochemistry, molecular biology, structural biology, and bioprocess laboratories. It seamlessly bridges benchtop mathematical calculations with regulatory record-keeping, cold-chain freezer management, analytical instrument parsing, and local retrieval-augmented intelligence.

---

## 🏛️ System Architecture

The ELN is designed around a modular, multi-tier architecture capable of running as a lightweight, zero-dependency benchtop server on a personal laptop or as a horizontally scalable, containerized multi-user deployment backed by PostgreSQL 16+ with `pgvector`.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               Modern Web SPA Frontend                                  │
│  ┌───────────────┬────────────────┬───────────────┬────────────────┬────────────────┐  │
│  │ Notebook Tab  │ FPLC Canvas    │ Gel Annotator │ NanoDrop Plot  │ Freezer 2D Grid│  │
│  ├───────────────┴────────────────┴───────────────┴────────────────┴────────────────┤  │
│  │ Kinetic Timers • HITL OCR Corrector • Sequence Viewer • Global RAG Assistant (⌘K)│  │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ HTTP / JSON REST & WebSockets
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                            Dual-Engine Server Runtime                                  │
│  ┌────────────────────────────────────────────────┬─────────────────────────────────┐  │
│  │ Primary Engine: FastAPI / Uvicorn (ASGI)       │ Fallback Engine: Pure-Python    │  │
│  │ • High-concurrency async request pipeline      │   Multi-threaded HTTP Server    │  │
│  │ • Real-time WebSocket broadcasting             │ • Zero third-party dependencies │  │
│  │ • Automated OpenAPI / Swagger documentation    │ • In-process synchronous routing│  │
│  └────────────────────────────────────────────────┴─────────────────────────────────┘  │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              Application Service Layer                                 │
│  ┌──────────────────────┬──────────────────────┬─────────────────────────────────────┐ │
│  │ CampaignService      │ SOPService           │ InventoryService                    │ │
│  │ • Multi-day studies  │ • Semantic versioning│ • 6-tier cold-chain spatial hierarchy│ │
│  │ • Yield aggregation  │ • GxP execution fork │ • 2D slot collision validation      │ │
│  ├──────────────────────┼──────────────────────┼─────────────────────────────────────┤ │
│  │ FPLCService          │ GelService           │ AuditService                        │ │
│  │ • Peak integration   │ • Lane densitometry  │ • SHA-256 hash-chained ledger       │ │
│  │ • Fraction pooling   │ • MW Rf calibration  │ • 21 CFR Part 11 tamper-evidence    │ │
│  └──────────────────────┴──────────────────────┴─────────────────────────────────────┘ │
└─────────────────────────────┬─────────────────────────────────────┬────────────────────┘
                              │                                     │
                              ▼                                     ▼
┌───────────────────────────────────────────────┐ ┌──────────────────────────────────────┐
│            Dual Database Abstraction          │ │ Content-Addressed Storage (CAS) Blob │
│ ┌───────────────────┬───────────────────────┐ │ │ • SHA-256 deduplicated file store   │
│ │ SQLite Engine     │ PostgreSQL 16+ Engine │ │ │ • Two-tier directory sharding        │
│ │ • Embedded local  │ • Multi-user cluster  │ │ │   ({base}/{sha256[:2]}/{sha256}.blob)│
│ │ • Pure-Python ORM │ • pgvector (HNSW)     │ │ │ • Atomic staging via temp files      │
│ │ • Custom vector   │ • JSONB + tsvector    │ │ │ • Local filesystem & S3/MinIO drivers│
│ │   scalar function │ • 21 relational tables│ │ │ • Full binary reproducibility        │
│ └───────────────────┴───────────────────────┘ │ └──────────────────────────────────────┘
└───────────────────────────────────────────────┘
```

---

## 🗄️ Dual-Engine Database Abstraction

The persistence layer (`biolabcalc.eln.schema.database`) implements an abstraction pattern allowing seamless switching between local SQLite storage and high-concurrency PostgreSQL clusters without altering service logic.

### 1. Zero-Dependency Pure-Python SQLite Engine
For single-investigator workstations, field expeditions, or air-gapped environments where external database packages or compiled C-extensions are unavailable, BioLabCalc incorporates an in-house declarative ORM:
* **Custom Metaclass ORM (`BaseModel`, `Field`, `Relationship`)**: Provides model registration, foreign-key resolution, cascading deletions, automatic JSON serialization, and entity tracking without requiring SQLAlchemy.
* **In-Database Vector Cosine Similarity**: SQLite does not natively support vector datatypes. BioLabCalc injects a compiled C-level scalar function directly into the SQLite connection:
  ```python
  conn.create_function("COSINE_SIMILARITY", 2, _sqlite_cosine_similarity)
  ```
  This enables nearest-neighbor hybrid search directly inside SQLite SQL queries without external vector libraries.
* **Transactional Identity Map**: The custom `Session` maintains an identity map and tracks `_new` and `_dirty` object sets, guaranteeing atomic commits and rollback capabilities.
* **Concurrency Locking**: When using in-memory SQLite (`:memory:`), `Engine` protects the shared connection with a `threading.Lock()` so concurrent multi-threaded operations do not collide or corrupt state.
* **Write-Ahead Logging (WAL) Mode**: For file-based SQLite databases, connections automatically execute `PRAGMA journal_mode = WAL;` and configure `timeout=30.0` to eliminate database locks under concurrent access.

### 2. Enterprise PostgreSQL 16+ with `pgvector`
For multi-user research institutions, core facilities, and regulated biopharma deployments, the ELN connects to PostgreSQL via SQLAlchemy and `psycopg2-binary` (installable via `pip install "biolabcalc[eln]"`). If a `postgresql://` or `postgres://` URI is specified without required dependencies, the engine raises an explicit `ValueError` rather than silently falling back to SQLite in-memory storage. The production DDL (`biolabcalc.eln.schema.ddl.sql`) provisions:
* **21 Relational Tables**: Covering users, audit logs, storage blobs, SOP templates, experimental campaigns, daily entries, kinetic timepoint logs, biological sequences, PCR assays, NanoDrop measurements, FPLC columns, FPLC runs, FPLC fractions, gel records, gel lanes, electrophysiology recordings, code analysis runs, storage hierarchy nodes, freezer boxes, inventory tubes, and RAG document chunks.
* **Vector Cosine Indexing (HNSW)**: 1536-dimensional embeddings indexed via Hierarchical Navigable Small World graphs:
  ```sql
  CREATE INDEX idx_rag_document_chunks_embedding_hnsw
      ON rag_document_chunks
      USING hnsw (embedding vector_cosine_ops)
      WITH (m = 16, ef_construction = 64);
  ```
* **Hybrid Search Indexes**: Generalized Inverted Indexes (`GIN`) on generated `tsvector` columns for full-text lexical search, GIN trigram indexes (`pg_trgm`) for fuzzy keyword matching, and GIN JSONB indexes for experimental parameter queries.

---

## 📦 Content-Addressed Storage (CAS) Engine

All raw instrument outputs, gel micrographs, chromatograms, and spectrophotometer runs are ingested through the Content-Addressed Storage subsystem (`biolabcalc.eln.storage.blob_store`).

### Core Features:
1. **Cryptographic Deduplication**: Every file is indexed strictly by the hexadecimal digest of its SHA-256 hash. If two researchers upload identical 500 MB FPLC run files, only one physical blob is written to disk.
2. **Two-Tier Directory Sharding**: To prevent filesystem performance degradation when storing tens of thousands of raw analytical files, blobs are sharded across subdirectories using the first two hex characters of their hash:
   ```
   .biolabcalc_data/blobs/
   ├── 3a/
   │   ├── 3a8f9c10...blob        <- Raw immutable binary payload
   │   └── 3a8f9c10...meta.json   <- Ingestion metadata, MIME type, size, attributes
   ├── d4/
   │   ├── d41d8cd9...blob
   │   └── d41d8cd9...meta.json
   ```
3. **Atomic Writes**: Blobs are written to a temporary staging file and atomically renamed to their final sharded path, preventing corrupt reads during concurrent multi-threaded uploads.
4. **Storage Backend Flexibility**: The storage layer is governed by the `StorageBackend` abstract interface, allowing effortless switching between local storage (`LocalStorageBackend`) and enterprise cloud buckets (`S3StorageBackend` / MinIO).

---

## 🖥️ Web Interface Walkthrough

The BioLabCalc ELN user interface is delivered as a modern Single-Page Application (SPA) located in `eln/web/templates/index.html` and styled via `eln/web/static/styles.css`.

| Tab / Module | Primary Purpose | Key Features |
| :--- | :--- | :--- |
| **📖 Notebook** | Multi-day campaign execution | Daily bench entries, carry-forward buffer/plasmid state, protocol deviation tracking, cumulative protein yield calculations. |
| **⏱️ Kinetic Timepoints** | In-run incubation & growth monitoring | Live multi-timer countdown/countup, optical density ($OD_{600}$) tracking, temperature/RPM logs, audio alerts on milestone completion. |
| **📈 FPLC Chromatogram** | Chromatography trace inspection | ÄKTA UNICORN interactive multi-trace canvas ($UV_{280}$, $UV_{260}$, $UV_{215}$, Conductivity, %B, Pressure), fraction tube mapping, peak integration. |
| **🧬 Gel Canvas** | Electrophoresis densitometry | Bio-Rad ChemiDoc & 16-bit TIFF rendering, lane profiling, molecular weight ($R_f$) logarithmic calibration, automated purity percentage calculation. |
| **🔬 NanoDrop Spectra** | Microvolume UV-Vis quantification | 220–350 nm spectral overlay, pathlength normalization, $A_{260}/A_{280}$ and $A_{260}/A_{230}$ purity diagnostics, phenol/guanidine contaminant detection. |
| **❄️ Freezer LIMS** | Cold-chain sample management | Multi-tier spatial tree (Room $\rightarrow$ Unit $\rightarrow$ Rack $\rightarrow$ Box), interactive 2D box grid (9x9, 10x10), slot collision prevention, upstream sample lineage graph. |
| **📝 OCR Digitizer** | Scanned bench notes digitization | Human-in-the-Loop (HITL) OCR corrector, confidence scoring, ambiguous biochemical character disambiguation, side-by-side interactive correction. |
| **🧬 Sequences & SOPs** | Master molecular registries | Plasmid construct repository, translated ORF biophysics (MW, pI, $\varepsilon_{280}$), master SOP catalog, and PI sign-off lifecycle. |
| **🔍 Assistant (⌘K)** | Context-aware RAG knowledge search | Hybrid BM25 + dense vector semantic search across all historical notebook entries, FPLC runs, and freezer tubes with citation provenance. |

---

## 🔄 Cross-Section Tool Reactive Routing

The BioLabCalc ELN single-page application implements an event-driven **Reactive Routing Bus** managed by the client-side `AppController`. Rather than treating bench calculations, gel images, spectrophotometer readings, cold-chain inventory, and daily notebook logs as siloed tools, the platform enables bi-directional, cross-tab data flow with single-click actions.

### Reactive Topology & Data Flow

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               CROSS-SECTION TOOL REACTIVE ROUTING TOPOLOGY                             │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘

                     ┌────────────────────────────────────────────────────────┐
                     │              Tab 8: Sequences & SOPs Registry          │
                     │  • Oligo / Template / Primer Sequence Input & Presets  │
                     │  • Instant MW, Tm, GC%, and Length Physicochem Matrix  │
                     └───────┬─────────────────┬────────────────┬─────────┬───┘
                             │                 │                │         │
                 Send to Gel │  Send to        │  Append to     │         │ Store in
                 (Simulate)  │  NanoDrop (QC)  │  Notebook      │         │ Freezer
                             ▼                 ▼                ▼         ▼
     ┌────────────────────────┐   ┌───────────────────────┐   ┌────────────────────────┐
     │   Tab 4: Gel Canvas    │   │ Tab 5: NanoDrop Plot  │   │  Tab 6: Freezer LIMS   │
     │ • Inverted ChemiDoc    │   │ • 220-350 nm Spectra  │   │ • 6-Tier Spatial Tree  │
     │ • Lane Densitometry    │   │ • Pathlength Corr.    │   │ • 2D Box Grid (9x9)    │
     │ • log₁₀(MW) = -1.85·Rf │   │ • A260/A280 Purity    │   │ • Tube Metadata & QC   │
     └───────────┬────────────┘   └───────┬─────────┬─────┘   └───────────▲────────────┘
                 │                        │         │                     │
                 │ Log Band / Lane MW     │ Log QC  │ Sync Concentration  │
                 │ & Rf Calibration       │ Metrics │ to Selected Tube    │
                 ▼                        ▼         └─────────────────────┘
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                Tab 1: Electronic Notebook                            │
│  • Immutable Daily Experimental Log in GitHub-Flavored Markdown                      │
│  • Live Audit Record Tables with Parameter Targets, Tolerances, and Pass/Fail Status │
│  • Upstream Campaign Provenance, SOP Deviations, and Multi-Day Yield Aggregation     │
└──────────────────▲──────────────────────────────────────────▲────────────────────────┘
                   │                                          │
                   │ Log Stamped Audit Table                  │ Finalize & Transfer
                   │ with Deviation Flagging                  │ Verified Bench Text
                   │                                          │
     ┌─────────────┴──────────────┐             ┌─────────────┴──────────────┐
     │ Tab 2: Kinetic Timers      │             │ Tab 7: OCR Digitizer       │
     │ • Multi-Timer State Engine │             │ • HITL Bracketed Corrector │
     │ • Temperature / RPM Log    │             │ • Confidence Ambiguity Fix │
     │ • Target vs Actual Minutes │             │ • Atomic Note Integration  │
     └────────────────────────────┘             └────────────────────────────┘
```

### Module Dispatch Workflows

#### 1. Sequences & SOPs (Tab 8) Reactive Dispatch
The Sequences & SOPs module acts as the biological source of truth for oligonucleotides, cloning inserts, plasmids, and master procedures. Using the top toolbar, researchers dispatch sequences directly into operational tabs:
* **🧪 Send to Gel (Tab 4)**: Calculates single- or double-stranded base-pair length and molecular weight, injecting synthetic migration markers into the Gel Canvas lane simulator. This enables instant visual comparison between expected amplicon sizes and wet-lab electrophoresis lanes.
* **🔬 Send to NanoDrop (Tab 5)**: Computes sequence-specific molar extinction coefficients ($\varepsilon_{260}$ or $\varepsilon_{280}$) and average molecular weight, automatically pre-populating theoretical concentration baselines and expected $A_{260}$ optical density targets for microvolume UV-Vis analysis.
* **📝 Append to Note (Tab 1)**: Formats nucleotide properties ($T_m$, GC%, MW, length) and active SOP compliance tags (e.g., `SOP-PROT-042 v2.4`) into structured Markdown tables and appends them directly to the active day's notebook entry.
* **❄️ Store in Freezer (Tab 6)**: Prompts for slot allocation within the active 2D box grid (e.g., Box B-07), creating an immutable tube entity containing sequence metadata, primer construct identifiers, concentration, and date stored.

#### 2. Gel Canvas (Tab 4) $\rightarrow$ Notebook Band Logging
The interactive Gel Canvas performs lane profiling, ChemiDoc contrast normalization, and molecular weight calibration via linear regression:
$$\log_{10}(\text{MW}) = -1.85 \cdot R_f + 2.45$$
Clicking **`📝 Log Band to Note`** extracts the selected band's calibrated molecular weight (e.g., 98.2 kDa for T7 RNA Polymerase), relative migration distance ($R_f$), and densitometric purity percentage (>98%), writing a validated measurement record into Tab 1 with automatic pass/fail tolerance checking against expected construct sizes.

#### 3. NanoDrop Spectra (Tab 5) $\rightarrow$ Dual Routing (Notebook & Freezer LIMS)
The microvolume UV-Vis module evaluates full 220–350 nm spectra with baseline correction and pathlength normalization:
* **`📝 Log QC to Note`**: Transfers $A_{260}$, $A_{280}$, $A_{230}$, $A_{260}/A_{280}$ purity ratios (target 1.8 for DNA, 2.0 for RNA), $A_{260}/A_{230}$ ratios (target 2.0), pathlength-corrected concentration ($\text{ng}/\mu\text{L}$), and chemical purity warnings (phenol at 270 nm, guanidine salts at 230 nm) into the Notebook QC ledger.
* **`❄️ Update Freezer Tube`**: Interactively synchronizes the quantified nucleic acid or protein concentration directly into the corresponding physical tube in the 2D Freezer Grid (Tab 6), updating sample records and lineage metadata without manual data re-entry.

#### 4. Kinetic Deviation Timers (Tab 2) $\rightarrow$ Notebook Stamped Audit Log
The real-time kinetic timer engine monitors incubations, enzymatic digestions, cell growth curves, and induction milestones:
* Clicking **`📝 Log to Note`** compiles active and completed timer milestones into an immutable, timestamped Markdown audit table.
* The generated log records Step Description, Planned Duration vs. Actual Elapsed Duration, Parameter Tracked ($OD_{600}$, Temperature, RPM), SOP Deviation Flagging, and Operator ID directly into the day's experimental log, satisfying [GxP Compliance & Audit Trails](GxP-Compliance-&-Audit-Trails) requirements.

#### 5. OCR Digitizer (Tab 7) $\rightarrow$ Notebook Verification Transfer
The Human-in-the-Loop (HITL) OCR corrector ingests handwritten bench notes and instrument slips, highlighting low-confidence tokens (e.g., `[[UNCERTAIN:id="ocr_4" text="B4 to B8" conf=0.74]]`):
* Once the researcher inspects and accepts or corrects ambiguous values, clicking **`Finalize & Log to Note`** strips internal uncertainty markers and atomically transfers human-verified experimental observations and harvest parameters into Tab 1.

---

## 🚀 Server Launch & Environment Setup

The ELN server can be configured for multiple environments (development, production, test, offline bench), designated via `config.yaml`, launched directly from the terminal, or initialized programmatically within Python.

### Multi-Environment Setup (`./configure`)
Use the `./configure` script to configure hosting parameters and security presets for different deployments:
```bash
# Set up development workstation (default: 127.0.0.1:8080)
./configure --env development

# Configure production server binding to all interfaces with anonymization enabled
./configure --env production --host 0.0.0.0 --port 8080 --anonymize

# Configure automated test fixture or offline bench environment
./configure --env test
./configure --env offline
```

### Configuration via `config.yaml`
The ELN automatically reads `config.yaml` (or `./config.yaml.example` as a template) to designate the server host, port, database, and anonymization policy:
```yaml
server:
  host: "127.0.0.1"        # Designated host to bind (e.g. "127.0.0.1", "0.0.0.0")
  port: 8080               # TCP port
  open_browser: false      # Auto-launch browser
  quiet: false             # Suppress startup banners

database:
  url: null                # Database URL (SQLite or PostgreSQL)
  storage_dir: null        # Blob & database directory

security:
  anonymize_logs: true     # Mask IP addresses, user paths, and auth tokens
  require_auth: false

environment: "production"  # development | production | test | offline
```

### Terminal CLI Execution
```bash
# Launch server with default settings or designated config.yaml
biolabcalc eln

# Designate specific config file
biolabcalc eln -c config.yaml

# Override host and port from CLI
biolabcalc eln --host 0.0.0.0 --port 9000

# Generate template config.yaml
biolabcalc eln --generate-config

# Enable anonymized logging
biolabcalc eln --anonymize --no-browser
```

### Server Command-Line Arguments Reference

| Option | Flag | Default | Description |
| :--- | :--- | :--- | :--- |
| `--host` | | `config.yaml` / `127.0.0.1` | Network interface IP address to bind. Use `0.0.0.0` for LAN access. |
| `--port` | `-p` | `config.yaml` / `8080` | TCP port for incoming HTTP/WebSocket connections. |
| `--config` | `-c` | `config.yaml` | Path to designated YAML configuration file. |
| `--anonymize` | | `True` | Redact IP addresses, home directory paths, and auth tokens. |
| `--generate-config` | | | Write default `config.yaml` in current working directory. |
| `--db-url` | | Local SQLite | Database connection URL (`sqlite:///path/to/db.sqlite` or `postgresql://...`). |
| `--no-browser` | | `False` | Disables launching the default operating system web browser on startup. |
| `-q`, `--quiet`| | `False` | Suppresses startup banners and decorative bars. |

### Environment Variables
* `BIOLABCALC_CONFIG`: Path to designated `config.yaml`.
* `BIOLABCALC_STORAGE_DIR`: Overrides the default base directory for all databases, audit files, and CAS blobs.
* `DATABASE_URL`: Connection string for PostgreSQL or custom database path.

---

## 🌐 Shared Network Drive Multi-User Deployment

For laboratories sharing a common network directory (e.g. Windows UNC `\\server\share\data`, mapped drive `Z:\...`, or NFS `/mnt/lab_share`), BioLabCalc provides a dedicated `network_share` architecture:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Shared Network Drive                            │
│  (UNC \\lab-nas\biology_share or Mapped Drive Z:\BioLabCalc_Data)       │
├────────────────────────────────┬───────────────────────────────────────┤
│ Central Relational Database    │ Shared CAS Blob Store                 │
│ • SQLite in DELETE mode        │ • SHA-256 content-addressable storage │
│ • 60s lock queue busy timeout  │ • Immutable raw instrument files      │
│ • Optimistic Concurrency (OCC) │ • Atomic staging and tempfile rename  │
├────────────────────────────────┴───────────────────────────────────────┤
│ Central Master Catalog: Protocols, BioSequences & Custom Templates     │
└────────────────────────────────────────────────────────────────────────┘
         ▲                                                ▲
         │ Advisory Lock & OCC Token                      │ Advisory Lock & OCC Token
┌────────┴──────────────┐                        ┌────────┴──────────────┐
│ Workstation 1 (Bench) │                        │ Workstation 2 (Office)│
│ • Standalone Runner   │                        │ • Standalone Runner   │
│ • Local Web Interface │                        │ • Local Web Interface │
└───────────────────────┘                        └───────────────────────┘
```

### Key Technical Mechanisms:
1. **Network-Safe Concurrency**: Replaces SQLite WAL mode (which fails across network boundaries due to `-shm` shared memory limitations) with `PRAGMA journal_mode = DELETE;` and `PRAGMA busy_timeout = 60000;`.
2. **Cross-Process Advisory Locking**: Coordinates write operations using `.lock` files with exponential backoff and stale-lock recovery.
3. **Optimistic Concurrency Control (OCC)**: Every campaign, daily entry, and SOP carries a UUID `version_token`. If another researcher saves modifications while you are editing, the system flags a concurrency conflict and offers merge options rather than silently overwriting data.

---

## 🎨 No-Code Customizable Experiment Engine

Wet-lab research encompasses diverse disciplines (molecular cloning, protein purification, cell biology, electrophysiology, chemical biology). Non-coding scientists can design custom experiment templates directly in the ELN:

### 1. Dynamic Form Builder & Field Types
Templates support:
* **Numeric Fields with Units**: Concentration (`mg/mL`, `µM`), Volume (`µL`, `mL`), Mass (`ng`, `µg`, `mg`), Temperature (`°C`), OD600.
* **Calculation Formulas**: Mathematical formulas evaluated via safe pure-Python Abstract Syntax Tree (AST) parsing without `eval()`:
  ```text
  total_yield_mg = (concentration_mg_ml * volume_ml)
  recovery_percent = (eluate_yield_mg / load_yield_mg) * 100.0
  ```
* **Step Checklists**: Sequential protocol steps with planned incubation countdown timers.
* **Select & Multi-Select Dropdowns**: Host strains, vectors, buffer types, cell lines.
* **Raw Instrument Slots**: Dedicated drag-and-drop slots for ÄKTA FPLC `.res`, Bio-Rad `.scn`, Axon `.abf`, or NanoDrop `.csv` files.

### 2. Pre-Packaged Templates
BioLabCalc ships with ready-to-use templates out of the box:
1. *General Lab Notebook Entry*
2. *Molecular Cloning & Assembly*
3. *Protein Expression & Purification*
4. *Cell Culture & Growth Kinetics*
5. *Electrophysiology Patch-Clamp Recording*
6. *Custom Blank Canvas*

Templates can be exported and imported as portable JSON or YAML files to share across research groups.

---

## 🛡️ Decentralized Non-PI Approval & Peer-Review Governance

Many academic research groups and core facilities operate with flat hierarchies, student peer review, or lab manager oversight rather than requiring the Principal Investigator for everyday checkoffs.

### 1. Configurable Approval Policies
Each laboratory workspace or campaign can designate its approval model:
* **Open Collaboration (`OPEN_COLLABORATION`)**: Entries are auto-finalized upon submission; ideal for exploratory or student research.
* **Peer Review (`PEER_REVIEW`)**: Any active colleague or lab member can review, verify checklists, and sign off.
* **Designated Reviewer (`DESIGNATED_REVIEWER`)**: The author assigns a specific senior researcher or lab manager.
* **PI Hierarchy (`PI_APPROVAL`)**: Formal GxP mode requiring a Principal Investigator role.

### 2. Cryptographic Digital Seals
Upon approval, BioLabCalc generates a tamper-evident SHA-256 seal:
$$\text{Seal} = \text{SHA256}(\text{EntryID} + \text{AuthorID} + \text{DataDigest} + \text{ReviewerID} + \text{Timestamp})$$
If any measurement, yield value, or protocol deviation is retroactively altered, the seal verification immediately fails and flags the entry as compromised.

---

## 🔗 Related Documentation
* [SOP & Protocol Management](SOP-&-Protocol-Management) — Authoring, semantic versioning, and immutable execution forks.
* [Instrument Data Parsers](Instrument-Data-Parsers) — Ingestion engines for ÄKTA FPLC, NanoDrop, Bio-Rad ChemiDoc, and Axon ABF.
* [Inventory & Freezer LIMS](Inventory-&-Freezer-LIMS) — 6-tier cold chain architecture and 2D box grid visualizer.
* [RAG & Local AI Assistant](RAG-&-Local-AI-Assistant) — Offline vector search and contextual laboratory synthesis.
* [GxP Compliance & Audit Trails](GxP-Compliance-&-Audit-Trails) — 21 CFR Part 11 cryptographic hash chains and role-based access.
* [Developer & Deployment Guide](Developer-&-Deployment-Guide) — Testing, Docker deployment, and PostgreSQL migration.
