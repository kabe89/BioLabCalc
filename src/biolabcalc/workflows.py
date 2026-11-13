"""Chained multi-step wet-lab workflows combining multiple BioLabCalc modules.

Provides orchestrated end-to-end workflows for common laboratory procedures:
1. CloningWorkflow: Primer design/analysis -> PCR kinetics -> Gel simulation ->
   Restriction digest -> Ligation / Gibson / Golden Gate assembly -> Transformation/Growth.
2. IVTWorkflow: Template analysis -> In vitro transcription yield -> Time optimization ->
   HEPES reaction buffer formulation -> Ethanol/Isopropanol precipitation.

Both workflows automatically register all critical QC parameters into a LabReport ledger.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union

from .lab_report import LabReport, auto_record, new_lab_report, get_active_report
from .primers import analyze_primer
from .pcr import calculate_pcr_kinetics, optimize_pcr_protocol
from .gels import simulate_gel, GelLaneSimulation
from .cloning import (
    plan_restriction_digest,
    calculate_ligation,
    calculate_gibson_assembly,
    calculate_golden_gate_assembly,
)
from .ecoli_growth import calculate_ecoli_growth, calculate_inoculation_volume
from .molecular_weight import calculate_rna_mw, calculate_dna_mw
from .transcription import calculate_ivt_yield, optimize_transcription_time
from .buffers import calculate_hepes_ivt_buffer
from .precipitation import calculate_precipitation


@dataclass
class CloningWorkflowResult:
    """Consolidated outcome of an end-to-end molecular cloning workflow."""
    primer_analysis: Optional[Dict[str, Any]]
    pcr_protocol: Optional[Any]
    pcr_kinetics: Any
    gel_simulation: Any
    digest_plan: Any
    assembly_plan: Any
    inoculation_plan: Any
    report: LabReport

    def summary(self) -> str:
        """Human-readable overview of the cloning pipeline results."""
        lines = [
            "=== Cloning Workflow Summary ===",
            f"PCR Amplicon: {getattr(self.pcr_kinetics, 'amplicon_length_bp', 'N/A')} bp, Yield: {getattr(self.pcr_kinetics, 'amplicon_yield_ng', 'N/A')} ng",
            f"Gel Bands Simulated: {len(getattr(self.gel_simulation, 'sample_bands', []))} bands",
            f"Digest Plan: {getattr(self.digest_plan, 'enzyme_1', '')} + {getattr(self.digest_plan, 'enzyme_2', '')} ({getattr(self.digest_plan, 'dna_mass_ug', '')} µg DNA)",
            f"Assembly Type: {type(self.assembly_plan).__name__}",
            f"E. coli Growth: {getattr(self.inoculation_plan, 'formatted_time', '')} to target OD600",
            f"Lab Report Records: {len(self.report.records)} metrics logged",
        ]
        return "\n".join(lines)


@dataclass
class IVTWorkflowResult:
    """Consolidated outcome of an end-to-end In Vitro Transcription synthesis workflow."""
    template_analysis: Any
    ivt_yield: Any
    incubation_time: Any
    precipitation_recipe: Any
    hepes_buffer: Any
    report: LabReport

    def summary(self) -> str:
        """Human-readable overview of the IVT synthesis pipeline results."""
        lines = [
            "=== In Vitro Transcription Workflow Summary ===",
            f"RNA Length: {getattr(self.ivt_yield, 'rna_length', 'N/A')} nt (MW: {getattr(self.template_analysis, 'average_mw', 'N/A')} Da)",
            f"Predicted Yield: {getattr(self.ivt_yield, 'rna_yield_ug', 'N/A')} µg (Turnover: {getattr(self.ivt_yield, 'transcript_turnover_ratio', 'N/A')}x)",
            f"Optimal Incubation: {getattr(self.incubation_time, 'optimal_incubation_hours', 'N/A')} hours",
            f"Precipitation Alcohol: {getattr(self.precipitation_recipe, 'alcohol_volume_ul', 'N/A')} µL {getattr(self.precipitation_recipe, 'alcohol_type', '')}",
            f"HEPES Buffer Formulation: {getattr(self.hepes_buffer, 'target_volume_ml', 'N/A')} mL (pH {getattr(self.hepes_buffer, 'target_ph', '7.5')})",
            f"Lab Report Records: {len(self.report.records)} metrics logged",
        ]
        return "\n".join(lines)


def cloning_workflow(
    primer_fwd: Optional[str] = None,
    primer_rev: Optional[str] = None,
    amplicon_len_bp: int = 1000,
    template_ng: float = 10.0,
    vector_length_bp: int = 3000,
    insert_length_bp: Optional[int] = None,
    enzyme_1: str = "EcoRI",
    enzyme_2: Optional[str] = "BamHI",
    dna_mass_ug: float = 1.0,
    assembly_method: str = "ligation",
    molar_ratio: float = 3.0,
    target_od600: float = 0.6,
    report: Optional[LabReport] = None,
    sample_id: str = "Clone-1",
    notes: str = "Molecular cloning workflow",
) -> CloningWorkflowResult:
    """Execute an end-to-end molecular cloning workflow pipeline.

    Chains:
    1. Primer Analysis (Tm, GC%, hairpins) if primers are supplied.
    2. PCR Cycling Protocol Optimization and 30-cycle Kinetics Simulation.
    3. Agarose Gel Electrophoresis band migration simulation.
    4. Restriction Enzyme Digestion setup.
    5. Molecular Assembly (standard T4 Ligation, Gibson Assembly, or Golden Gate).
    6. E. coli transformation recovery and post-inoculation growth prediction.
    7. Automated multi-parameter logging into a LabReport session.

    Args:
        primer_fwd: Forward primer sequence (5'->3').
        primer_rev: Reverse primer sequence (5'->3').
        amplicon_len_bp: Expected size of PCR amplicon in base pairs.
        template_ng: Initial template DNA mass in nanograms.
        vector_length_bp: Target cloning vector size in base pairs.
        insert_length_bp: Insert size in base pairs (defaults to amplicon_len_bp).
        enzyme_1: Primary restriction enzyme for digestion.
        enzyme_2: Secondary restriction enzyme for double digestion (optional).
        dna_mass_ug: Mass of plasmid DNA to digest in micrograms.
        assembly_method: 'ligation', 'gibson', or 'golden_gate'.
        molar_ratio: Molar excess of insert over vector.
        target_od600: Target optical density for downstream bacterial harvest.
        report: Optional target LabReport (creates or uses active report if None).
        sample_id: Sample tracking identifier.
        notes: Contextual notes for report records.

    Returns:
        CloningWorkflowResult containing all simulation outcomes and the populated report.
    """
    ins_bp = insert_length_bp if insert_length_bp is not None else amplicon_len_bp
    rep = report if report is not None else LabReport(title=f"Cloning Workflow Report - {sample_id}")

    # 1. Primer Analysis & Cycling Optimization
    primer_info: Optional[Dict[str, Any]] = None
    pcr_proto: Optional[Any] = None
    if primer_fwd and primer_rev:
        fwd_an = analyze_primer(primer_fwd)
        rev_an = analyze_primer(primer_rev)
        primer_info = {"fwd": fwd_an, "rev": rev_an}
        pcr_proto = optimize_pcr_protocol(
            primer_fwd_tm=fwd_an.tm_celsius,
            primer_rev_tm=rev_an.tm_celsius,
            amplicon_len_bp=amplicon_len_bp,
        )

    # 2. PCR Kinetics
    pcr_kin = calculate_pcr_kinetics(
        amplicon_len_bp=amplicon_len_bp,
        template_ng=template_ng,
    )
    auto_record(pcr_kin, report=rep, sample_id=sample_id, notes=f"{notes} (PCR Kinetics)")

    # 3. Gel Simulation
    gel_sim = simulate_gel(sample_sizes=[float(amplicon_len_bp), float(vector_length_bp)])

    # 4. Restriction Digestion
    dig_plan = plan_restriction_digest(
        dna_mass_ug=dna_mass_ug,
        enzyme_1=enzyme_1,
        enzyme_2=enzyme_2,
    )
    auto_record(dig_plan, report=rep, sample_id=sample_id, notes=f"{notes} (Digestion)")

    # 5. Assembly Setup
    method_lower = assembly_method.lower().replace("-", "_").replace(" ", "_")
    if method_lower == "gibson":
        assembly = calculate_gibson_assembly(
            vector_length_bp=vector_length_bp,
            insert_lengths_bp=[ins_bp],
            molar_ratio=molar_ratio,
        )
    elif method_lower in ("golden_gate", "goldengate"):
        assembly = calculate_golden_gate_assembly(
            vector_length_bp=vector_length_bp,
            insert_lengths_bp=[ins_bp],
            insert_to_vector_ratio=molar_ratio,
        )
    else:
        assembly = calculate_ligation(
            vector_length_bp=vector_length_bp,
            insert_length_bp=ins_bp,
            molar_ratio=molar_ratio,
        )
    auto_record(assembly, report=rep, sample_id=sample_id, notes=f"{notes} (Assembly: {assembly_method})")

    # 6. E. coli Growth Inoculation
    growth = calculate_ecoli_growth(
        initial_od600=0.05,
        target_od600=target_od600,
    )
    auto_record(growth, report=rep, sample_id=sample_id, notes=f"{notes} (Transformation & Growth)")

    rep.conclusions.append(
        f"Cloning workflow completed for {sample_id}: {amplicon_len_bp} bp insert into {vector_length_bp} bp vector via {assembly_method}."
    )

    return CloningWorkflowResult(
        primer_analysis=primer_info,
        pcr_protocol=pcr_proto,
        pcr_kinetics=pcr_kin,
        gel_simulation=gel_sim,
        digest_plan=dig_plan,
        assembly_plan=assembly,
        inoculation_plan=growth,
        report=rep,
    )


def ivt_workflow(
    rna_seq: str,
    reaction_volume_ul: float = 20.0,
    target_yield_ug: Optional[float] = None,
    template_dna_ng: Optional[float] = 1000.0,
    buffer_type: str = "hepes",
    target_buffer_volume_ml: float = 50.0,
    precipitation_alcohol: str = "ethanol",
    precipitation_salt: str = "naoac",
    report: Optional[LabReport] = None,
    sample_id: str = "IVT-Batch-1",
    notes: str = "IVT synthesis workflow",
) -> IVTWorkflowResult:
    """Execute an end-to-end In Vitro Transcription (IVT) mRNA synthesis workflow pipeline.

    Chains:
    1. Template & transcript molecular weight and biophysical property assessment.
    2. Multi-turnover IVT transcription yield kinetics and pyrophosphate accumulation.
    3. Reaction incubation duration optimization based on transcript length.
    4. HEPES IVT reaction buffer formulation.
    5. Downstream nucleic acid alcohol precipitation and recovery protocol.
    6. Automated multi-parameter logging into a LabReport session.

    Args:
        rna_seq: RNA transcript sequence (5'->3').
        reaction_volume_ul: IVT reaction volume in microliters.
        target_yield_ug: Optional target RNA mass in micrograms.
        template_dna_ng: Initial linear DNA template mass in nanograms.
        buffer_type: Reaction buffer type ('hepes' or 'tris').
        target_buffer_volume_ml: Batch volume for custom buffer preparation in mL.
        precipitation_alcohol: Alcohol for precipitation ('ethanol' or 'isopropanol').
        precipitation_salt: Salt for precipitation ('naoac', 'nacl', 'nh4oac', 'licl').
        report: Optional target LabReport (creates or uses active report if None).
        sample_id: Sample tracking identifier.
        notes: Contextual notes for report records.

    Returns:
        IVTWorkflowResult containing all simulation outcomes and the populated report.
    """
    clean_seq = rna_seq.strip().upper().replace("T", "U")
    rep = report if report is not None else LabReport(title=f"IVT Workflow Report - {sample_id}")

    # 1. Molecular Weight & Biophysical Assessment
    mw_res = calculate_rna_mw(clean_seq)
    auto_record(mw_res, report=rep, sample_id=sample_id, notes=f"{notes} (Biophysical MW)")

    # 2. IVT Yield Kinetics
    ivt_res = calculate_ivt_yield(
        rna_seq=clean_seq,
        reaction_volume_ul=reaction_volume_ul,
        target_yield_ug=target_yield_ug,
        template_dna_ng=template_dna_ng,
        buffer_type=buffer_type,
    )
    auto_record(ivt_res, report=rep, sample_id=sample_id, notes=f"{notes} (IVT Yield)")

    # 3. Time Optimization
    time_res = optimize_transcription_time(
        transcript_length_nt=len(clean_seq),
        reaction_volume_ul=reaction_volume_ul,
        target_yield_ug=target_yield_ug,
    )
    auto_record(time_res, report=rep, sample_id=sample_id, notes=f"{notes} (Time Optimization)")

    # 4. HEPES Buffer Formulation
    hepes_buf = calculate_hepes_ivt_buffer(target_volume_ml=target_buffer_volume_ml)
    auto_record(hepes_buf, report=rep, sample_id=sample_id, notes=f"{notes} (HEPES Buffer)")

    # 5. Precipitation
    precip = calculate_precipitation(
        sample_volume_ul=reaction_volume_ul,
        nucleic_acid="rna",
        alcohol=precipitation_alcohol,
        salt=precipitation_salt,
    )
    auto_record(precip, report=rep, sample_id=sample_id, notes=f"{notes} (Precipitation)")

    rep.conclusions.append(
        f"IVT workflow completed for {sample_id}: {len(clean_seq)} nt transcript, predicted yield {ivt_res.rna_yield_ug} µg ({ivt_res.transcript_turnover_ratio}x turnover)."
    )

    return IVTWorkflowResult(
        template_analysis=mw_res,
        ivt_yield=ivt_res,
        incubation_time=time_res,
        precipitation_recipe=precip,
        hepes_buffer=hepes_buf,
        report=rep,
    )
