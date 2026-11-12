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

## 🚀 Server Launch Options

The ELN server can be launched directly from the terminal or initialized programmatically within Python.

### Terminal CLI Execution
```bash
# Launch server with default settings (127.0.0.1:8080, local SQLite)
biolabcalc eln

# Bind to custom port and network interface
biolabcalc eln --host 0.0.0.0 --port 9000

# Connect to production PostgreSQL instance
biolabcalc eln --db "postgresql://lims_user:secret@db.lab.internal:5432/eln_production"

# Headless server launch (disable automatic browser pop-up)
biolabcalc eln --no-browser --port 8080

# Specify custom storage directory for database, audit ledger, and CAS blobs
biolabcalc eln --storage-dir /var/data/biolabcalc_storage
```

### Server Command-Line Arguments Reference

| Option | Flag | Default | Description |
| :--- | :--- | :--- | :--- |
| `--host` | `-H` | `127.0.0.1` | Network interface IP address to bind. Use `0.0.0.0` for LAN access. |
| `--port` | `-p` | `8080` | TCP port for incoming HTTP/WebSocket connections. |
| `--db` | `-d` | Local SQLite | Database connection URL (`sqlite:///path/to/db.sqlite` or `postgresql://...`). |
| `--no-browser` | | `False` | Disables launching the default operating system web browser on startup. |
| `--storage-dir`| | `~/.biolabcalc_eln`| Root directory for SQLite database, CAS blobs, and audit trails. |

### Environment Variables
* `BIOLABCALC_STORAGE_DIR`: Overrides the default base directory for all databases, audit files, and CAS blobs.
* `BIOLABCALC_AUDIT_LOG`: Explicit path to the append-only JSONL audit ledger.
* `DATABASE_URL`: Connection string for PostgreSQL or custom database path.

---

## 🔗 Related Documentation
* [SOP & Protocol Management](SOP-&-Protocol-Management) — Authoring, semantic versioning, and immutable execution forks.
* [Instrument Data Parsers](Instrument-Data-Parsers) — Ingestion engines for ÄKTA FPLC, NanoDrop, Bio-Rad ChemiDoc, and Axon ABF.
* [Inventory & Freezer LIMS](Inventory-&-Freezer-LIMS) — 6-tier cold chain architecture and 2D box grid visualizer.
* [RAG & Local AI Assistant](RAG-&-Local-AI-Assistant) — Offline vector search and contextual laboratory synthesis.
* [GxP Compliance & Audit Trails](GxP-Compliance-&-Audit-Trails) — 21 CFR Part 11 cryptographic hash chains and role-based access.
* [Developer & Deployment Guide](Developer-&-Deployment-Guide) — Testing, Docker deployment, and PostgreSQL migration.
