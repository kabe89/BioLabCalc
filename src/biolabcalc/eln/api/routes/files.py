"""
Module: biolabcalc.eln.api.routes.files
Component: Content-Addressable Storage (CAS) Upload & HITL OCR Token Correction Endpoints
Agent: @agent: eln-api-agent
Architectural Role: REST routes providing SHA-256 Content-Addressable Storage (CAS) file ingestion,
deduplication, and Human-In-The-Loop (HITL) OCR token review and manual correction workflows.
"""

from __future__ import annotations

import base64
import hashlib
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...services.audit_service import get_audit_service
from ...storage.blob_store import BlobStore
from ..auth import PERM_FILE_OCR_CORRECT, PERM_FILE_UPLOAD, UserSession, get_auth_service
from ..router import Router

router = Router(prefix="/api/files")
audit_service = get_audit_service()
auth_service = get_auth_service()


@dataclass
class OCRToken:
    """
    Individual OCR token recognized from an experimental document, gel scan, or spectrometer report.

    Agent: @agent: eln-api-agent
    Architectural Role: Stores bounding box, recognized text, confidence score, and human corrections.
    """

    token_id: str
    original_text: str
    corrected_text: str
    confidence: float
    bounding_box: Dict[str, float]  # x, y, width, height
    is_corrected: bool = False
    corrected_by: Optional[str] = None
    corrected_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize OCR token to dictionary. Agent: @agent: eln-api-agent"""
        return asdict(self)


@dataclass
class StoredFile:
    """
    Content-Addressable Storage (CAS) file metadata and payload envelope.

    Agent: @agent: eln-api-agent
    Architectural Role: Stores immutable SHA-256 hash, byte payload or storage path, and associated OCR tokens.
    """

    file_id: str
    sha256_hash: str
    filename: str
    mime_type: str
    size_bytes: int
    storage_path: str = ""
    content_b64: Optional[str] = None
    ocr_tokens: List[OCRToken] = field(default_factory=list)
    uploaded_by: str = "unknown"
    uploaded_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize stored file metadata to dictionary. Agent: @agent: eln-api-agent"""
        return {
            "file_id": self.file_id,
            "sha256_hash": self.sha256_hash,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "storage_path": self.storage_path,
            "uploaded_by": self.uploaded_by,
            "uploaded_at": self.uploaded_at,
            "ocr_tokens_count": len(self.ocr_tokens),
            "ocr_tokens": [t.to_dict() for t in self.ocr_tokens],
        }


class CASFileStorage:
    """
    CAS storage registry backed by disk BlobStore with SHA-256 deduplication and HITL OCR ledger.

    Agent: @agent: eln-api-agent
    Architectural Role: Governs immutable file deduplication, CAS persistence, and OCR token corrections.
    """

    def __init__(self, blob_store: Optional[BlobStore] = None) -> None:
        self._lock = threading.Lock()
        self.blob_store = blob_store or BlobStore()
        self._by_hash: Dict[str, StoredFile] = {}
        self._by_id: Dict[str, StoredFile] = {}

    def store_file(
        self,
        filename: str,
        content_bytes: bytes,
        mime_type: str = "application/octet-stream",
        uploaded_by: str = "unknown",
        ocr_tokens: Optional[List[Dict[str, Any]]] = None,
    ) -> StoredFile:
        """Store file using SHA-256 addressable key into BlobStore. Agent: @agent: eln-api-agent"""
        with self._lock:
            # Persist to disk-backed CAS BlobStore
            custom_attributes: Dict[str, Any] = {"uploaded_by": uploaded_by}
            if ocr_tokens:
                custom_attributes["ocr_tokens"] = ocr_tokens
            blob_meta = self.blob_store.store_bytes(
                data=content_bytes,
                filename=filename,
                mime_type=mime_type,
                custom_attributes=custom_attributes,
            )
            sha256_hex = blob_meta.sha256

            # Deduplication check
            if sha256_hex in self._by_hash:
                existing = self._by_hash[sha256_hex]
                return existing

            file_id = f"FILE-{sha256_hex[:12].upper()}"
            now_iso = datetime.now(timezone.utc).isoformat()

            tokens: List[OCRToken] = []
            if ocr_tokens:
                for idx, t in enumerate(ocr_tokens):
                    tokens.append(
                        OCRToken(
                            token_id=t.get("token_id", f"TOK-{idx+1}"),
                            original_text=t.get("original_text", ""),
                            corrected_text=t.get("corrected_text", t.get("original_text", "")),
                            confidence=float(t.get("confidence", 0.95)),
                            bounding_box=t.get("bounding_box", {"x": 0.0, "y": 0.0, "width": 50.0, "height": 20.0}),
                        )
                    )

            stored = StoredFile(
                file_id=file_id,
                sha256_hash=sha256_hex,
                filename=filename,
                mime_type=mime_type,
                size_bytes=len(content_bytes),
                storage_path=blob_meta.storage_path,
                content_b64=None,
                ocr_tokens=tokens,
                uploaded_by=uploaded_by,
                uploaded_at=now_iso,
            )
            self._by_hash[sha256_hex] = stored
            self._by_id[file_id] = stored
            return stored

    def get_file(self, file_id_or_hash: str) -> Optional[StoredFile]:
        """Lookup file by file_id or hash. Agent: @agent: eln-api-agent"""
        with self._lock:
            res = self._by_id.get(file_id_or_hash) or self._by_hash.get(file_id_or_hash)
            if res:
                return res
            # Check if exists in blob_store
            meta = self.blob_store.get_metadata(file_id_or_hash.lower())
            if meta:
                file_id = f"FILE-{meta.sha256[:12].upper()}"
                tokens: List[OCRToken] = []
                raw_tokens = meta.custom_attributes.get("ocr_tokens", [])
                for idx, t in enumerate(raw_tokens):
                    tokens.append(
                        OCRToken(
                            token_id=t.get("token_id", f"TOK-{idx+1}"),
                            original_text=t.get("original_text", ""),
                            corrected_text=t.get("corrected_text", t.get("original_text", "")),
                            confidence=float(t.get("confidence", 0.95)),
                            bounding_box=t.get("bounding_box", {"x": 0.0, "y": 0.0, "width": 50.0, "height": 20.0}),
                            is_corrected=t.get("is_corrected", False),
                            corrected_by=t.get("corrected_by"),
                            corrected_at=t.get("corrected_at"),
                        )
                    )
                stored = StoredFile(
                    file_id=file_id,
                    sha256_hash=meta.sha256,
                    filename=meta.filename,
                    mime_type=meta.mime_type,
                    size_bytes=meta.size_bytes,
                    storage_path=meta.storage_path,
                    uploaded_by=meta.custom_attributes.get("uploaded_by", "unknown"),
                    uploaded_at=meta.created_at,
                    ocr_tokens=tokens,
                )
                self._by_hash[meta.sha256] = stored
                self._by_id[file_id] = stored
                return stored
            return None

    def correct_ocr_token(
        self,
        file_id: str,
        token_id: str,
        corrected_text: str,
        user_id: str,
    ) -> OCRToken:
        """Apply human-in-the-loop OCR token correction. Agent: @agent: eln-api-agent"""
        with self._lock:
            file_obj = self._by_id.get(file_id)
            if not file_obj:
                raise KeyError(f"File '{file_id}' not found.")

            target_token = next((t for t in file_obj.ocr_tokens if t.token_id == token_id), None)
            if not target_token:
                raise KeyError(f"OCR token '{token_id}' not found in file '{file_id}'.")

            prev_state = target_token.to_dict()
            target_token.corrected_text = corrected_text
            target_token.is_corrected = True
            target_token.corrected_by = user_id
            target_token.corrected_at = datetime.now(timezone.utc).isoformat()

            try:
                self.blob_store.update_metadata(
                    file_obj.sha256_hash,
                    {"ocr_tokens": [t.to_dict() for t in file_obj.ocr_tokens]},
                )
            except Exception:
                pass

            audit_service.record_event(
                entity_type="ocr_token",
                entity_id=token_id,
                action="OCR_TOKEN_CORRECT",
                performed_by=user_id,
                previous_state=prev_state,
                new_state=target_token.to_dict(),
                metadata={"file_id": file_id, "original": target_token.original_text, "corrected": corrected_text},
            )
            return target_token


_cas_storage = CASFileStorage()


@router.post("/upload")
@auth_service.require_permission(PERM_FILE_UPLOAD)
def upload_file(payload: Dict[str, Any], current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Upload file into Content-Addressable Storage (CAS) with SHA-256 deduplication and optional OCR tokens.

    Agent: @agent: eln-api-agent
    Parameter payload (Dict[str, Any]): Upload payload containing 'filename', 'content_b64' or 'content_text', optional 'mime_type', 'ocr_tokens'.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    filename = payload["filename"]
    mime_type = payload.get("mime_type", "application/octet-stream")

    if "content_b64" in payload:
        raw_bytes = base64.b64decode(payload["content_b64"])
    elif "content_text" in payload:
        raw_bytes = payload["content_text"].encode("utf-8")
    else:
        raise ValueError("Payload must contain 'content_b64' or 'content_text'.")

    stored = _cas_storage.store_file(
        filename=filename,
        content_bytes=raw_bytes,
        mime_type=mime_type,
        uploaded_by=user_id,
        ocr_tokens=payload.get("ocr_tokens"),
    )
    return {"status": "success", "file": stored.to_dict()}


@router.get("/{file_id}")
def get_file_metadata(file_id: str, current_user: Optional[UserSession] = None) -> Dict[str, Any]:
    """
    Retrieve stored file metadata and OCR tokens.

    Agent: @agent: eln-api-agent
    Parameter file_id (str): CAS file ID or SHA-256 hash.
    Parameter current_user (Optional[UserSession]): Authenticated user.
    Return Type: Dict[str, Any]
    """
    file_obj = _cas_storage.get_file(file_id)
    if not file_obj:
        return {"status": "error", "message": f"File '{file_id}' not found."}, 404
    return {"status": "success", "file": file_obj.to_dict()}


@router.post("/{file_id}/ocr-correct")
@auth_service.require_permission(PERM_FILE_OCR_CORRECT)
def correct_ocr_token(
    file_id: str,
    payload: Dict[str, Any],
    current_user: Optional[UserSession] = None,
) -> Dict[str, Any]:
    """
    Human-In-The-Loop (HITL) OCR token correction endpoint.

    Agent: @agent: eln-api-agent
    Parameter file_id (str): Target file ID.
    Parameter payload (Dict[str, Any]): Correction payload ('token_id', 'corrected_text').
    Parameter current_user (Optional[UserSession]): Authenticated operator.
    Return Type: Dict[str, Any]
    """
    user_id = current_user.username if current_user else "active_researcher"
    token = _cas_storage.correct_ocr_token(
        file_id=file_id,
        token_id=payload["token_id"],
        corrected_text=payload["corrected_text"],
        user_id=user_id,
    )
    return {"status": "success", "corrected_token": token.to_dict()}
