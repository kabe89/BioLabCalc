"""
Module: biolabcalc.eln.storage.network_storage
Component: Network Storage Manager, Advisory File Locking, and Optimistic Concurrency Control
Architectural Role: Provides SMB/CIFS/NFS network share compatibility, UNC and mapped drive
detection, network-safe SQLite pragma configurations, cross-platform distributed advisory file
locking with stale lock recovery, centralized atomic Content-Addressable Storage (CAS) blob
management, and Optimistic Concurrency Control (OCC) helpers.
"""

from __future__ import annotations

import datetime
import difflib
import errno
import hashlib
import json
import os
import random
import re
import socket
import sqlite3
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path, PurePath, PureWindowsPath
from typing import (
    Any,
    BinaryIO,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

try:
    from biolabcalc.eln.storage.blob_store import BlobMetadata, StorageBackend
except ImportError:
    # Graceful fallback if blob_store is imported in isolation or minimal test context
    StorageBackend = object  # type: ignore[misc,assignment]
    BlobMetadata = None  # type: ignore[misc,assignment]


# ============================================================================
# Exceptions
# ============================================================================

class LockTimeoutError(TimeoutError):
    """Raised when acquiring an advisory network file lock exceeds the configured timeout."""
    pass


class ConcurrencyConflictError(Exception):
    """
    Raised when an Optimistic Concurrency Control (OCC) version token conflict is detected.

    Attributes:
        current_token (str): The existing version token currently persisted in storage/DB.
        expected_token (str): The version token submitted by the client/workstation.
        diff_context (Optional[Any]): Detailed delta or semantic difference between records.
        record_id (Optional[str]): Identifier of the record experiencing conflict.
        message (str): Human-readable diagnostic description of the conflict.
    """

    def __init__(
        self,
        current_token: str,
        expected_token: str,
        diff_context: Optional[Any] = None,
        record_id: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.current_token = current_token
        self.expected_token = expected_token
        self.diff_context = diff_context
        self.record_id = record_id
        if not message:
            msg = (
                f"Concurrency conflict detected: current record version '{current_token}' "
                f"does not match expected version '{expected_token}'."
            )
            if record_id:
                msg += f" (Record ID: {record_id})"
            if diff_context:
                msg += f" Diff context: {diff_context}"
            self.message = msg
        else:
            self.message = message
        super().__init__(self.message)


# ============================================================================
# Advisory Network File Lock
# ============================================================================

class NetworkFileLock:
    """
    Cross-platform advisory file locking mechanism designed for network file shares (SMB/CIFS/NFS).

    Uses atomic file creation (.lock file) via O_CREAT | O_EXCL with timeout,
    retry, randomized exponential backoff (jitter), and automatic stale lock
    detection and recovery. Supports context manager syntax (`with lock:`).
    """

    def __init__(
        self,
        target_path: Union[str, Path],
        timeout: float = 60.0,
        stale_timeout: float = 120.0,
        initial_delay: float = 0.02,
        max_delay: float = 0.5,
        backoff_factor: float = 1.3,
        lock_file_suffix: str = ".lock",
    ) -> None:
        """
        Initialize the network file lock.

        Args:
            target_path (Union[str, Path]): Target file/directory being protected, or the lock path.
            timeout (float): Total seconds to wait before raising LockTimeoutError (default 60s).
            stale_timeout (float): Age in seconds after which an existing lock is deemed abandoned/stale.
            initial_delay (float): Initial retry sleep interval in seconds.
            max_delay (float): Maximum cap for retry sleep interval.
            backoff_factor (float): Multiplier for exponential backoff.
            lock_file_suffix (str): Suffix appended to target_path if it doesn't already end with it.
        """
        target_str = str(target_path)
        if target_str.endswith(lock_file_suffix):
            self.lock_path = Path(target_str).resolve()
            self.target_path = Path(target_str[:-len(lock_file_suffix)])
        else:
            self.target_path = Path(target_str).resolve()
            self.lock_path = Path(f"{target_str}{lock_file_suffix}").resolve()

        self.lock_file = self.lock_path  # Convenience alias
        self.timeout = float(timeout)
        self.stale_timeout = float(stale_timeout)
        self.initial_delay = float(initial_delay)
        self.max_delay = float(max_delay)
        self.backoff_factor = float(backoff_factor)
        self.lock_id: str = uuid.uuid4().hex
        self._acquired: bool = False

    @property
    def is_acquired(self) -> bool:
        """Return True if this lock instance currently holds the lock."""
        return self._acquired

    @property
    def is_locked(self) -> bool:
        """Return True if the lock file exists on disk."""
        return self.lock_path.exists()

    def _read_lock_metadata(self) -> Optional[Dict[str, Any]]:
        """Read and parse lock file metadata if readable."""
        try:
            if not self.lock_path.exists():
                return None
            content = self.lock_path.read_text(encoding="utf-8")
            if not content.strip():
                return None
            return json.loads(content)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None

    def _is_stale(self) -> bool:
        """
        Determine if the existing lock file is stale/abandoned.

        Returns True if the lock file's internal timestamp or mtime exceeds stale_timeout.
        """
        try:
            if not self.lock_path.exists():
                return False

            now = time.time()
            meta = self._read_lock_metadata()
            if meta and "created_at" in meta:
                try:
                    age = now - float(meta["created_at"])
                    if age > self.stale_timeout:
                        return True
                    return False
                except (ValueError, TypeError):
                    pass

            # Fallback to filesystem modification time
            mtime = os.path.getmtime(self.lock_path)
            return (now - mtime) > self.stale_timeout
        except (OSError, FileNotFoundError):
            return False

    def _recover_stale_lock(self) -> bool:
        """
        Attempt to break a stale lock by removing the lock file.

        Returns True if removed, False otherwise.
        """
        try:
            if self.lock_path.exists():
                self.lock_path.unlink()
                return True
        except (FileNotFoundError, PermissionError, OSError):
            pass
        return False

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire the lock with exponential backoff and stale lock recovery.

        Args:
            timeout (Optional[float]): Optional override for acquisition timeout in seconds.

        Returns:
            bool: True upon successful lock acquisition.

        Raises:
            LockTimeoutError: If timeout expires before lock can be acquired.
        """
        if self._acquired:
            return True

        effective_timeout = self.timeout if timeout is None else float(timeout)
        start_time = time.monotonic()
        delay = self.initial_delay
        self.lock_id = uuid.uuid4().hex

        # Ensure parent directory exists
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        while True:
            # 1. Attempt atomic creation via O_CREAT | O_EXCL
            try:
                fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_RDWR,
                    0o666,
                )
                try:
                    metadata = {
                        "lock_id": self.lock_id,
                        "pid": os.getpid(),
                        "hostname": socket.gethostname(),
                        "created_at": time.time(),
                        "created_at_iso": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "stale_timeout": self.stale_timeout,
                        "target_path": str(self.target_path),
                    }
                    payload = json.dumps(metadata, indent=2).encode("utf-8")
                    os.write(fd, payload)
                    try:
                        os.fsync(fd)
                    except OSError:
                        pass
                finally:
                    os.close(fd)

                self._acquired = True
                return True

            except (FileExistsError, PermissionError, OSError) as e:
                # Handle EEXIST and transient file access conflicts during concurrent creation
                if isinstance(e, OSError) and e.errno not in (errno.EEXIST, errno.EACCES, errno.ENOENT):
                    if not (hasattr(e, "winerror") and e.winerror in (32, 13)):
                        raise

                # 2. Check for stale lock recovery
                if self._is_stale():
                    self._recover_stale_lock()
                    # After breaking stale lock, loop immediately to attempt acquisition
                    continue

                # 3. Check elapsed time against timeout
                elapsed = time.monotonic() - start_time
                if elapsed >= effective_timeout:
                    raise LockTimeoutError(
                        f"Timed out after {elapsed:.2f}s acquiring lock on '{self.lock_path}'. "
                        f"Active lock held by another process/workstation."
                    )

                # 4. Exponential backoff with random jitter
                jitter = delay * random.uniform(0.0, 0.25)
                sleep_duration = min(delay + jitter, self.max_delay)
                time.sleep(sleep_duration)
                delay = min(delay * self.backoff_factor, self.max_delay)

    def release(self) -> None:
        """
        Release the advisory lock.

        Ensures that only the owner who acquired the lock unlinks the file.
        """
        if not self._acquired:
            return

        try:
            if self.lock_path.exists():
                # On Windows or network shares, another process checking the lock
                # might momentarily conflict with unlink. Retry unlinking with micro-backoff.
                for _ in range(50):
                    try:
                        if not self.lock_path.exists():
                            break
                        self.lock_path.unlink()
                        break
                    except (FileNotFoundError, OSError):
                        time.sleep(0.005)
        finally:
            self._acquired = False

    def break_lock(self) -> bool:
        """
        Force-break the lock unconditionally (admin / emergency cleanup).

        Returns:
            bool: True if lock file was unlinked, False otherwise.
        """
        try:
            if self.lock_path.exists():
                self.lock_path.unlink()
                self._acquired = False
                return True
        except (FileNotFoundError, OSError):
            pass
        self._acquired = False
        return False

    def __enter__(self) -> NetworkFileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()

    def __repr__(self) -> str:
        return (
            f"<NetworkFileLock path='{self.lock_path}' "
            f"acquired={self._acquired} timeout={self.timeout}s>"
        )


# ============================================================================
# Optimistic Concurrency Control (OCC) Helper
# ============================================================================

class OptimisticConcurrencyControl:
    """
    Optimistic Concurrency Control helper for multi-user network lab environments.

    Manages UUID4 version tokens and detects concurrent update conflicts with detailed
    semantic diff context.
    """

    @staticmethod
    def generate_version_token() -> str:
        """
        Generate a cryptographically random UUID4 version token.

        Returns:
            str: Hexadecimal UUID4 string.
        """
        return str(uuid.uuid4())

    @classmethod
    def compute_diff(cls, current_record: Any, proposed_record: Any) -> Dict[str, Any]:
        """
        Compute structured difference context between two record states.

        Supports dictionaries, dataclasses, string payloads, and general objects.

        Args:
            current_record (Any): The state currently in the database/storage.
            proposed_record (Any): The state submitted by the client.

        Returns:
            Dict[str, Any]: Structured summary of modified, added, and removed attributes.
        """
        # Convert dataclasses to dicts if needed
        if is_dataclass(current_record) and not isinstance(current_record, type):
            current_record = asdict(current_record)
        if is_dataclass(proposed_record) and not isinstance(proposed_record, type):
            proposed_record = asdict(proposed_record)

        if isinstance(current_record, dict) and isinstance(proposed_record, dict):
            curr_keys = set(current_record.keys())
            prop_keys = set(proposed_record.keys())

            added = {k: proposed_record[k] for k in (prop_keys - curr_keys)}
            removed = {k: current_record[k] for k in (curr_keys - prop_keys)}
            modified: Dict[str, Dict[str, Any]] = {}

            for k in (curr_keys & prop_keys):
                if current_record[k] != proposed_record[k]:
                    modified[k] = {
                        "current": current_record[k],
                        "proposed": proposed_record[k],
                    }

            return {
                "type": "dictionary_diff",
                "modified_fields": modified,
                "added_fields": added,
                "removed_fields": removed,
                "changed_count": len(modified) + len(added) + len(removed),
            }

        if isinstance(current_record, str) and isinstance(proposed_record, str):
            curr_lines = current_record.splitlines(keepends=True)
            prop_lines = proposed_record.splitlines(keepends=True)
            diff = list(difflib.unified_diff(
                curr_lines,
                prop_lines,
                fromfile="current_record",
                tofile="proposed_record",
            ))
            return {
                "type": "text_diff",
                "unified_diff": "".join(diff),
                "has_diff": len(diff) > 0,
            }

        # Fallback for generic objects
        return {
            "type": "value_comparison",
            "current": str(current_record),
            "proposed": str(proposed_record),
        }

    @classmethod
    def check_conflict(
        cls,
        current_token: str,
        expected_token: str,
        current_record: Optional[Any] = None,
        proposed_record: Optional[Any] = None,
        diff_context: Optional[Any] = None,
        record_id: Optional[str] = None,
    ) -> None:
        """
        Validate whether the client's expected version token matches the current record token.

        Args:
            current_token (str): Current active version token in storage.
            expected_token (str): Client's supplied token representing the state when loaded.
            current_record (Optional[Any]): Current state of the record.
            proposed_record (Optional[Any]): Proposed new state of the record.
            diff_context (Optional[Any]): Precomputed or custom difference metadata.
            record_id (Optional[str]): Record primary key or unique identifier.

        Raises:
            ConcurrencyConflictError: If current_token != expected_token.
        """
        curr = str(current_token).strip()
        exp = str(expected_token).strip()

        if curr != exp:
            if diff_context is None and (current_record is not None or proposed_record is not None):
                diff_context = cls.compute_diff(current_record, proposed_record)
            elif diff_context is None:
                diff_context = {
                    "conflict": True,
                    "current_token": curr,
                    "expected_token": exp,
                }

            raise ConcurrencyConflictError(
                current_token=curr,
                expected_token=exp,
                diff_context=diff_context,
                record_id=record_id,
            )


# ============================================================================
# Network SQLite Pragmas
# ============================================================================

NETWORK_SQLITE_PRAGMAS: Dict[str, Union[str, int]] = {
    "journal_mode": "DELETE",
    "busy_timeout": 60000,
    "locking_mode": "NORMAL",
}

NETWORK_SQLITE_PRAGMA_STATEMENTS: List[str] = [
    "PRAGMA journal_mode = DELETE;",
    "PRAGMA busy_timeout = 60000;",
    "PRAGMA locking_mode = NORMAL;",
]


def get_network_sqlite_pragmas(
    journal_mode: str = "DELETE",
    busy_timeout: int = 60000,
    locking_mode: str = "NORMAL",
) -> Dict[str, Union[str, int]]:
    """
    Return dictionary of network-safe SQLite pragmas.

    Args:
        journal_mode (str): Journaling mode, typically 'DELETE' or 'TRUNCATE' (avoids -shm over SMB).
        busy_timeout (int): Lock acquisition timeout in milliseconds (default 60000ms = 60s).
        locking_mode (str): File locking policy ('NORMAL' allows concurrent readers and serialized writers).

    Returns:
        Dict[str, Union[str, int]]: Pragma names mapped to target values.
    """
    return {
        "journal_mode": journal_mode.upper(),
        "busy_timeout": int(busy_timeout),
        "locking_mode": locking_mode.upper(),
    }


def get_network_sqlite_pragma_statements(
    journal_mode: str = "DELETE",
    busy_timeout: int = 60000,
    locking_mode: str = "NORMAL",
) -> List[str]:
    """
    Return list of SQL statements configuring network-safe SQLite pragmas.

    Returns:
        List[str]: List of SQL statements.
    """
    return [
        f"PRAGMA journal_mode = {journal_mode.upper()};",
        f"PRAGMA busy_timeout = {int(busy_timeout)};",
        f"PRAGMA locking_mode = {locking_mode.upper()};",
    ]


def apply_network_pragmas(
    conn: sqlite3.Connection,
    journal_mode: str = "DELETE",
    busy_timeout: int = 60000,
    locking_mode: str = "NORMAL",
) -> Dict[str, Any]:
    """
    Apply network-safe pragmas to an active SQLite connection.

    Prevents SQLite shared memory (-shm) failures over SMB/CIFS/NFS mounts by setting
    journal_mode to DELETE or TRUNCATE, expanding busy_timeout to 60s, and ensuring
    locking_mode is NORMAL.

    Args:
        conn (sqlite3.Connection): Open SQLite connection.
        journal_mode (str): 'DELETE' or 'TRUNCATE'.
        busy_timeout (int): Timeout in ms.
        locking_mode (str): 'NORMAL'.

    Returns:
        Dict[str, Any]: Dictionary of applied values returned by the database engine.
    """
    cursor = conn.cursor()
    try:
        # 1. Apply journal_mode
        cursor.execute(f"PRAGMA journal_mode = {journal_mode.upper()};")
        row = cursor.fetchone()
        applied_journal = row[0] if row else journal_mode

        # 2. Apply busy_timeout
        cursor.execute(f"PRAGMA busy_timeout = {int(busy_timeout)};")

        # 3. Apply locking_mode
        cursor.execute(f"PRAGMA locking_mode = {locking_mode.upper()};")
        row = cursor.fetchone()
        applied_locking = row[0] if row else locking_mode

        # 4. Verify busy_timeout
        cursor.execute("PRAGMA busy_timeout;")
        row = cursor.fetchone()
        verified_busy = row[0] if row else busy_timeout

        return {
            "journal_mode": str(applied_journal).upper(),
            "busy_timeout": int(verified_busy),
            "locking_mode": str(applied_locking).upper(),
        }
    finally:
        cursor.close()


# ============================================================================
# Network Share Storage Manager
# ============================================================================

class NetworkShareStorageManager:
    """
    Network Share Storage Manager for shared lab environments.

    Coordinates:
      1. UNC network path and mapped drive letter detection.
      2. Network-safe SQLite configuration pragmas.
      3. Distributed cross-platform advisory file locking (NetworkFileLock).
      4. Centralized atomic Content-Addressable Storage (CAS) blob management.
      5. Optimistic Concurrency Control (OCC) version token conflict management.
    """

    # Default assumed mapped network drive letters (can be augmented dynamically)
    DEFAULT_MAPPED_DRIVES: Set[str] = {"Z", "Y", "X", "W", "V", "U", "S"}

    def __init__(
        self,
        shared_dir: Optional[Union[str, Path]] = None,
        mapped_drives: Optional[Iterable[str]] = None,
    ) -> None:
        """
        Initialize the NetworkShareStorageManager.

        Args:
            shared_dir (Optional[Union[str, Path]]): Base directory on network share or local disk.
            mapped_drives (Optional[Iterable[str]]): Collection of drive letters to treat as mapped network drives.
        """
        self.shared_dir: Optional[Path] = Path(shared_dir) if shared_dir else None

        # Build active set of mapped drives
        self._mapped_drives: Set[str] = set()
        if mapped_drives is not None:
            for d in mapped_drives:
                clean = self._normalize_drive_letter(d)
                if clean:
                    self._mapped_drives.add(clean)
        else:
            self._mapped_drives = set(self.DEFAULT_MAPPED_DRIVES)

        # Set up CAS blob directory
        if self.shared_dir is not None:
            if self.shared_dir.name.lower() == "blobs":
                self.blobs_dir = self.shared_dir
            else:
                self.blobs_dir = self.shared_dir / "blobs"
            self.tmp_dir = self.blobs_dir / ".tmp"
        else:
            self.blobs_dir = None
            self.tmp_dir = None

    @staticmethod
    def _normalize_drive_letter(drive_str: str) -> Optional[str]:
        """Normalize drive letter input (e.g., 'Z:', 'z', 'Z:\\' -> 'Z')."""
        s = str(drive_str).strip()
        if not s:
            return None
        letter = s[0]
        if letter.isalpha():
            return letter.upper()
        return None

    # ------------------------------------------------------------------------
    # Network Path & Drive Detection
    # ------------------------------------------------------------------------

    @staticmethod
    def is_unc_path(path: Union[str, Path]) -> bool:
        """
        Detect whether a path is a Universal Naming Convention (UNC) network path.

        Handles:
          - Windows standard UNC: `\\\\server\\share\\...`
          - Forward slash UNC: `//server/share/...`
          - Long UNC prefixes: `\\\\?\\UNC\\server\\share\\...` or `//?/UNC/server/share/...`
          - URI schemes: `smb://server/share/...`, `cifs://server/share/...`

        Args:
            path (Union[str, Path]): Path string or Path object to evaluate.

        Returns:
            bool: True if path is a UNC network path, False otherwise.
        """
        if not path:
            return False

        p = str(path).strip()

        # Handle URI schemes
        if p.lower().startswith(("smb://", "cifs://")):
            return True

        # Handle long UNC device paths (\\?\UNC\server\share or //?/UNC/server/share)
        long_unc_pattern = re.compile(r"^[\\/]{2}\?[\\/]UNC[\\/]+([^\\/]+)[\\/]+([^\\/]+)", re.IGNORECASE)
        if long_unc_pattern.match(p):
            return True

        # Handle standard UNC (\\server\share or //server/share)
        unc_pattern = re.compile(r"^[\\/]{2}(?!\?)([^\\/]+)[\\/]+([^\\/]+)")
        if unc_pattern.match(p):
            return True

        return False

    def is_mapped_drive(
        self,
        path: Union[str, Path],
        check_os: bool = True,
    ) -> bool:
        """
        Detect whether a path points to a mapped network drive letter (e.g. `Z:\\...`).

        Checks:
          1. Registered / configured mapped drive letter sets.
          2. Windows OS kernel drive query (`GetDriveTypeW == DRIVE_REMOTE`) if on Windows.

        Args:
            path (Union[str, Path]): File or directory path.
            check_os (bool): Whether to query OS kernel drive type if available.

        Returns:
            bool: True if path begins with a mapped network drive letter.
        """
        if not path:
            return False

        p = str(path).strip()
        letter = self.extract_drive_letter(p)
        if not letter:
            return False

        # 1. Check registered mapped drive letters
        if letter in self._mapped_drives:
            return True

        # 2. Query Windows OS Kernel if enabled
        if check_os and os.name == "nt":
            try:
                import ctypes
                DRIVE_REMOTE = 4
                drive_root = f"{letter}:\\"
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_root)
                if drive_type == DRIVE_REMOTE:
                    return True
            except Exception:
                pass

        return False

    @staticmethod
    def extract_drive_letter(path: Union[str, Path]) -> Optional[str]:
        """
        Extract drive letter from a path if present (e.g. 'Z:\\lab' -> 'Z').

        Args:
            path (Union[str, Path]): Path string or Path object.

        Returns:
            Optional[str]: Uppercase single-character drive letter, or None.
        """
        if not path:
            return None
        p = str(path).strip()
        if len(p) >= 2 and p[0].isalpha() and p[1] == ":":
            return p[0].upper()
        return None

    def is_network_path(self, path: Union[str, Path]) -> bool:
        """
        Determine if the given path is located on network storage (UNC path or mapped drive).

        Args:
            path (Union[str, Path]): Target path to inspect.

        Returns:
            bool: True if path is a UNC path or mapped drive, False if local.
        """
        return self.is_unc_path(path) or self.is_mapped_drive(path)

    @property
    def is_network(self) -> bool:
        """Return True if the configured shared_dir is a network path."""
        if not self.shared_dir:
            return False
        return self.is_network_path(self.shared_dir)

    def register_mapped_drive(self, drive_letter: str) -> None:
        """Register a drive letter as a mapped network drive."""
        letter = self._normalize_drive_letter(drive_letter)
        if letter:
            self._mapped_drives.add(letter)

    def unregister_mapped_drive(self, drive_letter: str) -> None:
        """Unregister a drive letter from mapped network drives."""
        letter = self._normalize_drive_letter(drive_letter)
        if letter:
            self._mapped_drives.discard(letter)

    def get_mapped_drives(self) -> Set[str]:
        """Return set of currently registered mapped drive letters."""
        return set(self._mapped_drives)

    # ------------------------------------------------------------------------
    # Network SQLite Pragmas
    # ------------------------------------------------------------------------

    def get_sqlite_pragmas(
        self,
        journal_mode: str = "DELETE",
        busy_timeout: int = 60000,
        locking_mode: str = "NORMAL",
    ) -> Dict[str, Union[str, int]]:
        """Return dictionary of network-safe SQLite pragmas."""
        return get_network_sqlite_pragmas(
            journal_mode=journal_mode,
            busy_timeout=busy_timeout,
            locking_mode=locking_mode,
        )

    def get_sqlite_pragma_statements(
        self,
        journal_mode: str = "DELETE",
        busy_timeout: int = 60000,
        locking_mode: str = "NORMAL",
    ) -> List[str]:
        """Return SQL statements configuring network-safe SQLite pragmas."""
        return get_network_sqlite_pragma_statements(
            journal_mode=journal_mode,
            busy_timeout=busy_timeout,
            locking_mode=locking_mode,
        )

    def apply_sqlite_pragmas(
        self,
        conn: sqlite3.Connection,
        journal_mode: str = "DELETE",
        busy_timeout: int = 60000,
        locking_mode: str = "NORMAL",
    ) -> Dict[str, Any]:
        """Apply network-safe pragmas to an active SQLite connection."""
        return apply_network_pragmas(
            conn=conn,
            journal_mode=journal_mode,
            busy_timeout=busy_timeout,
            locking_mode=locking_mode,
        )

    # ------------------------------------------------------------------------
    # Advisory File Locking
    # ------------------------------------------------------------------------

    def get_file_lock(
        self,
        target_path: Union[str, Path],
        timeout: float = 60.0,
        stale_timeout: float = 120.0,
        initial_delay: float = 0.05,
        max_delay: float = 2.0,
        backoff_factor: float = 1.5,
    ) -> NetworkFileLock:
        """
        Create a cross-platform advisory file lock for the given resource.

        Args:
            target_path (Union[str, Path]): Target file or directory being locked.
            timeout (float): Max acquisition wait time in seconds.
            stale_timeout (float): Inactivity duration before existing lock is treated as stale.
            initial_delay (float): Starting backoff interval.
            max_delay (float): Max backoff interval.
            backoff_factor (float): Multiplier for exponential backoff.

        Returns:
            NetworkFileLock: Configured lock object.
        """
        return NetworkFileLock(
            target_path=target_path,
            timeout=timeout,
            stale_timeout=stale_timeout,
            initial_delay=initial_delay,
            max_delay=max_delay,
            backoff_factor=backoff_factor,
        )

    def file_lock(
        self,
        target_path: Union[str, Path],
        timeout: float = 60.0,
        stale_timeout: float = 120.0,
    ) -> NetworkFileLock:
        """Convenience alias for `get_file_lock`, ideal for `with manager.file_lock(path):`."""
        return self.get_file_lock(
            target_path=target_path,
            timeout=timeout,
            stale_timeout=stale_timeout,
        )

    # ------------------------------------------------------------------------
    # Centralized CAS Blob Directory Management
    # ------------------------------------------------------------------------

    def _ensure_cas_dirs(self) -> Tuple[Path, Path]:
        """Ensure blobs root and temp directory exist on disk."""
        if self.blobs_dir is None or self.tmp_dir is None:
            raise ValueError(
                "shared_dir must be configured on NetworkShareStorageManager to use CAS blob storage."
            )
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        return self.blobs_dir, self.tmp_dir

    def get_blob_path(self, sha256_hash: str) -> Path:
        """
        Compute sharded filesystem path for a given SHA-256 hash.

        Directory structure:
            {shared_dir}/blobs/{hash[:2]}/{hash}.blob

        Args:
            sha256_hash (str): 64-character hex-encoded SHA-256 digest.

        Returns:
            Path: Absolute or relative Path pointing to the blob file.
        """
        if self.blobs_dir is None:
            raise ValueError("shared_dir is not configured.")

        clean_hash = sha256_hash.strip().lower()
        if len(clean_hash) < 2:
            raise ValueError("Invalid SHA-256 hash: too short.")
        shard = clean_hash[:2]
        return self.blobs_dir / shard / f"{clean_hash}.blob"

    def store_blob(
        self,
        data: Union[bytes, str, BinaryIO, Path],
        expected_hash: Optional[str] = None,
    ) -> str:
        """
        Atomically store binary data into Content-Addressable Storage (CAS).

        Writes to a temporary file in `{shared_dir}/blobs/.tmp`, calculates SHA-256,
        verifies against expected_hash (if provided), flushes/syncs to disk, and
        atomically replaces into `{shared_dir}/blobs/{hash[:2]}/{hash}.blob`.

        Args:
            data (Union[bytes, str, BinaryIO, Path]): Payload bytes, string, stream, or file path.
            expected_hash (Optional[str]): Optional expected SHA-256 digest to verify.

        Returns:
            str: 64-character hex SHA-256 digest of stored blob.

        Raises:
            ValueError: If expected_hash does not match computed SHA-256 digest.
        """
        blobs_dir, tmp_dir = self._ensure_cas_dirs()

        # Handle Path or str pointing to existing file
        if isinstance(data, (Path, str)) and os.path.isfile(str(data)):
            source_file = Path(data)
            return self.store_blob_from_file(source_file, expected_hash=expected_hash)

        # Handle str payload
        if isinstance(data, str):
            payload = data.encode("utf-8")
        elif isinstance(data, bytes):
            payload = data
        elif hasattr(data, "read"):
            payload = data.read()
            if isinstance(payload, str):
                payload = payload.encode("utf-8")
        else:
            raise TypeError(f"Unsupported data type for store_blob: {type(data)}")

        hasher = hashlib.sha256()
        hasher.update(payload)
        computed_hash = hasher.hexdigest().lower()

        if expected_hash is not None:
            exp = expected_hash.strip().lower()
            if computed_hash != exp:
                raise ValueError(
                    f"SHA-256 verification mismatch: expected '{exp}', computed '{computed_hash}'."
                )

        final_path = self.get_blob_path(computed_hash)
        if final_path.exists():
            # Already exists (CAS deduplication)
            return computed_hash

        # Write to temporary file on the SAME filesystem/volume
        shard_dir = final_path.parent
        shard_dir.mkdir(parents=True, exist_ok=True)

        temp_filename = f".tmp_{computed_hash}_{uuid.uuid4().hex}.tmp"
        temp_path = tmp_dir / temp_filename

        try:
            with open(temp_path, "wb") as f:
                f.write(payload)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass

            # Atomic rename / replace
            os.replace(temp_path, final_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

        return computed_hash

    def store_blob_from_file(
        self,
        source_path: Union[str, Path],
        expected_hash: Optional[str] = None,
        chunk_size: int = 65536,
    ) -> str:
        """
        Stream a file into CAS storage with atomic rename and SHA-256 verification.

        Args:
            source_path (Union[str, Path]): Path to source file on disk.
            expected_hash (Optional[str]): Optional SHA-256 hash to assert.
            chunk_size (int): Read buffer size in bytes.

        Returns:
            str: 64-character SHA-256 digest.
        """
        blobs_dir, tmp_dir = self._ensure_cas_dirs()
        src = Path(source_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src}")

        temp_filename = f".tmp_stream_{uuid.uuid4().hex}.tmp"
        temp_path = tmp_dir / temp_filename

        hasher = hashlib.sha256()
        try:
            with open(src, "rb") as fin, open(temp_path, "wb") as fout:
                while True:
                    chunk = fin.read(chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    fout.write(chunk)
                fout.flush()
                try:
                    os.fsync(fout.fileno())
                except OSError:
                    pass

            computed_hash = hasher.hexdigest().lower()
            if expected_hash is not None:
                exp = expected_hash.strip().lower()
                if computed_hash != exp:
                    raise ValueError(
                        f"SHA-256 mismatch for file '{src}': expected '{exp}', got '{computed_hash}'."
                    )

            final_path = self.get_blob_path(computed_hash)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp_path, final_path)
            return computed_hash
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def get_blob(self, sha256_hash: str, verify: bool = True) -> bytes:
        """
        Retrieve binary contents of a CAS blob.

        Args:
            sha256_hash (str): 64-character SHA-256 digest.
            verify (bool): Whether to recalculate SHA-256 on read to verify integrity.

        Returns:
            bytes: Binary content of blob.

        Raises:
            FileNotFoundError: If blob is not present in storage.
            ValueError: If integrity verification fails.
        """
        path = self.get_blob_path(sha256_hash)
        if not path.exists():
            raise FileNotFoundError(f"CAS blob not found: {sha256_hash} at '{path}'")

        data = path.read_bytes()
        if verify:
            calculated = hashlib.sha256(data).hexdigest().lower()
            expected = sha256_hash.strip().lower()
            if calculated != expected:
                raise ValueError(
                    f"Integrity check failed for blob '{expected}'. File content hash is '{calculated}'."
                )
        return data

    def get_blob_stream(
        self,
        sha256_hash: str,
        chunk_size: int = 65536,
    ) -> Generator[bytes, None, None]:
        """
        Stream binary chunks of a stored CAS blob.

        Args:
            sha256_hash (str): 64-character SHA-256 digest.
            chunk_size (int): Size of chunks to yield.

        Yields:
            bytes: Successive binary chunks.
        """
        path = self.get_blob_path(sha256_hash)
        if not path.exists():
            raise FileNotFoundError(f"CAS blob not found: {sha256_hash}")

        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    def has_blob(self, sha256_hash: str) -> bool:
        """Check whether a blob exists in storage."""
        try:
            return self.get_blob_path(sha256_hash).exists()
        except ValueError:
            return False

    def verify_blob(self, sha256_hash: str) -> bool:
        """
        Verify the cryptographic integrity of a stored blob by recalculating its SHA-256 hash.

        Args:
            sha256_hash (str): Expected SHA-256 digest.

        Returns:
            bool: True if file exists and SHA-256 matches, False otherwise.
        """
        try:
            path = self.get_blob_path(sha256_hash)
            if not path.exists():
                return False

            hasher = hashlib.sha256()
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    hasher.update(chunk)

            return hasher.hexdigest().lower() == sha256_hash.strip().lower()
        except Exception:
            return False

    def delete_blob(self, sha256_hash: str) -> bool:
        """
        Delete a blob from CAS storage.

        Args:
            sha256_hash (str): SHA-256 digest.

        Returns:
            bool: True if deleted, False if not found.
        """
        try:
            path = self.get_blob_path(sha256_hash)
            if path.exists():
                path.unlink()
                return True
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------------
    # Optimistic Concurrency Control (OCC)
    # ------------------------------------------------------------------------

    @staticmethod
    def generate_version_token() -> str:
        """Generate a random UUID4 version token for Optimistic Concurrency Control."""
        return OptimisticConcurrencyControl.generate_version_token()

    @staticmethod
    def compute_diff(current_record: Any, proposed_record: Any) -> Dict[str, Any]:
        """Compute structured difference context between two record states."""
        return OptimisticConcurrencyControl.compute_diff(current_record, proposed_record)

    @staticmethod
    def check_conflict(
        current_token: str,
        expected_token: str,
        current_record: Optional[Any] = None,
        proposed_record: Optional[Any] = None,
        diff_context: Optional[Any] = None,
        record_id: Optional[str] = None,
    ) -> None:
        """
        Check for an OCC version conflict and raise ConcurrencyConflictError if tokens differ.

        Args:
            current_token (str): Current active version token.
            expected_token (str): Client expected version token.
            current_record (Optional[Any]): Current state.
            proposed_record (Optional[Any]): Proposed state.
            diff_context (Optional[Any]): Precomputed difference metadata.
            record_id (Optional[str]): Record ID.
        """
        OptimisticConcurrencyControl.check_conflict(
            current_token=current_token,
            expected_token=expected_token,
            current_record=current_record,
            proposed_record=proposed_record,
            diff_context=diff_context,
            record_id=record_id,
        )


# ============================================================================
# StorageBackend Adapter for BlobStore Integration
# ============================================================================

class NetworkStorageBackend(StorageBackend):
    """
    StorageBackend adapter providing seamless integration of NetworkShareStorageManager
    into the biolabcalc.eln.storage.BlobStore architecture.
    """

    def __init__(self, shared_dir: Union[str, Path]) -> None:
        self.manager = NetworkShareStorageManager(shared_dir=shared_dir)
        self.shared_dir = Path(shared_dir).resolve()
        self.manager._ensure_cas_dirs()

    def store(self, sha256: str, data: bytes, metadata: Any) -> Any:
        self.manager.store_blob(data, expected_hash=sha256)
        blob_path = str(self.manager.get_blob_path(sha256))
        if metadata is not None:
            metadata.storage_path = blob_path
            metadata.backend = "network_share"
            # Write sidecar metadata json
            meta_path = Path(blob_path).with_suffix(".meta.json")
            if hasattr(metadata, "to_dict"):
                meta_path.write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")
        return metadata

    def retrieve(self, sha256: str) -> bytes:
        return self.manager.get_blob(sha256, verify=True)

    def get_path(self, sha256: str) -> str:
        return str(self.manager.get_blob_path(sha256))

    def exists(self, sha256: str) -> bool:
        return self.manager.has_blob(sha256)

    def delete(self, sha256: str) -> bool:
        p = self.manager.get_blob_path(sha256)
        meta_p = p.with_suffix(".meta.json")
        deleted = self.manager.delete_blob(sha256)
        if meta_p.exists():
            try:
                meta_p.unlink()
            except OSError:
                pass
        return deleted

    def get_metadata(self, sha256: str) -> Optional[Any]:
        p = self.manager.get_blob_path(sha256)
        meta_p = p.with_suffix(".meta.json")
        if meta_p.exists() and BlobMetadata is not None:
            try:
                data = json.loads(meta_p.read_text(encoding="utf-8"))
                return BlobMetadata.from_dict(data)
            except Exception:
                return None
        return None

    def list_blobs(self, limit: Optional[int] = None, offset: int = 0) -> List[Any]:
        if not self.manager.blobs_dir or not self.manager.blobs_dir.exists():
            return []
        results = []
        for meta_file in sorted(self.manager.blobs_dir.glob("*/*.meta.json")):
            if BlobMetadata is not None:
                try:
                    data = json.loads(meta_file.read_text(encoding="utf-8"))
                    results.append(BlobMetadata.from_dict(data))
                except Exception:
                    pass
        if offset:
            results = results[offset:]
        if limit is not None:
            results = results[:limit]
        return results

    def update_metadata(self, sha256: str, custom_attributes: Dict[str, Any]) -> Optional[Any]:
        meta = self.get_metadata(sha256)
        if meta is None:
            return None
        if hasattr(meta, "custom_attributes"):
            meta.custom_attributes.update(custom_attributes)
            p = self.manager.get_blob_path(sha256)
            meta_p = p.with_suffix(".meta.json")
            if hasattr(meta, "to_dict"):
                meta_p.write_text(json.dumps(meta.to_dict(), indent=2), encoding="utf-8")
        return meta
