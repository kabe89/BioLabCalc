# Plasmid Engineering & In-Silico Restriction Workbench

The **BioLabCalc v0.4.0** plasmid engineering suite introduces comprehensive, offline-first synthetic biology capabilities for designing expression constructs, simulating enzymatic restriction digestion, and visualizing circular plasmids in an interactive, responsive Elm Architecture (TEA) workbench.

---

## 📖 Table of Contents

- [Overview & Architectural Philosophy](#overview--architectural-philosophy)
- [Biological Sequence Storage & Catalog (`biolabcalc.sequence_store`)](#biological-sequence-storage--catalog)
- [Circular Plasmid Representation & GenBank I/O (`biolabcalc.plasmid`)](#circular-plasmid-representation--genbank-io)
- [In-Silico Restriction Digestion & Virtual Gels (`biolabcalc.restriction_engine`)](#in-silico-restriction-digestion--virtual-gels)
- [Automated Expression Plasmid Engineering (`biolabcalc.plasmid_engineering`)](#automated-expression-plasmid-engineering)
- [The Elm Architecture (TEA) State Runtime (`biolabcalc.tea_runtime`)](#the-elm-architecture-tea-state-runtime)
- [Interactive HTML5/SVG Plasmid Workbench (`biolabcalc.interactive_plasmid`)](#interactive-html5svg-plasmid-workbench)
- [Command-Line Interface (CLI) Usage](#command-line-interface-cli-usage)
- [Python API Code Examples](#python-api-code-examples)

---

## Overview & Architectural Philosophy

Molecular cloning workflows require exact sequence manipulation, circular coordinate tracking, and restriction fragment verification. BioLabCalc v0.4.0 implements these operations following strict biochemical conventions:

1. **Strict Immutability:** Every domain entity (`SequenceRecord`, `PlasmidRecord`, `PlasmidFeature`, `DigestionPrediction`, `EngineeredPlasmidResult`) is implemented as an immutable `@dataclass(frozen=True)` with tuple collections.
2. **1-Based Inclusive Coordinates:** All sequence positions adhere to GenBank and SnapGene standard 1-based indexing ($1 \le \text{pos} \le L$).
3. **Origin-Spanning Circular Features:** In a circular plasmid of length $L$, features crossing the origin have $\text{start} > \text{end}$. Feature length is calculated as:
   $$\text{Length} = (L - \text{start} + 1) + \text{end}$$
4. **Exact Overhang Phosphodiester Tracking:** Cleavage offsets for top-strand ($5' \to 3'$) and bottom-strand ($3' \to 5'$) phosphodiesters are tracked independently. Cohesive overhang sequences are dynamically extracted from the cleaved DNA sequence itself, essential for degenerate IUPAC enzymes (e.g., SfiI) and Type IIS enzymes (e.g., BsaI, BsmBI, SapI).
5. **Deterministic State Transitions:** The Elm Architecture (`Model`, `Msg`, `update`, `view`, `Cmd`) guarantees reproducible state management and reversible time-travel history without side effects.

---

## Biological Sequence Storage & Catalog

Module: `biolabcalc.sequence_store`

### Core Data Structures
- **`SequenceAnnotation`**: Feature name, feature type (e.g., `promoter`, `CDS`, `tag`), 1-based coordinates `[start .. end]`, strand ($+1$ or $-1$), and optional notes.
- **`SequenceRecord`**: Unique ID, name, sequence string, sequence type (`dna`, `rna`, `protein`), topology (`linear`, `circular`, `dsdna`), automatic SHA-256 checksum (first 16 hex characters), sequence length, GC percentage, and exact biophysical molecular weight in Daltons.

### Pre-Seeded Reference Sequences
BioLabCalc includes a default catalog of verified public-domain reference sequences:
- `T7_PROMOTER` (20 bp): Bacteriophage T7 RNA Polymerase Promoter (-17 to +3)
- `SP6_PROMOTER` (23 bp): Bacteriophage SP6 RNA Polymerase Promoter
- `T3_PROMOTER` (20 bp): Bacteriophage T3 RNA Polymerase Promoter
- `GLUK2_EXON1_AMPLICON` (120 bp): Diagnostic PCR amplicon for human GRIK2 exon 1
- `GLUA1_LBD_CDS` (753 bp): Ligand-binding domain (S1S2) coding sequence of human GRIA1
- `AB9SR_APTAMER` (79 nt): High-affinity synthetic RNA aptamer
- `EGFP_CDS` (720 bp): Enhanced Green Fluorescent Protein reporter gene
- `HIS6_TEV_TAG` (39 bp): Hexahistidine affinity tag fused to a TEV protease cleavage site
- `KANR_CDS` (816 bp): Kanamycin / neomycin resistance gene (aphA-3)
- `AMPR_CDS` (861 bp): Ampicillin resistance gene (beta-lactamase, bla)

### Persistence & FASTA I/O
- `save_sequence(record, filepath=None)`: Atomically persists sequences to `~/.biolabcalc/sequences.json`.
- `get_sequence(id_or_name, filepath=None)`: Retrieves record by identifier or display name.
- `import_fasta(text_or_path, seq_type="dna")`: Parses standard single or multi-record FASTA files into immutable `SequenceRecord` objects.
- `export_fasta(records, filepath=None)`: Serializes records into standard FASTA format with 70-character line wrapping.

---

## Circular Plasmid Representation & GenBank I/O

Module: `biolabcalc.plasmid`

### Plasmid Features & Coordinates
- **`PlasmidFeature`**: Represents annotations on circular DNA. Supports forward strand ($+1$) and reverse strand ($-1$), customizable hex display colors, and circular origin wrapping.
- **`PlasmidRecord`**: Represents the complete circular plasmid. Calculates GC content, double-stranded molecular weight (using standard $650\text{ Da/bp}$ or base-exact composition), and feature distributions.

### Coordinate & Slicing Operations
- **`extract_subsequence(plasmid, start, end, strand=1)`**: Extracts linear subsequence across 1-based coordinates. Correctly handles circular wrap when $\text{start} > \text{end}$ by concatenating segment $[\text{start} \dots L]$ with $[1 \dots \text{end}]$.
- **`rotate_origin(plasmid, new_origin_1based)`**: Rotates the physical base 1 coordinate of the circular plasmid to any arbitrary index. Recalculates all feature start and end coordinates with modulo-$L$ invariance.
- **`insert_subsequence(plasmid, index_1based, insert_seq, replace_end_1based=None)`**: Inserts or replaces DNA fragments, adjusting all downstream feature coordinates and expanding origin-spanning features.
- **`find_orfs(plasmid_or_seq, min_aa=50, circular=True)`**: Discovers open reading frames across all 6 reading frames, tracking ORFs that cross the circular origin boundary.

### Standard Plasmid Catalog
- **`pUC19`** (2,686 bp): Complete sequence with annotated ColE1/pUC origin, beta-lactamase (`AmpR`), lac promoter, and multiple cloning site (MCS).
- **`pET-28a(+)`**: Bacterial T7 expression cassette with N-terminal 6xHis-Thrombin-T7 tag, MCS, and C-terminal 6xHis tag.
- **`pcDNA3.1(+)`**: Mammalian expression cassette with human cytomegalovirus (CMV) promoter, BGH polyadenylation signal, and f1 origin.
- **`pGoldenGate-Dest`**: Synthetic destination vector with flanking outward-facing BsaI sites for Golden Gate Type IIS assembly.

### GenBank Flatfile Parsing & Export
- `parse_genbank(gb_text_or_path)`: Full parser extracting `LOCUS`, `DEFINITION`, `ACCESSION`, `ORIGIN`, and `FEATURES` table into a native `PlasmidRecord`.
- `export_genbank(plasmid, filepath=None)`: Exports complete GenBank-compliant flatfiles, with origin-spanning features formatted as `join(start..L, 1..end)`.

---

## In-Silico Restriction Digestion & Virtual Gels

Module: `biolabcalc.restriction_engine`

### Cleavage Mechanics
Restriction enzymes cleave top and bottom strands at distinct phosphodiester offsets relative to their recognition sequence:
- **Type II Palindromic Enzymes**: E.g., EcoRI recognizes `G^AATTC` (cleavage top = 1, bottom = 5), leaving a $5'$ cohesive overhang `AATT`. SmaI recognizes `CCC^GGG` (cleavage top = 3, bottom = 3), leaving blunt ends.
- **Type IIS Asymmetric Enzymes**: E.g., BsaI recognizes `GGTCTC(N1/N5)`, cleaving outside its recognition site (cut top = 7, bottom = 11) to yield an arbitrary 4-bp sticky overhang.

### Digestion Simulation Engine
- `simulate_restriction_digest(plasmid, enzymes, complete=True)`: Simulates complete single, double, or multiplex digestion setups.
  - Generates `DigestionPrediction` containing fragment lengths, start/end coordinates, and exact 5' and 3' terminal overhang sequences.
  - Calculates fragment molecular weights and relative stoichiometric abundance.
  - Accounts for circular plasmid linearization (1 cut site = 1 linear fragment of length $L$) and multiple cut sites ($N$ cut sites = $N$ fragments whose lengths sum to $L$).
- `digest_matches_gel(predicted_bands, observed_bands, tolerance_bp=50)`: Compares predicted in-silico fragments with wet-lab experimental agarose gel bands, scoring migration consistency.

### Virtual Agarose Gel Electrophoresis
- `generate_virtual_gel_ascii(prediction, ladder_key="dna_1kb_plus")`: Generates high-resolution terminal ASCII diagrams simulating agarose gel band migration and relative fluorescence intensity.
- `render_virtual_gel_svg(predictions_by_lane, ladder_key="dna_1kb_plus")`: Generates publication-quality scalable vector graphics (SVG) virtual gel representations with calibrated log-linear band dispersion.

---

## Automated Expression Plasmid Engineering

Module: `biolabcalc.plasmid_engineering`

Automates the complete design of expression plasmids for protein production or mammalian transfection:

### Assembly Modes
1. **Directional Restriction-Ligation**: Inserts target CDS between two compatible unique restriction sites in the MCS (e.g., BamHI + XhoI in pET-28a).
2. **Gibson / Isothermal Assembly**: Inserts target fragment with 25–40 bp vector homology overhangs for exonuclease-polymerase-ligase assembly.
3. **Golden Gate Assembly (Type IIS)**: Inserts target CDS into destination vectors using BsaI, BsmBI, or PaqCI, with customizable 4-bp overhangs.

### Reading Frame Synchronization & Auto-Padding
Ensures the target open reading frame stays strictly in-frame with N-terminal affinity tags (e.g., 6xHis, TEV, FLAG):
- Calculates translation frame offset:
  $$\Delta_{\text{frame}} = (\text{insertion\_index} - \text{tag\_frame\_origin}) \pmod 3$$
- Automatically introduces non-disruptive padding nucleotides (e.g., `GC` or `A`) into PCR primer overhangs when $\Delta_{\text{frame}} \ne 0$.

### Silent Restriction Domestication
If an insert contains internal recognition sites for cloning enzymes (e.g., an internal BsaI site in Golden Gate assembly), `domesticate_restriction_sites` introduces synonymous codon mutations:
- Identifies conflicting motifs on both sense and antisense strands.
- Substitutes rare or motif-causing codons with preferred synonymous host codons (E. coli or human) without changing the translated amino acid sequence.

### 7-Point Vector Quality Audit
Before outputting any engineered construct, the engine executes a comprehensive 7-point quality audit:
1. **In-Frame Verification**: Confirms insertion maintains continuous reading frame from initiator ATG through stop codon.
2. **Start Codon Integrity**: Verifies presence of canonical initiator codon.
3. **Stop Codon Integrity**: Verifies termination codon (TAA, TAG, TGA).
4. **Premature Termination Check**: Verifies zero internal in-frame stop codons.
5. **RBS / Kozak Alignment**: Confirms Shine-Dalgarno or Kozak spacing is optimal (5–9 nt to ATG).
6. **Origin of Replication Intact**: Confirms ColE1/pUC/f1 origin is completely unaltered.
7. **Selection Marker Intact**: Confirms antibiotic resistance CDS is functional.

---

## The Elm Architecture (TEA) State Runtime

Module: `biolabcalc.tea_runtime`

The Elm Architecture (TEA) provides a purely functional state engine for interactive workbench applications:

```text
               +-----------------------+
               |                       |
               |      User Action      |
               |                       |
               +-----------+-----------+
                           |
                           v
               +-----------------------+
               |                       |
               |       Msg (Union)     |
               |                       |
               +-----------+-----------+
                           |
                           v
+--------------+       +-----------------------+
|              |       |                       |
|  Old Model   +------>+   update(msg, model)  +------> (New Model, Cmd)
|              |       |                       |
+--------------+       +-----------+-----------+
                                   |
                                   v
                       +-----------------------+
                       |                       |
                       |      view(model)      |
                       |                       |
                       +-----------+-----------+
                                   |
                                   v
                       +-----------------------+
                       |   Markdown / SVG /    |
                       |    Interactive HTML   |
                       +-----------------------+
```

### Core Components
- **`BioLabModel`**: Immutable snapshot containing loaded plasmid, selected restriction enzymes, active digestion prediction, engineered vector result, and time-travel history.
- **`Msg` Hierarchy**:
  - `LoadPlasmidMsg(plasmid_id, custom_plasmid)`
  - `SelectEnzymesMsg(enzyme_names)`
  - `RunDigestMsg()`
  - `InsertGeneMsg(gene_name, insert_seq, mode, enzyme_5prime, enzyme_3prime, tag)`
  - `RotateOriginMsg(new_origin)`
  - `UndoMsg()` and `RedoMsg()`
- **`update(msg, model) -> Tuple[BioLabModel, Cmd]`**: Pure state transition function returning new model and external command.
- **`view(model) -> str`**: Pure renderer generating structured Markdown and SVG visualization.

---

## Interactive HTML5/SVG Plasmid Workbench

Module: `biolabcalc.interactive_plasmid`

Generates zero-dependency standalone HTML5/SVG web applications:
- **Circular Plasmid Map**: Scalable vector graphics (SVG) with color-coded feature arcs, directional gene arrows, restriction site ticks, and origin marker.
- **Virtual Gel Lane Simulation**: Live simulated agarose gel lane calibrated against standard 1 kb Plus DNA ladders.
- **Dynamic Tooltips & Inspection**: Hover over any feature or restriction site to inspect coordinates, amino acid translation, and cleavage overhang details.
- **Export Capabilities**: Download engineered plasmid maps as SVG, GenBank flatfiles (`.gb`), or FASTA files directly from the browser.

---

## Command-Line Interface (CLI) Usage

BioLabCalc v0.4.0 exposes unified subcommands for all plasmid and restriction capabilities:

### 1. Sequence Management (`sequence`)
```bash
# List all pre-seeded and custom sequences
biolabcalc sequence --list

# Inspect a sequence by ID
biolabcalc sequence --get EGFP_CDS

# Import a sequence from a FASTA file
biolabcalc sequence --import-fasta my_insert.fasta --type dna
```

### 2. Plasmid Catalog & GenBank I/O (`plasmid`)
```bash
# List standard plasmid catalog
biolabcalc plasmid --list

# Inspect pUC19 features and restriction sites
biolabcalc plasmid --get pUC19 --info

# Export plasmid to GenBank format
biolabcalc plasmid --get pET-28a(+) --export-gb pet28a.gb

# Import custom plasmid from GenBank file
biolabcalc plasmid --import-gb my_vector.gb
```

### 3. In-Silico Restriction Digestion (`digest`)
```bash
# Digest pUC19 with EcoRI and HindIII
biolabcalc digest --plasmid pUC19 --enzymes EcoRI HindIII

# Display ASCII virtual agarose gel
biolabcalc digest --plasmid pUC19 --enzymes EcoRI BamHI --simulate-gel
```

### 4. Automated Plasmid Engineering (`engineer-plasmid`)
```bash
# Directional cloning of EGFP into pET-28a(+) via BamHI and XhoI
biolabcalc engineer-plasmid \
  --vector "pET-28a(+)" \
  --insert-seq "ATGGTGAGCAAGGGCGAGGAGCTG..." \
  --gene-name "EGFP" \
  --mode restriction_ligation \
  --e5 BamHI \
  --e3 XhoI \
  --tag "6xHis"

# Output engineered GenBank file directly
biolabcalc engineer-plasmid \
  --vector "pET-28a(+)" \
  --insert-seq "ATGGTGAGCAAGGGCGAGGAGCTG..." \
  --output-gb "pET28a-EGFP.gb"
```

### 5. Interactive Plasmid Workbench (`plasmid-workbench`)
```bash
# Export standalone HTML5/SVG workbench for pUC19
biolabcalc plasmid-workbench --plasmid pUC19 --output pUC19_workbench.html

# Launch workbench in local browser
biolabcalc plasmid-workbench --plasmid "pET-28a(+)" --open-browser
```

---

## Python API Code Examples

### Example 1: Restriction Digestion & Gel Simulation
```python
from biolabcalc.plasmid import get_plasmid
from biolabcalc.restriction_engine import simulate_restriction_digest, generate_virtual_gel_ascii

# Load pUC19 from catalog
puc19 = get_plasmid("pUC19")

# Simulate double digestion with EcoRI and PstI
prediction = simulate_restriction_digest(puc19, ["EcoRI", "PstI"])

print(f"Fragments generated: {prediction.fragment_count}")
for frag in prediction.fragments:
    print(f"  - Length: {frag.length_bp} bp | Coordinates: {frag.start}..{frag.end}")

# Print terminal ASCII virtual gel
print(generate_virtual_gel_ascii(prediction))
```

### Example 2: Directional Expression Plasmid Engineering
```python
from biolabcalc.plasmid_engineering import engineer_plasmid
from biolabcalc.sequence_store import get_sequence

# Retrieve EGFP coding sequence
egfp = get_sequence("EGFP_CDS")

# Assemble into pET-28a(+) with frame synchronization
result = engineer_plasmid(
    vector="pET-28a(+)",
    insert_seq=egfp.sequence,
    gene_name="EGFP",
    mode="restriction_ligation",
    enzyme_5prime="BamHI",
    enzyme_3prime="XhoI",
    auto_domesticate=True,
)

print(f"Cloning Mode: {result.mode}")
print(f"Reading Frame Synchronized: {result.in_frame}")
print(f"Forward Primer: {result.forward_primer_full_seq}")
print(f"Reverse Primer: {result.reverse_primer_full_seq}")
print(f"Predicted Yield: {result.predicted_expression_yield_mg_l:.1f} mg/L culture")
```

### Example 3: TEA State Engine Execution
```python
from biolabcalc.tea_runtime import init, update, LoadPlasmidMsg, RunDigestMsg, view

# Initialize TEA runtime model
model, cmd = init("pUC19")

# Update model with digestion message
model, cmd = update(RunDigestMsg(), model)

# Render Markdown view of current state
print(view(model))
```
