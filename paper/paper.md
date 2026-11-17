---
title: 'BioLabCalc: A Pure-Python Molecular Biology, Biophysics, and Laboratory Automation Engine'
tags:
  - Python
  - molecular biology
  - biophysics
  - cloning
  - laboratory automation
  - electronic lab notebook
authors:
  - name: Kabeer
    orcid: 0000-0000-0000-0000
    affiliation: 1
affiliations:
  - name: Core Maintainer & Lead Architect, BioLabCalc Project
    index: 1
date: 17 November 2026
bibliography: paper.bib
---

# Summary

Molecular biology and biochemical research depend heavily on routine calculations: stoichiometry, in vitro transcription kinetics, PCR amplicon yield, restriction digestion, buffer equilibrium, and high-throughput liquid handling. However, existing computational utilities are fragmented across proprietary vendor websites, unmaintained scripts, or heavyweight monolithic bioinformatics packages with complex binary C-extensions.

`BioLabCalc` is a pure-Python molecular biology and biophysical calculation suite engineered with **zero mandatory external dependencies**. Adhering strictly to pure functional immutability principles, `BioLabCalc` provides 45 Command-Line Interface (CLI) tools, interactive browser-based SVG visualizers, rich Jupyter notebook integration (`_repr_html_`, `_repr_svg_`), an Electronic Lab Notebook (ELN) and LIMS service, and high-throughput 96/384-well microplate automation protocols for Labcyte Echo, Opentrons, and PyLabRobot.

# Statement of Need

Modern biological labs require computational tooling that is deterministic, reproducible, auditable, and easily deployable across air-gapped workstations, cloud CI runners, and robotic liquid handlers without dependency conflicts. 

Common tools often suffer from three critical flaws:
1. **Dependency Hell and Fragility**: Requiring compilation of C/Fortran libraries or specific NumPy/SciPy ABI versions, complicating installation on heterogeneous lab computers.
2. **Coordinate and Modulo Confusion**: Standard 0-based Python indexing frequently introduces off-by-one errors when processing 1-based biological coordinates or circular plasmid origins where genomic features cross the zero-base boundary ($L \to 1$).
3. **State Mutation**: In-place mutation of sequence objects and calculation buffers hinders concurrent pipelines and distributed execution.

`BioLabCalc` resolves these issues by implementing a self-contained, mathematically rigorous computational foundation written in 100% pure Python standard library.

# Core Architecture & Invariants

Every module and data model in `BioLabCalc` obeys six non-negotiable architectural invariants:

1. **Functional Immutability**: All domain entities and calculation results are defined as frozen dataclasses (`@dataclass(frozen=True)`). Updates are performed purely via immutable replacements (`dataclasses.replace`).
2. **Immutable Collections**: Sequence attributes and collection fields within data models are stored as immutable `Tuple[...]` instances rather than mutable lists or sets.
3. **Zero-Dependency Stdlib Core**: The default core installation requires zero third-party packages (`dependencies = []`). Advanced capabilities (Excel export, matplotlib gels, FastAPI ELN servers) reside strictly within optional extras with graceful fallback handlers.
4. **1-Based Inclusive Coordinates**: Coordinates across all sequence annotations, restriction cleavage sites, and plasmid maps follow 1-based inclusive indexing ($1 .. L$). Origin-spanning circular plasmid features ($start > end$) are computed with exact modulo arithmetic: length is $(L - start + 1) + end$.
5. **Cross-Platform Handle Safety**: File interactions avoid hardcoded POSIX `/tmp` paths and explicitly release all file handles and temporary files, guaranteeing zero `WinError 32` file locks on Windows.
6. **Atomic Persistence**: JSON databases and local record stores are written atomically using sibling temporary files, POSIX `fsync`, and atomic directory replacement (`os.replace`).

# Key Modules & Scientific Capabilities

`BioLabCalc` consolidates advanced biophysical and molecular calculations:

- **Multi-Metal Competitive Buffer Speciation**: Implements a pure-Python Newton-Raphson log-space solver evaluating non-linear mass balances with Davies ionic-strength activity corrections and temperature drift ($d\text{p}K_a/dT$), resolving simultaneous competitive equilibria for $\text{Mg}^{2+}$, $\text{Ca}^{2+}$, $\text{ATP}^{4-}$, $\text{EGTA}^{4-}$, and $\text{EDTA}^{4-}$.
- **Aptamer Thermodynamics & Counter-SELEX**: Computes RNA secondary structure folding free energies using the Turner (2004) nearest-neighbor thermodynamic parameters [@Turner2004] and models subunit-selective aptamer enrichment via Dirichlet-smoothed Counter-SELEX with Benjamini-Hochberg False Discovery Rate control.
- **Deterministic Allosteric Pathway Tracing**: Uses the Gaussian Network Model (GNM) Kirchhoff Laplacian matrix [@Bahar1997] and Perturbation Response Scanning (PRS) [@Atilgan2010] to identify allosteric communication bottlenecks and auto-generate site-directed mutagenesis primers.
- **Thermodynamic Oligonucleotide Alignments**: Evaluates self-dimer, heterodimer, and hairpin secondary structures using SantaLucia nearest-neighbor thermodynamics [@SantaLucia1998] with full ASCII alignment displays.
- **Type IIS Golden Gate Assembly**: Models 4-bp cohesive overhang fidelity, palindromic self-ligation risk, and reverse-complement collisions based on comprehensive T4 DNA ligase profiling [@Potapov2018].
- **Sequence Interoperability**: Provides native binary decoders for SnapGene (`.dna`) packets, Applied Biosystems ABIF Sanger sequencing chromatograms (`.ab1`), and ELN Consortium RO-Crate research archives (`.eln`) [@SoilandReyes2022].
- **Microplate Automation**: Designs 96-well and 384-well serial dilution grids and PCR master mix layouts, directly compiling ready-to-run protocols for Labcyte Echo acoustic liquid handlers, Opentrons OT-2/Flex platforms, and PyLabRobot.

# Availability and Verification

`BioLabCalc` is licensed under the MIT License and hosted on GitHub (`https://github.com/kabe89/BioLabCalc`). The test suite comprises over 520 automated unit tests executed across Ubuntu and Windows runners under Python 3.8 through 3.12. Complete documentation, tutorials, and interactive demonstrations are accessible via the GitHub repository and wiki.

# References
