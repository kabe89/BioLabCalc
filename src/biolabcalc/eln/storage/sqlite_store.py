"""
Module: biolabcalc.eln.storage.sqlite_store
Component: Lightweight Zero-Dependency SQLite Persistence Engine
Architectural Role: Provides thread-safe, WAL-enabled JSON entity and key-value persistence
for all ELN and LIMS services (campaigns, SOPs, sequences, timepoints, approvals, inventory)
using standard library sqlite3 without external ORM dependencies.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ...profile import get_profile_dir

logger = logging.getLogger("biolabcalc.eln.storage.sqlite_store")


class SQLiteStore:
    """
    Standard-library SQLite persistence store for ELN and LIMS records.

    Provides atomic read, write, update, and delete operations for document-style
    entity records and scalar configurations across service restarts.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize SQLiteStore.

        Args:
            db_path: Path to eln_lims.db or ':memory:'. If None, resolves from
                     BIOLABCALC_STORAGE_DIR / BIOLABCALC_HOME / ~/.biolabcalc.
        """
        self._lock = threading.RLock()
        if db_path is None:
            storage_dir = get_profile_dir()
            self._db_path = str(storage_dir / "eln_lims.db")
        else:
            self._db_path = str(db_path)

        # Handle sqlite:/// URI prefix if present
        if self._db_path.startswith("sqlite:///"):
            self._db_path = self._db_path[len("sqlite:///"):]

        self._is_memory = self._db_path in (":memory:", "")
        if not self._is_memory:
            os.makedirs(os.path.dirname(os.path.abspath(self._db_path)), exist_ok=True)

        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Return an active connection configured with WAL and busy timeout."""
        if self._is_memory:
            if self._conn is None:
                self._conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._conn.execute("PRAGMA foreign_keys = ON;")
            return self._conn

        try:
            conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=10.0)
            try:
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA busy_timeout = 5000;")
                conn.execute("PRAGMA foreign_keys = ON;")
            except Exception:
                pass
            return conn
        except (sqlite3.OperationalError, OSError) as e:
            logger.warning(f"Unable to open SQLite database at '{self._db_path}' ({e}); falling back to in-memory store.")
            self._is_memory = True
            if self._conn is None:
                self._conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._conn.execute("PRAGMA foreign_keys = ON;")
            return self._conn

    def _init_db(self) -> None:
        """Initialize core persistence tables if they do not exist."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS entity_store (
                            entity_type TEXT NOT NULL,
                            entity_id TEXT NOT NULL,
                            data_json TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            PRIMARY KEY (entity_type, entity_id)
                        );
                    """)
                    conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_entity_type 
                        ON entity_store (entity_type);
                    """)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS kv_store (
                            key TEXT PRIMARY KEY,
                            value_json TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                    """)
            finally:
                if not self._is_memory:
                    conn.close()

    def put_entity(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> None:
        """
        Persist or update an entity record atomically.

        Args:
            entity_type: Entity namespace (e.g. 'campaign', 'sop', 'sequence', 'timepoint', 'approval').
            entity_id: Primary identifier of the entity.
            data: Complete entity dictionary to serialize as JSON.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(data, ensure_ascii=False)
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        INSERT INTO entity_store (entity_type, entity_id, data_json, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                            data_json = excluded.data_json,
                            updated_at = excluded.updated_at;
                    """, (entity_type, entity_id, payload, now_iso, now_iso))
            finally:
                if not self._is_memory:
                    conn.close()

    def get_entity(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single entity by type and ID."""
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT data_json FROM entity_store 
                    WHERE entity_type = ? AND entity_id = ?;
                """, (entity_type, entity_id))
                row = cur.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
                return None
            finally:
                if not self._is_memory:
                    conn.close()

    def list_entities(self, entity_type: str) -> List[Dict[str, Any]]:
        """Retrieve all entities of a given type."""
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT data_json FROM entity_store 
                    WHERE entity_type = ?
                    ORDER BY updated_at ASC;
                """, (entity_type,))
                results: List[Dict[str, Any]] = []
                for row in cur.fetchall():
                    if row and row[0]:
                        try:
                            results.append(json.loads(row[0]))
                        except Exception:
                            pass
                return results
            finally:
                if not self._is_memory:
                    conn.close()

    def delete_entity(self, entity_type: str, entity_id: str) -> bool:
        """Delete an entity by type and ID. Returns True if a record was removed."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cur = conn.execute("""
                        DELETE FROM entity_store 
                        WHERE entity_type = ? AND entity_id = ?;
                    """, (entity_type, entity_id))
                    return cur.rowcount > 0
            finally:
                if not self._is_memory:
                    conn.close()

    def set_kv(self, key: str, value: Any) -> None:
        """Store arbitrary key-value data."""
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(value, ensure_ascii=False)
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("""
                        INSERT INTO kv_store (key, value_json, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(key) DO UPDATE SET
                            value_json = excluded.value_json,
                            updated_at = excluded.updated_at;
                    """, (key, payload, now_iso))
            finally:
                if not self._is_memory:
                    conn.close()

    def get_kv(self, key: str, default: Any = None) -> Any:
        """Retrieve value by key."""
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT value_json FROM kv_store WHERE key = ?;", (key,))
                row = cur.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
                return default
            finally:
                if not self._is_memory:
                    conn.close()

    def delete_kv(self, key: str) -> bool:
        """Delete key from kv_store. Returns True if deleted."""
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    cur = conn.execute("DELETE FROM kv_store WHERE key = ?;", (key,))
                    return cur.rowcount > 0
            finally:
                if not self._is_memory:
                    conn.close()

    def close(self) -> None:
        """Close active database connection if open."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    def __del__(self) -> None:
        """Destructor ensuring connection cleanup."""
        try:
            self.close()
        except Exception:
            pass


_GLOBAL_STORE: Optional[SQLiteStore] = None
_STORE_LOCK = threading.RLock()


def get_sqlite_store(db_path: Optional[Union[str, Path]] = None) -> SQLiteStore:
    """Return singleton SQLiteStore instance or instantiate for specified path."""
    global _GLOBAL_STORE
    with _STORE_LOCK:
        if db_path is not None:
            return SQLiteStore(db_path)
        current_expected_path = str(get_profile_dir() / "eln_lims.db")
        if _GLOBAL_STORE is None or (not _GLOBAL_STORE._is_memory and _GLOBAL_STORE._db_path != current_expected_path):
            _GLOBAL_STORE = SQLiteStore(current_expected_path)
        return _GLOBAL_STORE


def reset_sqlite_store() -> None:
    """Reset the global singleton SQLite store instance."""
    global _GLOBAL_STORE
    with _STORE_LOCK:
        _GLOBAL_STORE = None
