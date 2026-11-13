"""
Module: tests.test_approval_workflow
Component: Automated Unit and Integration Test Suite for ELN Approval & Governance Workflows
Architectural Role: Verifies multi-policy review routing, peer sign-off, designated reviewer RBAC,
changes requested feedback loops, and 21 CFR Part 11 cryptographic seal immutability.
"""

from __future__ import annotations

import hashlib
import os
import sys
import unittest
from datetime import datetime, timezone
from typing import Any, Dict

# Sys.path bootstrap so the test suite can execute standalone
_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.eln.api.app import TestClient, create_app
from biolabcalc.eln.api.auth import (
    ROLE_ACTIVE_RESEARCHER,
    ROLE_ALUMNI_READONLY,
    ROLE_PI_ADMIN,
    ROLE_ROTATION_STUDENT,
)
from biolabcalc.eln.api.routes.approvals import router as approvals_router
from biolabcalc.eln.services.approval_service import (
    ApprovalAuthorizationError,
    ApprovalPolicy,
    ApprovalStatus,
    get_approval_service,
)


class TestApprovalWorkflowService(unittest.TestCase):
    """
    Unit test suite covering the core business logic of ApprovalService.
    """

    def setUp(self) -> None:
        """Reset service state before each test run."""
        self.service = get_approval_service()
        self.service.clear_for_testing()

    def test_open_collaboration_auto_finalization(self) -> None:
        """
        Test that OPEN_COLLABORATION policy immediately auto-finalizes upon submission,
        transitioning directly to APPROVED status and generating a cryptographic seal.
        """
        entry_id = "ENTRY-OPEN-101"
        author_id = "USR-RES-001"
        data_digest = "sha256:fedcba9876543210abcdef"

        record = self.service.submit_for_review(
            entry_id=entry_id,
            author_id=author_id,
            policy=ApprovalPolicy.OPEN_COLLABORATION,
            data_digest=data_digest,
            metadata={"notes": "Open notebook entry for protocol screening"},
        )

        # Status must immediately be APPROVED
        self.assertEqual(record.status, ApprovalStatus.APPROVED)
        self.assertEqual(record.policy, ApprovalPolicy.OPEN_COLLABORATION)
        self.assertEqual(record.author_id, author_id)
        self.assertEqual(record.reviewer_id, author_id)
        self.assertTrue(record.checklists_verified)
        self.assertIsNotNone(record.signature_hash)
        self.assertEqual(len(record.signature_hash), 64)
        self.assertIsNotNone(record.timestamp)

        # Cryptographic seal must verify as authentic
        is_valid = self.service.verify_seal(
            entry_id=entry_id,
            signature_hash=record.signature_hash,
            author_id=record.author_id,
            data_digest=record.data_digest,
            reviewer_id=record.reviewer_id,
            timestamp=record.timestamp,
        )
        self.assertTrue(is_valid)

        # Audit history must capture the auto-finalization event
        history = self.service.get_audit_history(entry_id)
        self.assertGreaterEqual(len(history), 1)
        self.assertIn("AUTO_FINALIZE", history[0].action)
        self.assertEqual(history[0].performed_by, author_id)

    def test_peer_review_workflow(self) -> None:
        """
        Test PEER_REVIEW workflow:
        1. Submission enters PENDING_REVIEW.
        2. Author cannot peer-review their own entry.
        3. Read-only or unauthorized roles cannot approve.
        4. Active peer researcher signs and approves, generating cryptographic seal.
        """
        entry_id = "ENTRY-PEER-201"
        author_id = "USR-RES-001"
        peer_reviewer_id = "USR-RES-002"
        data_digest = "sha256:1234567890abcdef123456"

        # 1. Submission
        record = self.service.submit_for_review(
            entry_id=entry_id,
            author_id=author_id,
            policy=ApprovalPolicy.PEER_REVIEW,
            data_digest=data_digest,
        )
        self.assertEqual(record.status, ApprovalStatus.PENDING_REVIEW)
        self.assertIsNone(record.signature_hash)

        # 2. Author self-review forbidden
        with self.assertRaises(ApprovalAuthorizationError):
            self.service.sign_and_approve(
                entry_id=entry_id,
                reviewer_id=author_id,
                reviewer_role=ROLE_ACTIVE_RESEARCHER,
                review_notes="Attempted self review",
            )

        # 3. Alumni read-only role forbidden
        with self.assertRaises(ApprovalAuthorizationError):
            self.service.sign_and_approve(
                entry_id=entry_id,
                reviewer_id="USR-ALU-001",
                reviewer_role=ROLE_ALUMNI_READONLY,
                review_notes="Attempted alumni approval",
            )

        # 4. Valid peer review sign-off
        approved_record = self.service.sign_and_approve(
            entry_id=entry_id,
            reviewer_id=peer_reviewer_id,
            reviewer_role=ROLE_ACTIVE_RESEARCHER,
            review_notes="All standard operating controls verified. Gel lanes match ladder.",
            checklists_verified=True,
        )

        self.assertEqual(approved_record.status, ApprovalStatus.APPROVED)
        self.assertEqual(approved_record.reviewer_id, peer_reviewer_id)
        self.assertIsNotNone(approved_record.signature_hash)
        self.assertIsNotNone(approved_record.timestamp)

        # Verify seal
        self.assertTrue(
            self.service.verify_seal(
                entry_id=entry_id,
                signature_hash=approved_record.signature_hash,
                author_id=author_id,
                data_digest=data_digest,
                reviewer_id=peer_reviewer_id,
                timestamp=approved_record.timestamp,
            )
        )

        # Check audit trail
        history = self.service.get_audit_history(entry_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].action, "SUBMIT")
        self.assertEqual(history[1].action, "SIGN_AND_APPROVE")

    def test_designated_reviewer_enforcement(self) -> None:
        """
        Test DESIGNATED_REVIEWER enforcement:
        - Submission fails if designated reviewer ID is missing or equal to author.
        - Non-designated users cannot sign off.
        - Only the specifically nominated reviewer can approve.
        """
        entry_id = "ENTRY-DESIG-301"
        author_id = "USR-RES-001"
        designated_reviewer = "USR-SPECIFIC-007"
        data_digest = "sha256:deadbeefcafe01234567"

        # Missing designated reviewer raises ValueError
        with self.assertRaises(ValueError):
            self.service.submit_for_review(
                entry_id=entry_id,
                author_id=author_id,
                policy=ApprovalPolicy.DESIGNATED_REVIEWER,
                designated_reviewer_id=None,
            )

        # Author cannot designate themselves
        with self.assertRaises(ValueError):
            self.service.submit_for_review(
                entry_id=entry_id,
                author_id=author_id,
                policy=ApprovalPolicy.DESIGNATED_REVIEWER,
                designated_reviewer_id=author_id,
            )

        # Successful submission with designated reviewer
        self.service.submit_for_review(
            entry_id=entry_id,
            author_id=author_id,
            policy=ApprovalPolicy.DESIGNATED_REVIEWER,
            designated_reviewer_id=designated_reviewer,
            data_digest=data_digest,
        )

        # Unauthorized colleague tries to sign off
        with self.assertRaises(ApprovalAuthorizationError):
            self.service.sign_and_approve(
                entry_id=entry_id,
                reviewer_id="USR-RANDOM-009",
                reviewer_role=ROLE_ACTIVE_RESEARCHER,
                review_notes="Unauthorized approval attempt",
            )

        # Designated reviewer successfully signs off
        approved = self.service.sign_and_approve(
            entry_id=entry_id,
            reviewer_id=designated_reviewer,
            reviewer_role=ROLE_ACTIVE_RESEARCHER,
            review_notes="Designated review complete and confirmed.",
            checklists_verified=True,
        )

        self.assertEqual(approved.status, ApprovalStatus.APPROVED)
        self.assertEqual(approved.reviewer_id, designated_reviewer)
        self.assertTrue(self.service.verify_entry_seal(entry_id))

    def test_pi_approval_policy_enforcement(self) -> None:
        """
        Test PI_APPROVAL policy:
        Only users with traditional PI role (pi_admin) can sign off.
        """
        entry_id = "ENTRY-PI-401"
        author_id = "USR-RES-001"
        data_digest = "sha256:pi_protocol_check"

        self.service.submit_for_review(
            entry_id=entry_id,
            author_id=author_id,
            policy=ApprovalPolicy.PI_APPROVAL,
            data_digest=data_digest,
        )

        # Active researcher (non-PI) cannot sign
        with self.assertRaises(ApprovalAuthorizationError):
            self.service.sign_and_approve(
                entry_id=entry_id,
                reviewer_id="USR-RES-002",
                reviewer_role=ROLE_ACTIVE_RESEARCHER,
                review_notes="Attempted postdoc sign-off on PI entry",
            )

        # PI successfully signs
        approved = self.service.sign_and_approve(
            entry_id=entry_id,
            reviewer_id="USR-PI-001",
            reviewer_role=ROLE_PI_ADMIN,
            review_notes="Principal Investigator sign-off granted.",
        )
        self.assertEqual(approved.status, ApprovalStatus.APPROVED)
        self.assertEqual(approved.reviewer_role, ROLE_PI_ADMIN)

    def test_changes_requested_loop_back_to_author(self) -> None:
        """
        Test the CHANGES_REQUESTED iterative loop:
        1. Author submits entry (PENDING_REVIEW).
        2. Reviewer requests changes with specific comments (CHANGES_REQUESTED).
        3. Approval is blocked while changes are requested.
        4. Author updates data and resubmits (PENDING_REVIEW).
        5. Reviewer reviews updated work and approves (APPROVED).
        """
        entry_id = "ENTRY-LOOP-501"
        author_id = "USR-RES-001"
        reviewer_id = "USR-RES-002"
        initial_digest = "sha256:initial_incomplete_data"
        revised_digest = "sha256:revised_complete_data"

        # 1. Initial submission
        self.service.submit_for_review(
            entry_id=entry_id,
            author_id=author_id,
            policy=ApprovalPolicy.PEER_REVIEW,
            data_digest=initial_digest,
        )

        # 2. Reviewer requests changes
        revision_feedback = "Please re-calculate lysis buffer: 10% dead volume was omitted."
        change_record = self.service.request_changes(
            entry_id=entry_id,
            reviewer_id=reviewer_id,
            reviewer_role=ROLE_ACTIVE_RESEARCHER,
            revision_comments=revision_feedback,
        )

        self.assertEqual(change_record.status, ApprovalStatus.CHANGES_REQUESTED)
        self.assertEqual(change_record.revision_comments, revision_feedback)

        # 3. Approval is blocked while in CHANGES_REQUESTED
        with self.assertRaises(ValueError):
            self.service.sign_and_approve(
                entry_id=entry_id,
                reviewer_id=reviewer_id,
                reviewer_role=ROLE_ACTIVE_RESEARCHER,
                review_notes="Premature approval without resubmission",
            )

        # 4. Author resubmits updated notebook entry
        resubmitted = self.service.submit_for_review(
            entry_id=entry_id,
            author_id=author_id,
            policy=ApprovalPolicy.PEER_REVIEW,
            data_digest=revised_digest,
        )
        self.assertEqual(resubmitted.status, ApprovalStatus.PENDING_REVIEW)
        self.assertEqual(resubmitted.data_digest, revised_digest)

        # 5. Reviewer signs off on revised submission
        final_approved = self.service.sign_and_approve(
            entry_id=entry_id,
            reviewer_id=reviewer_id,
            reviewer_role=ROLE_ACTIVE_RESEARCHER,
            review_notes="Buffer volumes corrected. Approved.",
            checklists_verified=True,
        )
        self.assertEqual(final_approved.status, ApprovalStatus.APPROVED)
        self.assertEqual(final_approved.data_digest, revised_digest)

        # Verify complete audit history trail contains all 4 milestones
        history = self.service.get_audit_history(entry_id)
        actions = [evt.action for evt in history]
        self.assertEqual(actions, ["SUBMIT", "REQUEST_CHANGES", "RESUBMIT", "SIGN_AND_APPROVE"])

    def test_cryptographic_seal_verification_and_tampering_detection(self) -> None:
        """
        Test mathematical seal verification and tamper detection:
        - Correct parameters produce True.
        - Tampered data digest produces False.
        - Tampered author, reviewer, or timestamp produces False.
        - Tampered signature hash produces False.
        """
        entry_id = "ENTRY-CRYPTO-601"
        author_id = "USR-RES-001"
        reviewer_id = "USR-RES-002"
        data_digest = "sha256:original_authentic_content_digest"
        timestamp = "2026-11-13T15:00:00+00:00"

        # Compute authentic signature hash
        expected_raw = f"{entry_id}:{author_id}:{data_digest}:{reviewer_id}:{timestamp}".encode("utf-8")
        authentic_sig = hashlib.sha256(expected_raw).hexdigest()

        # 1. Untampered verification
        self.assertTrue(
            self.service.verify_seal(
                entry_id=entry_id,
                signature_hash=authentic_sig,
                author_id=author_id,
                data_digest=data_digest,
                reviewer_id=reviewer_id,
                timestamp=timestamp,
            )
        )

        # 2. Tampered data digest
        tampered_digest = "sha256:tampered_modified_content_digest"
        self.assertFalse(
            self.service.verify_seal(
                entry_id=entry_id,
                signature_hash=authentic_sig,
                author_id=author_id,
                data_digest=tampered_digest,
                reviewer_id=reviewer_id,
                timestamp=timestamp,
            )
        )

        # 3. Tampered author ID
        self.assertFalse(
            self.service.verify_seal(
                entry_id=entry_id,
                signature_hash=authentic_sig,
                author_id="USR-IMPOSTOR",
                data_digest=data_digest,
                reviewer_id=reviewer_id,
                timestamp=timestamp,
            )
        )

        # 4. Tampered reviewer ID
        self.assertFalse(
            self.service.verify_seal(
                entry_id=entry_id,
                signature_hash=authentic_sig,
                author_id=author_id,
                data_digest=data_digest,
                reviewer_id="USR-IMPOSTOR",
                timestamp=timestamp,
            )
        )

        # 5. Tampered timestamp
        self.assertFalse(
            self.service.verify_seal(
                entry_id=entry_id,
                signature_hash=authentic_sig,
                author_id=author_id,
                data_digest=data_digest,
                reviewer_id=reviewer_id,
                timestamp="2026-11-13T16:00:00+00:00",
            )
        )

        # 6. Corrupted signature hash
        corrupted_sig = authentic_sig[:-4] + "0000"
        self.assertFalse(
            self.service.verify_seal(
                entry_id=entry_id,
                signature_hash=corrupted_sig,
                author_id=author_id,
                data_digest=data_digest,
                reviewer_id=reviewer_id,
                timestamp=timestamp,
            )
        )

    def test_checklists_verified_enforcement(self) -> None:
        """
        Verify that sign_and_approve requires checklists_verified=True.
        """
        entry_id = "ENTRY-CHECKLIST-701"
        self.service.submit_for_review(
            entry_id=entry_id,
            author_id="USR-RES-001",
            policy=ApprovalPolicy.PEER_REVIEW,
        )

        with self.assertRaises(ValueError):
            self.service.sign_and_approve(
                entry_id=entry_id,
                reviewer_id="USR-RES-002",
                reviewer_role=ROLE_ACTIVE_RESEARCHER,
                checklists_verified=False,
            )


class TestApprovalRESTEndpoints(unittest.TestCase):
    """
    Integration test suite verifying REST API routes for approvals:
    - POST /api/v1/approvals/submit
    - POST /api/v1/approvals/sign
    - POST /api/v1/approvals/request-changes
    - GET /api/v1/approvals/verify/{entry_id}
    - GET /api/v1/approvals/history/{entry_id}
    """

    def setUp(self) -> None:
        """Initialize test application, router, and TestClient."""
        self.app = create_app()
        # Mount approvals router
        self.app.router.include_router(approvals_router)
        self.client = TestClient(self.app)

        # Reset service state
        self.service = get_approval_service()
        self.service.clear_for_testing()

    def test_rest_submit_and_peer_approval_flow(self) -> None:
        """Verify full submit -> sign -> verify -> history cycle via REST API."""
        entry_id = "API-ENTRY-001"

        # 1. Submit for peer review
        submit_res = self.client.post(
            "/api/v1/approvals/submit",
            {
                "entry_id": entry_id,
                "author_id": "active_researcher",
                "policy": "PEER_REVIEW",
                "data_digest": "sha256:abc123digest",
            },
        )
        self.assertEqual(submit_res["status_code"], 200)
        self.assertEqual(submit_res["json"]["status"], "success")
        self.assertEqual(submit_res["json"]["approval"]["status"], "PENDING_REVIEW")

        # 2. Peer signs and approves
        sign_res = self.client.post(
            "/api/v1/approvals/sign",
            {
                "entry_id": entry_id,
                "reviewer_id": "pi_admin",
                "reviewer_role": "pi_admin",
                "review_notes": "SOP verification complete and approved.",
                "checklists_verified": True,
            },
        )
        self.assertEqual(sign_res["status_code"], 200)
        self.assertEqual(sign_res["json"]["status"], "success")
        self.assertEqual(sign_res["json"]["approval"]["status"], "APPROVED")
        sig_hash = sign_res["json"]["approval"]["signature_hash"]
        self.assertIsNotNone(sig_hash)

        # 3. Verify seal endpoint
        verify_res = self.client.get(f"/api/v1/approvals/verify/{entry_id}")
        self.assertEqual(verify_res["status_code"], 200)
        self.assertTrue(verify_res["json"]["valid"])
        self.assertEqual(verify_res["json"]["signature_hash"], sig_hash)

        # 4. Verify seal endpoint detects tampering
        tamper_res = self.client.get(f"/api/v1/approvals/verify/{entry_id}?data_digest=sha256:tampered")
        self.assertEqual(tamper_res["status_code"], 200)
        self.assertFalse(tamper_res["json"]["valid"])

        # 5. Audit history endpoint
        hist_res = self.client.get(f"/api/v1/approvals/history/{entry_id}")
        self.assertEqual(hist_res["status_code"], 200)
        self.assertEqual(hist_res["json"]["count"], 2)
        actions = [item["action"] for item in hist_res["json"]["history"]]
        self.assertIn("SUBMIT", actions)
        self.assertIn("SIGN_AND_APPROVE", actions)

    def test_rest_request_changes_loop(self) -> None:
        """Verify request-changes and re-submission cycle via REST API."""
        entry_id = "API-ENTRY-LOOP"

        # 1. Initial submission
        self.client.post(
            "/api/v1/approvals/submit",
            {
                "entry_id": entry_id,
                "author_id": "active_researcher",
                "policy": "PEER_REVIEW",
            },
        )

        # 2. Request changes
        req_res = self.client.post(
            "/api/v1/approvals/request-changes",
            {
                "entry_id": entry_id,
                "reviewer_id": "dr_reviewer",
                "reviewer_role": "active_researcher",
                "revision_comments": "Please add molecular weight standard documentation.",
            },
        )
        self.assertEqual(req_res["status_code"], 200)
        self.assertEqual(req_res["json"]["approval"]["status"], "CHANGES_REQUESTED")

        # 3. Resubmit
        resub_res = self.client.post(
            "/api/v1/approvals/submit",
            {
                "entry_id": entry_id,
                "author_id": "active_researcher",
                "policy": "PEER_REVIEW",
                "data_digest": "sha256:updated_mw_data",
            },
        )
        self.assertEqual(resub_res["status_code"], 200)
        self.assertEqual(resub_res["json"]["approval"]["status"], "PENDING_REVIEW")

        # 4. Sign and finalize
        final_sign = self.client.post(
            "/api/v1/approvals/sign",
            {
                "entry_id": entry_id,
                "reviewer_id": "dr_reviewer",
                "reviewer_role": "active_researcher",
                "review_notes": "Standards included properly. Approved.",
            },
        )
        self.assertEqual(final_sign["status_code"], 200)
        self.assertEqual(final_sign["json"]["approval"]["status"], "APPROVED")

    def test_rest_designated_reviewer_unauthorized_rejection(self) -> None:
        """Verify that an unauthorized reviewer gets HTTP 403 on designated reviewer policy."""
        entry_id = "API-ENTRY-DESIG"

        self.client.post(
            "/api/v1/approvals/submit",
            {
                "entry_id": entry_id,
                "author_id": "active_researcher",
                "policy": "DESIGNATED_REVIEWER",
                "designated_reviewer_id": "dr_expert_reviewer",
            },
        )

        # Impostor attempts to sign -> HTTP 403
        bad_sign = self.client.post(
            "/api/v1/approvals/sign",
            {
                "entry_id": entry_id,
                "reviewer_id": "unauthorized_user",
                "reviewer_role": "active_researcher",
                "review_notes": "Attempting unauthorized approval",
            },
        )
        self.assertEqual(bad_sign["status_code"], 403)
        self.assertEqual(bad_sign["json"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
