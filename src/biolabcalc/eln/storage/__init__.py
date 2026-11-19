"""
Module: biolabcalc.eln.storage
Component: Content-Addressable Storage (CAS) and Asset Preview Package
Architectural Role: Exports Content-Addressable Storage engine, metadata schemas,
storage backends, and multi-modal preview generators for the ELN & LIMS pipeline.
"""

from biolabcalc.eln.storage.blob_store import (
    BlobMetadata,
    BlobStore,
    LocalStorageBackend,
    S3StorageBackend,
    StorageBackend,
)
from biolabcalc.eln.storage.preview_generator import (
    PreviewGenerator,
    PreviewResult,
)
from biolabcalc.eln.storage.sqlite_store import (
    SQLiteStore,
    get_sqlite_store,
)

__all__ = [
    "BlobMetadata",
    "BlobStore",
    "StorageBackend",
    "LocalStorageBackend",
    "S3StorageBackend",
    "PreviewGenerator",
    "PreviewResult",
    "SQLiteStore",
    "get_sqlite_store",
]
