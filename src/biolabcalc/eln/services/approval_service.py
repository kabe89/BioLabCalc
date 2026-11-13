"""
Module: biolabcalc.eln.services.approval_service
Component: Approval & Governance Workflow Service for Electronic Lab Notebook & LIMS Pipeline
Architectural Role: Governing multi-policy peer review, designated reviewer routing, PI formal approval,
and open collaboration workflows with 21 CFR Part 11 compliant cryptographic tamper-evident seals.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from ..api.auth import (
    ROLE_ACTIVE_RESEARCHER,
    ROLE_ALUMNI_READONLY,
    ROLE_GUEST,
    ROLE_PI_ADMIN,
    ROLE_ROTATION_STUDENT,
    AuthorizationError,
)
from .audit_service import AuditService, get_audit_service


class ApprovalPolicy(str, Enum):
    """
    Governance policies regulating lab notebook entry approvals.

    Architectural Role: Dictates the approval routing, role requirements,
    and delegation constraints for final verification.
    """

    OPEN_COLLABORATION = "OPEN_COLLABORATION"
    PEER_REVIEW = "PEER_REVIEW"
    DESIGNATED_REVIEWER = "DESIGNATED_REVIEWER"
    PI_APPROVAL = "PI_APPROVAL"


class ApprovalStatus(str, Enum):
    """
    Lifecycle status states for an approval request.

    Architectural Role: Enforces sequential state progression from draft to final approved seal.
    """

    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    ARCHIVED = "ARCHIVED"


class ApprovalAuthorizationError(AuthorizationError, PermissionError):
    """
    Exception raised when an actor lacks permission under the active approval policy.
    Inherits from both AuthorizationError and PermissionError for universal exception handling.
    """

    pass


def normalize_policy(val: Union[ApprovalPolicy, str]) -> ApprovalPolicy:
    """Normalize string or enum into canonical ApprovalPolicy enum."""
    if isinstance(val, ApprovalPolicy):
        return val
    if not isinstance(val, str):
        raise ValueError(f"Invalid policy type: {type(val)}")
    upper_val = val.strip().upper()
    try:
        return ApprovalPolicy(upper_val)
    except ValueError:
        valid_policies = [p.value for p in ApprovalPolicy]
        raise ValueError(f"Unknown approval policy: '{val}'. Expected one of {valid_policies}")


def normalize_status(val: Union[ApprovalStatus, str]) -> ApprovalStatus:
    """Normalize string or enum into canonical ApprovalStatus enum."""
    if isinstance(val, ApprovalStatus):
        return val
    upper_val = str(val).strip().upper()
    try:
        return ApprovalStatus(upper_val)
    except ValueError:
        valid_statuses = [s.value for s in ApprovalStatus]
        raise ValueError(f"Unknown approval status: '{val}'. Expected one of {valid_statuses}")


@dataclass
class ApprovalHistoryEvent:
    """
    Immutable historical audit event capturing an approval lifecycle transition.
    Supports both object attribute access and dictionary subscripting.
    """

    event_id: str
    entry_id: str
    action: str  # SUBMIT, AUTO_FINALIZE, SIGN_AND_APPROVE, REQUEST_CHANGES, RESUBMIT, ARCHIVE
    performed_by: str
    role: Optional[str]
    status: str
    timestamp: str
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary representation."""
        return asdict(self)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass
class ApprovalRecord:
    """
    Lab notebook approval entity tracking review status, nominated reviewers, and cryptographic seal.
    """

    entry_id: str
    author_id: str
    policy: ApprovalPolicy
    status: ApprovalStatus
    designated_reviewer_id: Optional[str] = None
    data_digest: str = ""
    reviewer_id: Optional[str] = None
    reviewer_role: Optional[str] = None
    review_notes: str = ""
    revision_comments: Optional[str] = None
    checklists_verified: bool = False
    signature_hash: Optional[str] = None
    timestamp: Optional[str] = None
    submitted_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize approval record to JSON-compatible dictionary."""
        return {
            "entry_id": self.entry_id,
            "author_id": self.author_id,
            "policy": self.policy.value if hasattr(self.policy, "value") else str(self.policy),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "designated_reviewer_id": self.designated_reviewer_id,
            "data_digest": self.data_digest,
            "reviewer_id": self.reviewer_id,
            "reviewer_role": self.reviewer_role,
            "review_notes": self.review_notes,
            "revision_comments": self.revision_comments,
            "checklists_verified": self.checklists_verified,
            "signature_hash": self.signature_hash,
            "timestamp": self.timestamp,
            "submitted_at": self.submitted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class ApprovalService:
    """
    Core service orchestrating governance, review policies, cryptographic tamper-evident signing,
    and 21 CFR Part 11 electronic records compliance for the ELN & LIMS pipeline.
    """

    def __init__(self, audit_service: Optional[AuditService] = None) -> None:
        """
        Initialize the approval service with thread safety lock and in-memory registry.
        """
        self._lock = threading.RLock()
        self._records: Dict[str, ApprovalRecord] = {}
        self._history: Dict[str, List[ApprovalHistoryEvent]] = {}
        self._audit_service = audit_service or get_audit_service()

    @staticmethod
    def verify_seal(
        entry_id: str,
        signature_hash: str,
        author_id: str,
        data_digest: str,
        reviewer_id: str,
        timestamp: str,
    ) -> bool:
        """
        Verify cryptographic tamper-evident seal against expected SHA-256 hash.

        Calculates:
            hashlib.sha256(f"{entry_id}:{author_id}:{data_digest}:{reviewer_id}:{timestamp}".encode()).hexdigest()

        Parameter entry_id (str): Target notebook entry identifier.
        Parameter signature_hash (str): Cryptographic seal to verify.
        Parameter author_id (str): Original author identifier.
        Parameter data_digest (str): Cryptographic checksum of notebook entry content.
        Parameter reviewer_id (str): Approving reviewer identifier.
        Parameter timestamp (str): Timestamp recorded during sign off.
        Return Type: bool (True if untampered, False if mismatch or tampered)
        """
        if not signature_hash or not isinstance(signature_hash, str):
            return False
        expected_raw = f"{entry_id}:{author_id}:{data_digest}:{reviewer_id}:{timestamp}".encode("utf-8")
        expected_hash = hashlib.sha256(expected_raw).hexdigest()
        return hmac.compare_digest(expected_hash, signature_hash)

    def submit_for_review(
        self,
        entry_id: str,
        author_id: str,
        policy: Union[ApprovalPolicy, str] = ApprovalPolicy.PEER_REVIEW,
        designated_reviewer_id: Optional[str] = None,
        data_digest: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ApprovalRecord:
        """
        Submit a notebook entry for governance review according to the designated policy.

        Parameter entry_id (str): Unique notebook entry ID.
        Parameter author_id (str): ID of researcher submitting the entry.
        Parameter policy (Union[ApprovalPolicy, str]): Desired approval policy.
        Parameter designated_reviewer_id (Optional[str]): Reviewer ID required for DESIGNATED_REVIEWER.
        Parameter data_digest (Optional[str]): Checksum of entry content. Defaults to deterministic hash.
        Parameter metadata (Optional[Dict[str, Any]]): Additional submission metadata.
        Return Type: ApprovalRecord
        """
        with self._lock:
            if not entry_id or not entry_id.strip():
                raise ValueError("entry_id is required.")
            if not author_id or not author_id.strip():
                raise ValueError("author_id is required.")

            active_policy = normalize_policy(policy)
            now_iso = datetime.now(timezone.utc).isoformat()
            digest = data_digest or hashlib.sha256(f"digest:{entry_id}:{now_iso}".encode("utf-8")).hexdigest()
            meta = dict(metadata or {})

            existing = self._records.get(entry_id)

            if existing is not None:
                if existing.status == ApprovalStatus.APPROVED:
                    raise ValueError(f"Entry '{entry_id}' is already approved and sealed.")
                if existing.status == ApprovalStatus.PENDING_REVIEW:
                    raise ValueError(f"Entry '{entry_id}' is already pending review.")
                # Resubmission from CHANGES_REQUESTED or DRAFT
                is_resubmission = existing.status == ApprovalStatus.CHANGES_REQUESTED
            else:
                is_resubmission = False

            # Policy-specific validation during submission
            if active_policy == ApprovalPolicy.DESIGNATED_REVIEWER:
                if not designated_reviewer_id or not designated_reviewer_id.strip():
                    raise ValueError("designated_reviewer_id is required when policy is DESIGNATED_REVIEWER.")
                if designated_reviewer_id.strip() == author_id.strip():
                    raise ValueError("Author cannot nominate themselves as the designated reviewer.")

            # OPEN_COLLABORATION: Auto-finalized immediately upon submission
            if active_policy == ApprovalPolicy.OPEN_COLLABORATION:
                signature_hash = hashlib.sha256(
                    f"{entry_id}:{author_id}:{digest}:{author_id}:{now_iso}".encode("utf-8")
                ).hexdigest()

                record = ApprovalRecord(
                    entry_id=entry_id,
                    author_id=author_id,
                    policy=active_policy,
                    status=ApprovalStatus.APPROVED,
                    designated_reviewer_id=None,
                    data_digest=digest,
                    reviewer_id=author_id,
                    reviewer_role=ROLE_ACTIVE_RESEARCHER,
                    review_notes="Auto-finalized upon submission under OPEN_COLLABORATION policy.",
                    revision_comments=None,
                    checklists_verified=True,
                    signature_hash=signature_hash,
                    timestamp=now_iso,
                    submitted_at=now_iso,
                    created_at=existing.created_at if existing else now_iso,
                    updated_at=now_iso,
                    metadata=meta,
                )
                self._records[entry_id] = record

                action = "RESUBMIT_AND_AUTO_FINALIZE" if is_resubmission else "SUBMIT_AND_AUTO_FINALIZE"
                self._record_history_event(
                    entry_id=entry_id,
                    action=action,
                    performed_by=author_id,
                    role=ROLE_ACTIVE_RESEARCHER,
                    status=ApprovalStatus.APPROVED.value,
                    timestamp=now_iso,
                    notes="Auto-finalized upon submission.",
                    signature_hash=signature_hash,
                    metadata={"policy": active_policy.value, "data_digest": digest},
                )
                return record

            # Standard policies: Transition to PENDING_REVIEW
            record = ApprovalRecord(
                entry_id=entry_id,
                author_id=author_id,
                policy=active_policy,
                status=ApprovalStatus.PENDING_REVIEW,
                designated_reviewer_id=designated_reviewer_id.strip() if designated_reviewer_id else None,
                data_digest=digest,
                reviewer_id=None,
                reviewer_role=None,
                review_notes="",
                revision_comments=None,
                checklists_verified=False,
                signature_hash=None,
                timestamp=None,
                submitted_at=now_iso,
                created_at=existing.created_at if existing else now_iso,
                updated_at=now_iso,
                metadata=meta,
            )
            self._records[entry_id] = record

            action = "RESUBMIT" if is_resubmission else "SUBMIT"
            self._record_history_event(
                entry_id=entry_id,
                action=action,
                performed_by=author_id,
                role=None,
                status=ApprovalStatus.PENDING_REVIEW.value,
                timestamp=now_iso,
                notes=f"Submitted under {active_policy.value} policy.",
                signature_hash=None,
                metadata={
                    "policy": active_policy.value,
                    "designated_reviewer_id": record.designated_reviewer_id,
                    "data_digest": digest,
                },
            )
            return record

    def sign_and_approve(
        self,
        entry_id: str,
        reviewer_id: str,
        reviewer_role: str,
        review_notes: str = "",
        checklists_verified: bool = True,
        data_digest: Optional[str] = None,
    ) -> ApprovalRecord:
        """
        Validate reviewer permissions against active policy and apply cryptographic seal.

        Parameter entry_id (str): Entry ID to sign and approve.
        Parameter reviewer_id (str): User ID of the reviewer signing off.
        Parameter reviewer_role (str): Role of the reviewer (e.g. active_researcher, pi_admin).
        Parameter review_notes (str): Quality verification or peer comments.
        Parameter checklists_verified (bool): Affirmation that required checklists are verified.
        Parameter data_digest (Optional[str]): Optional digest override verifying content immutability.
        Return Type: ApprovalRecord
        """
        with self._lock:
            if entry_id not in self._records:
                raise KeyError(f"Approval record for entry '{entry_id}' not found.")

            record = self._records[entry_id]

            if record.status != ApprovalStatus.PENDING_REVIEW:
                if record.status == ApprovalStatus.APPROVED:
                    raise ValueError(f"Entry '{entry_id}' is already approved.")
                if record.status == ApprovalStatus.CHANGES_REQUESTED:
                    raise ValueError(f"Entry '{entry_id}' has pending change requests and must be resubmitted.")
                raise ValueError(f"Entry '{entry_id}' is in status '{record.status.value}', expected PENDING_REVIEW.")

            if not checklists_verified:
                raise ValueError("All required checklists and protocol checkpoints must be verified before approval.")

            clean_role = str(reviewer_role).strip().lower()
            clean_reviewer_id = str(reviewer_id).strip()

            # Disallow unauthorized unauthenticated/alumni/guest roles across all policies
            if clean_role in (ROLE_ALUMNI_READONLY, ROLE_GUEST, "alumni_readonly", "guest"):
                raise ApprovalAuthorizationError(
                    f"Role '{reviewer_role}' has read-only or guest access and cannot sign off on entries.",
                    required_role=ROLE_ACTIVE_RESEARCHER,
                )

            # Policy enforcement
            if record.policy == ApprovalPolicy.PEER_REVIEW:
                if clean_reviewer_id == record.author_id.strip():
                    raise ApprovalAuthorizationError(
                        f"Author '{reviewer_id}' cannot peer-review their own submission under PEER_REVIEW policy.",
                        required_role=ROLE_ACTIVE_RESEARCHER,
                    )
                if clean_role not in (ROLE_ACTIVE_RESEARCHER, ROLE_PI_ADMIN, "active_researcher", "pi_admin", "pi"):
                    raise ApprovalAuthorizationError(
                        f"Reviewer role '{reviewer_role}' is not authorized for PEER_REVIEW. Active researcher or PI required.",
                        required_role=ROLE_ACTIVE_RESEARCHER,
                    )

            elif record.policy == ApprovalPolicy.DESIGNATED_REVIEWER:
                if clean_reviewer_id != (record.designated_reviewer_id or "").strip():
                    raise ApprovalAuthorizationError(
                        f"User '{reviewer_id}' is not the designated reviewer '{record.designated_reviewer_id}' for this entry.",
                        required_role=ROLE_ACTIVE_RESEARCHER,
                    )
                if clean_role not in (
                    ROLE_ACTIVE_RESEARCHER,
                    ROLE_PI_ADMIN,
                    ROLE_ROTATION_STUDENT,
                    "active_researcher",
                    "pi_admin",
                    "rotation_student",
                ):
                    raise ApprovalAuthorizationError(
                        f"Reviewer role '{reviewer_role}' is not authorized to sign off.",
                        required_role=ROLE_ACTIVE_RESEARCHER,
                    )

            elif record.policy == ApprovalPolicy.PI_APPROVAL:
                if clean_role not in (ROLE_PI_ADMIN, "pi_admin", "pi"):
                    raise ApprovalAuthorizationError(
                        f"Role '{reviewer_role}' is not authorized for PI_APPROVAL policy. Traditional PI role required.",
                        required_role=ROLE_PI_ADMIN,
                    )

            # Generate Cryptographic Tamper-Evident Seal
            now_iso = datetime.now(timezone.utc).isoformat()
            effective_digest = data_digest if data_digest is not None else record.data_digest
            if not effective_digest:
                effective_digest = hashlib.sha256(f"digest:{entry_id}".encode("utf-8")).hexdigest()

            signature_hash = hashlib.sha256(
                f"{entry_id}:{record.author_id}:{effective_digest}:{clean_reviewer_id}:{now_iso}".encode("utf-8")
            ).hexdigest()

            record.status = ApprovalStatus.APPROVED
            record.reviewer_id = clean_reviewer_id
            record.reviewer_role = reviewer_role
            record.review_notes = review_notes
            record.checklists_verified = True
            record.data_digest = effective_digest
            record.signature_hash = signature_hash
            record.timestamp = now_iso
            record.updated_at = now_iso

            self._record_history_event(
                entry_id=entry_id,
                action="SIGN_AND_APPROVE",
                performed_by=clean_reviewer_id,
                role=reviewer_role,
                status=ApprovalStatus.APPROVED.value,
                timestamp=now_iso,
                notes=review_notes,
                signature_hash=signature_hash,
                metadata={
                    "policy": record.policy.value,
                    "author_id": record.author_id,
                    "data_digest": effective_digest,
                    "checklists_verified": True,
                },
            )
            return record

    def request_changes(
        self,
        entry_id: str,
        reviewer_id: str,
        reviewer_role: str,
        revision_comments: str,
    ) -> ApprovalRecord:
        """
        Transition entry to CHANGES_REQUESTED with reviewer feedback, routing back to author.

        Parameter entry_id (str): Target entry ID.
        Parameter reviewer_id (str): Reviewer requesting modifications.
        Parameter reviewer_role (str): Role of the reviewer.
        Parameter revision_comments (str): Detailed feedback outlining required revisions.
        Return Type: ApprovalRecord
        """
        with self._lock:
            if entry_id not in self._records:
                raise KeyError(f"Approval record for entry '{entry_id}' not found.")

            record = self._records[entry_id]

            if record.status != ApprovalStatus.PENDING_REVIEW:
                if record.status == ApprovalStatus.APPROVED:
                    raise ValueError(f"Entry '{entry_id}' is already approved and locked.")
                raise ValueError(f"Entry '{entry_id}' is in status '{record.status.value}', expected PENDING_REVIEW.")

            if not revision_comments or not revision_comments.strip():
                raise ValueError("revision_comments cannot be empty when requesting changes.")

            clean_role = str(reviewer_role).strip().lower()
            clean_reviewer_id = str(reviewer_id).strip()

            if clean_role in (ROLE_ALUMNI_READONLY, ROLE_GUEST, "alumni_readonly", "guest"):
                raise ApprovalAuthorizationError(
                    f"Role '{reviewer_role}' lacks authority to request revisions.",
                    required_role=ROLE_ACTIVE_RESEARCHER,
                )

            if record.policy == ApprovalPolicy.PEER_REVIEW:
                if clean_reviewer_id == record.author_id.strip():
                    raise ApprovalAuthorizationError(
                        "Author cannot request changes on their own submission under PEER_REVIEW.",
                        required_role=ROLE_ACTIVE_RESEARCHER,
                    )
            elif record.policy == ApprovalPolicy.DESIGNATED_REVIEWER:
                if clean_reviewer_id != (record.designated_reviewer_id or "").strip() and clean_role not in (
                    ROLE_PI_ADMIN,
                    "pi_admin",
                    "pi",
                ):
                    raise ApprovalAuthorizationError(
                        f"User '{reviewer_id}' is not the designated reviewer '{record.designated_reviewer_id}'.",
                        required_role=ROLE_ACTIVE_RESEARCHER,
                    )
            elif record.policy == ApprovalPolicy.PI_APPROVAL:
                if clean_role not in (ROLE_PI_ADMIN, "pi_admin", "pi"):
                    raise ApprovalAuthorizationError(
                        f"Role '{reviewer_role}' is not authorized for PI_APPROVAL. Traditional PI role required.",
                        required_role=ROLE_PI_ADMIN,
                    )

            now_iso = datetime.now(timezone.utc).isoformat()
            record.status = ApprovalStatus.CHANGES_REQUESTED
            record.reviewer_id = clean_reviewer_id
            record.reviewer_role = reviewer_role
            record.revision_comments = revision_comments
            record.updated_at = now_iso

            self._record_history_event(
                entry_id=entry_id,
                action="REQUEST_CHANGES",
                performed_by=clean_reviewer_id,
                role=reviewer_role,
                status=ApprovalStatus.CHANGES_REQUESTED.value,
                timestamp=now_iso,
                notes=revision_comments,
                signature_hash=None,
                metadata={"policy": record.policy.value, "revision_comments": revision_comments},
            )
            return record

    def get_audit_history(self, entry_id: str) -> List[ApprovalHistoryEvent]:
        """
        Retrieve complete audit history trail for the specified notebook entry.

        Parameter entry_id (str): Entry ID to query.
        Return Type: List[ApprovalHistoryEvent]
        """
        with self._lock:
            events = self._history.get(entry_id, [])
            return list(events)

    def get_approval(self, entry_id: str) -> Optional[ApprovalRecord]:
        """
        Retrieve current approval record for the specified entry.

        Parameter entry_id (str): Target entry ID.
        Return Type: Optional[ApprovalRecord]
        """
        with self._lock:
            return self._records.get(entry_id)

    def list_approvals(
        self,
        status: Optional[Union[ApprovalStatus, str]] = None,
        policy: Optional[Union[ApprovalPolicy, str]] = None,
    ) -> List[ApprovalRecord]:
        """
        List approval records, optionally filtered by status or policy.

        Parameter status (Optional[Union[ApprovalStatus, str]]): Status filter.
        Parameter policy (Optional[Union[ApprovalPolicy, str]]): Policy filter.
        Return Type: List[ApprovalRecord]
        """
        with self._lock:
            results = list(self._records.values())
            if status is not None:
                norm_status = normalize_status(status)
                results = [r for r in results if r.status == norm_status]
            if policy is not None:
                norm_policy = normalize_policy(policy)
                results = [r for r in results if r.policy == norm_policy]
            return results

    def verify_entry_seal(self, entry_id: str) -> bool:
        """
        Verify the recorded cryptographic seal on an approved notebook entry.

        Parameter entry_id (str): Target entry ID.
        Return Type: bool
        """
        with self._lock:
            record = self._records.get(entry_id)
            if not record or record.status != ApprovalStatus.APPROVED or not record.signature_hash:
                return False
            return self.verify_seal(
                entry_id=record.entry_id,
                signature_hash=record.signature_hash,
                author_id=record.author_id,
                data_digest=record.data_digest,
                reviewer_id=record.reviewer_id or "",
                timestamp=record.timestamp or "",
            )

    def clear_for_testing(self) -> None:
        """
        Clear all in-memory records and history. For test harness setup only.
        """
        with self._lock:
            self._records.clear()
            self._history.clear()

    def _record_history_event(
        self,
        entry_id: str,
        action: str,
        performed_by: str,
        role: Optional[str],
        status: str,
        timestamp: str,
        notes: str = "",
        signature_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ApprovalHistoryEvent:
        """Record internal event and mirror into 21 CFR Part 11 cryptographically chained audit service."""
        event_id = f"APPR-EVT-{uuid.uuid4().hex[:8]}"
        evt = ApprovalHistoryEvent(
            event_id=event_id,
            entry_id=entry_id,
            action=action,
            performed_by=performed_by,
            role=role,
            status=status,
            timestamp=timestamp,
            notes=notes,
            signature_hash=signature_hash,
            metadata=dict(metadata or {}),
        )

        if entry_id not in self._history:
            self._history[entry_id] = []
        self._history[entry_id].append(evt)

        # Mirror to global audit service
        try:
            self._audit_service.record_event(
                entity_type="approval_entry",
                entity_id=entry_id,
                action=action,
                performed_by=performed_by,
                previous_state=None,
                new_state={"status": status, "signature_hash": signature_hash},
                metadata={"notes": notes, **(metadata or {})},
            )
        except Exception:
            pass

        return evt


_global_approval_service = ApprovalService()


def get_approval_service() -> ApprovalService:
    """
    Retrieve process-level singleton instance of ApprovalService.

    Return Type: ApprovalService
    """
    return _global_approval_service
