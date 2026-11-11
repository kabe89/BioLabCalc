"""
Module: biolabcalc.eln.api.auth
Component: Role-Based Access Control (RBAC) & Authentication Engine
Architectural Role: Core security module defining user identities, session authorization tokens,
fine-grained permission matrices for laboratory roles (pi_admin, active_researcher, rotation_student,
alumni_readonly), and route protection decorators.
"""

from __future__ import annotations

import functools
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

# Standard ELN laboratory roles
ROLE_PI_ADMIN: str = "pi_admin"
ROLE_ACTIVE_RESEARCHER: str = "active_researcher"
ROLE_ROTATION_STUDENT: str = "rotation_student"
ROLE_ALUMNI_READONLY: str = "alumni_readonly"
ROLE_GUEST: str = "guest"

ALL_ROLES: Set[str] = {
    ROLE_PI_ADMIN,
    ROLE_ACTIVE_RESEARCHER,
    ROLE_ROTATION_STUDENT,
    ROLE_ALUMNI_READONLY,
    ROLE_GUEST,
}

# Fine-grained granular permissions
PERM_CAMPAIGN_CREATE: str = "campaign:create"
PERM_CAMPAIGN_EDIT: str = "campaign:edit"
PERM_CAMPAIGN_COMPLETE: str = "campaign:complete"
PERM_ENTRY_CREATE: str = "entry:create"
PERM_ENTRY_EDIT: str = "entry:edit"
PERM_SOP_CREATE: str = "sop:create"
PERM_SOP_APPROVE: str = "sop:approve"
PERM_SOP_FORK: str = "sop:fork"
PERM_TIMEPOINT_RECORD: str = "timepoint:record"
PERM_FPLC_POOL: str = "fplc:pool"
PERM_GEL_TAG: str = "gel:tag"
PERM_INVENTORY_PLACE: str = "inventory:place"
PERM_INVENTORY_MOVE: str = "inventory:move"
PERM_INVENTORY_DELETE: str = "inventory:delete"
PERM_AUDIT_VIEW: str = "audit:view"
PERM_AUDIT_VERIFY: str = "audit:verify"
PERM_FILE_UPLOAD: str = "file:upload"
PERM_FILE_OCR_CORRECT: str = "file:ocr_correct"

# Role-to-Permissions Mapping
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    ROLE_PI_ADMIN: {
        PERM_CAMPAIGN_CREATE,
        PERM_CAMPAIGN_EDIT,
        PERM_CAMPAIGN_COMPLETE,
        PERM_ENTRY_CREATE,
        PERM_ENTRY_EDIT,
        PERM_SOP_CREATE,
        PERM_SOP_APPROVE,
        PERM_SOP_FORK,
        PERM_TIMEPOINT_RECORD,
        PERM_FPLC_POOL,
        PERM_GEL_TAG,
        PERM_INVENTORY_PLACE,
        PERM_INVENTORY_MOVE,
        PERM_INVENTORY_DELETE,
        PERM_AUDIT_VIEW,
        PERM_AUDIT_VERIFY,
        PERM_FILE_UPLOAD,
        PERM_FILE_OCR_CORRECT,
    },
    ROLE_ACTIVE_RESEARCHER: {
        PERM_CAMPAIGN_CREATE,
        PERM_CAMPAIGN_EDIT,
        PERM_ENTRY_CREATE,
        PERM_ENTRY_EDIT,
        PERM_SOP_CREATE,
        PERM_SOP_FORK,
        PERM_TIMEPOINT_RECORD,
        PERM_FPLC_POOL,
        PERM_GEL_TAG,
        PERM_INVENTORY_PLACE,
        PERM_INVENTORY_MOVE,
        PERM_AUDIT_VIEW,
        PERM_AUDIT_VERIFY,
        PERM_FILE_UPLOAD,
        PERM_FILE_OCR_CORRECT,
    },
    ROLE_ROTATION_STUDENT: {
        PERM_ENTRY_CREATE,
        PERM_ENTRY_EDIT,
        PERM_SOP_FORK,
        PERM_TIMEPOINT_RECORD,
        PERM_INVENTORY_PLACE,
        PERM_AUDIT_VIEW,
        PERM_FILE_UPLOAD,
    },
    ROLE_ALUMNI_READONLY: {
        PERM_AUDIT_VIEW,
    },
    ROLE_GUEST: set(),
}


class AuthorizationError(Exception):
    """
    Raised when an authenticated user lacks sufficient role or permission.

    """

    def __init__(self, message: str, required_role: Optional[str] = None, required_permission: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.required_role = required_role
        self.required_permission = required_permission


@dataclass
class UserSession:
    """
    Authenticated user session representation.

    Architectural Role: Carries operator identity, laboratory role, and effective permissions.
    """

    user_id: str
    username: str
    display_name: str
    role: str
    token: str
    created_at: str

    def has_permission(self, permission: str) -> bool:
        """
        Check if user's role grants the requested permission.

        Parameter permission (str): Required permission key.
        Return Type: bool
        """
        role_perms = ROLE_PERMISSIONS.get(self.role, set())
        return permission in role_perms

    def to_dict(self) -> Dict[str, Any]:
        """Serialize user session to dictionary."""
        return asdict(self)


class AuthService:
    """
    Authentication & RBAC session manager for the ELN & LIMS pipeline.

    Architectural Role: Manages token issuance, user session lookup, and permission validation.
    """

    def __init__(self) -> None:
        """
        Initialize AuthService and register default laboratory accounts.

        """
        self._lock = threading.Lock()
        self._sessions: Dict[str, UserSession] = {}
        self._seed_default_users()

    def _seed_default_users(self) -> None:
        """
        Pre-seed default accounts for development and automated pipeline testing.

        """
        defaults = [
            ("USR-PI-001", "pi_admin", "Prof. Principal Investigator", ROLE_PI_ADMIN, "token-pi-admin"),
            ("USR-RES-001", "active_researcher", "Dr. Lead Postdoc", ROLE_ACTIVE_RESEARCHER, "token-active-researcher"),
            ("USR-STU-001", "rotation_student", "Alex Student", ROLE_ROTATION_STUDENT, "token-rotation-student"),
            ("USR-ALU-001", "alumni_readonly", "Dr. Former LabMember", ROLE_ALUMNI_READONLY, "token-alumni-readonly"),
        ]
        now_iso = datetime.now(timezone.utc).isoformat()
        for uid, uname, dname, role, token in defaults:
            self._sessions[token] = UserSession(
                user_id=uid,
                username=uname,
                display_name=dname,
                role=role,
                token=token,
                created_at=now_iso,
            )

    def authenticate_token(self, token_or_header: Optional[str]) -> UserSession:
        """
        Authenticate bearer token or header and return active UserSession.

        Parameter token_or_header (Optional[str]): Bearer token string or 'Bearer <token>' header.
        Return Type: UserSession
        """
        with self._lock:
            if not token_or_header:
                now_iso = datetime.now(timezone.utc).isoformat()
                return UserSession(
                    user_id="USR-GUEST",
                    username="guest",
                    display_name="Guest User",
                    role=ROLE_GUEST,
                    token="",
                    created_at=now_iso,
                )

            token = token_or_header.strip()
            if token.lower().startswith("bearer "):
                token = token[7:].strip()

            session = self._sessions.get(token)
            if not session:
                raise AuthorizationError(f"Invalid or expired authentication token: '{token}'")
            return session

    def require_role(self, allowed_roles: List[str]) -> Callable:
        """
        Decorator enforcing that caller has one of the allowed roles.

        Parameter allowed_roles (List[str]): List of acceptable roles.
        Return Type: Callable
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                user = kwargs.get("current_user")
                if not user:
                    # Check first arg if instance of UserSession
                    for a in args:
                        if isinstance(a, UserSession):
                            user = a
                            break

                if not user or user.role not in allowed_roles:
                    uname = user.username if user else "anonymous"
                    urole = user.role if user else "none"
                    raise AuthorizationError(
                        f"Access denied: User '{uname}' with role '{urole}' "
                        f"does not have required role in {allowed_roles}",
                        required_role=",".join(allowed_roles),
                    )
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def require_permission(self, permission: str) -> Callable:
        """
        Decorator enforcing that caller has a specific granular permission.

        Parameter permission (str): Required permission key.
        Return Type: Callable
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                user = kwargs.get("current_user")
                if not user:
                    for a in args:
                        if isinstance(a, UserSession):
                            user = a
                            break

                if not user or not user.has_permission(permission):
                    uname = user.username if user else "anonymous"
                    urole = user.role if user else "none"
                    raise AuthorizationError(
                        f"Access denied: User '{uname}' with role '{urole}' "
                        f"lacks required permission '{permission}'",
                        required_permission=permission,
                    )
                return func(*args, **kwargs)

            return wrapper

        return decorator


_global_auth_service = AuthService()


def get_auth_service() -> AuthService:
    """
    Get the process-level singleton instance of AuthService.

    Return Type: AuthService
    """
    return _global_auth_service
