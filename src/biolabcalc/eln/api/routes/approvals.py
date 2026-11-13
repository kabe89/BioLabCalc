"""
Module: biolabcalc.eln.api.routes.approvals
Component: Approval & Governance Workflow REST Endpoints
Architectural Role: Exposes REST API routes for multi-policy review submission, peer sign-off,
designated reviewer enforcement, revision change requests, cryptographic seal verification,
and 21 CFR Part 11 audit history retrieval.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from ...services.approval_service import (
    ApprovalAuthorizationError,
    ApprovalPolicy,
    ApprovalStatus,
    get_approval_service,
)
from ..auth import (
    PERM_AUDIT_VERIFY,
    PERM_AUDIT_VIEW,
    AuthorizationError,
    UserSession,
    get_auth_service,
)
from ..router import Route, Router

router = Router(prefix="/api/v1/approvals")
approval_service = get_approval_service()
auth_service = get_auth_service()


@router.post("/submit")
def submit_for_review_endpoint(
    payload: Dict[str, Any],
    current_user: Optional[UserSession] = None,
) -> Tuple[Dict[str, Any], int]:
    """
    Submit a lab notebook entry for governance review under a specified policy.

    Parameter payload (Dict[str, Any]): Submission payload containing:
        - entry_id (str, required)
        - author_id (Optional[str], defaults to authenticated user)
        - policy (Optional[str], defaults to PEER_REVIEW)
        - designated_reviewer_id (Optional[str], required if policy is DESIGNATED_REVIEWER)
        - data_digest (Optional[str], content checksum)
        - metadata (Optional[dict])
    Parameter current_user (Optional[UserSession]): Authenticated user session.
    Return Type: Tuple[Dict[str, Any], int]
    """
    entry_id = payload.get("entry_id")
    if not entry_id or not str(entry_id).strip():
        return {"status": "error", "message": "Missing required field 'entry_id'."}, 400

    author_id = payload.get("author_id")
    if not author_id or not str(author_id).strip():
        if current_user:
            author_id = current_user.username or current_user.user_id
        else:
            author_id = "active_researcher"

    policy_raw = payload.get("policy", ApprovalPolicy.PEER_REVIEW)
    designated_reviewer_id = payload.get("designated_reviewer_id")
    data_digest = payload.get("data_digest")
    metadata = payload.get("metadata", {})

    try:
        record = approval_service.submit_for_review(
            entry_id=str(entry_id).strip(),
            author_id=str(author_id).strip(),
            policy=policy_raw,
            designated_reviewer_id=str(designated_reviewer_id).strip() if designated_reviewer_id else None,
            data_digest=data_digest,
            metadata=metadata,
        )
        return {"status": "success", "approval": record.to_dict()}, 200
    except (ApprovalAuthorizationError, AuthorizationError, PermissionError) as ae:
        return {"status": "error", "message": str(ae)}, 403
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}, 400
    except Exception as ex:
        return {"status": "error", "message": f"Internal server error: {ex}"}, 500


@router.post("/sign")
def sign_and_approve_endpoint(
    payload: Dict[str, Any],
    current_user: Optional[UserSession] = None,
) -> Tuple[Dict[str, Any], int]:
    """
    Sign and approve a lab notebook entry, validating permissions and generating cryptographic seal.

    Parameter payload (Dict[str, Any]): Signing payload containing:
        - entry_id (str, required)
        - reviewer_id (Optional[str], defaults to authenticated user)
        - reviewer_role (Optional[str], defaults to authenticated user role)
        - review_notes (Optional[str])
        - checklists_verified (Optional[bool], defaults to True)
        - data_digest (Optional[str])
    Parameter current_user (Optional[UserSession]): Authenticated user session.
    Return Type: Tuple[Dict[str, Any], int]
    """
    entry_id = payload.get("entry_id")
    if not entry_id or not str(entry_id).strip():
        return {"status": "error", "message": "Missing required field 'entry_id'."}, 400

    reviewer_id = payload.get("reviewer_id")
    if not reviewer_id or not str(reviewer_id).strip():
        if current_user:
            reviewer_id = current_user.username or current_user.user_id
        else:
            reviewer_id = "active_researcher"

    reviewer_role = payload.get("reviewer_role")
    if not reviewer_role or not str(reviewer_role).strip():
        if current_user:
            reviewer_role = current_user.role
        else:
            reviewer_role = "active_researcher"

    review_notes = payload.get("review_notes", "")
    checklists_verified = payload.get("checklists_verified", True)
    data_digest = payload.get("data_digest")

    try:
        record = approval_service.sign_and_approve(
            entry_id=str(entry_id).strip(),
            reviewer_id=str(reviewer_id).strip(),
            reviewer_role=str(reviewer_role).strip(),
            review_notes=review_notes,
            checklists_verified=bool(checklists_verified),
            data_digest=data_digest,
        )
        return {"status": "success", "approval": record.to_dict()}, 200
    except KeyError as ke:
        return {"status": "error", "message": str(ke)}, 404
    except (ApprovalAuthorizationError, AuthorizationError, PermissionError) as ae:
        return {"status": "error", "message": str(ae)}, 403
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}, 400
    except Exception as ex:
        return {"status": "error", "message": f"Internal server error: {ex}"}, 500


@router.post("/request-changes")
def request_changes_endpoint(
    payload: Dict[str, Any],
    current_user: Optional[UserSession] = None,
) -> Tuple[Dict[str, Any], int]:
    """
    Request revisions on a notebook entry, moving it to CHANGES_REQUESTED and returning to author.

    Parameter payload (Dict[str, Any]): Change request payload containing:
        - entry_id (str, required)
        - reviewer_id (Optional[str], defaults to authenticated user)
        - reviewer_role (Optional[str], defaults to authenticated user role)
        - revision_comments (str, required)
    Parameter current_user (Optional[UserSession]): Authenticated user session.
    Return Type: Tuple[Dict[str, Any], int]
    """
    entry_id = payload.get("entry_id")
    if not entry_id or not str(entry_id).strip():
        return {"status": "error", "message": "Missing required field 'entry_id'."}, 400

    revision_comments = payload.get("revision_comments") or payload.get("comments") or payload.get("review_notes")
    if not revision_comments or not str(revision_comments).strip():
        return {"status": "error", "message": "Missing required field 'revision_comments'."}, 400

    reviewer_id = payload.get("reviewer_id")
    if not reviewer_id or not str(reviewer_id).strip():
        if current_user:
            reviewer_id = current_user.username or current_user.user_id
        else:
            reviewer_id = "active_researcher"

    reviewer_role = payload.get("reviewer_role")
    if not reviewer_role or not str(reviewer_role).strip():
        if current_user:
            reviewer_role = current_user.role
        else:
            reviewer_role = "active_researcher"

    try:
        record = approval_service.request_changes(
            entry_id=str(entry_id).strip(),
            reviewer_id=str(reviewer_id).strip(),
            reviewer_role=str(reviewer_role).strip(),
            revision_comments=str(revision_comments).strip(),
        )
        return {"status": "success", "approval": record.to_dict()}, 200
    except KeyError as ke:
        return {"status": "error", "message": str(ke)}, 404
    except (ApprovalAuthorizationError, AuthorizationError, PermissionError) as ae:
        return {"status": "error", "message": str(ae)}, 403
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}, 400
    except Exception as ex:
        return {"status": "error", "message": f"Internal server error: {ex}"}, 500


@router.get("/verify/{entry_id}")
def verify_seal_endpoint(
    entry_id: str,
    signature_hash: Optional[str] = None,
    author_id: Optional[str] = None,
    data_digest: Optional[str] = None,
    reviewer_id: Optional[str] = None,
    timestamp: Optional[str] = None,
    current_user: Optional[UserSession] = None,
) -> Tuple[Dict[str, Any], int]:
    """
    Verify the cryptographic tamper-evident seal of an approved entry.

    Parameter entry_id (str): Target notebook entry ID.
    Parameter signature_hash (Optional[str]): Override signature hash to test.
    Parameter author_id (Optional[str]): Override author ID to test.
    Parameter data_digest (Optional[str]): Override data digest to test tampering.
    Parameter reviewer_id (Optional[str]): Override reviewer ID to test.
    Parameter timestamp (Optional[str]): Override timestamp to test.
    Parameter current_user (Optional[UserSession]): Authenticated user session.
    Return Type: Tuple[Dict[str, Any], int]
    """
    record = approval_service.get_approval(entry_id)
    if not record:
        return {"status": "error", "message": f"Approval record for entry '{entry_id}' not found."}, 404

    target_sig = signature_hash if signature_hash is not None else record.signature_hash
    target_auth = author_id if author_id is not None else record.author_id
    target_digest = data_digest if data_digest is not None else record.data_digest
    target_rev = reviewer_id if reviewer_id is not None else (record.reviewer_id or "")
    target_ts = timestamp if timestamp is not None else (record.timestamp or "")

    if not target_sig:
        return {
            "status": "error",
            "message": f"Entry '{entry_id}' is in status '{record.status.value}' and does not possess a cryptographic seal.",
        }, 400

    is_valid = approval_service.verify_seal(
        entry_id=entry_id,
        signature_hash=target_sig,
        author_id=target_auth,
        data_digest=target_digest,
        reviewer_id=target_rev,
        timestamp=target_ts,
    )

    return {
        "status": "success",
        "entry_id": entry_id,
        "valid": is_valid,
        "signature_hash": target_sig,
        "policy": record.policy.value,
        "approval_status": record.status.value,
        "message": "Seal verified successfully. Entry is untampered."
        if is_valid
        else "Cryptographic verification failed: Seal does not match contents or has been tampered with.",
    }, 200


@router.get("/history/{entry_id}")
def get_audit_history_endpoint(
    entry_id: str,
    current_user: Optional[UserSession] = None,
) -> Tuple[Dict[str, Any], int]:
    """
    Retrieve full 21 CFR Part 11 audit history trail for an entry.

    Parameter entry_id (str): Target notebook entry ID.
    Parameter current_user (Optional[UserSession]): Authenticated user session.
    Return Type: Tuple[Dict[str, Any], int]
    """
    history = approval_service.get_audit_history(entry_id)
    serialized = [h.to_dict() if hasattr(h, "to_dict") else h for h in history]
    return {
        "status": "success",
        "entry_id": entry_id,
        "count": len(serialized),
        "history": serialized,
    }, 200


@router.get("/{entry_id}")
def get_approval_endpoint(
    entry_id: str,
    current_user: Optional[UserSession] = None,
) -> Tuple[Dict[str, Any], int]:
    """
    Retrieve approval status and details for an entry.

    Parameter entry_id (str): Target notebook entry ID.
    Parameter current_user (Optional[UserSession]): Authenticated user session.
    Return Type: Tuple[Dict[str, Any], int]
    """
    record = approval_service.get_approval(entry_id)
    if not record:
        return {"status": "error", "message": f"Approval record for entry '{entry_id}' not found."}, 404
    return {"status": "success", "approval": record.to_dict()}, 200


# Register alias paths for /api/approvals/... alongside /api/v1/approvals/...
for existing_route in list(router.routes):
    alias_path = existing_route.path_pattern.replace("/api/v1/approvals", "/api/approvals")
    if alias_path != existing_route.path_pattern:
        router.routes.append(
            Route(
                method=existing_route.method,
                path_pattern=alias_path,
                handler=existing_route.handler,
            )
        )
