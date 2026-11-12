# Python API Reference

BioLabCalc provides a modular Python API for computational molecular biology, stoichiometry, reaction kinetics, and laboratory reporting.

```python
# Primary top-level module
import biolabcalc as blc

# High-level convenience module with flexible unit parsing
import biolabcalc.easy as easy
```

---

## 1. Convenience Module (`biolabcalc.easy`)

The `biolabcalc.easy` module provides single-function entry points designed for interactive terminal sessions, Jupyter notebooks, and quick scripts. It supports both raw floats and human-readable strings with unit suffixes (e.g., `'500 uL'`, `'25 mM'`, `'1.5 ug'`).

### `easy.dilute`

Solves $C_1 V_1 = C_2 V_2$ for any single missing parameter. Exactly one argument must be omitted or passed as `None`.

```python
def dilute(
    c1: Optional[Union[str, float]] = None,
    v1: Optional[Union[str, float]] = None,
    c2: Optional[Union[str, float]] = None,
    v2: Optional[Union[str, float]] = None,
) -> Dict[str, float]
```

- **Returns**: Dictionary containing resolved `c1`, `v1`, `c2`, `v2`, and `diluent_needed` (in consistent units: concentration in $\text{mM}$ or $\text{mg/mL}$, volumes in $\mu\text{L}$).
- **Example**:
  ```python
  from biolabcalc.easy import dilute
  res = dilute(c1="100 mM", c2="25 mM", v2="16 mL")
  print(f"Pipette {res['v1']/1000} mL stock and {res['diluent_needed']/1000} mL buffer.")
  ```

### `easy.ntp_mix`

Prepares and neutralizes equimolar or individual NTP working solutions from disodium or free acid stocks.

```python
def ntp_mix(
    initial_volume: Union[str, float] = "4.0 mL",
    initial_conc: Union[str, float] = "100.0 mM",
    target_volume: Union[str, float] = "16.0 mL",
    target_conc: Optional[Union[str, float]] = "25.0 mM",
    target_ph: float = 7.5,
    starting_form: str = "disodium_salt",
    species: str = "equimolar_mix",
    naoh_stock: Union[str, float] = "5.0 M",
) -> NTPNeutralizationResult
```

### `easy.primer`

Performs thermodynamic analysis on a single oligonucleotide primer, including melting temperature ($T_m$), GC content, $3'$ GC clamp count, hairpin formation, and self-dimerization risks.

```python
def primer(
    sequence: str,
    primer_conc: Union[str, float] = "400 nM",
    mg_conc: Union[str, float] = "1.5 mM"
) -> PrimerAnalysis
```

### `easy.ivt`

Calculates *in vitro* transcription stoichiometry, limiting reagents, transcript turnover ratios, and pyrophosphate release.

```python
def ivt(
    rna_sequence: str,
    reaction_volume: Union[str, float] = "20 uL",
    measured_yield: Optional[Union[str, float]] = None,
    target_yield: Optional[Union[str, float]] = "50 ug",
) -> IVTResult
```

### `easy.buffer`

Generates volume-scaled chemical formulation recipes for standard laboratory buffers (e.g., `'10X_PBS'`, `'50X_TAE'`, `'10X_TBE'`).

```python
def buffer(
    name: str,
    volume: Union[str, float] = "1000 mL"
) -> BufferRecipeResult
```

### `easy.golden_gate`

Plans Type IIS restriction-ligation assembly reactions (Golden Gate), generating stoichiometric mass ratios and thermocycling schedules.

```python
def golden_gate(
    vector_bp: int,
    insert_bps: List[int],
    target_fmol: float = 20.0,
    enzyme: str = "BsaI-HFv2",
    ratio: float = 2.0,
) -> GoldenGateResult
```

### `easy.phenol_chloroform`

Formulates Phenol:Chloroform:Isoamyl alcohol extraction protocols and identifies phase partitioning behavior based on target nucleic acid type.

```python
def phenol_chloroform(
    sample_volume: Union[str, float],
    nucleic_acid: str = "rna",
    phenol_ph: Optional[float] = None,
) -> PhenolChloroformProtocol
```

### `easy.nanodrop_purity`

Evaluates $A_{260}$, $A_{280}$, and $A_{230}$ absorbance readings for chemical contaminants (phenol, chaotropic salts, proteins, ethanol) and computes turbidity-corrected concentrations.

```python
def nanodrop_purity(
    a260: float,
    a280: float,
    a230: float,
    sample_type: str = "rna",
) -> NanoDropPurityResult
```

### `easy.hepes_buffer`

Calculates chemical formulation for concentrated (10X or 5X) HEPES-KOH IVT buffers, automatically applying temperature compensation for $\Delta\text{p}K_a/\Delta T$.

```python
def hepes_buffer(
    volume: Union[str, float] = "50 mL",
    stock: int = 10,
    target_ph: float = 7.50,
) -> HepesIVTBufferResult
```

### `easy.ivt_time`

Calculates the kinetic synthesis trajectory and optimal incubation window for *in vitro* transcription reactions.

```python
def ivt_time(
    length_nt: int,
    temp_c: float = 37.0,
    ipp: bool = True,
) -> TranscriptionTimeOptimizationResult
```

### `easy.rna_mw`

Computes molecular weight for synthetic or modified RNA with customized $5'$, $3'$, and backbone linkages.

```python
def rna_mw(
    sequence: str,
    end_5: str = "triphosphate",
    end_3: str = "hydroxyl",
    backbone: str = "monophosphate",
) -> MolecularWeightResult
```

### `easy.western`

Generates an experimental plan for Western blot analysis (gel percentage, transfer parameters, lysate loading recipes, and primary/secondary antibody dilutions).

```python
def western(
    protein_name: str,
    mw_kda: float,
    is_phospho: bool = False,
    is_membrane: bool = False,
    transfer: str = "wet_tank",
    membrane: str = "pvdf",
) -> WesternBlotPlanResult
```

### `easy.wb_transfer`

Calculates electrotransfer voltage/current, membrane pore size, and duration based on target molecular weight.

```python
def wb_transfer(
    mw_kda: float,
    system: str = "wet_tank",
    membrane: str = "pvdf",
) -> TransferConditionsResult
```

### `easy.wb_loading`

Calculates lysate volume, $4\text{X}$ sample loading buffer, and reducing agent requirements per well.

```python
def wb_loading(
    lysate_conc: Union[str, float] = "2.5 mg/mL",
    target_ug: float = 20.0,
    num_lanes: int = 10,
    is_membrane: bool = False,
) -> LysateLoadingResult
```

### `easy.wb_troubleshoot`

Diagnoses Western blot artifacts (e.g., `'ghost_bands'`, `'high_background'`, `'no_signal'`) and recommends corrective actions.

```python
def wb_troubleshoot(symptom: str) -> WesternTroubleshootingResult
```

### `easy.new_report`, `easy.record`, and `easy.export_report`

Session-based laboratory notebook and QC measurement logging:

```python
def new_report(
    title: str = "Laboratory Experiment Report",
    experimenter: str = "Researcher",
    project: str = "General",
    objective: str = "",
) -> LabReport

def record(
    sample_id: str,
    parameter: str,
    value: float,
    unit: str,
    target: Optional[float] = None,
    tolerance_pct: Optional[float] = None,
    notes: str = "",
) -> MeasurementRecord

def export_report(filepath: str, title: Optional[str] = None) -> str
```

---

## 2. Top-Level Core Functions (`biolabcalc`)

### Sequence Utilities (`biolabcalc.seq_utils`)

```python
clean_sequence(seq: str) -> str
validate_sequence(seq: str, seq_type: str = "dna") -> bool
reverse_complement(seq: str, seq_type: str = "dna") -> str
calculate_gc_content(seq: str) -> float
count_bases(seq: str) -> Dict[str, int]
translate_dna(seq: str, reading_frame: int = 1) -> str
```

### Molecular Weight & Conversions (`biolabcalc.molecular_weight`)

```python
calculate_dna_mw(
    seq: str,
    double_stranded: bool = False,
    end_5: Literal["hydroxyl", "monophosphate", "triphosphate"] = "hydroxyl",
    circular: bool = False
) -> MolecularWeightResult

calculate_rna_mw(
    seq: str,
    end_5: Literal["triphosphate", "monophosphate", "hydroxyl", "cap0", "cap1"] = "triphosphate",
    end_3: Literal["hydroxyl", "monophosphate", "diphosphate", "triphosphate", "cyclic_phosphate"] = "hydroxyl",
    backbone: Literal["monophosphate", "phosphorothioate"] = "monophosphate",
    circular: bool = False
) -> MolecularWeightResult

calculate_protein_mw(seq: str) -> MolecularWeightResult

mass_to_moles(mass_g: float, mw_da: float) -> float
moles_to_mass(moles: float, mw_da: float) -> float
mass_to_copy_number(mass_g: float, mw_da: float) -> float
copy_number_to_mass(copies: float, mw_da: float) -> float
concentration_to_molarity(conc_g_l: float, mw_da: float) -> float
```

### *In Vitro* Transcription (`biolabcalc.transcription`)

```python
calculate_ivt_yield(
    rna_seq: str,
    reaction_volume_ul: float = 20.0,
    measured_yield_ug: Optional[float] = None,
    target_yield_ug: Optional[float] = None,
    atp_mm: float = 5.0,
    ctp_mm: float = 5.0,
    gtp_mm: float = 5.0,
    utp_mm: float = 5.0,
    mg_conc_mm: float = 20.0,
    use_pyrophosphatase: bool = True,
    template_dna_ng: Optional[float] = None,
    template_dna_length_bp: Optional[int] = None,
    auto_trim_promoter: bool = True,
    add_5prime_gg: int = 0,
    cap_analog: Optional[str] = None,
    modified_ntp: Optional[str] = None,
    end_5: Literal["triphosphate", "monophosphate", "hydroxyl", "cap0", "cap1"] = "triphosphate",
    end_3: Literal["hydroxyl", "monophosphate", "diphosphate", "triphosphate", "cyclic_phosphate"] = "hydroxyl",
    backbone: Literal["monophosphate", "phosphorothioate"] = "monophosphate",
    temperature_celsius: float = 37.0,
    buffer_type: str = "hepes"
) -> IVTResult

optimize_transcription_time(
    transcript_length_nt: int,
    temperature_celsius: float = 37.0,
    use_pyrophosphatase: bool = True
) -> TranscriptionTimeOptimizationResult

detect_and_trim_promoter(seq: str) -> Tuple[str, Optional[str], int]
evaluate_initiation_efficiency(initial_bases: str) -> InitiationAnalysis
```

### Polymerase Chain Reaction (`biolabcalc.pcr`)

```python
calculate_pcr_kinetics(
    amplicon_len_bp: int,
    template_ng: float,
    cycles: int = 30,
    reaction_volume_ul: float = 50.0,
    efficiency: float = 0.95,
    initial_dntp_mm: float = 0.2
) -> PCRResult

calculate_qpcr_efficiency(slope: float) -> Tuple[float, float]

build_master_mix(
    num_reactions: int,
    reaction_volume_ul: float = 50.0,
    buffer_conc: str = "5X",
    dntp_stock_mm: float = 10.0,
    dntp_final_mm: float = 0.2,
    fwd_primer_stock_um: float = 10.0,
    fwd_primer_final_um: float = 0.4,
    rev_primer_stock_um: float = 10.0,
    rev_primer_final_um: float = 0.4,
    poly_units_per_rxn: float = 1.0,
    poly_stock_units_per_ul: float = 2.0,
    template_volume_ul: float = 2.0,
    excess_percent: float = 10.0
) -> List[MasterMixItem]

optimize_pcr_protocol(
    primer_fwd_tm: float,
    primer_rev_tm: float,
    amplicon_len_bp: int,
    polymerase: str = "taq",
    gc_percent: float = 50.0
) -> PCROptimizationResult
```

### Protein Spectroscopy & Assays (`biolabcalc.protein`)

```python
calculate_extinction_coefficient(seq: str, oxidized_cysteines: int = 0) -> ExtinctionCoefficientResult

quantify_protein_a280(
    seq: str,
    a280_absorbance: float,
    volume_ml: float = 1.0,
    pathlength_cm: float = 1.0,
    dilution_factor: float = 1.0,
    oxidized_cysteines: int = 0,
    sample_name: str = "Sample"
) -> ProteinYieldResult

fit_standard_curve(
    standards: List[Tuple[float, float]],
    assay_type: str = "BCA"
) -> StandardCurveResult
```

### Primer Design & Thermodynamics (`biolabcalc.primers`)

```python
calculate_tm_santalucia(
    seq: str,
    primer_conc_nm: float = 400.0,
    na_conc_mm: float = 50.0,
    mg_conc_mm: float = 1.5,
    dntp_conc_mm: float = 0.8,
    is_excess_primer: bool = False
) -> Tuple[float, float, float, float]  # Tm, dH, dS, dG_37 (alias: calculate_tm_santaluicia)

analyze_primer(
    seq: str,
    primer_conc_nm: float = 400.0,
    na_conc_mm: float = 50.0,
    mg_conc_mm: float = 1.5,
    dntp_conc_mm: float = 0.8
) -> PrimerAnalysis

design_primers(
    template_seq: str,
    target_tm: float = 60.0,
    min_tm: float = 57.0,
    max_tm: float = 64.0,
    min_length: int = 18,
    max_length: int = 25,
    min_amplicon_bp: int = 100,
    max_amplicon_bp: int = 1000,
    max_pairs: int = 5,
    primer_conc_nm: float = 400.0
) -> List[PrimerPair]

check_heterodimer(primer1_seq: str, primer2_seq: str) -> Tuple[int, int, bool]
```

### Fluorophore Labeling & Spectroscopy (`biolabcalc.fluorescence`, `biolabcalc.spectroscopy`)

```python
get_fluorophore(name: str) -> Fluorophore
apply_fluorophore_modification(base_result: MolecularWeightResult, modifications: List[str]) -> LabeledMoleculeResult

calculate_degree_of_labeling(
    absorbance_max_dye: float,
    absorbance_280: Optional[float] = None,
    absorbance_260: Optional[float] = None,
    fluorophore_name: str = "FAM",
    protein_extinction_coeff: Optional[float] = None,
    oligo_extinction_coeff: Optional[float] = None,
    pathlength_cm: float = 1.0
) -> DegreeOfLabelingResult

prepare_standard_solution(
    target_molarity_um: float,
    target_volume_ul: float,
    sequence: Optional[str] = None,
    seq_type: str = "rna",
    rna_length_nt: Optional[int] = None,
    stock_conc_ng_ul: Optional[float] = None,
    end_5: str = "hydroxyl"
) -> SolutionRecipeResult

assess_nanodrop_purity(
    a260: float,
    a280: float,
    a230: float,
    sample_type: str = "rna"
) -> NanoDropPurityResult
```

### Gel Electrophoresis (`biolabcalc.gels`, `biolabcalc.interactive_gel`, `biolabcalc.gel_annotator`)

```python
simulate_gel(sample_sizes: List[float], ladder_key: str = "1kb_dna") -> GelLaneSimulation
calculate_rf(size: float, min_size: float, max_size: float) -> float
get_interactive_html() -> str
save_interactive_app(output_html_path: str = "gel_annotator.html") -> str
calculate_ladder_standard_curve(ladder_bands_with_rf: List[Tuple[float, float]]) -> Tuple[float, float, float]
estimate_band_mw(rf: float, slope: float, intercept: float) -> float
launch_interactive_annotator(port: int = 8501, open_browser: bool = True, blocking: bool = False) -> str

# Class: GelAnnotator
GelAnnotator.synthetic(num_lanes: int = 6, title: str = "Simulated Gel Electrophoresis", gel_info: str = "1.0% Agarose in 1X TAE", invert_colors: bool = True) -> GelAnnotator
GelAnnotator.from_image(image_path: str, title: str = "Gel Electrophoresis Analysis", gel_info: str = "1.0% Agarose", invert_colors: bool = False) -> GelAnnotator
```

### Microbiology & Culture Growth (`biolabcalc.ecoli_growth`)

```python
calculate_ecoli_growth(initial_od600: float = 0.05, target_od600: float = 0.6, temperature_celsius: float = 37.0, media: str = "LB") -> EcoliGrowthResult
calculate_inoculation_volume(starter_od600: float, target_volume_ml: float, target_od600: float = 0.05) -> Dict[str, float]
estimate_plasmid_yield(culture_volume_ml: float = 5.0, final_od600: float = 3.0, plasmid_type: str = "pUC", plasmid_length_bp: int = 3000) -> PlasmidYieldResult
optimize_protein_induction(protein_mw_da: float, culture_volume_ml: float = 1000.0, final_od600: float = 4.0, expression_percent_of_total: float = 15.0, temperature_celsius: float = 37.0) -> ProteinInductionResult
```

### Molecular Cloning (`biolabcalc.cloning`)

```python
get_restriction_enzyme(name: str) -> RestrictionEnzyme
are_overhangs_compatible(enzyme_1: str, enzyme_2: str) -> Tuple[bool, str]

plan_restriction_digest(
    dna_mass_ug: float,
    reaction_volume_ul: float = 50.0,
    enzyme_1: str = "EcoRI",
    enzyme_2: Optional[str] = None,
    dna_conc_ng_ul: Optional[float] = None,
    units_per_ug: float = 5.0
) -> DigestSetupResult

calculate_ligation(
    vector_length_bp: int,
    insert_length_bp: int,
    vector_mass_ng: float = 50.0,
    molar_ratio: float = 3.0,
    vector_conc_ng_ul: Optional[float] = None,
    insert_conc_ng_ul: Optional[float] = None,
    reaction_volume_ul: float = 20.0
) -> LigationSetupResult

calculate_gibson_assembly(
    vector_length_bp: int,
    insert_lengths_bp: List[int],
    vector_mass_ng: float = 100.0,
    molar_ratio: float = 2.0,
    vector_conc_ng_ul: Optional[float] = None,
    insert_concs_ng_ul: Optional[List[float]] = None,
    reaction_volume_ul: float = 20.0
) -> GibsonAssemblyResult

calculate_golden_gate_assembly(
    vector_length_bp: int,
    insert_lengths_bp: List[int],
    vector_mass_ng: Optional[float] = None,
    target_vector_fmol: float = 20.0,
    insert_to_vector_ratio: float = 2.0,
    type_iis_enzyme: str = "BsaI-HFv2",
    reaction_volume_ul: float = 20.0,
    vector_conc_ng_ul: Optional[float] = None,
    insert_concs_ng_ul: Optional[List[float]] = None
) -> GoldenGateResult
```

### Buffers & Chemistry (`biolabcalc.buffers`)

```python
calculate_buffer_recipe(buffer_key: str, target_volume_ml: float = 1000.0) -> BufferRecipeResult
calculate_hepes_ivt_buffer(target_volume_ml: float = 50.0, stock_multiplier: int = 10, target_ph_37c: float = 7.5, koh_stock_m: float = 5.0) -> HepesIVTBufferResult
calculate_tris_temperature_shift(ph_at_25c: float, target_temp_celsius: float) -> float
calculate_ntp_ph_adjustment(initial_volume_ml: float = 4.0, initial_conc_mm: float = 100.0, target_volume_ml: float = 16.0, target_conc_mm: Optional[float] = 25.0, target_ph: float = 7.5, starting_form: str = "disodium_salt", ntp_species: str = "equimolar_mix", naoh_stock_m: float = 5.0) -> NTPNeutralizationResult
create_custom_buffer(name: str, components: List[Dict[str, Any]], ph: str = "7.5", target_volume_ml: float = 1000.0, storage: str = "Room temperature", safety: Optional[str] = None, save_to_disk: bool = False) -> BufferRecipeResult
```

### Precipitation & Clean-up (`biolabcalc.precipitation`)

```python
calculate_precipitation(
    sample_volume_ul: float,
    nucleic_acid: str = "dna",
    alcohol: str = "ethanol",
    salt: str = "naoac",
    low_concentration_carrier: bool = True,
    target_resuspension_conc_ng_ul: Optional[float] = None,
    estimated_total_ng: Optional[float] = None
) -> PrecipitationProtocol

calculate_phenol_chloroform_extraction(
    sample_volume_ul: float,
    nucleic_acid: str = "rna",
    phenol_ph: Optional[float] = None
) -> PhenolChloroformProtocol
```

---

## 3. Dataclass Return Types Specification

### 1. `SolutionRecipeResult`
Returned by `prepare_standard_solution`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `target_molarity_um` | `float` | Target solution concentration in micromolar ($\mu\text{M}$) |
| `target_volume_ul` | `float` | Target preparation volume in microliters ($\mu\text{L}$) |
| `sequence` | `str` | Biomolecule sequence string |
| `seq_type` | `str` | Molecule type (`rna`, `dna`, `ssdna`, `dsdna`, `protein`) |
| `end_5` | `str` | 5' terminal phosphorylation state (`hydroxyl`, `triphosphate`, etc.) |
| `length_nt` | `int` | Sequence length in nucleotides or amino acids |
| `molecular_weight` | `float` | Molecular weight in $\text{g/mol}$ ($\text{Da}$) |
| `base_counts` | `Dict[str, int]` | Frequency count of each individual nucleotide |
| `sequence_extinction_coeff_260` | `int` | Nearest-neighbor molar extinction coefficient at 260 nm ($\text{M}^{-1}\text{cm}^{-1}$) |
| `sequence_specific_conversion_factor` | `float` | Conversion factor ($\mu\text{g/mL per } A_{260}$) derived from sequence |
| `required_moles_nmol` | `float` | Required molar quantity in nanomoles |
| `required_moles_pmol` | `float` | Required molar quantity in picomoles |
| `required_mass_ug` | `float` | Required sample mass in micrograms |
| `required_mass_ng` | `float` | Required sample mass in nanograms |
| `actual_concentration_ng_ul` | `float` | Final physical concentration in $\text{ng/}\mu\text{L}$ |
| `expected_nanodrop_a260_sequence_specific` | `float` | Expected 10 mm normalized $A_{260}$ reading using nearest-neighbor $\varepsilon_{260}$ |
| `expected_nanodrop_a260_generic_factor` | `float` | Expected 10 mm normalized $A_{260}$ using standard conversion factors |
| `expected_nanodrop_display_ng_ul_generic_mode` | `float` | Predicted display reading on a NanoDrop in standard RNA/DNA mode |
| `expected_nanodrop_a260_1mm` | `float` | Predicted raw unscaled absorbance reading across a 1 mm physical pedestal |
| `expected_a260_a280_ratio` | `float` | Benchmark purity ratio expected for an uncontaminated sample |
| `stock_volume_needed_ul` | `Optional[float]` | Volume of stock solution to pipette (if stock concentration provided) |
| `buffer_volume_needed_ul` | `Optional[float]` | Volume of diluent buffer to bring to final volume |
| `preparation_instructions` | `str` | Formatted pipetting instructions for the bench |

---

### 2. `GibsonAssemblyResult`
Returned by `calculate_gibson_assembly`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `vector_length_bp` | `int` | Destination vector length in base pairs |
| `insert_lengths_bp` | `List[int]` | Ordered list of insert fragment lengths in base pairs |
| `vector_mass_ng` | `float` | Recommended vector mass input in nanograms |
| `insert_masses_ng` | `List[float]` | Recommended mass inputs for each insert fragment in nanograms |
| `total_dna_pmol` | `float` | Total DNA input in picomoles (ideal range: $0.02\text{--}0.2\text{ pmol}$) |
| `reagent_volumes` | `Dict[str, float]`| Pipetting recipe mapping reagents to volumes in $\mu\text{L}$ |
| `incubation_protocol` | `str` | Incubation temperature and time guidelines |

---

### 3. `GoldenGateResult`
Returned by `calculate_golden_gate_assembly`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `enzyme` | `str` | Type IIS restriction enzyme (e.g., `'BsaI-HFv2'`) |
| `vector_length_bp` | `int` | Vector length in base pairs |
| `insert_lengths_bp` | `List[int]` | Lengths of all insert fragments in base pairs |
| `vector_mass_ng` | `float` | Vector mass input in nanograms |
| `vector_fmol` | `float` | Vector molar quantity in femtomoles |
| `insert_masses_ng` | `List[float]` | Insert mass inputs in nanograms |
| `insert_fmols` | `List[float]` | Insert molar quantities in femtomoles |
| `insert_to_vector_ratio` | `float` | Configured molar ratio (typically $2:1$) |
| `total_dna_mass_ng` | `float` | Cumulative DNA mass in reaction |
| `reaction_volume_ul` | `float` | Total assembly reaction volume in $\mu\text{L}$ |
| `reagent_volumes` | `Dict[str, float]`| Pipetting recipe mapping reagents to volumes |
| `thermocycling_protocol` | `List[str]` | Digestion-ligation temperature cycling program |
| `notes` | `List[str]` | Enzyme handling and reaction assembly guidance |

---

### 4. `DigestSetupResult`
Returned by `plan_restriction_digest`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `enzyme_1` | `RestrictionEnzyme`| First restriction enzyme object |
| `enzyme_2` | `Optional[RestrictionEnzyme]`| Second restriction enzyme object (if double digest) |
| `dna_mass_ug` | `float` | Substrate DNA input in micrograms |
| `reaction_volume_ul` | `float` | Total digestion volume in microliters |
| `recommended_buffer` | `str` | Buffer providing $\ge 100\%$ relative activity for all enzymes |
| `incubation_temp_celsius` | `int` | Optimal incubation temperature (°C) |
| `incubation_time_min` | `int` | Recommended incubation time in minutes |
| `heat_inactivation` | `str` | Heat inactivation temperature and time (or column clean-up) |
| `reagent_volumes` | `Dict[str, float]`| Complete pipetting recipe |
| `star_activity_warning` | `bool` | True if enzyme volume exceeds 10% of total reaction |
| `notes` | `List[str]` | Star activity and methylation compatibility warnings |

---

### 5. `LigationSetupResult`
Returned by `calculate_ligation`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `vector_length_bp` | `int` | Vector length in base pairs |
| `insert_length_bp` | `int` | Insert length in base pairs |
| `vector_mass_ng` | `float` | Vector mass in nanograms |
| `insert_mass_ng` | `float` | Insert mass in nanograms |
| `molar_ratio_insert_to_vector` | `float`| Configured molar ratio (typically $3:1$) |
| `vector_pmol` | `float` | Vector molar quantity in picomoles |
| `insert_pmol` | `float` | Insert molar quantity in picomoles |
| `reagent_volumes` | `Dict[str, float]`| Pipetting volumes for ligation reaction |
| `incubation_guidelines` | `str` | Incubation protocol (16°C overnight or 22°C for 2h) |

---

### 6. `TransferConditionsResult`
Returned by `calculate_transfer_conditions`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `target_mw_kda` | `float` | Target protein molecular mass in kDa |
| `transfer_system` | `str` | Method: `wet_tank`, `semi_dry`, or `fast_semi_dry` |
| `membrane_type` | `str` | Membrane material: `pvdf` or `nitrocellulose` |
| `pore_size_um` | `float` | Membrane pore size ($0.2\text{ }\mu\text{m}$ for $<20\text{ kDa}$; $0.45\text{ }\mu\text{m}$ for $\ge 20\text{ kDa}$) |
| `activation_required` | `bool` | True if membrane requires methanol pre-wetting |
| `activation_instructions` | `str` | Step-by-step pre-wetting and equilibration protocol |
| `transfer_buffer_name` | `str` | Recommended transfer buffer formulation |
| `transfer_buffer_recipe` | `Dict[str, str]` | Chemical recipe components for transfer buffer |
| `voltage_or_current` | `str` | Electrical parameters (e.g., `'100V constant'` or `'2.5A'`) |
| `duration_minutes` | `int` | Recommended transfer duration in minutes |
| `temperature_conditions` | `str` | Cooling conditions (e.g., `'4°C with ice pack'`) |
| `expert_tips` | `List[str]` | SDS/methanol tuning advice for high/low MW proteins |

---

### 7. `LysateLoadingResult`
Returned by `calculate_lysate_loading`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `lysate_conc_mg_ml` | `float` | Stock cell lysate total protein concentration ($\text{mg/mL}$) |
| `target_protein_ug_per_lane` | `float` | Target total protein loaded per lane ($\mu\text{g}$) |
| `num_lanes` | `int` | Number of planned gel lanes |
| `lysate_volume_per_lane_ul` | `float` | Volume of lysate required per lane ($\mu\text{L}$) |
| `sample_buffer_volume_per_lane_ul` | `float` | Volume of 4X loading buffer per lane ($\mu\text{L}$) |
| `reducing_agent_volume_ul` | `float` | Volume of 1M DTT or $\beta$-ME required |
| `diluent_volume_ul` | `float` | Volume of buffer or water for volume normalization |
| `total_volume_per_lane_ul` | `float` | Total loading volume per well |
| `master_mix_recipe` | `Dict[str, float]`| Pooled sample preparation master mix |
| `denaturation_temperature_celsius` | `int` | Denaturation temperature (95°C standard; 70°C for membrane proteins) |
| `denaturation_time_minutes` | `int` | Denaturation heating duration |
| `normalization_recommendation` | `str` | Guidance on equalizing lane loading volumes |
| `notes` | `List[str]` | Protocol precautions (e.g., transmembrane precipitation warnings) |

---

### 8. `WesternTroubleshootingResult`
Returned by `troubleshoot_western_blot`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `symptom` | `str` | Reported blot defect (e.g., `'ghost_bands'`, `'high_background'`) |
| `likely_causes` | `List[str]` | Prioritized biochemical and technical root causes |
| `corrective_actions` | `List[str]` | Actionable bench remedies for subsequent runs |
| `preventative_protocol` | `str` | Best practice guidelines to permanently resolve artifact |

---

### 9. `DegreeOfLabelingResult`
Returned by `calculate_degree_of_labeling`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `molecule_type` | `str` | Macromolecule class (`protein` or `oligonucleotide`) |
| `fluorophore_name` | `str` | Attached dye identifier |
| `absorbance_max_dye` | `float` | Peak absorbance of attached fluorophore ($A_{\text{max}}$) |
| `absorbance_corrected_biomolecule`| `float` | Absorbance at 280/260 nm corrected for dye spectral crossover |
| `biomolecule_concentration_um` | `float` | Concentration of target macromolecule in $\mu\text{M}$ |
| `dye_concentration_um` | `float` | Concentration of attached dye in $\mu\text{M}$ |
| `degree_of_labeling` | `float` | Moles of dye per mole of biomolecule |
| `labeling_efficiency_percent` | `float` | Conjugation efficiency relative to stoichiometric target |
| `interpretation` | `str` | Clinical/biochemical assessment of conjugation quality |

---

### 10. `GelLaneSimulation`
Returned by `simulate_gel`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `ladder_name` | `str` | Reference ladder name |
| `sample_sizes` | `List[float]` | Input sample fragment sizes |
| `ladder_bands` | `List[GelBand]`| Calibrated ladder bands with calculated $R_f$ |
| `sample_bands` | `List[GelBand]`| Sample bands with calculated $R_f$ |
| `recommended_gel_percentage` | `str` | Recommended matrix percentage (e.g., `'1.0%'` or `'10-12% SDS-PAGE'`) |
| `ascii_visualization` | `str` | Multi-line formatted terminal ASCII graphic |

---

### 11. `EcoliGrowthResult`
Returned by `calculate_ecoli_growth`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `initial_od600` | `float` | Starting culture optical density |
| `target_od600` | `float` | Target harvest/induction optical density |
| `temperature_celsius` | `float` | Culture incubation temperature (°C) |
| `media` | `str` | Broth type (`LB`, `2xYT`, `TB`, `M9`) |
| `doubling_time_min` | `float` | Generation doubling time in minutes |
| `growth_rate_per_hour` | `float` | Exponential specific growth rate $\mu$ ($\text{h}^{-1}$) |
| `num_doublings` | `float` | Total cell division generations required |
| `hours_to_target_od` | `float` | Duration in decimal hours |
| `formatted_time` | `str` | Human-readable schedule string (e.g., `'2h 15m'`) |
| `target_cells_per_ml` | `float` | Estimated cell concentration at target OD |
| `warnings` | `List[str]` | Aeration and stationary phase warnings |

---

### 12. `PlasmidYieldResult`
Returned by `estimate_plasmid_yield`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `plasmid_type` | `str` | Replicon origin (e.g., `'pUC'`, `'pET'`, `'pBR322'`) |
| `plasmid_length_bp` | `int` | Vector length in base pairs |
| `culture_volume_ml` | `float` | Bacterial culture volume in mL |
| `final_od600` | `float` | Culture density at harvest |
| `total_bacterial_cells` | `float` | Estimated total biomass cell count |
| `plasmid_copies_per_cell` | `int` | Vector copy number per bacterium |
| `total_plasmid_copies` | `float` | Cumulative plasmid molecules |
| `theoretical_yield_ug` | `float` | 100% stoichiometric yield in micrograms |
| `typical_miniprep_yield_ug` | `float` | Expected silica column kit recovery (~55%) |

---

### 13. `ProteinInductionResult`
Returned by `optimize_protein_induction`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `protein_mw_da` | `float` | Target recombinant protein molecular mass in Da |
| `culture_volume_ml` | `float` | Culture harvest volume in mL |
| `final_od600` | `float` | Culture density at harvest |
| `total_cellular_protein_mg` | `float` | Total host cellular protein biomass in mg |
| `expression_percent_of_total`| `float` | Target protein expression percentage of total protein |
| `recombinant_protein_yield_mg`| `float` | Expected recombinant protein mass in mg |
| `recombinant_protein_nmol` | `float` | Expected recombinant protein molar quantity in nmol |
| `recombinant_protein_yield_ng`| `float` | Expected yield in nanograms |
| `recommended_conditions` | `str` | IPTG inducer concentration and temperature advice |

---

### 14. `PCROptimizationResult`
Returned by `optimize_pcr_protocol`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `annealing_temp_celsius` | `float` | Calculated optimal annealing temperature ($T_a$) |
| `denaturation_temp_celsius`| `float` | Initial/cycling denaturation temperature (°C) |
| `extension_time_seconds` | `int` | Polymerase extension duration in seconds |
| `extension_temp_celsius` | `float` | Extension temperature (°C) |
| `polymerase` | `str` | Polymerase brand/fidelity class |
| `amplicon_len_bp` | `int` | Target amplicon length in bp |
| `gc_percent` | `float` | Amplicon GC content |
| `touchdown_initial_ta` | `float` | Initial annealing temperature for touchdown PCR |
| `touchdown_cycles` | `int` | Number of touchdown cycles |
| `recommended_additives` | `List[str]` | Additive recommendations (DMSO, betaine, $\text{Mg}^{2+}$) |
| `cycling_protocol_summary`| `str` | Complete thermal cycling profile string |

---

### 15. `PCRResult`
Returned by `calculate_pcr_kinetics`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `amplicon_length_bp` | `int` | Amplicon length in base pairs |
| `amplicon_mw` | `float` | Amplicon molecular weight in Da |
| `template_initial_copies` | `float` | Input template copy count |
| `template_initial_ng` | `float` | Input template mass in nanograms |
| `amplicon_yield_ng` | `float` | Synthesized amplicon mass in nanograms |
| `amplicon_yield_pmol` | `float` | Synthesized amplicon molar yield in picomoles |
| `amplicon_final_copies` | `float` | Final amplicon copy count |
| `cycles_run` | `int` | Number of completed cycles |
| `efficiency` | `float` | Cycle efficiency decimal ($0.0\text{--}1.0$) |
| `efficiency_percent` | `float` | Cycle efficiency percentage |
| `dntp_initial_nmol` | `Dict[str, float]`| Starting nanomoles of each dNTP |
| `dntp_consumed_nmol` | `Dict[str, float]`| Nanomoles of each dNTP incorporated into DNA |
| `dntp_remaining_um` | `Dict[str, float]`| Residual micromolar concentration of each dNTP |
| `limiting_dntp` | `str` | First dNTP exhausted based on sequence |
| `dntp_exhaustion_cycle` | `Optional[int]` | Cycle number at which dNTP exhaustion triggers plateau |
| `theoretical_max_amplicon_ug`| `float` | Maximum attainable yield under dNTP supply |
| `limiting_reagent` | `str` | Identity of limiting reaction component |

---

### 16. `IVTResult`
Returned by `calculate_ivt_yield`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `rna_length` | `int` | Final synthesized transcript length in nt |
| `rna_sequence` | `str` | Cleaned transcript sequence |
| `rna_mw` | `float` | Transcript molecular weight in Da |
| `reaction_volume_ul` | `float` | Total reaction volume in $\mu\text{L}$ |
| `rna_yield_ug` | `float` | Synthesized RNA mass in micrograms |
| `rna_yield_pmol` | `float` | Synthesized RNA molar yield in picomoles |
| `theoretical_max_yield_ug` | `float` | Upper-bound yield limited by stoichiometric NTP supply |
| `limiting_ntp` | `str` | First NTP species exhausted |
| `ntp_initial_mm` | `Dict[str, float]`| Initial millimolar concentration per NTP |
| `ntp_consumed_nmol` | `Dict[str, float]`| Nanomoles incorporated into RNA per NTP |
| `ntp_remaining_mm` | `Dict[str, float]`| Residual concentration per NTP |
| `ntp_incorporation_percent`| `Dict[str, float]`| Percent substrate converted per NTP |
| `overall_efficiency_percent`| `float` | Overall conversion efficiency |
| `pyrophosphate_released_nmol`| `float` | Molar quantity of byproduct $\text{PPi}$ released |
| `pyrophosphate_released_ug` | `float` | Mass of byproduct $\text{PPi}$ released |
| `transcript_turnover_ratio`| `Optional[float]` | RNA transcript copies produced per template DNA |
| `free_mg_initial_mm` | `float` | Free unchelated magnesium remaining |
| `promoter_detected` | `Optional[str]` | Trimmed promoter name (`T7`, `T3`, `SP6`) |
| `promoter_trimmed_nt` | `int` | Number of upstream promoter nucleotides excised |
| `added_5prime_gs` | `int` | Number of 5' Guanines prepended for initiation |
| `initiation_efficiency_rating`| `str` | Efficiency classification (`OPTIMAL`, `MODERATE`, `POOR`) |
| `initiation_recommendations`| `List[str]` | Sequence recommendations to optimize initiation |
| `warnings` | `List[str]` | $\text{PPi}$ precipitation and pH shift warnings |
| `cap_analog` | `Optional[str]` | Co-transcriptional cap analog used |
| `predicted_capping_efficiency_percent`| `Optional[float]`| Estimated capping percentage |
| `modified_ntp` | `Optional[str]` | Modified nucleotide replacement (e.g., `'m1Psi'`) |
| `modified_mw` | `Optional[float]` | Molecular weight incorporating nucleotide modification |
| `recommended_incubation_hours`| `float` | Recommended reaction incubation time |
| `protons_released_nmol` | `float` | Hydrogen ions released during phosphodiester synthesis |
| `buffer_recommendation` | `str` | Buffer evaluation (HEPES vs. Tris) |
| `hepes_vs_tris_comparison` | `str` | Comparative buffering capacity assessment |
| `end_5` | `str` | 5' terminal phosphorylation state |
| `end_3` | `str` | 3' terminal phosphorylation state |
| `backbone` | `str` | Internucleotide backbone chemistry |

---

### 17. `MolecularWeightResult`
Returned by `calculate_dna_mw`, `calculate_rna_mw`, and `calculate_protein_mw`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `sequence` | `str` | Cleaned uppercase sequence |
| `seq_type` | `str` | Molecule type (`dsDNA`, `ssDNA`, `ssRNA`, `Protein`) |
| `length` | `int` | Length in nucleotides or residues |
| `average_mw` | `float` | Average isotopic molecular mass in Daltons ($\text{g/mol}$) |
| `monoisotopic_mw` | `float` | Monoisotopic molecular mass in Daltons |
| `base_counts` | `Dict[str, int]` | Frequency count of each monomer |
| `gc_content` | `float` | GC percentage (nucleic acids) |
| `end_5` | `str` | 5' terminal chemistry |
| `end_3` | `str` | 3' terminal chemistry |
| `backbone` | `str` | Backbone linkage chemistry |
| `formula_delta` | `str` | Mass shift summary relative to default standard |

---

### 18. `PrimerAnalysis`
Returned by `analyze_primer`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `sequence` | `str` | 5' to 3' primer sequence |
| `length` | `int` | Oligonucleotide length in nucleotides |
| `tm_celsius` | `float` | SantaLucia nearest-neighbor melting temperature ($T_m$) |
| `gc_percent` | `float` | Guanine-Cytosine content percentage |
| `gc_clamp_count` | `int` | Number of G/C bases within the 5 terminal 3' positions |
| `has_gc_clamp` | `bool` | True if $3'$ end possesses at least one G or C |
| `delta_h_kcal` | `float` | Nearest-neighbor enthalpy $\Delta H^\circ$ ($\text{kcal/mol}$) |
| `delta_s_cal` | `float` | Nearest-neighbor entropy $\Delta S^\circ$ ($\text{cal/(mol}\cdot\text{K)}$) |
| `delta_g_37_kcal` | `float` | Free energy $\Delta G_{37}^\circ$ ($\text{kcal/mol}$) |
| `homopolymer_warning` | `bool` | True if sequence contains $\ge 4$ identical consecutive bases |
| `dimer_score` | `int` | Self-dimerization penalty score |
| `hairpin_score` | `int` | Stem-loop hairpin formation penalty score |
| `quality_score` | `float` | Overall thermodynamic quality score ($0\text{--}100$) |

---

### 19. `PrimerPair`
Returned by `design_primers`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `forward_primer` | `PrimerAnalysis`| Thermodynamic analysis of forward primer |
| `reverse_primer` | `PrimerAnalysis`| Thermodynamic analysis of reverse primer |
| `amplicon_length_bp` | `int` | Expected PCR product length in base pairs |
| `tm_difference` | `float` | Absolute difference between primer melting temperatures ($\Delta T_m$) |
| `product_start` | `int` | 1-based start coordinate on template |
| `product_end` | `int` | 1-based end coordinate on template |
| `pair_quality_score` | `float` | Composite pair quality metric |
| `heterodimer_score` | `int` | Cross-primer hybridization penalty score |
| `three_prime_heterodimer_score`| `int` | Primer-dimer penalty specifically at $3'$ ends |
| `heterodimer_warning` | `bool` | True if significant cross-dimer risk exists |

---

### 20. `ExtinctionCoefficientResult`
Returned by `calculate_extinction_coefficient`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `sequence` | `str` | Polypeptide sequence |
| `length` | `int` | Number of amino acids |
| `molecular_weight` | `float` | Polypeptide molecular weight in Da |
| `extinction_coeff_m_cm` | `int` | Molar extinction coefficient $\varepsilon_{280}$ ($\text{M}^{-1}\text{cm}^{-1}$) |
| `a280_1mg_ml` | `float` | Absorbance at 280 nm for a $1.0\text{ mg/mL}$ solution in a 1 cm cuvette |
| `tryptophan_count` | `int` | Count of Trp (W) residues ($5,500\text{ }\text{M}^{-1}\text{cm}^{-1}$ each) |
| `tyrosine_count` | `int` | Count of Tyr (Y) residues ($1,490\text{ }\text{M}^{-1}\text{cm}^{-1}$ each) |
| `cystine_pairs` | `int` | Count of disulfide bonded cystine pairs ($125\text{ }\text{M}^{-1}\text{cm}^{-1}$ each) |

---

### 21. `StandardCurveResult`
Returned by `fit_standard_curve`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `assay_type` | `str` | Assay name (`BCA`, `Bradford`, `Lowry`) |
| `slope` | `float` | Linear regression slope ($m$) |
| `intercept` | `float` | Linear regression y-intercept ($c$) |
| `r_squared` | `float` | Coefficient of determination ($R^2$) |
| `formula_str` | `str` | Formatted equation string (e.g., `'y = 0.00115x + 0.0450'`) |

---

### 22. `BufferRecipeResult`
Returned by `calculate_buffer_recipe` and `create_custom_buffer`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `buffer_id` | `str` | Catalog or custom identifier |
| `name` | `str` | Full descriptive buffer name |
| `target_volume_ml` | `float` | Scaled preparation volume in mL |
| `components` | `List[BufferComponent]`| Detailed chemical formulation components |
| `ph_specification` | `str` | Target pH specification at stated temperature |
| `preparation_steps` | `List[str]` | Sequential preparation and dissolution steps |
| `storage_conditions` | `str` | Recommended temperature and shelf-life |
| `safety_notes` | `Optional[str]` | Hazardous handling precautions |

---

### 23. `NTPNeutralizationResult`
Returned by `calculate_ntp_ph_adjustment`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `initial_volume_ml` | `float` | Starting NTP stock volume in mL |
| `initial_conc_mm` | `float` | Starting concentration in mM |
| `target_volume_ml` | `float` | Target diluted volume in mL |
| `target_conc_mm` | `float` | Target working concentration in mM |
| `target_ph` | `float` | Target neutralized pH |
| `ntp_species` | `str` | Identity of nucleotide species or mix |
| `starting_form` | `str` | Starting chemical form (`disodium_salt`, `free_acid`) |
| `total_ntp_mmol` | `float` | Total NTP substance in millimoles |
| `naoh_equivalents` | `float` | Hydroxide equivalents required per mole NTP |
| `naoh_mmol` | `float` | Total $\text{NaOH}$ base substance in millimoles |
| `naoh_volume_ul` | `Dict[str, float]`| Required volumes for standard $\text{NaOH}$ stocks (5M, 10M, 1M) |
| `water_volume_ml` | `float` | Approximate volume of diluent water to add |
| `warnings` | `List[str]` | Exothermic and local over-titration warnings |
| `logic_checks` | `List[str]` | Verification tests confirming mass balance |
| `preparation_steps` | `List[str]` | Step-by-step titration and mixing instructions |

---

### 24. `PrecipitationProtocol`
Returned by `calculate_precipitation`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `sample_volume_ul` | `float` | Starting aqueous sample volume in $\mu\text{L}$ |
| `nucleic_acid_type` | `str` | Nucleic acid class (`DNA` or `RNA`) |
| `alcohol_type` | `str` | Alcohol used (`Ethanol` or `Isopropanol`) |
| `salt_type` | `str` | Neutralizing salt used (e.g., `Sodium Acetate 3M pH 5.2`) |
| `salt_volume_ul` | `float` | Volume of salt stock to add |
| `alcohol_volume_ul` | `float` | Volume of 100% cold alcohol to add |
| `carrier_added` | `str` | Co-precipitant added (`Glycogen`, `tRNA`, or `None`) |
| `carrier_volume_ul` | `float` | Volume of carrier stock to add |
| `incubation_temp` | `str` | Incubation temperature and duration |
| `centrifugation_speed` | `str` | Centrifugation g-force (e.g., `'≥ 16,000 x g'`) |
| `centrifugation_time_min` | `int` | Centrifugation duration in minutes |
| `wash_volume_70pct_ethanol_ul`| `float` | Volume of 70% cold ethanol wash to add |
| `drying_instructions` | `str` | Pellet drying guidance to avoid over-drying |
| `resuspension_guidelines` | `str` | Recommended resuspension buffers |
| `reagent_summary` | `Dict[str, float]`| Volume summary of all added components |
| `vessel_warning` | `Optional[str]` | Warning if total volume exceeds standard $1.5\text{ mL}$ microtube |

---

### 25. `PhenolChloroformProtocol`
Returned by `calculate_phenol_chloroform_extraction`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `sample_volume_ul` | `float` | Starting aqueous sample volume in $\mu\text{L}$ |
| `phenol_type` | `str` | Phenol specification (Acid pH 4.5 for RNA; Buffered pH 8.0 for DNA) |
| `target_nucleic_acid` | `str` | Target molecule to recover |
| `pci_volume_ul` | `float` | Volume of Phenol:Chloroform:Isoamyl alcohol to add |
| `chloroform_volume_ul` | `float` | Volume of Chloroform:Isoamyl alcohol for back-extraction |
| `aqueous_phase_layer` | `str` | Spatial position of target aqueous phase (upper vs. lower) |
| `protocol_steps` | `List[str]` | Step-by-step extraction procedure |
| `safety_notes` | `List[str]` | Fume hood, glove, and chemical burn hazard instructions |
| `reagent_volumes` | `Dict[str, float]`| Recipe component volume summary |

---

### 26. `NanoDropPurityResult`
Returned by `assess_nanodrop_purity`.

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `a260` | `float` | Raw absorbance reading at 260 nm |
| `a280` | `float` | Raw absorbance reading at 280 nm |
| `a230` | `float` | Raw absorbance reading at 230 nm |
| `sample_type` | `str` | Sample class (`RNA` or `DNA`) |
| `a260_a280_ratio` | `float` | Ratio of absorbance at 260 nm to 280 nm |
| `a260_a230_ratio` | `float` | Ratio of absorbance at 260 nm to 230 nm |
| `purity_status` | `str` | Overall assessment (`PURE`, `SUSPECT`, `CONTAMINATED`) |
| `protein_contamination` | `bool` | True if low $A_{260}/A_{280}$ indicates protein/phenol presence |
| `salt_or_solvent_contamination`| `bool` | True if low $A_{260}/A_{230}$ indicates guanidine/EDTA/solvent |
| `phenol_contamination_risk` | `bool` | True if $A_{230}$ and $A_{270}$ shifts indicate residual phenol |
| `corrected_a260` | `float` | Absorbance at 260 nm after subtracting baseline background |
| `corrected_concentration_ng_ul`| `float` | Adjusted concentration in $\text{ng/}\mu\text{L}$ |
| `diagnostic_feedback` | `List[str]` | Prioritized diagnostic notes and clean-up recommendations |
