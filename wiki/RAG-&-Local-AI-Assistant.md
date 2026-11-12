# Retrieval-Augmented Generation (RAG) & Local AI Assistant

Biotechnology discovery and biopharma patents involve highly confidential, proprietary intellectual property. Sending unreleased construct sequences, experimental notes, or novel purification protocols to public cloud LLM endpoints (e.g. OpenAI, Anthropic) introduces significant data-leakage and compliance risks. 

The BioLabCalc **Retrieval-Augmented Generation (RAG) and Local AI Assistant** subsystem (`biolabcalc.eln.rag`) provides an **air-gapped, zero-data-leakage intelligence layer** that runs entirely on local workstation hardware or institutional GPU clusters. It combines protocol-aware semantic chunking, dense-sparse hybrid retrieval with Reciprocal Rank Fusion (RRF), and offline local language models.

---

## 🏛️ RAG Engine Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Laboratory Query                                     │
│  "What was the optimal imidazole concentration and elution volume for T7RNAP?"         │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Hybrid Retrieval Engine (`hybrid_search.py`)                    │
│  ┌────────────────────────────────────────┬─────────────────────────────────────────┐  │
│  │ Dense Semantic Search                  │ Sparse Lexical Search (BM25)            │  │
│  │ • 1536-dim vector embeddings           │ • Token frequency inverted index        │  │
│  │ • Cosine similarity scoring            │ • Biological entity boost (constructs,  │  │
│  │ • Understands biophysical synonyms    │   columns, resins, mutations)           │  │
│  └───────────────────┬────────────────────┴────────────────────┬────────────────────┘  │
│                      │                                         │                       │
│                      └────────────────────┬────────────────────┘                       │
│                                           │                                            │
│                                           ▼                                            │
│                         Reciprocal Rank Fusion (RRF Scoring)                           │
│                         RRF(d) = 1/(60 + r_dense) + 1/(60 + r_sparse)                  │
│                                           │                                            │
│                                           ▼                                            │
│                      Multi-User Temporal & Provenance Filters                          │
│                      (Filter by project, author, alumni status, date)                  │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ Top-K Ranked Laboratory Chunks
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     Contextual Citation Synthesizer (`synthesizer.py`)                 │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Assembles structured prompt with laboratory provenance blocks:                   │  │
│  │   [Ref 1] Author: Dr. Rosalind Franklin | Campaign: CMP-2026-T7 | Day 4          │  │
│  │           Instrument: ÄKTA pure 25 | File: /runs/t7rnap_histrap_04.res           │  │
│  │           "Elution occurred at 250 mM imidazole with peak UV280 at Ve = 14.5 mL" │  │
│  └────────────────────────────────────────┬─────────────────────────────────────────┘  │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Local Inference Client (`local_llm.py`)                         │
│  ┌────────────────────────────────────────┬─────────────────────────────────────────┐  │
│  │ On-Premise GPU / Cluster Endpoints     │ Air-Gapped Offline Fallback Engine      │  │
│  │ • Ollama (Llama 3, Mistral, Qwen)      │ • Deterministic n-gram hypersphere      │  │
│  │ • vLLM / OpenClaw / LocalAI (GGUF)     │   pseudo-embedding generator            │  │
│  │ • SLURM head-node HTTP inference       │ • Rule-based biochemical reasoning      │  │
│  │ • Zero cloud API calls or data escape  │ • 100% test reliability with no network │  │
│  └────────────────────────────────────────┴─────────────────────────────────────────┘  │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 Synthesized Lab Output                                 │
│  Authoritative answer with exact provenance citations [Ref 1], stoichiometric checks,  │
│  and direct links to underlying notebook entries and FPLC fractions.                  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📑 Protocol-Aware Semantic Chunker (`chunker.py`)

Generic text chunkers split documents at arbitrary token counts (e.g. 500 tokens), frequently severing multi-line reaction recipes, splitting pipetting tables, or separating centrifuge parameters from their steps. 

BioLabCalc implements a **Domain-Specific Laboratory Chunker**:
1. **Structural Boundary Respect**: Chunks respect Markdown headings, numbered protocol steps, and delimiter blocks.
2. **Table Preservation**: Multi-column reagent recipes and plate maps are preserved as intact units.
3. **Biological Entity Extraction (`LaboratoryEntityExtractor`)**: Ingestion automatically extracts normalized scientific entities into metadata tags:
   * **Constructs & Plasmids**: `pET-28a`, `pGEX-6P-1`, `pUC19`, `pBAD`.
   * **Chromatography Resins & Columns**: `HisTrap HP 5 mL`, `Superdex 200 Increase 10/300 GL`, `Mono Q`.
   * **Reagents & Buffers**: `50 mM Tris-HCl`, `500 mM Imidazole`, `1 mM DTT`, `10X PBS`.
   * **Quantitative Metrics**: Elution volumes ($V_e = 14.5\text{ mL}$), total yields ($19.25\text{ mg}$), and purity ($94.2\%$).
4. **Comprehensive Provenance Tags (`ProvenanceMetadata`)**: Each chunk retains the author ID, author name, project tag, campaign ID, day number, instrument run ID, and file path.

---

## 🔍 Hybrid Retrieval Engine (`hybrid_search.py`)

Pure dense vector search frequently fails on exact scientific identifiers (such as catalog numbers, plasmid names like `pET-28a-T7-K12A`, or buffer concentrations). Pure lexical search (BM25) fails when the user asks conceptual or biophysical questions ("How do I prevent column fouling during cell lysis?").

BioLabCalc resolves this via **Dense-Sparse Hybrid Retrieval with Reciprocal Rank Fusion**:

$$RRF(d) = \sum_{m \in \{\text{dense}, \text{sparse}\}} \frac{1}{k + r_m(d)}$$

where $k = 60$ is the standard smoothing parameter, and $r_m(d)$ is the 1-based rank of chunk $d$ in retrieval method $m$.

### Search Engine Capabilities:
* **Lexical Inverted Index (BM25)**: Matches exact keywords, primer sequences, and catalog codes with term-frequency saturation.
* **Dense Vector Indexing**: Evaluates conceptual similarity using 1536-dimensional embeddings.
* **Biological Entity Boost**: Chunks containing exact matches for detected constructs or enzymes receive an automated score boost.
* **Alumni & Temporal Provenance Filtering**: Enables filtering queries to active researchers vs. historical alumni records (e.g., retrieving only protocols validated within the last 12 months).

---

## 🔒 Offline Local LLM Integration (`local_llm.py`)

The local inference client provides zero-dependency connectivity to local open-weights language models:

```python
from biolabcalc.eln.rag.local_llm import LocalLLMClient

# Connect to local Ollama server running Llama-3 or Mistral
client = LocalLLMClient(
    base_url="http://localhost:11434",
    model_name="llama3:latest",
)

response = client.generate(
    prompt="Summarize the lysis buffer composition for Campaign CMP-2026-T7.",
    system="You are an expert bioprocess laboratory assistant. Cite all references.",
)
```

### Supported On-Premise Backends:
* **Ollama**: Default local desktop and workstation server (`http://localhost:11434`).
* **vLLM / OpenClaw / LocalAI**: High-throughput GPU inference servers running quantized GGUF, AWQ, or FP16 models.
* **HPC / SLURM Head-Nodes**: Direct HTTP endpoint forwarding to institutional supercomputing clusters.

### Air-Gapped Fallback Architecture:
When running on minimal machines without GPU hardware or network access to an Ollama server, the client automatically falls back to:
1. **`OfflineEmbeddingGenerator`**: A deterministic hashing engine that maps text n-grams and scientific tokens to a unit hypersphere vector space, enabling full unit testing and basic vector search without PyTorch or CUDA.
2. **`OfflineHeuristicGenerator`**: A rule-based biochemical reasoning engine that extracts metrics ($V_e$, yields, buffers) from retrieved context blocks and formats authoritative responses citing `[Ref 1]`, `[Ref 2]`.

---

## 💡 RAG Synthesizer & Laboratory Capabilities (`synthesizer.py`)

The `ContextualSynthesizer` coordinates the complete RAG loop, generating answers with verifiable citation footnotes.

### Key Use Cases:

#### 1. Protocol Querying & Historical Methodology
* *Query*: "What was the optimal wash volume and imidazole concentration used for the HisTrap step in Campaign 001?"
* *Response*: Summarizes the 10 column-volume (CV) wash at 25 mM imidazole and elution at 250 mM imidazole, appending a direct reference link to `[Ref 1]` (Day 4 Notebook Entry by Alice).

#### 2. Troubleshooting & Failure Diagnostics
* *Query*: "Why did the Day 3 induction yield drop to 2.1 mg/L culture in the GFP campaign?"
* *Response*: Analyzes the kinetic timepoint logs and notes that the incubator temperature drifted to 41.2°C for 45 minutes due to a sensor malfunction, leading to inclusion body formation.

#### 3. Stoichiometric & Buffer Verification
* *Query*: "Check the calculations for scaling the lysis buffer from 500 mL to 4 Liters."
* *Response*: Cross-references `biolabcalc.buffers` and validates that Tris-HCl, NaCl, and Triton X-100 quantities scale linearly while warning that DTT must be added fresh immediately prior to lysis.

---

## 🔗 Related Documentation
* [Electronic Lab Notebook (ELN)](Electronic-Lab-Notebook-(ELN)) — Launching the global RAG modal via the web UI (⌘K).
* [Instrument Data Parsers](Instrument-Data-Parsers) — How analytical outputs are extracted for vector indexing.
* [GxP Compliance & Audit Trails](GxP-Compliance-&-Audit-Trails) — Audit logging for AI-assisted protocol adjustments.
