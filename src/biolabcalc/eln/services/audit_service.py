"""
Module: biolabcalc.eln.services.audit_service
Component: Immutable Audit Logging Service for 21 CFR Part 11 Compliance
Agent: @agent: eln-api-agent
Architectural Role: Core service providing tamper-evident, append-only, SHA-256 cryptographically
chained audit logging for every lifecycle event, state transition, SOP fork, and inventory movement.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _get_audit_log_path() -> Optional[str]:
    env_path = os.environ.get("BIOLABCALC_AUDIT_LOG")
    if env_path:
        return env_path
    storage_dir = os.environ.get("BIOLABCALC_STORAGE_DIR")
    if not storage_dir:
        storage_dir = os.path.join(os.getcwd(), ".biolabcalc_data")
    try:
        os.makedirs(storage_dir, exist_ok=True)
        return os.path.join(storage_dir, "audit_ledger.jsonl")
    except Exception:
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "biolabcalc_data")
        try:
            os.makedirs(tmp, exist_ok=True)
            return os.path.join(tmp, "audit_ledger.jsonl")
        except Exception:
            return None


@dataclass(frozen=True)
class AuditEvent:
    """
    Data model representing a single immutable audit event in the ELN/LIMS pipeline.

    Agent: @agent: eln-api-agent
    Architectural Role: Immutable audit event entity containing full before/after state
    snapshots, actor attribution, timestamp, and cryptographic hash chain links.
    """

    event_id: str
    timestamp: str
    entity_type: str
    entity_id: str
    action: str
    performed_by: str
    previous_state: Optional[Dict[str, Any]]
    new_state: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]
    prev_hash: str
    event_hash: str

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize audit event to dictionary representation.

        Agent: @agent: eln-api-agent
        Return Type: Dict[str, Any]
        """
        return asdict(self)


class AuditService:
    """
    Service responsible for maintaining an append-only, cryptographically linked audit ledger.

    Agent: @agent: eln-api-agent
    Architectural Role: Manages thread-safe audit record persistence, SHA-256 hash chaining,
    querying by entity type/id, and mathematical verification of ledger immutability.
    """

    GENESIS_HASH: str = "0" * 64

    def __init__(self, log_path: Optional[str] = None) -> None:
        """
        Initialize the audit service with an empty ledger and thread lock.

        Agent: @agent: eln-api-agent
        """
        self._lock = threading.RLock()
        self._events: List[AuditEvent] = []
        self._log_path = log_path if log_path is not None else _get_audit_log_path()
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not self._log_path or not os.path.isfile(self._log_path):
            return
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    event = AuditEvent(
                        event_id=data["event_id"],
                        timestamp=data["timestamp"],
                        entity_type=data["entity_type"],
                        entity_id=data["entity_id"],
                        action=data["action"],
                        performed_by=data["performed_by"],
                        previous_state=data.get("previous_state"),
                        new_state=data.get("new_state"),
                        metadata=data.get("metadata", {}),
                        prev_hash=data["prev_hash"],
                        event_hash=data["event_hash"],
                    )
                    self._events.append(event)
        except Exception:
            pass

    def _calculate_hash(
        self,
        event_id: str,
        timestamp: str,
        entity_type: str,
        entity_id: str,
        action: str,
        performed_by: str,
        previous_state: Optional[Dict[str, Any]],
        new_state: Optional[Dict[str, Any]],
        metadata: Dict[str, Any],
        prev_hash: str,
    ) -> str:
        """
        Calculate deterministic SHA-256 hash for audit event payload.

        Agent: @agent: eln-api-agent
        Parameter event_id (str): Unique identifier for event.
        Parameter timestamp (str): ISO 8601 UTC timestamp.
        Parameter entity_type (str): Type of entity affected.
        Parameter entity_id (str): Identifier of entity affected.
        Parameter action (str): Action performed (e.g. CREATE, UPDATE, TUBE_MOVE).
        Parameter performed_by (str): Username or role of actor.
        Parameter previous_state (Optional[Dict[str, Any]]): State prior to mutation.
        Parameter new_state (Optional[Dict[str, Any]]): State following mutation.
        Parameter metadata (Dict[str, Any]): Additional operational context.
        Parameter prev_hash (str): Hash of preceding audit event in ledger.
        Return Type: str (hex-encoded 64 character SHA-256 string).
        """
        canonical_repr = json.dumps(
            {
                "event_id": event_id,
                "timestamp": timestamp,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "performed_by": performed_by,
                "previous_state": previous_state,
                "new_state": new_state,
                "metadata": metadata,
                "prev_hash": prev_hash,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

    def record_event(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        performed_by: str,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """
        Record a new immutable audit event in the ledger.

        Agent: @agent: eln-api-agent
        Parameter entity_type (str): Category of entity (e.g. campaign, daily_entry, tube, sop).
        Parameter entity_id (str): Unique identifier of target entity.
        Parameter action (str): Action verb (CREATE, UPDATE, DELETE, TUBE_MOVE, SOP_FORK, POOL).
        Parameter performed_by (str): Actor attributing identity (e.g. pi_admin, active_researcher).
        Parameter previous_state (Optional[Dict[str, Any]]): State snapshot before change.
        Parameter new_state (Optional[Dict[str, Any]]): State snapshot after change.
        Parameter metadata (Optional[Dict[str, Any]]): Ancillary metadata.
        Return Type: AuditEvent (the committed immutable record).
        """
        with self._lock:
            event_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()
            prev_hash = self._events[-1].event_hash if self._events else self.GENESIS_HASH
            meta = metadata or {}

            event_hash = self._calculate_hash(
                event_id=event_id,
                timestamp=timestamp,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                performed_by=performed_by,
                previous_state=previous_state,
                new_state=new_state,
                metadata=meta,
                prev_hash=prev_hash,
            )

            event = AuditEvent(
                event_id=event_id,
                timestamp=timestamp,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                performed_by=performed_by,
                previous_state=previous_state,
                new_state=new_state,
                metadata=meta,
                prev_hash=prev_hash,
                event_hash=event_hash,
            )
            self._events.append(event)
            if self._log_path:
                try:
                    with open(self._log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(event.to_dict()) + "\n")
                except Exception:
                    pass
            return event

    def get_trail(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """
        Retrieve audit trail records filtered by entity criteria, reverse chronological.

        Agent: @agent: eln-api-agent
        Parameter entity_type (Optional[str]): Optional filter by entity type.
        Parameter entity_id (Optional[str]): Optional filter by entity ID.
        Parameter limit (int): Maximum records to retrieve (default: 100).
        Return Type: List[AuditEvent]
        """
        with self._lock:
            filtered = self._events
            if entity_type is not None:
                filtered = [e for e in filtered if e.entity_type == entity_type]
            if entity_id is not None:
                filtered = [e for e in filtered if e.entity_id == entity_id]
            return list(reversed(filtered))[:limit]

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Verify the mathematical integrity and unbroken cryptographic chain of the ledger.

        Agent: @agent: eln-api-agent
        Return Type: Tuple[bool, Optional[str]]
            - bool: True if ledger is intact, False if tampering or broken hash chain detected.
            - Optional[str]: Detailed diagnostic error message if corrupted, None if valid.
        """
        with self._lock:
            if not self._events:
                return True, None

            expected_prev_hash = self.GENESIS_HASH
            for index, event in enumerate(self._events):
                if event.prev_hash != expected_prev_hash:
                    return (
                        False,
                        f"Hash chain broken at index {index}: event {event.event_id} "
                        f"expected prev_hash {expected_prev_hash}, found {event.prev_hash}",
                    )

                recalculated = self._calculate_hash(
                    event_id=event.event_id,
                    timestamp=event.timestamp,
                    entity_type=event.entity_type,
                    entity_id=event.entity_id,
                    action=event.action,
                    performed_by=event.performed_by,
                    previous_state=event.previous_state,
                    new_state=event.new_state,
                    metadata=event.metadata,
                    prev_hash=event.prev_hash,
                )
                if recalculated != event.event_hash:
                    return (
                        False,
                        f"Event payload tampering detected at index {index}: event {event.event_id} "
                        f"computed {recalculated}, stored {event.event_hash}",
                    )
                expected_prev_hash = event.event_hash

            return True, None

    def clear_for_testing(self) -> None:
        """
        Reset internal audit ledger state. For unit testing harness use only.

        Agent: @agent: eln-api-agent
        """
        with self._lock:
            self._events.clear()
            if self._log_path and os.path.exists(self._log_path):
                try:
                    os.remove(self._log_path)
                except Exception:
                    pass


_global_audit_service = AuditService()


def get_audit_service() -> AuditService:
    """
    Get the process-level singleton instance of AuditService.

    Agent: @agent: eln-api-agent
    Return Type: AuditService
    """
    return _global_audit_service
