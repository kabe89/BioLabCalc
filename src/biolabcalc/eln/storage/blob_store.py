"""
Module: biolabcalc.eln.storage.blob_store
Component: Content-Addressable Storage (CAS) Engine
Architectural Role: Provides SHA-256 deduplicated, tamper-evident immutable blob
storage with local filesystem sharding and S3/MinIO cloud backend abstraction.
"""

from __future__ import annotations

import abc
import datetime
import hashlib
import json
import mimetypes
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class BlobMetadata:
    """
    Metadata representation for a stored content-addressable blob.

    Attributes:
        sha256 (str): Hex-encoded SHA-256 digest of the blob contents.
        size_bytes (int): Total size of the blob in bytes.
        mime_type (str): Media MIME type of the stored asset.
        filename (str): Original or canonical filename of the stored artifact.
        created_at (str): ISO 8601 UTC timestamp recording insertion time.
        storage_path (str): Relative or URI-based path where the blob is retained.
        etag (Optional[str]): S3/MinIO ETag or entity identifier.
        backend (str): Identifier of the active storage backend ('local', 's3', etc.).
        custom_attributes (Dict[str, Any]): Supplementary domain-specific tags or metadata.

    Architectural Role:
        Data transfer object for immutable CAS references across ELN and LIMS layers.
    """

    sha256: str
    size_bytes: int
    mime_type: str
    filename: str
    created_at: str
    storage_path: str
    etag: Optional[str] = None
    backend: str = "local"
    custom_attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize metadata object to a dictionary.

        Returns:
            Dict[str, Any]: Key-value dictionary matching schema fields.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BlobMetadata:
        """
        Deserialize dictionary into a BlobMetadata object.

        Args:
            data (Dict[str, Any]): Key-value mapping representing blob metadata.

        Returns:
            BlobMetadata: Instantiated and typed metadata object.
        """
        return cls(
            sha256=data["sha256"],
            size_bytes=int(data["size_bytes"]),
            mime_type=data.get("mime_type", "application/octet-stream"),
            filename=data.get("filename", ""),
            created_at=data.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            storage_path=data.get("storage_path", ""),
            etag=data.get("etag"),
            backend=data.get("backend", "local"),
            custom_attributes=data.get("custom_attributes", {}),
        )


class StorageBackend(abc.ABC):
    """
    Abstract base interface for content-addressable storage backends.

    Architectural Role:
        Decouples storage mechanics (Local Disk, S3, MinIO) from higher-level
        ingestion and parser orchestration.
    """

    @abc.abstractmethod
    def store(self, sha256: str, data: bytes, metadata: BlobMetadata) -> BlobMetadata:
        """
        Store raw bytes indexed by their SHA-256 digest.

        Args:
            sha256 (str): SHA-256 hexadecimal hash.
            data (bytes): Raw binary content.
            metadata (BlobMetadata): Ingestion metadata.

        Returns:
            BlobMetadata: Persisted metadata descriptor.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def retrieve(self, sha256: str) -> bytes:
        """
        Retrieve raw binary data associated with the given SHA-256 digest.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            bytes: Binary payload.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_path(self, sha256: str) -> str:
        """
        Resolve the physical path or URI location of the blob.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            str: Absolute file path or URI string.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def exists(self, sha256: str) -> bool:
        """
        Check if a blob exists in the storage backend.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            bool: True if present, False otherwise.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, sha256: str) -> bool:
        """
        Delete a blob and its metadata from storage.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            bool: True if deleted, False if not found.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_metadata(self, sha256: str) -> Optional[BlobMetadata]:
        """
        Load metadata associated with the given SHA-256 hash.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            Optional[BlobMetadata]: Blob metadata if present, else None.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def list_blobs(self, limit: Optional[int] = None, offset: int = 0) -> List[BlobMetadata]:
        """
        Enumerate all blobs stored in this backend.

        Returns:
            List[BlobMetadata]: Collection of stored blob metadata entries.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def update_metadata(self, sha256: str, custom_attributes: Dict[str, Any]) -> Optional[BlobMetadata]:
        """
        Update custom attributes for a stored blob.

        Args:
            sha256 (str): SHA-256 hash.
            custom_attributes (Dict[str, Any]): Attributes to merge into existing metadata.

        Returns:
            Optional[BlobMetadata]: Updated metadata if blob exists, else None.
        """
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    """
    Local filesystem CAS implementation with two-tier directory sharding.

    Blobs are organized on disk using the first 2 characters of their SHA-256 hash:
        {base_dir}/{sha256[:2]}/{sha256}.blob
        {base_dir}/{sha256[:2]}/{sha256}.meta.json

    Architectural Role:
        High-throughput local and workstation storage driver.
    """

    def __init__(self, base_dir: Union[str, Path] = ".biolabcalc_data/blobs"):
        """
        Initialize the local storage backend.

        Args:
            base_dir (Union[str, Path]): Root directory for blob and metadata storage.
        """
        self.base_dir = Path(base_dir).resolve()
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            self.base_dir = Path(tempfile.gettempdir()) / "biolabcalc_data" / "blobs"
            self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_shard_dir(self, sha256: str) -> Path:
        """
        Compute sharded directory path from the SHA-256 prefix.

        Args:
            sha256 (str): Hash key.

        Returns:
            Path: Destination directory for shard.
        """
        shard = sha256[:2].lower()
        shard_path = self.base_dir / shard
        shard_path.mkdir(parents=True, exist_ok=True)
        return shard_path

    def _blob_file(self, sha256: str) -> Path:
        """
        Get target path for blob binary file.

        Args:
            sha256 (str): Hash key.

        Returns:
            Path: Path to .blob file.
        """
        return self._get_shard_dir(sha256) / f"{sha256}.blob"

    def _meta_file(self, sha256: str) -> Path:
        """
        Get target path for blob metadata JSON.

        Args:
            sha256 (str): Hash key.

        Returns:
            Path: Path to .meta.json file.
        """
        return self._get_shard_dir(sha256) / f"{sha256}.meta.json"

    def store(self, sha256: str, data: bytes, metadata: BlobMetadata) -> BlobMetadata:
        """
        Store data with atomic file writes to prevent corrupted reads.

        Args:
            sha256 (str): SHA-256 hash.
            data (bytes): Content bytes.
            metadata (BlobMetadata): Ingestion metadata.

        Returns:
            BlobMetadata: Stored metadata with finalized local file path.
        """
        blob_path = self._blob_file(sha256)
        meta_path = self._meta_file(sha256)

        metadata.storage_path = str(blob_path)
        metadata.backend = "local"

        # Deduplication check: if file exists and size matches, write metadata only if needed
        if blob_path.exists() and blob_path.stat().st_size == len(data):
            if not meta_path.exists():
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(metadata.to_dict(), f, indent=2)
            return metadata

        # Atomic write to temporary file first, then replace
        temp_dir = self._get_shard_dir(sha256)
        with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False) as tf:
            tf.write(data)
            temp_name = tf.name

        shutil.move(temp_name, str(blob_path))

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2)

        return metadata

    def retrieve(self, sha256: str) -> bytes:
        """
        Retrieve raw binary data from disk.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            bytes: Content bytes.

        Raises:
            FileNotFoundError: If blob is absent.
        """
        blob_path = self._blob_file(sha256)
        if not blob_path.exists():
            raise FileNotFoundError(f"Blob with hash {sha256} not found in CAS store.")
        with open(blob_path, "rb") as f:
            return f.read()

    def get_path(self, sha256: str) -> str:
        """
        Resolve absolute path to blob file.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            str: String path to .blob file.
        """
        return str(self._blob_file(sha256))

    def exists(self, sha256: str) -> bool:
        """
        Check if blob is present.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            bool: True if exists, False otherwise.
        """
        return self._blob_file(sha256).exists()

    def delete(self, sha256: str) -> bool:
        """
        Remove blob and its metadata from disk.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            bool: True if removed, False if nonexistent.
        """
        blob_path = self._blob_file(sha256)
        meta_path = self._meta_file(sha256)
        deleted = False

        if blob_path.exists():
            blob_path.unlink()
            deleted = True
        if meta_path.exists():
            meta_path.unlink()
            deleted = True

        return deleted

    def get_metadata(self, sha256: str) -> Optional[BlobMetadata]:
        """
        Read JSON metadata descriptor for hash.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            Optional[BlobMetadata]: Parsed descriptor or None.
        """
        meta_path = self._meta_file(sha256)
        if not meta_path.exists():
            if self.exists(sha256):
                # Synthesize fallback metadata if blob exists but meta file is missing
                blob_path = self._blob_file(sha256)
                stat = blob_path.stat()
                return BlobMetadata(
                    sha256=sha256,
                    size_bytes=stat.st_size,
                    mime_type="application/octet-stream",
                    filename=f"{sha256}.bin",
                    created_at=datetime.datetime.fromtimestamp(stat.st_ctime, tz=datetime.timezone.utc).isoformat(),
                    storage_path=str(blob_path),
                    backend="local",
                )
            return None

        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return BlobMetadata.from_dict(data)

    def list_blobs(self, limit: Optional[int] = None, offset: int = 0) -> List[BlobMetadata]:
        """
        Scan sharded storage tree and enumerate all stored blobs with optional pagination.

        Returns:
            List[BlobMetadata]: List of metadata for all persisted blobs.
        """
        results: List[BlobMetadata] = []
        for meta_file in self.base_dir.glob("*/*.meta.json"):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    results.append(BlobMetadata.from_dict(data))
            except Exception:
                continue
        sorted_res = sorted(results, key=lambda m: m.created_at, reverse=True)
        if offset > 0:
            sorted_res = sorted_res[offset:]
        if limit is not None:
            sorted_res = sorted_res[:limit]
        return sorted_res

    def update_metadata(self, sha256: str, custom_attributes: Dict[str, Any]) -> Optional[BlobMetadata]:
        """
        Update custom attributes for a stored blob on disk.

        Args:
            sha256 (str): SHA-256 hash.
            custom_attributes (Dict[str, Any]): Attributes to merge into existing metadata.

        Returns:
            Optional[BlobMetadata]: Updated metadata if blob exists, else None.
        """
        meta = self.get_metadata(sha256)
        if not meta:
            return None
        meta.custom_attributes.update(custom_attributes)
        meta_path = self._meta_file(sha256)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta.to_dict(), f, indent=2)
        return meta


class S3StorageBackend(StorageBackend):
    """
    S3 and MinIO object storage abstraction.

    Supports direct integration with boto3 when available in the environment,
    with an internal resilient in-memory/simulated cache mode for environments
    operating without AWS credentials or boto3.

    Architectural Role:
        Cloud-native scaling layer for distributed lab deployments.
    """

    def __init__(
        self,
        bucket_name: str = "biolabcalc-blobs",
        endpoint_url: Optional[str] = None,
        region_name: str = "us-east-1",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        prefix: str = "cas_blobs/",
    ):
        """
        Initialize S3/MinIO backend.

        Args:
            bucket_name (str): S3 bucket name.
            endpoint_url (Optional[str]): S3 or MinIO API endpoint.
            region_name (str): AWS region.
            access_key (Optional[str]): Access key identifier.
            secret_key (Optional[str]): Secret access key.
            prefix (str): Object key prefix inside bucket.
        """
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.region_name = region_name
        self.access_key = access_key
        self.secret_key = secret_key
        self.prefix = prefix.strip("/") + "/" if prefix else ""
        self._s3_client = None
        self._simulated_store: Dict[str, bytes] = {}
        self._simulated_meta: Dict[str, BlobMetadata] = {}

        # Attempt to initialize boto3 client if installed
        try:
            import boto3  # type: ignore

            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region_name,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            )
        except Exception:
            self._s3_client = None

    def _object_key(self, sha256: str) -> str:
        """
        Compute object key for blob.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            str: S3 key string.
        """
        return f"{self.prefix}{sha256[:2]}/{sha256}"

    def store(self, sha256: str, data: bytes, metadata: BlobMetadata) -> BlobMetadata:
        """
        Store blob in S3/MinIO bucket.

        Args:
            sha256 (str): SHA-256 hash.
            data (bytes): Blob bytes.
            metadata (BlobMetadata): Ingestion descriptor.

        Returns:
            BlobMetadata: Updated metadata.
        """
        key = self._object_key(sha256)
        metadata.storage_path = f"s3://{self.bucket_name}/{key}"
        metadata.backend = "s3"

        if self._s3_client is not None:
            import json as py_json

            meta_json = py_json.dumps(metadata.to_dict())
            response = self._s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=metadata.mime_type,
                Metadata={"cas-meta": meta_json},
            )
            metadata.etag = response.get("ETag", "").strip('"')
            return metadata

        # Resilient simulation mode
        self._simulated_store[sha256] = data
        metadata.etag = f'"{sha256[:16]}"'
        self._simulated_meta[sha256] = metadata
        return metadata

    def retrieve(self, sha256: str) -> bytes:
        """
        Download blob bytes from S3/MinIO.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            bytes: Content bytes.

        Raises:
            FileNotFoundError: If absent.
        """
        key = self._object_key(sha256)
        if self._s3_client is not None:
            try:
                response = self._s3_client.get_object(Bucket=self.bucket_name, Key=key)
                return response["Body"].read()
            except Exception as e:
                raise FileNotFoundError(f"S3 blob {key} could not be retrieved: {e}") from e

        if sha256 in self._simulated_store:
            return self._simulated_store[sha256]
        raise FileNotFoundError(f"Simulated S3 blob {sha256} not found.")

    def get_path(self, sha256: str) -> str:
        """
        Resolve S3 URI.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            str: S3 URI string.
        """
        return f"s3://{self.bucket_name}/{self._object_key(sha256)}"

    def exists(self, sha256: str) -> bool:
        """
        Check existence in S3.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            bool: True if key exists.
        """
        key = self._object_key(sha256)
        if self._s3_client is not None:
            try:
                self._s3_client.head_object(Bucket=self.bucket_name, Key=key)
                return True
            except Exception:
                return False
        return sha256 in self._simulated_store

    def delete(self, sha256: str) -> bool:
        """
        Delete object in S3.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            bool: True if deleted.
        """
        key = self._object_key(sha256)
        if self._s3_client is not None:
            try:
                self._s3_client.delete_object(Bucket=self.bucket_name, Key=key)
                return True
            except Exception:
                return False
        if sha256 in self._simulated_store:
            del self._simulated_store[sha256]
            self._simulated_meta.pop(sha256, None)
            return True
        return False

    def get_metadata(self, sha256: str) -> Optional[BlobMetadata]:
        """
        Fetch S3 object metadata.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            Optional[BlobMetadata]: Metadata descriptor or None.
        """
        if self._s3_client is not None:
            key = self._object_key(sha256)
            try:
                head = self._s3_client.head_object(Bucket=self.bucket_name, Key=key)
                cas_meta_raw = head.get("Metadata", {}).get("cas-meta")
                if cas_meta_raw:
                    data = json.loads(cas_meta_raw)
                    return BlobMetadata.from_dict(data)
                return BlobMetadata(
                    sha256=sha256,
                    size_bytes=head.get("ContentLength", 0),
                    mime_type=head.get("ContentType", "application/octet-stream"),
                    filename=f"{sha256}.bin",
                    created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    storage_path=self.get_path(sha256),
                    etag=head.get("ETag", "").strip('"'),
                    backend="s3",
                )
            except Exception:
                return None
        return self._simulated_meta.get(sha256)

    def list_blobs(self, limit: Optional[int] = None, offset: int = 0) -> List[BlobMetadata]:
        """
        Enumerate blobs in S3 with optional pagination.

        Returns:
            List[BlobMetadata]: List of metadata entries.
        """
        if self._s3_client is not None:
            # Query S3 listing
            results = []
            try:
                paginator = self._s3_client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix):
                    for obj in page.get("Contents", []):
                        key = obj["Key"]
                        sha256 = Path(key).name
                        meta = self.get_metadata(sha256)
                        if meta:
                            results.append(meta)
            except Exception:
                pass
            res = sorted(results, key=lambda m: m.created_at, reverse=True)
        else:
            res = sorted(list(self._simulated_meta.values()), key=lambda m: m.created_at, reverse=True)

        if offset > 0:
            res = res[offset:]
        if limit is not None:
            res = res[:limit]
        return res

    def update_metadata(self, sha256: str, custom_attributes: Dict[str, Any]) -> Optional[BlobMetadata]:
        """
        Update custom attributes for a stored blob in S3.

        Args:
            sha256 (str): SHA-256 hash.
            custom_attributes (Dict[str, Any]): Attributes to merge into existing metadata.

        Returns:
            Optional[BlobMetadata]: Updated metadata if blob exists, else None.
        """
        meta = self.get_metadata(sha256)
        if not meta:
            return None
        meta.custom_attributes.update(custom_attributes)
        if self._s3_client is not None:
            key = self._object_key(sha256)
            try:
                meta_json = json.dumps(meta.to_dict())
                self._s3_client.copy_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    CopySource={"Bucket": self.bucket_name, "Key": key},
                    Metadata={"cas-meta": meta_json},
                    MetadataDirective="REPLACE",
                )
            except Exception:
                pass
        else:
            self._simulated_meta[sha256] = meta
        return meta


class BlobStore:
    """
    Main Content-Addressable Storage (CAS) facade.

    Features:
        - Cryptographic SHA-256 hashing on all stored assets.
        - Idempotent deduplication (storing identical payload returns same metadata).
        - MIME type auto-detection.
        - Integrity validation against SHA-256 hash checksums.

    Architectural Role:
        Primary interface used by ELN entries, LIMS sample attachments,
        parsers, and preview generators.
    """

    def __init__(self, backend: Optional[StorageBackend] = None, base_dir: Union[str, Path] = ".biolabcalc_data/blobs"):
        """
        Initialize the CAS BlobStore.

        Args:
            backend (Optional[StorageBackend]): Backend implementation to use.
                Defaults to LocalStorageBackend(base_dir).
            base_dir (Union[str, Path]): Local storage directory when backend is default.
        """
        if backend is not None:
            self.backend = backend
        else:
            self.backend = LocalStorageBackend(base_dir=base_dir)

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """
        Compute SHA-256 hexadecimal string for raw data bytes.

        Args:
            data (bytes): Raw bytes to hash.

        Returns:
            str: 64-character lowercase hexadecimal hash.
        """
        hasher = hashlib.sha256()
        hasher.update(data)
        return hasher.hexdigest().lower()

    @staticmethod
    def detect_mime_type(filename: str, fallback: str = "application/octet-stream") -> str:
        """
        Detect MIME media type from filename or extension.

        Args:
            filename (str): Name of the file with extension.
            fallback (str): Fallback MIME type when unresolvable.

        Returns:
            str: Detected MIME type string.
        """
        if not filename:
            return fallback

        ext = Path(filename).suffix.lower()
        mapping = {
            ".csv": "text/csv",
            ".tsv": "text/tab-separated-values",
            ".asc": "text/plain",
            ".txt": "text/plain",
            ".abf": "application/x-axon-binary-format",
            ".res": "application/x-unicorn-res",
            ".ndv": "application/x-nanodrop-ndv",
            ".scn": "application/x-biorad-scn",
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".json": "application/json",
        }
        if ext in mapping:
            return mapping[ext]

        guessed, _ = mimetypes.guess_type(filename)
        if guessed:
            return guessed

        return fallback

    def store_bytes(
        self,
        data: bytes,
        filename: str = "",
        mime_type: str = "",
        custom_attributes: Optional[Dict[str, Any]] = None,
    ) -> BlobMetadata:
        """
        Store raw bytes into the Content-Addressable Storage.

        Args:
            data (bytes): Binary payload to store.
            filename (str): Descriptive or original filename.
            mime_type (str): Media MIME type. If empty, automatically detected.
            custom_attributes (Optional[Dict[str, Any]]): Arbitrary supplementary tags.

        Returns:
            BlobMetadata: Persisted CAS metadata object with SHA-256 hash key.
        """
        if not isinstance(data, bytes):
            raise TypeError(f"Expected bytes, got {type(data).__name__}")

        sha256 = self.compute_sha256(data)
        size_bytes = len(data)

        if not mime_type:
            mime_type = self.detect_mime_type(filename)

        if not filename:
            filename = f"{sha256}.bin"

        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metadata = BlobMetadata(
            sha256=sha256,
            size_bytes=size_bytes,
            mime_type=mime_type,
            filename=filename,
            created_at=created_at,
            storage_path="",
            backend=getattr(self.backend, "backend_name", "unknown"),
            custom_attributes=custom_attributes or {},
        )

        return self.backend.store(sha256, data, metadata)

    def store_file(
        self,
        source_path: Union[str, Path],
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        custom_attributes: Optional[Dict[str, Any]] = None,
    ) -> BlobMetadata:
        """
        Read a file from disk and store it into Content-Addressable Storage.

        Args:
            source_path (Union[str, Path]): Path to source file on disk.
            filename (Optional[str]): Override filename (defaults to source_path basename).
            mime_type (Optional[str]): Override MIME type.
            custom_attributes (Optional[Dict[str, Any]]): Supplementary metadata.

        Returns:
            BlobMetadata: Persisted CAS metadata.
        """
        p = Path(source_path)
        if not p.is_file():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        with open(p, "rb") as f:
            data = f.read()

        resolved_filename = filename if filename else p.name
        resolved_mime = mime_type if mime_type else self.detect_mime_type(resolved_filename)

        return self.store_bytes(
            data=data,
            filename=resolved_filename,
            mime_type=resolved_mime,
            custom_attributes=custom_attributes,
        )

    def get_bytes(self, sha256: str) -> bytes:
        """
        Retrieve binary payload by its SHA-256 hash.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            bytes: Content bytes.
        """
        clean_sha = sha256.strip().lower()
        return self.backend.retrieve(clean_sha)

    def get_file_path(self, sha256: str) -> str:
        """
        Get the filesystem path or URI of the stored blob.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            str: Path to the blob.
        """
        clean_sha = sha256.strip().lower()
        return self.backend.get_path(clean_sha)

    def exists(self, sha256: str) -> bool:
        """
        Check if a blob with the specified SHA-256 hash is present in storage.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            bool: True if present, False otherwise.
        """
        clean_sha = sha256.strip().lower()
        return self.backend.exists(clean_sha)

    def delete(self, sha256: str) -> bool:
        """
        Delete a blob from storage.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            bool: True if deleted, False otherwise.
        """
        clean_sha = sha256.strip().lower()
        return self.backend.delete(clean_sha)

    def get_metadata(self, sha256: str) -> Optional[BlobMetadata]:
        """
        Retrieve metadata descriptor for a given SHA-256 hash.

        Args:
            sha256 (str): SHA-256 hash.

        Returns:
            Optional[BlobMetadata]: Stored metadata or None if missing.
        """
        clean_sha = sha256.strip().lower()
        return self.backend.get_metadata(clean_sha)

    def list_blobs(self, limit: Optional[int] = None, offset: int = 0) -> List[BlobMetadata]:
        """
        Enumerate all blobs currently stored in the CAS repository with optional pagination.

        Returns:
            List[BlobMetadata]: List of metadata records.
        """
        return self.backend.list_blobs(limit=limit, offset=offset)

    def update_metadata(self, sha256: str, custom_attributes: Dict[str, Any]) -> Optional[BlobMetadata]:
        """
        Update custom attributes for a stored blob.

        Args:
            sha256 (str): SHA-256 hash.
            custom_attributes (Dict[str, Any]): Attributes to merge.

        Returns:
            Optional[BlobMetadata]: Updated metadata or None.
        """
        clean_sha = sha256.strip().lower()
        return self.backend.update_metadata(clean_sha, custom_attributes)

    def verify_integrity(self, sha256: str) -> bool:
        """
        Validate data integrity by comparing retrieved data hash to the requested hash.

        Args:
            sha256 (str): Expected SHA-256 hash.

        Returns:
            bool: True if data exists and hash matches exactly; False otherwise.
        """
        clean_sha = sha256.strip().lower()
        if not self.exists(clean_sha):
            return False
        try:
            data = self.get_bytes(clean_sha)
            computed = self.compute_sha256(data)
            return computed == clean_sha
        except Exception:
            return False
