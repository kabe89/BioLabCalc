# Developer & Production Deployment Guide

This guide details the repository structure, local development environment setup, unit testing protocols, database migration strategies, and production deployment procedures for **BioLabCalc** and its **Electronic Lab Notebook (ELN) / Multi-Modal LIMS** subsystem.

---

## 📂 Repository Directory Layout

The codebase follows modern Python packaging standards with clear architectural separation between core biophysical calculators, the ELN subsystem, analytical parsers, and browser assets:

```
biolabcalc_repository/
├── src/
│   └── biolabcalc/
│       ├── __init__.py                 <- Package root and version exports
│       ├── cli.py                      <- Click/argparse CLI entrypoint (29 commands)
│       ├── easy.py                     <- High-level convenience API for Jupyter / IPython
│       ├── molecular_weight.py         <- MW, isotopic distribution, and elemental formula
│       ├── protein.py                  <- Extinction coefficients (e280), pI, Net charge
│       ├── buffers.py                  <- Recipe generator, dilution (C1V1), pH Henderson-Hasselbalch
│       ├── cloning.py                  <- Gibson assembly, Golden Gate Type IIS, restriction digest
│       ├── pcr.py                      <- SantaLucia thermodynamics, primer annealing, Q5/Taq
│       ├── gels.py                     <- Agarose / SDS-PAGE band simulation & Rf mapping
│       ├── western_blot.py             <- Membrane transfer scaling, antibody dilution math
│       ├── fluorescence.py             <- Fluorophore excitation/emission spectra & FRET overlap
│       ├── ecoli_growth.py             <- Bacterial doubling kinetics, OD600 biomass modeling
│       ├── precipitation.py            <- Ethanol/isopropanol/NaOAc desalting stoichiometry
│       └── eln/                        <- Electronic Lab Notebook & LIMS Subsystem
│           ├── server.py               <- Dual-engine server launcher (Uvicorn ASGI / HTTP fallback)
│           ├── api/                    <- REST routing, WebSockets, and authentication
│           │   ├── app.py              <- FastAPI application factory
│           │   ├── router.py           <- Unified API route aggregator
│           │   ├── websocket_manager.py<- Real-time client state broadcaster
│           │   └── routes/             <- Domain-specific endpoint handlers (sops, inventory, etc.)
│           ├── parsers/                <- Analytical instrument file decoders
│           │   ├── fplc_parser.py      <- ÄKTA UNICORN (.res, .csv, .zip) multi-channel reader
│           │   ├── nanodrop_parser.py  <- Thermo NanoDrop UV-Vis spectral curve extractor
│           │   ├── biorad_parser.py    <- Bio-Rad Image Lab (.scn) & 16-bit TIFF densitometer
│           │   ├── abf_parser.py       <- Pure-Python Axon Binary Format (ABF v1/v2, ATF) decoder
│           │   ├── doc_parser.py       <- Protocol Markdown and table structure parser
│           │   └── ocr_engine.py       <- HITL OCR engine with biochemical entity disambiguation
│           ├── rag/                    <- Local intelligence & retrieval-augmented generation
│           │   ├── chunker.py          <- Laboratory entity extractor & semantic chunker
│           │   ├── hybrid_search.py    <- BM25 + dense vector Reciprocal Rank Fusion engine
│           │   ├── local_llm.py        <- Local inference client (Ollama/GGUF) + offline fallback
│           │   └── synthesizer.py      <- Contextual citation synthesizer with footnotes
│           ├── schema/                 <- Relational models, DDL, and database engines
│           │   ├── database.py         <- Dual database abstraction (custom SQLite ORM + PostgreSQL)
│           │   ├── ddl.sql             <- PostgreSQL 16+ pgvector production DDL (21 tables)
│           │   └── models.py           <- Declarative entity models
│           ├── services/               <- Core business logic & GxP governance
│           │   ├── audit_service.py    <- SHA-256 cryptographically chained immutable ledger
│           │   ├── sop_service.py      <- SOP versioning, PI sign-offs, and execution forks
│           │   ├── inventory_service.py<- 6-tier freezer hierarchy, 2D grid, sample lineage
│           │   ├── campaign_service.py <- Multi-day experimental campaign management
│           │   └── fplc_service.py     <- Fraction collection and chromatogram integration
│           ├── storage/                <- Content-Addressed Storage (CAS)
│           │   ├── blob_store.py       <- SHA-256 sharded file storage (local & S3/MinIO)
│           │   └── preview_generator.py<- Web preview downsampling for large analytical files
│           └── web/                    <- Single-Page Application assets
│               ├── templates/index.html<- Unified HTML5 laboratory workspace
│               └── static/             <- Canvases, timers, freezer grids, and stylesheets
├── tests/                              <- Test suite
├── pyproject.toml                      <- Build configuration, dependencies, and entrypoints
└── README.md                           <- Repository overview
```

---

## 🛠️ Development Setup & Testing

### 1. Development Installation
Clone the repository and install in editable mode with development dependencies:

```bash
# Clone the repository
git clone https://github.com/your-org/biolabcalc.git
cd biolabcalc

# Create and activate an isolated Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install package in editable mode with development and ELN extras
pip install -e ".[dev,eln]"
```

### 2. Running the Test Suite
The repository maintains exhaustive test coverage across all calculators, parsers, and ELN services using Python's standard `unittest` framework:

```bash
# Execute entire test suite
python -m unittest discover tests

# Run ELN test suites
python -m unittest tests/test_eln_services_and_api.py
python -m unittest tests/test_eln_parsers.py
python -m unittest tests/test_eln_rag.py
python -m unittest tests/test_eln_schema.py
python -m unittest tests/test_eln_integration.py
```

---

## 🗄️ Database Migration: SQLite to PostgreSQL 16+

While the zero-dependency SQLite engine is optimal for local evaluation, high-throughput multi-user enterprise deployments should run on **PostgreSQL 16+** with the **`pgvector`** extension.

Connecting to PostgreSQL requires SQLAlchemy and psycopg2-binary, installed via `pip install "biolabcalc[eln]"`. When using file-based SQLite, WAL mode (`PRAGMA journal_mode = WAL;`) and a 30-second busy timeout are automatically enabled to ensure reliable concurrency, while in-memory SQLite connections are guarded by thread synchronization locks.

### Step 1: Provision PostgreSQL & Enable Extensions
```sql
CREATE DATABASE eln_production;
\c eln_production;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
```

### Step 2: Execute Production DDL
Apply the complete 21-table production schema located at `src/biolabcalc/eln/schema/ddl.sql`:

```bash
psql -U postgres -d eln_production -f src/biolabcalc/eln/schema/ddl.sql
```

### Step 3: Configure Database Connection
Launch the ELN server targeting the PostgreSQL database:
```bash
biolabcalc eln --db "postgresql://eln_user:secret_password@localhost:5432/eln_production" --port 8080
```
Or export the standard environment variable:
```bash
export DATABASE_URL="postgresql://eln_user:secret_password@localhost:5432/eln_production"
biolabcalc eln
```

---

## 🐳 Production Deployment Architectures

### Option A: Docker & Docker Compose (Recommended)

Create a `docker-compose.yml` to provision PostgreSQL with `pgvector` alongside the BioLabCalc ELN application container:

```yaml
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg16
    restart: always
    environment:
      POSTGRES_DB: eln_production
      POSTGRES_USER: eln_admin
      POSTGRES_PASSWORD: secure_biolab_password
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./src/biolabcalc/eln/schema/ddl.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

  eln:
    build: .
    restart: always
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql://eln_admin:secure_biolab_password@db:5432/eln_production
      BIOLABCALC_STORAGE_DIR: /data/storage
      BIOLABCALC_AUDIT_LOG: /data/storage/audit_ledger.jsonl
    volumes:
      - eln_data:/data/storage
    ports:
      - "8080:8080"
    command: ["biolabcalc", "eln", "--host", "0.0.0.0", "--port", "8080", "--no-browser"]

volumes:
  pgdata:
  eln_data:
```

Launch the cluster:
```bash
docker-compose up -d
```

---

### Option B: Linux Systemd Service

For standard bare-metal or virtual server deployments running on Ubuntu / Debian / RHEL:

Create `/etc/systemd/system/biolabcalc-eln.service`:
```ini
[Unit]
Description=BioLabCalc Electronic Lab Notebook & LIMS Service
After=network.target postgresql.service

[Service]
Type=simple
User=biolab
Group=biolab
WorkingDirectory=/opt/biolabcalc
Environment="PATH=/opt/biolabcalc/venv/bin:/usr/bin"
Environment="DATABASE_URL=postgresql://eln_user:secret@localhost:5432/eln_production"
Environment="BIOLABCALC_STORAGE_DIR=/var/lib/biolabcalc/data"
ExecStart=/opt/biolabcalc/venv/bin/biolabcalc eln --host 127.0.0.1 --port 8080 --no-browser
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now biolabcalc-eln.service
```

---

### Option C: Production Nginx Reverse Proxy Configuration

Deploy Nginx in front of BioLabCalc to manage SSL/TLS termination, request buffering, client upload limits, and WebSocket upgrade protocols:

```nginx
server {
    listen 80;
    server_name eln.lab.institution.edu;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name eln.lab.institution.edu;

    ssl_certificate /etc/letsencrypt/live/eln.lab.institution.edu/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/eln.lab.institution.edu/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Allow large instrument file uploads (FPLC runs, gel micrographs up to 500 MB)
    client_max_body_size 500M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support for real-time timer sync and live updates
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

---

## ⚡ Performance Tuning & Storage Maintenance

### 1. SQLite Concurrency (WAL Mode)
When running the embedded SQLite engine in multi-threaded laboratory setups, enable Write-Ahead Logging (WAL) mode to permit concurrent readers during writes:
```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000; -- 64 MB memory cache
PRAGMA foreign_keys = ON;
```

### 2. CAS Blob Store Deduplication & Pruning
Content-Addressed Storage automatically deduplicates uploads based on SHA-256 hash digests. To remove unreferenced "orphan" blobs (e.g. from deleted temporary drafts):
```python
from biolabcalc.eln.storage.blob_store import BlobStore

store = BlobStore(base_dir="/var/lib/biolabcalc/data/blobs")
# Enumerate all physical blobs
all_blobs = store.list_blobs()
print(f"Total stored blobs: {len(all_blobs)}")
```

### 3. Disaster Recovery & Backup Strategy
* **Database Backup**: Standard automated PostgreSQL dumps:
  ```bash
  pg_dump -U eln_admin -Fc eln_production > /backup/eln_$(date +%Y%m%d_%H%M%S).dump
  ```
* **CAS Blob Synchronization**: Because blobs are immutable and named by SHA-256 hashes, they can be synchronized incrementally to cold storage (e.g. AWS S3 Glacier or NAS) using `rsync` or S3 sync:
  ```bash
  rsync -av --ignore-existing /var/lib/biolabcalc/data/blobs/ /mnt/backup_nas/blobs/
  ```

---

## 🔗 Related Documentation
* [Electronic Lab Notebook (ELN)](Electronic-Lab-Notebook-(ELN)) — System architecture and server options.
* [GxP Compliance & Audit Trails](GxP-Compliance-&-Audit-Trails) — 21 CFR Part 11 ledger verification commands.
* [RAG & Local AI Assistant](RAG-&-Local-AI-Assistant) — Configuring local LLM endpoints (Ollama, vLLM).
