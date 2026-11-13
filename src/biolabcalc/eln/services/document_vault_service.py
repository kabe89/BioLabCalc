"""
Module: biolabcalc.eln.services.document_vault_service
Component: Laboratory Document Vault & CAS Knowledge Base Service
Architectural Role: Core service managing storage, cataloging, full-text retrieval,
and lifecycle of lab documentation (SOP PDFs, instrument manuals, chemical safety sheets,
published papers, experimental protocols) backed by Content-Addressable Storage (CAS)
with SHA-256 deduplication and manifest export/import capabilities.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

try:
    from biolabcalc.eln.storage.blob_store import BlobMetadata, BlobStore
    from biolabcalc.eln.services.audit_service import get_audit_service
except ImportError:
    from ..storage.blob_store import BlobMetadata, BlobStore
    from .audit_service import get_audit_service

# Standard regulatory and laboratory documentation categories
STANDARD_CATEGORIES: Tuple[str, ...] = (
    "SOP",
    "Instrument Manual",
    "Safety Sheet",
    "Paper",
    "Protocol",
)


@dataclass
class DocumentRecord:
    """
    Catalog metadata entity representing a registered lab documentation artifact.

    Architectural Role: Canonical catalog record indexing documentation assets
    stored in the Content-Addressable Storage (CAS) layer.

    Attributes:
        id (str): Unique document identifier (e.g. DOC-SOP-001 or DOC-A1B2C3D4).
        title (str): Human-readable document title or descriptive headline.
        category (str): Document classification (SOP, Instrument Manual, Safety Sheet, Paper, Protocol).
        tags (List[str]): Categorical keywords and metadata tags for faceted searching.
        sha256 (str): Hex-encoded SHA-256 digest referencing the CAS blob storage.
        filename (str): Original or canonical filename (e.g. 'AKTA_Pure_Manual.pdf').
        file_size_bytes (int): Total payload size in bytes.
        uploaded_by (str): Operator or researcher username who ingested the artifact.
        created_at (str): ISO 8601 UTC timestamp recording catalog insertion time.
        description (str): Detailed summary, abstract, or contextual notes.
        mime_type (str): Media MIME type of the document.
        metadata (Dict[str, Any]): Supplementary domain-specific or instrument metadata.
    """

    id: str
    title: str
    category: str
    tags: List[str]
    sha256: str
    filename: str
    file_size_bytes: int
    uploaded_by: str
    created_at: str
    description: str = ""
    mime_type: str = "application/octet-stream"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize document catalog entry to dictionary.

        Returns:
            Dict[str, Any]: Dictionary matching catalog schema.
        """
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "tags": list(self.tags),
            "sha256": self.sha256,
            "filename": self.filename,
            "file_size_bytes": self.file_size_bytes,
            "uploaded_by": self.uploaded_by,
            "created_at": self.created_at,
            "description": self.description,
            "mime_type": self.mime_type,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DocumentRecord:
        """
        Deserialize dictionary into a typed DocumentRecord.

        Args:
            data (Dict[str, Any]): Dictionary containing document fields.

        Returns:
            DocumentRecord: Reconstituted document entity.
        """
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            category=str(data.get("category", "Protocol")),
            tags=list(data.get("tags", [])),
            sha256=str(data["sha256"]),
            filename=str(data.get("filename", "")),
            file_size_bytes=int(data.get("file_size_bytes", 0)),
            uploaded_by=str(data.get("uploaded_by", "unknown")),
            created_at=str(data.get("created_at", datetime.now(timezone.utc).isoformat())),
            description=str(data.get("description", "")),
            mime_type=str(data.get("mime_type", "application/octet-stream")),
            metadata=dict(data.get("metadata", {})),
        )

    def __getitem__(self, item: str) -> Any:
        """Allow subscript access like a dictionary."""
        return getattr(self, item)

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow subscript mutation like a dictionary."""
        setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Dictionary-like get method."""
        return getattr(self, key, default)


class DocumentVaultService:
    """
    Laboratory Document Vault & Content-Addressable Knowledge Base Service.

    Features:
        - Cryptographic Content-Addressable Storage (CAS) with SHA-256 deduplication.
        - Structured cataloging for SOPs, Instrument Manuals, Safety Sheets (MSDS),
          Papers, and Experimental Protocols.
        - Multi-field faceted filtering and full-text keyword search across document
          metadata, tags, and decoded textual contents.
        - Manifest export/import for cross-laboratory protocol synchronization
          and disaster-recovery backups.
        - 21 CFR Part 11 compliant audit logging for all document lifecycle actions.
    """

    def __init__(
        self,
        blob_store: Optional[BlobStore] = None,
        base_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Initialize the Document Vault Service.

        Args:
            blob_store (Optional[BlobStore]): Custom or injected CAS BlobStore instance.
            base_dir (Optional[Union[str, Path]]): Base filesystem directory for local CAS storage
                when default BlobStore is instantiated.
        """
        self._lock = threading.RLock()
        self._catalog: Dict[str, DocumentRecord] = {}

        if blob_store is not None:
            self._blob_store = blob_store
        else:
            if base_dir is not None:
                self._blob_store = BlobStore(base_dir=base_dir)
            else:
                self._blob_store = BlobStore()

        self._audit_service = get_audit_service()

    @property
    def blob_store(self) -> BlobStore:
        """Access the underlying Content-Addressable Storage engine."""
        return self._blob_store

    def ingest_document(
        self,
        data: Union[bytes, str, Path],
        title: str,
        category: str = "Protocol",
        tags: Optional[Sequence[str]] = None,
        filename: str = "",
        uploaded_by: str = "unknown",
        doc_id: Optional[str] = None,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DocumentRecord:
        """
        Ingest a laboratory document into Content-Addressable Storage and index in catalog.

        Deduplication Guarantee:
            If an identical file has previously been ingested, CAS stores only a single
            physical copy on disk. Both catalog entries safely point to the identical
            SHA-256 content address.

        Args:
            data (Union[bytes, str, Path]): Raw bytes, text string, or path to file on disk.
            title (str): Descriptive document title.
            category (str): Document category ('SOP', 'Instrument Manual', 'Safety Sheet', 'Paper', 'Protocol').
            tags (Optional[Sequence[str]]): Tag keywords for search and filtering.
            filename (str): Original or intended filename (e.g. 'SOP_Ni_NTA_Purification.pdf').
            uploaded_by (str): Username or ID of the uploader.
            doc_id (Optional[str]): Explicit document ID. Generated automatically if omitted.
            description (str): Summary or contextual notes.
            metadata (Optional[Dict[str, Any]]): Arbitrary supplementary attributes.

        Returns:
            DocumentRecord: Registered catalog document record.
        """
        with self._lock:
            # Resolve binary payload and filename
            data_bytes: bytes
            resolved_filename = filename

            if isinstance(data, Path) or (isinstance(data, str) and os.path.isfile(data)):
                p = Path(data)
                if not resolved_filename:
                    resolved_filename = p.name
                with open(p, "rb") as f:
                    data_bytes = f.read()
            elif isinstance(data, str):
                data_bytes = data.encode("utf-8")
                if not resolved_filename:
                    resolved_filename = f"{title.lower().replace(' ', '_')[:32]}.txt"
            elif isinstance(data, bytes):
                data_bytes = data
                if not resolved_filename:
                    resolved_filename = f"doc_{uuid.uuid4().hex[:8]}.bin"
            elif hasattr(data, "read"):
                raw = data.read()
                data_bytes = raw if isinstance(raw, bytes) else str(raw).encode("utf-8")
                if not resolved_filename:
                    resolved_filename = f"doc_{uuid.uuid4().hex[:8]}.bin"
            else:
                raise TypeError(f"Unsupported document data type: {type(data).__name__}")

            # Store into CAS blob store (computes SHA-256 and deduplicates)
            blob_meta: BlobMetadata = self._blob_store.store_bytes(
                data=data_bytes,
                filename=resolved_filename,
                custom_attributes=metadata or {},
            )

            # Generate canonical Document ID if not specified
            if not doc_id:
                clean_cat = "".join(c for c in category.upper() if c.isalnum())[:6] or "DOC"
                doc_id = f"DOC-{clean_cat}-{uuid.uuid4().hex[:8].upper()}"

            now_iso = datetime.now(timezone.utc).isoformat()
            tags_list = list(tags) if tags else []

            record = DocumentRecord(
                id=doc_id,
                title=title,
                category=category,
                tags=tags_list,
                sha256=blob_meta.sha256,
                filename=resolved_filename,
                file_size_bytes=blob_meta.size_bytes,
                uploaded_by=uploaded_by,
                created_at=now_iso,
                description=description,
                mime_type=blob_meta.mime_type,
                metadata=metadata or {},
            )

            self._catalog[doc_id] = record

            # Record tamper-evident audit event
            self._audit_service.record_event(
                entity_type="document",
                entity_id=doc_id,
                action="INGEST",
                performed_by=uploaded_by,
                previous_state=None,
                new_state=record.to_dict(),
                metadata={
                    "sha256": blob_meta.sha256,
                    "category": category,
                    "file_size_bytes": blob_meta.size_bytes,
                },
            )

            return record

    # Ergonomic aliases
    add_document = ingest_document
    store_document = ingest_document
    upload_document = ingest_document

    def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        """
        Retrieve document catalog record by ID.

        Args:
            doc_id (str): Document ID.

        Returns:
            Optional[DocumentRecord]: Document record or None if absent.
        """
        with self._lock:
            return self._catalog.get(doc_id)

    def get_document_bytes(self, doc_id: str) -> bytes:
        """
        Retrieve raw binary payload of document from CAS blob storage.

        Args:
            doc_id (str): Document ID.

        Returns:
            bytes: Binary content.

        Raises:
            KeyError: If document ID is not in catalog.
            FileNotFoundError: If underlying blob is missing.
        """
        with self._lock:
            doc = self._catalog.get(doc_id)
            if not doc:
                raise KeyError(f"Document with ID '{doc_id}' not found in vault catalog.")
            return self._blob_store.get_bytes(doc.sha256)

    def get_document_path(self, doc_id: str) -> str:
        """
        Resolve filesystem path or URI for a stored document's CAS blob.

        Args:
            doc_id (str): Document ID.

        Returns:
            str: Path or URI of the blob.
        """
        with self._lock:
            doc = self._catalog.get(doc_id)
            if not doc:
                raise KeyError(f"Document with ID '{doc_id}' not found in vault catalog.")
            return self._blob_store.get_file_path(doc.sha256)

    def delete_document(self, doc_id: str, delete_blob_if_orphan: bool = False) -> bool:
        """
        Remove document from catalog, with optional orphan CAS blob deletion.

        Args:
            doc_id (str): Document ID.
            delete_blob_if_orphan (bool): When True, deletes physical CAS blob if no other
                catalog entry references its SHA-256 hash.

        Returns:
            bool: True if document existed and was deleted; False otherwise.
        """
        with self._lock:
            doc = self._catalog.pop(doc_id, None)
            if not doc:
                return False

            prev_state = doc.to_dict()

            if delete_blob_if_orphan:
                other_refs = any(d.sha256 == doc.sha256 for d in self._catalog.values())
                if not other_refs:
                    self._blob_store.delete(doc.sha256)

            self._audit_service.record_event(
                entity_type="document",
                entity_id=doc_id,
                action="DELETE",
                performed_by="vault_admin",
                previous_state=prev_state,
                new_state=None,
                metadata={"sha256": doc.sha256, "orphan_deleted": delete_blob_if_orphan},
            )
            return True

    def list_documents(
        self,
        category: Optional[str] = None,
        tags: Optional[Union[Sequence[str], str]] = None,
    ) -> List[DocumentRecord]:
        """
        List cataloged documents, optionally filtered by category and tags.

        Args:
            category (Optional[str]): Category filter.
            tags (Optional[Union[Sequence[str], str]]): Required tags.

        Returns:
            List[DocumentRecord]: Matching document records.
        """
        with self._lock:
            docs = list(self._catalog.values())

            if category:
                cat_clean = category.strip().lower()
                docs = [d for d in docs if d.category.strip().lower() == cat_clean]

            if tags:
                tag_list = [tags] if isinstance(tags, str) else list(tags)
                req_tags = {t.strip().lower() for t in tag_list if t.strip()}
                docs = [
                    d for d in docs
                    if req_tags.issubset({t.strip().lower() for t in d.tags})
                ]

            return sorted(docs, key=lambda d: d.created_at, reverse=True)

    def search_documents(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[Union[Sequence[str], str]] = None,
    ) -> List[DocumentRecord]:
        """
        Full-text search and keyword tagging filter across document catalog and contents.

        Search Evaluation:
            1. Category filter: exact case-insensitive match on `category`.
            2. Tag filter: document must possess all specified `tags` (case-insensitive subset).
            3. Query string filter: matches against title, filename, description, tags,
               and full-text content of the stored CAS blob (decoded UTF-8 text).

        Args:
            query (Optional[str]): Text search term or phrase.
            category (Optional[str]): Filter by document category (e.g. 'SOP', 'Safety Sheet').
            tags (Optional[Union[Sequence[str], str]]): Filter by keyword tags.

        Returns:
            List[DocumentRecord]: Matching document records sorted by creation timestamp descending.
        """
        with self._lock:
            candidates = list(self._catalog.values())

            # 1. Filter by category
            if category:
                cat_lower = category.strip().lower()
                candidates = [c for c in candidates if c.category.strip().lower() == cat_lower]

            # 2. Filter by keyword tags
            if tags:
                tag_list = [tags] if isinstance(tags, str) else list(tags)
                required_tags = {t.strip().lower() for t in tag_list if t.strip()}
                candidates = [
                    c for c in candidates
                    if required_tags.issubset({t.strip().lower() for t in c.tags})
                ]

            # 3. Filter by text query across metadata and blob contents
            if query and query.strip():
                q = query.strip().lower()
                matched: List[DocumentRecord] = []

                for doc in candidates:
                    # Check metadata fields
                    if (
                        q in doc.title.lower()
                        or q in doc.filename.lower()
                        or q in doc.description.lower()
                        or any(q in t.lower() for t in doc.tags)
                    ):
                        matched.append(doc)
                        continue

                    # Check full-text content inside the CAS blob
                    try:
                        content_bytes = self._blob_store.get_bytes(doc.sha256)
                        # Decode up to first 2 MB of textual content
                        sample_bytes = content_bytes[:2 * 1024 * 1024]
                        text_content = sample_bytes.decode("utf-8", errors="ignore").lower()
                        if q in text_content:
                            matched.append(doc)
                    except Exception:
                        pass

                candidates = matched

            return sorted(candidates, key=lambda d: d.created_at, reverse=True)

    def export_manifest(self, filepath: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Export all document catalog metadata as a standardized JSON manifest.

        Args:
            filepath (Optional[Union[str, Path]]): Destination file path. If provided, writes
                manifest to disk.

        Returns:
            Dict[str, Any]: Manifest dictionary containing metadata list.
        """
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            manifest = {
                "manifest_version": "1.0",
                "exported_at": now_iso,
                "total_documents": len(self._catalog),
                "documents": [doc.to_dict() for doc in self._catalog.values()],
            }

            if filepath:
                p = Path(filepath)
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)

            return manifest

    def export_manifest_json(self) -> str:
        """
        Export manifest serialized as formatted JSON string.

        Returns:
            str: JSON representation of vault manifest.
        """
        return json.dumps(self.export_manifest(), indent=2)

    def import_manifest(
        self,
        manifest_data: Union[Dict[str, Any], List[Dict[str, Any]], str, Path],
        merge: bool = True,
    ) -> int:
        """
        Import catalog metadata from an exported manifest.

        Args:
            manifest_data: Manifest dictionary, document list, JSON string, or path to JSON file.
            merge (bool): If True (default), updates existing records and inserts new ones.
                If False, wipes current catalog before importing.

        Returns:
            int: Total number of documents successfully imported.
        """
        with self._lock:
            # Normalize manifest input
            parsed_data: Any = manifest_data
            if isinstance(manifest_data, (Path, str)):
                if os.path.isfile(str(manifest_data)):
                    with open(manifest_data, "r", encoding="utf-8") as f:
                        parsed_data = json.load(f)
                elif isinstance(manifest_data, str) and manifest_data.strip().startswith(("{", "[")):
                    parsed_data = json.loads(manifest_data)

            doc_items: List[Dict[str, Any]] = []
            if isinstance(parsed_data, dict):
                doc_items = parsed_data.get("documents", [])
            elif isinstance(parsed_data, list):
                doc_items = parsed_data

            if not merge:
                self._catalog.clear()

            imported_count = 0
            for item in doc_items:
                try:
                    record = DocumentRecord.from_dict(item)
                    self._catalog[record.id] = record
                    imported_count += 1
                except Exception:
                    continue

            self._audit_service.record_event(
                entity_type="document_manifest",
                entity_id=f"MANIFEST-IMPORT-{uuid.uuid4().hex[:6].upper()}",
                action="IMPORT_MANIFEST",
                performed_by="vault_admin",
                previous_state=None,
                new_state={"imported_count": imported_count, "merge": merge},
                metadata={"imported_documents": imported_count},
            )

            return imported_count

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Compute CAS storage efficiency and deduplication metrics.

        Returns:
            Dict[str, Any]: Metrics on total documents, unique blobs, logical vs. disk bytes,
                and storage deduplication savings.
        """
        with self._lock:
            total_docs = len(self._catalog)
            unique_shas: Set[str] = {doc.sha256 for doc in self._catalog.values()}
            total_logical_bytes = sum(doc.file_size_bytes for doc in self._catalog.values())

            # Disk bytes for unique blobs
            disk_bytes = 0
            for sha in unique_shas:
                meta = self._blob_store.get_metadata(sha)
                if meta:
                    disk_bytes += meta.size_bytes

            savings = total_logical_bytes - disk_bytes
            ratio = (total_logical_bytes / disk_bytes) if disk_bytes > 0 else 1.0

            return {
                "total_documents": total_docs,
                "unique_blobs": len(unique_shas),
                "total_logical_bytes": total_logical_bytes,
                "deduplicated_disk_bytes": disk_bytes,
                "space_saved_bytes": max(0, savings),
                "deduplication_ratio": round(ratio, 2),
            }

    def clear_for_testing(self) -> None:
        """
        Reset internal catalog state. For unit testing harness use only.
        """
        with self._lock:
            self._catalog.clear()


_global_document_vault_service = DocumentVaultService()


def get_document_vault_service() -> DocumentVaultService:
    """
    Get the process-level singleton instance of DocumentVaultService.

    Returns:
        DocumentVaultService: Global singleton instance.
    """
    return _global_document_vault_service
