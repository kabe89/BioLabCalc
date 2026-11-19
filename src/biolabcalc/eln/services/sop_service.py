"""
Module: biolabcalc.eln.services.sop_service
Component: Standard Operating Procedure (SOP) Versioning & Execution Forking Engine
Architectural Role: Core service providing regulatory SOP lifecycle management, semantic versioning,
and "Instantiate SOP into Daily Notebook Entry" execution forking with locked parameter state
and structured step checklists.
"""

from __future__ import annotations

import copy
import logging
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .audit_service import get_audit_service
from ..storage.sqlite_store import SQLiteStore, get_sqlite_store

logger = logging.getLogger("biolabcalc.eln.services.sop_service")


@dataclass
class SOPStep:
    """
    Structured step instruction within an SOP protocol checklist.

    Architectural Role: Atomic operational protocol step with expected duration, reagent requirements,
    and checkpoint criteria.
    """

    step_index: int
    name: str
    instruction: str
    planned_duration_minutes: Optional[float] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    required_inputs: List[str] = field(default_factory=list)
    required_outputs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize step to dictionary.

        Return Type: Dict[str, Any]
        """
        return asdict(self)


@dataclass
class MasterSOP:
    """
    Master Standard Operating Procedure entity with version control and parameter specifications.

    Architectural Role: Master protocol blueprint defining standardized parameters and sequential steps.
    """

    sop_id: str
    title: str
    version: str
    category: str  # Expression, Purification, Molecular Biology, Analytics
    description: str
    parameters: Dict[str, Any]
    steps: List[SOPStep]
    status: str  # draft, approved, deprecated
    created_by: str
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize Master SOP to dictionary.

        Return Type: Dict[str, Any]
        """
        return {
            "sop_id": self.sop_id,
            "title": self.title,
            "version": self.version,
            "category": self.category,
            "description": self.description,
            "parameters": self.parameters,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class StepExecution:
    """
    Checklist execution instance for an instantiated SOP step.

    Architectural Role: Records operator checkoff, execution timestamp, actual duration, and deviations.
    """

    step_index: int
    name: str
    instruction: str
    planned_duration_minutes: Optional[float]
    status: str  # pending, in_progress, completed, skipped
    completed_at: Optional[str] = None
    completed_by: Optional[str] = None
    actual_duration_minutes: Optional[float] = None
    deviation_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize step execution to dictionary.

        Return Type: Dict[str, Any]
        """
        return asdict(self)


@dataclass
class SOPFork:
    """
    Instantiated execution fork of an SOP locked to a specific daily notebook entry.

    Architectural Role: GxP-compliant frozen execution instance locking the SOP version,
    parameter snapshot, and interactive checklist to protect historical reproducibility.
    """

    fork_id: str
    sop_id: str
    sop_version: str
    sop_title: str
    entry_id: str
    forked_by: str
    forked_at: str
    locked_parameters: Dict[str, Any]
    step_executions: List[StepExecution]
    is_completed: bool = False
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize SOP fork to dictionary.

        Return Type: Dict[str, Any]
        """
        return {
            "fork_id": self.fork_id,
            "sop_id": self.sop_id,
            "sop_version": self.sop_version,
            "sop_title": self.sop_title,
            "entry_id": self.entry_id,
            "forked_by": self.forked_by,
            "forked_at": self.forked_at,
            "locked_parameters": self.locked_parameters,
            "step_executions": [s.to_dict() for s in self.step_executions],
            "is_completed": self.is_completed,
            "completed_at": self.completed_at,
        }


class SOPService:
    """
    Service managing SOP versioning and immutable execution forking.

    Architectural Role: Governs master SOP catalog, approval workflows, and forking into daily
    notebook entries with parameter lock-in.
    """

    def __init__(self, store: Optional[SQLiteStore] = None) -> None:
        """
        Initialize SOPService repository with SQLite persistence and thread synchronization.
        """
        self._lock = threading.RLock()
        self._store = store or get_sqlite_store()
        self._sops: Dict[str, MasterSOP] = {}
        self._forks: Dict[str, SOPFork] = {}
        self._audit_service = get_audit_service()
        self._load_from_store()

    def _load_from_store(self) -> None:
        try:
            for item in self._store.list_entities("sop"):
                steps = [SOPStep(**s) if isinstance(s, dict) else s for s in item.get("steps", [])]
                sop = MasterSOP(
                    sop_id=item["sop_id"],
                    title=item.get("title", ""),
                    version=item.get("version", "1.0"),
                    category=item.get("category", ""),
                    description=item.get("description", ""),
                    parameters=item.get("parameters", {}),
                    steps=steps,
                    status=item.get("status", "draft"),
                    created_by=item.get("created_by", "unknown"),
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                )
                self._sops[sop.sop_id] = sop

            for item in self._store.list_entities("sop_fork"):
                step_execs = [
                    StepExecution(**s) if isinstance(s, dict) else s
                    for s in item.get("step_executions", [])
                ]
                fork = SOPFork(
                    fork_id=item["fork_id"],
                    sop_id=item.get("sop_id", ""),
                    sop_version=item.get("sop_version", "1.0"),
                    sop_title=item.get("sop_title", ""),
                    entry_id=item.get("entry_id", ""),
                    forked_by=item.get("forked_by", "unknown"),
                    forked_at=item.get("forked_at", ""),
                    locked_parameters=item.get("locked_parameters", {}),
                    step_executions=step_execs,
                    is_completed=item.get("is_completed", False),
                    completed_at=item.get("completed_at"),
                )
                self._forks[fork.fork_id] = fork
        except Exception as e:
            logger.warning(f"Error loading SOPs/forks from SQLite: {e}")

    def _save_sop(self, sop: MasterSOP) -> None:
        self._sops[sop.sop_id] = sop
        try:
            self._store.put_entity("sop", sop.sop_id, sop.to_dict())
        except Exception as e:
            logger.warning(f"Failed to persist SOP {sop.sop_id}: {e}")

    def _save_fork(self, fork: SOPFork) -> None:
        self._forks[fork.fork_id] = fork
        try:
            self._store.put_entity("sop_fork", fork.fork_id, fork.to_dict())
        except Exception as e:
            logger.warning(f"Failed to persist SOP fork {fork.fork_id}: {e}")

    def create_sop(
        self,
        sop_id: str,
        title: str,
        version: str,
        category: str,
        description: str,
        parameters: Dict[str, Any],
        steps: List[Dict[str, Any]],
        created_by: str,
    ) -> MasterSOP:
        """
        Register a new master SOP protocol.

        Parameter sop_id (str): Unique SOP code (e.g. SOP-PCR-002).
        Parameter title (str): Descriptive title.
        Parameter version (str): Version identifier (e.g. '1.0').
        Parameter category (str): Scientific category.
        Parameter description (str): Summary and scope.
        Parameter parameters (Dict[str, Any]): Standard default protocol parameters.
        Parameter steps (List[Dict[str, Any]]): Ordered list of step dictionaries.
        Parameter created_by (str): Author ID.
        Return Type: MasterSOP
        """
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            step_objs: List[SOPStep] = []
            for idx, s in enumerate(steps, start=1):
                step_objs.append(
                    SOPStep(
                        step_index=s.get("step_index", idx),
                        name=s.get("name", f"Step {idx}"),
                        instruction=s.get("instruction", ""),
                        planned_duration_minutes=s.get("planned_duration_minutes"),
                        parameters=s.get("parameters", {}),
                        required_inputs=s.get("required_inputs", []),
                        required_outputs=s.get("required_outputs", []),
                    )
                )

            sop = MasterSOP(
                sop_id=sop_id,
                title=title,
                version=version,
                category=category,
                description=description,
                parameters=parameters,
                steps=step_objs,
                status="draft",
                created_by=created_by,
                created_at=now_iso,
                updated_at=now_iso,
            )
            self._save_sop(sop)

            self._audit_service.record_event(
                entity_type="sop",
                entity_id=sop_id,
                action="CREATE",
                performed_by=created_by,
                previous_state=None,
                new_state=sop.to_dict(),
                metadata={"version": version, "category": category},
            )
            return sop

    def approve_sop(self, sop_id: str, approver_id: str) -> MasterSOP:
        """
        Approve an SOP, locking it for clinical or experimental execution.

        Parameter sop_id (str): Target SOP ID.
        Parameter approver_id (str): Authorizing PI or lab administrator.
        Return Type: MasterSOP
        """
        with self._lock:
            sop = self._sops.get(sop_id)
            if not sop:
                raise KeyError(f"SOP with ID '{sop_id}' not found.")

            prev_state = sop.to_dict()
            sop.status = "approved"
            sop.updated_at = datetime.now(timezone.utc).isoformat()
            self._save_sop(sop)

            self._audit_service.record_event(
                entity_type="sop",
                entity_id=sop_id,
                action="APPROVE",
                performed_by=approver_id,
                previous_state=prev_state,
                new_state=sop.to_dict(),
                metadata={"approved_version": sop.version},
            )
            return sop

    def get_sop(self, sop_id: str) -> Optional[MasterSOP]:
        """
        Retrieve master SOP by ID.

        Parameter sop_id (str): SOP ID.
        Return Type: Optional[MasterSOP]
        """
        with self._lock:
            return self._sops.get(sop_id)

    def list_sops(self, category: Optional[str] = None, status: Optional[str] = None) -> List[MasterSOP]:
        """
        List SOPs filtered by category and status.

        Parameter category (Optional[str]): Category filter.
        Parameter status (Optional[str]): Status filter.
        Return Type: List[MasterSOP]
        """
        with self._lock:
            sops = list(self._sops.values())
            if category:
                sops = [s for s in sops if s.category == category]
            if status:
                sops = [s for s in sops if s.status == status]
            return sops

    def fork_sop_for_entry(
        self,
        sop_id: str,
        entry_id: str,
        forked_by: str,
        parameter_overrides: Optional[Dict[str, Any]] = None,
    ) -> SOPFork:
        """
        Instantiate an SOP into a Daily Notebook Entry, locking parameter state and creating execution checklist.

        GxP Requirement: Creates an immutable snapshot of the SOP version, parameters (with any approved
        overrides merged), and sequential step checklist. Subsequent edits to master SOP do not modify
        this frozen fork.

        Parameter sop_id (str): Master SOP ID.
        Parameter entry_id (str): Daily notebook entry ID.
        Parameter forked_by (str): Operator username.
        Parameter parameter_overrides (Optional[Dict[str, Any]]): Custom overrides for this execution run.
        Return Type: SOPFork
        """
        with self._lock:
            master = self._sops.get(sop_id)
            if not master:
                raise KeyError(f"Master SOP '{sop_id}' does not exist.")

            if master.status != "approved":
                raise ValueError(
                    f"Cannot fork SOP '{sop_id}' with status '{master.status}'. Only approved SOPs can be executed in experimental entries."
                )

            # Create deep copy of parameters and merge overrides
            locked_params = copy.deepcopy(master.parameters)
            if parameter_overrides:
                locked_params.update(parameter_overrides)

            fork_id = f"FORK-{sop_id}-{uuid.uuid4().hex[:6].upper()}"
            now_iso = datetime.now(timezone.utc).isoformat()

            step_execs = [
                StepExecution(
                    step_index=s.step_index,
                    name=s.name,
                    instruction=s.instruction,
                    planned_duration_minutes=s.planned_duration_minutes,
                    status="pending",
                )
                for s in master.steps
            ]

            fork = SOPFork(
                fork_id=fork_id,
                sop_id=master.sop_id,
                sop_version=master.version,
                sop_title=master.title,
                entry_id=entry_id,
                forked_by=forked_by,
                forked_at=now_iso,
                locked_parameters=locked_params,
                step_executions=step_execs,
                is_completed=False,
            )
            self._save_fork(fork)

            self._audit_service.record_event(
                entity_type="sop_fork",
                entity_id=fork_id,
                action="SOP_FORK",
                performed_by=forked_by,
                previous_state=None,
                new_state=fork.to_dict(),
                metadata={
                    "sop_id": master.sop_id,
                    "sop_version": master.version,
                    "entry_id": entry_id,
                },
            )
            return fork

    def get_fork(self, fork_id: str) -> Optional[SOPFork]:
        """
        Retrieve instantiated SOP fork by ID.

        Parameter fork_id (str): Fork identifier.
        Return Type: Optional[SOPFork]
        """
        with self._lock:
            return self._forks.get(fork_id)

    def checkoff_step(
        self,
        fork_id: str,
        step_index: int,
        completed_by: str,
        actual_duration_minutes: Optional[float] = None,
        deviation_notes: str = "",
    ) -> SOPFork:
        """
        Record checkoff completion of an instantiated step checklist item.

        Parameter fork_id (str): Target SOP fork ID.
        Parameter step_index (int): Ordinal step index (1-based).
        Parameter completed_by (str): Operator ID.
        Parameter actual_duration_minutes (Optional[float]): Actual duration in minutes.
        Parameter deviation_notes (str): Operator explanation if procedure deviated.
        Return Type: SOPFork
        """
        with self._lock:
            fork = self._forks.get(fork_id)
            if not fork:
                raise KeyError(f"SOP Fork '{fork_id}' not found.")

            target_step = next((s for s in fork.step_executions if s.step_index == step_index), None)
            if not target_step:
                raise KeyError(f"Step index {step_index} not found in fork '{fork_id}'.")

            prev_state = fork.to_dict()
            now_iso = datetime.now(timezone.utc).isoformat()

            target_step.status = "completed"
            target_step.completed_at = now_iso
            target_step.completed_by = completed_by
            target_step.actual_duration_minutes = actual_duration_minutes
            target_step.deviation_notes = deviation_notes

            # Check if all steps completed
            if all(s.status == "completed" for s in fork.step_executions):
                fork.is_completed = True
                fork.completed_at = now_iso

            self._save_fork(fork)

            self._audit_service.record_event(
                entity_type="sop_fork",
                entity_id=fork_id,
                action="STEP_CHECKOFF",
                performed_by=completed_by,
                previous_state=prev_state,
                new_state=fork.to_dict(),
                metadata={"step_index": step_index, "deviation_notes": deviation_notes},
            )
            return fork

    def clear_for_testing(self) -> None:
        """
        Reset internal SOP and fork state. For unit testing harness use only.

        """
        with self._lock:
            for sid in list(self._sops.keys()):
                try:
                    self._store.delete_entity("sop", sid)
                except Exception:
                    pass
            for fid in list(self._forks.keys()):
                try:
                    self._store.delete_entity("sop_fork", fid)
                except Exception:
                    pass
            self._sops.clear()
            self._forks.clear()


_global_sop_service = SOPService()


def get_sop_service() -> SOPService:
    """
    Get the process-level singleton instance of SOPService.

    Return Type: SOPService
    """
    return _global_sop_service
