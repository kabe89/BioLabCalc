"""
Module: biolabcalc.eln.api.routes.in_vivo
Component: In-Vivo Mouse Model & ARRIVE 2.0 REST Endpoints
Architectural Role: REST routes exposing genetic strains, animal subject enrollment,
longitudinal welfare scoring, tissue harvesting linkages, and ARRIVE 2.0 report generation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...services.in_vivo_service import get_in_vivo_service
from ..auth import UserSession, get_auth_service
from ..router import Router

router = Router(prefix="/api/v1/in-vivo")
in_vivo_service = get_in_vivo_service()
auth_service = get_auth_service()


@router.get("/strains")
def list_strains(current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """List all registered mouse genetic strains."""
    strains = in_vivo_service.list_strains()
    return {"status": "success", "count": len(strains), "strains": strains}


@router.post("/strains")
def create_strain(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Register a new mouse genetic strain."""
    strain = in_vivo_service.create_strain(
        name=payload["name"],
        rrid=payload.get("rrid", ""),
        stock_number=payload.get("stock_number", ""),
        genetic_background=payload.get("genetic_background", "C57BL/6J"),
        modified_alleles=payload.get("modified_alleles"),
        phenotype_notes=payload.get("phenotype_notes", ""),
        breeding_scheme=payload.get("breeding_scheme", ""),
        vendor_or_source=payload.get("vendor_or_source", "Jackson Laboratory"),
    )
    return {"status": "success", "strain": strain}


@router.get("/subjects")
def list_subjects(
    strain_id: Optional[str] = None,
    cage_id: Optional[str] = None,
    cohort: Optional[str] = None,
    current_user: Optional[UserSession] = None,
) -> Dict[str, Any]:
    """List animal subjects with optional strain, cage, or cohort filtering."""
    subjects = in_vivo_service.list_subjects(strain_id=strain_id, cage_id=cage_id, cohort=cohort)
    return {"status": "success", "count": len(subjects), "subjects": subjects}


@router.post("/subjects")
def create_subject(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Enroll a new individual mouse subject."""
    subject = in_vivo_service.create_subject(
        ear_tag=payload.get("ear_tag") or payload.get("subject_id") or "",
        strain_id=payload["strain_id"],
        sex=payload.get("sex", "M"),
        date_of_birth=payload.get("date_of_birth"),
        genotype=payload.get("genotype", "WT"),
        cage_id=payload.get("cage_id", ""),
        litter_id=payload.get("litter_id", ""),
        baseline_weight_g=float(payload.get("baseline_weight_g", 25.0)),
        cohort=payload.get("cohort", ""),
    )
    return {"status": "success", "subject": subject}


@router.get("/observations")
def list_observations(subject_id: Optional[str] = None, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """List longitudinal observations for animals."""
    observations = in_vivo_service.list_observations(subject_id=subject_id)
    return {"status": "success", "count": len(observations), "observations": observations}


@router.post("/observations")
def log_observation(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Log clinical observation and evaluate humane endpoint triggers."""
    obs = in_vivo_service.log_observation(
        subject_id=payload["subject_id"],
        weight_g=float(payload["weight_g"]),
        clinical_score=int(payload.get("clinical_score", 0)),
        clinical_signs=payload.get("clinical_signs"),
        notes=payload.get("notes", ""),
        timestamp=payload.get("timestamp"),
    )
    return {"status": "success", "observation": obs}


@router.get("/experiments")
def list_experiments(current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """List all registered in-vivo studies."""
    experiments = in_vivo_service.list_experiments()
    return {"status": "success", "count": len(experiments), "experiments": experiments}


@router.post("/experiments")
def create_experiment(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Create an ARRIVE 2.0 structured experiment record."""
    exp = in_vivo_service.create_experiment(
        iacuc_protocol_number=payload["iacuc_protocol_number"],
        title=payload["title"],
        primary_investigator=payload.get("primary_investigator") or (current_user.username if current_user else "PI"),
        hypothesis_or_objective=payload.get("hypothesis_or_objective", ""),
        experimental_design_type=payload.get("experimental_design_type", "parallel_cohort"),
        sample_size_rationale=payload.get("sample_size_rationale", ""),
        randomization_procedure=payload.get("randomization_procedure", ""),
        blinding_procedure=payload.get("blinding_procedure", ""),
        inclusion_exclusion_criteria=payload.get("inclusion_exclusion_criteria", ""),
        cohorts=payload.get("cohorts"),
        subject_ids=payload.get("subject_ids"),
    )
    return {"status": "success", "experiment": exp}


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """Fetch details of a single experiment."""
    exp = in_vivo_service.get_experiment(experiment_id)
    if not exp:
        return {"status": "error", "message": f"Experiment '{experiment_id}' not found"}
    return {"status": "success", "experiment": exp}


@router.post("/experiments/{experiment_id}/harvest")
def link_harvested_tissue(
    experiment_id: str, payload: Dict[str, Any], current_user: Optional[UserSession] = None
) -> Dict[str, Any]:
    """Link harvested tissue tube to freezer inventory."""
    tube_id = payload["tube_id"]
    exp = in_vivo_service.link_harvested_tissue(experiment_id, tube_id)
    return {"status": "success", "experiment": exp}


@router.get("/experiments/{experiment_id}/arrive")
def export_arrive_report(
    experiment_id: str, format: str = "html", current_user: Optional[UserSession] = None
) -> Dict[str, Any]:
    """Export ARRIVE 2.0 report in HTML or Markdown."""
    try:
        report = in_vivo_service.export_arrive_report(experiment_id, format=format)
        return {"status": "success", "format": format, "report": report}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
