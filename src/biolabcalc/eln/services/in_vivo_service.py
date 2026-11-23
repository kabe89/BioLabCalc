"""
Module: biolabcalc.eln.services.in_vivo_service
Component: In-Vivo Mouse Experiment Documentation & ARRIVE 2.0 Management Service
Architectural Role: Core ELN service governing mouse strains, subjects, longitudinal welfare
observations, humane endpoints, tissue harvesting linkages to freezer tubes, and ARRIVE 2.0 reporting.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..storage.sqlite_store import SQLiteStore, get_sqlite_store
from ...in_vivo import (
    MouseStrainModel,
    MouseSubject,
    MouseObservation,
    MouseExperimentRecord,
    evaluate_mouse_welfare,
    export_arrive_report_html,
    export_arrive_report_markdown,
)

logger = logging.getLogger("biolabcalc.eln.services.in_vivo_service")


class InVivoService:
    """Thread-safe persistent service managing in-vivo mouse models and ARRIVE 2.0 experiments."""

    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        self._store = store or get_sqlite_store()
        self._lock = threading.RLock()

    def create_strain(
        self,
        name: str,
        rrid: str = "",
        stock_number: str = "",
        genetic_background: str = "C57BL/6J",
        modified_alleles: Optional[List[str]] = None,
        phenotype_notes: str = "",
        breeding_scheme: str = "",
        vendor_or_source: str = "Jackson Laboratory",
    ) -> Dict[str, Any]:
        """Register a new mouse genetic strain."""
        with self._lock:
            strain_id = f"strain_{uuid.uuid4().hex[:10]}"
            now_iso = datetime.now(timezone.utc).isoformat()
            data = {
                "strain_id": strain_id,
                "name": name,
                "rrid": rrid,
                "stock_number": stock_number,
                "genetic_background": genetic_background,
                "modified_alleles": modified_alleles or [],
                "phenotype_notes": phenotype_notes,
                "breeding_scheme": breeding_scheme,
                "vendor_or_source": vendor_or_source,
                "created_at": now_iso,
            }
            self._store.put_entity("mouse_strain", strain_id, data)
            logger.info(f"Created mouse strain '{name}' ({strain_id})")
            return data

    def get_strain(self, strain_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve strain by identifier."""
        return self._store.get_entity("mouse_strain", strain_id)

    def list_strains(self) -> List[Dict[str, Any]]:
        """List all registered mouse strains."""
        return self._store.list_entities("mouse_strain")

    def create_subject(
        self,
        ear_tag: str,
        strain_id: str,
        sex: str = "M",
        date_of_birth: Optional[str] = None,
        genotype: str = "WT",
        cage_id: str = "",
        litter_id: str = "",
        baseline_weight_g: float = 25.0,
        cohort: str = "",
    ) -> Dict[str, Any]:
        """Enroll an individual mouse subject."""
        with self._lock:
            subject_id = ear_tag.strip() or f"mouse_{uuid.uuid4().hex[:8]}"
            now_iso = datetime.now(timezone.utc).isoformat()
            data = {
                "subject_id": subject_id,
                "strain_id": strain_id,
                "sex": sex.upper(),
                "date_of_birth": date_of_birth,
                "genotype": genotype,
                "cage_id": cage_id,
                "litter_id": litter_id,
                "baseline_weight_g": float(baseline_weight_g),
                "status": "active",
                "assigned_cohort": cohort,
                "created_at": now_iso,
            }
            self._store.put_entity("mouse_subject", subject_id, data)
            logger.info(f"Enrolled mouse subject '{subject_id}' (strain {strain_id})")
            return data

    def get_subject(self, subject_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve subject by identifier."""
        return self._store.get_entity("mouse_subject", subject_id)

    def list_subjects(
        self,
        strain_id: Optional[str] = None,
        cage_id: Optional[str] = None,
        cohort: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List subjects with optional filters."""
        subs = self._store.list_entities("mouse_subject")
        if strain_id:
            subs = [s for s in subs if s.get("strain_id") == strain_id]
        if cage_id:
            subs = [s for s in subs if s.get("cage_id") == cage_id]
        if cohort:
            subs = [s for s in subs if s.get("assigned_cohort") == cohort]
        return subs

    def log_observation(
        self,
        subject_id: str,
        weight_g: float,
        clinical_score: int = 0,
        clinical_signs: Optional[List[str]] = None,
        notes: str = "",
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Log longitudinal clinical observation, evaluating welfare and humane endpoints."""
        with self._lock:
            sub = self.get_subject(subject_id)
            baseline = float(sub.get("baseline_weight_g", 25.0)) if sub else 25.0

            obs_id = f"obs_{uuid.uuid4().hex[:10]}"
            ts = timestamp or datetime.now(timezone.utc).isoformat()

            obs_result = evaluate_mouse_welfare(
                baseline_weight_g=baseline,
                current_weight_g=float(weight_g),
                clinical_score=clinical_score,
                clinical_signs=clinical_signs,
                subject_id=subject_id,
                observation_id=obs_id,
                timestamp=ts,
            )

            data = {
                "observation_id": obs_id,
                "subject_id": subject_id,
                "timestamp": ts,
                "weight_g": obs_result.weight_g,
                "baseline_weight_g": obs_result.baseline_weight_g,
                "weight_change_pct": obs_result.weight_change_pct,
                "clinical_score": obs_result.clinical_score,
                "clinical_signs": list(obs_result.clinical_signs),
                "is_humane_endpoint": obs_result.is_humane_endpoint,
                "endpoint_reasons": list(obs_result.endpoint_reasons),
                "action_taken": obs_result.action_taken,
                "notes": notes,
            }
            self._store.put_entity("mouse_observation", obs_id, data)

            # Update subject status if critical endpoint reached
            if obs_result.is_humane_endpoint and sub:
                sub["status"] = "humane_endpoint"
                sub["endpoint_reached_at"] = ts
                self._store.put_entity("mouse_subject", subject_id, sub)
                logger.warning(f"HUMANE ENDPOINT REACHED for subject '{subject_id}': {obs_result.endpoint_reasons}")

            return data

    def list_observations(self, subject_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List longitudinal observations, optionally filtered by animal."""
        obs = self._store.list_entities("mouse_observation")
        if subject_id:
            obs = [o for o in obs if o.get("subject_id") == subject_id]
        return sorted(obs, key=lambda x: x.get("timestamp", ""))

    def create_experiment(
        self,
        iacuc_protocol_number: str,
        title: str,
        primary_investigator: str,
        hypothesis_or_objective: str = "",
        experimental_design_type: str = "parallel_cohort",
        sample_size_rationale: str = "",
        randomization_procedure: str = "",
        blinding_procedure: str = "",
        inclusion_exclusion_criteria: str = "",
        cohorts: Optional[List[str]] = None,
        subject_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create an ARRIVE 2.0 structured in-vivo experiment record."""
        with self._lock:
            exp_id = f"mexp_{uuid.uuid4().hex[:10]}"
            now_iso = datetime.now(timezone.utc).isoformat()
            data = {
                "experiment_id": exp_id,
                "iacuc_protocol_number": iacuc_protocol_number,
                "title": title,
                "primary_investigator": primary_investigator,
                "hypothesis_or_objective": hypothesis_or_objective,
                "experimental_design_type": experimental_design_type,
                "sample_size_rationale": sample_size_rationale,
                "randomization_procedure": randomization_procedure,
                "blinding_procedure": blinding_procedure,
                "inclusion_exclusion_criteria": inclusion_exclusion_criteria,
                "cohorts": cohorts or [],
                "subject_ids": subject_ids or [],
                "harvested_tissue_tube_ids": [],
                "adverse_events_summary": "",
                "created_at": now_iso,
            }
            self._store.put_entity("mouse_experiment", exp_id, data)
            logger.info(f"Created in-vivo experiment '{title}' ({exp_id})")
            return data

    def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve experiment record."""
        return self._store.get_entity("mouse_experiment", experiment_id)

    def list_experiments(self) -> List[Dict[str, Any]]:
        """List all in-vivo experiments."""
        return self._store.list_entities("mouse_experiment")

    def link_harvested_tissue(self, experiment_id: str, tube_id: str) -> Dict[str, Any]:
        """Link an ELN freezer inventory tube ID (harvested organ/tissue) to the experiment."""
        with self._lock:
            exp = self.get_experiment(experiment_id)
            if not exp:
                raise ValueError(f"Experiment '{experiment_id}' not found.")
            tubes = exp.get("harvested_tissue_tube_ids", [])
            if tube_id not in tubes:
                tubes.append(tube_id)
                exp["harvested_tissue_tube_ids"] = tubes
                self._store.put_entity("mouse_experiment", experiment_id, exp)
                logger.info(f"Linked tissue tube '{tube_id}' to experiment '{experiment_id}'")
            return exp

    def export_arrive_report(self, experiment_id: str, format: str = "html") -> str:
        """Export comprehensive ARRIVE 2.0 report in HTML or Markdown."""
        exp = self.get_experiment(experiment_id)
        if not exp:
            raise ValueError(f"Experiment '{experiment_id}' not found.")

        # Reconstruct dataclasses
        subjects = []
        for s_id in exp.get("subject_ids", []):
            s_dict = self.get_subject(s_id)
            if s_dict:
                subjects.append(
                    MouseSubject(
                        subject_id=s_dict["subject_id"],
                        strain_id=s_dict["strain_id"],
                        sex=s_dict.get("sex", "M"),
                        date_of_birth=s_dict.get("date_of_birth"),
                        genotype=s_dict.get("genotype", "WT"),
                        cage_id=s_dict.get("cage_id", ""),
                        litter_id=s_dict.get("litter_id", ""),
                        baseline_weight_g=float(s_dict.get("baseline_weight_g", 25.0)),
                        status=s_dict.get("status", "active"),
                        assigned_cohort=s_dict.get("assigned_cohort", ""),
                    )
                )

        # Collect observations efficiently: query store once and group by subject ID
        subject_id_set = {s.subject_id for s in subjects}
        all_obs = self._store.list_entities("mouse_observation")
        obs_by_subject: Dict[str, List[Dict[str, Any]]] = {}
        for o in all_obs:
            sid = o.get("subject_id")
            if sid in subject_id_set:
                obs_by_subject.setdefault(sid, []).append(o)

        observations = []
        for s in subjects:
            s_obs = sorted(obs_by_subject.get(s.subject_id, []), key=lambda x: x.get("timestamp", ""))
            for o_dict in s_obs:
                observations.append(
                    MouseObservation(
                        observation_id=o_dict["observation_id"],
                        subject_id=o_dict["subject_id"],
                        timestamp=o_dict["timestamp"],
                        weight_g=float(o_dict["weight_g"]),
                        baseline_weight_g=float(o_dict["baseline_weight_g"]),
                        weight_change_pct=float(o_dict["weight_change_pct"]),
                        clinical_score=int(o_dict.get("clinical_score", 0)),
                        clinical_signs=tuple(o_dict.get("clinical_signs", [])),
                        is_humane_endpoint=bool(o_dict.get("is_humane_endpoint", False)),
                        endpoint_reasons=tuple(o_dict.get("endpoint_reasons", [])),
                        action_taken=o_dict.get("action_taken", ""),
                    )
                )

        rec = MouseExperimentRecord(
            experiment_id=exp["experiment_id"],
            iacuc_protocol_number=exp["iacuc_protocol_number"],
            title=exp["title"],
            hypothesis_or_objective=exp.get("hypothesis_or_objective", ""),
            primary_investigator=exp["primary_investigator"],
            experimental_design_type=exp.get("experimental_design_type", "parallel_cohort"),
            sample_size_rationale=exp.get("sample_size_rationale", ""),
            randomization_procedure=exp.get("randomization_procedure", ""),
            blinding_procedure=exp.get("blinding_procedure", ""),
            inclusion_exclusion_criteria=exp.get("inclusion_exclusion_criteria", ""),
            cohorts=tuple(exp.get("cohorts", [])),
            subjects=tuple(subjects),
            observations=tuple(observations),
            harvested_tissue_tube_ids=tuple(exp.get("harvested_tissue_tube_ids", [])),
            adverse_events_summary=exp.get("adverse_events_summary", ""),
            created_at=exp.get("created_at", ""),
        )

        if format.lower() == "md" or format.lower() == "markdown":
            return export_arrive_report_markdown(rec)
        return export_arrive_report_html(rec)


_in_vivo_service_instance: Optional[InVivoService] = None
_in_vivo_service_lock = threading.Lock()


def get_in_vivo_service() -> InVivoService:
    """Retrieve singleton instance of InVivoService."""
    global _in_vivo_service_instance
    if _in_vivo_service_instance is None:
        with _in_vivo_service_lock:
            if _in_vivo_service_instance is None:
                _in_vivo_service_instance = InVivoService()
    return _in_vivo_service_instance
