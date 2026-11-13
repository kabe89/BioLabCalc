"""
Test Suite: test_network_storage
Component: Network Storage Manager, Advisory Locking, CAS Blobs, and OCC
Architectural Role: Comprehensive test suite for UNC and mapped drive detection,
network-safe SQLite pragmas, distributed advisory file locking (.lock) with timeout
and stale lock recovery, centralized atomic Content-Addressable Storage (CAS) blob
directory management, and Optimistic Concurrency Control (OCC) conflict detection.
"""

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Bootstrap sys.path so tests can execute standalone
_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc.eln.storage.network_storage import (
    ConcurrencyConflictError,
    LockTimeoutError,
    NetworkFileLock,
    NetworkShareStorageManager,
    NetworkStorageBackend,
    OptimisticConcurrencyControl,
    apply_network_pragmas,
    get_network_sqlite_pragma_statements,
    get_network_sqlite_pragmas,
)


class TestNetworkPathDetection(unittest.TestCase):
    """Test suite for UNC path and mapped drive letter detection."""

    def setUp(self):
        self.manager = NetworkShareStorageManager()

    def test_unc_path_detection_windows_standard(self):
        """Verify Windows standard UNC paths are detected."""
        self.assertTrue(self.manager.is_unc_path(r"\\server\share\eln_data"))
        self.assertTrue(self.manager.is_unc_path(r"\\192.168.1.100\lab_share\db.sqlite"))
        self.assertTrue(self.manager.is_unc_path(r"\\nas.university.edu\biology\samples"))

    def test_unc_path_detection_forward_slashes(self):
        """Verify forward slash UNC paths are detected (SMB/CIFS mounted on Unix/Linux)."""
        self.assertTrue(self.manager.is_unc_path("//server/share/eln_data"))
        self.assertTrue(self.manager.is_unc_path("//10.0.0.50/lab/storage"))
        self.assertTrue(self.manager.is_unc_path("//nas.domain.org/shared_data/blobs"))

    def test_unc_path_detection_long_unc_and_uri(self):
        """Verify long device UNC paths and URI schemes are detected."""
        self.assertTrue(self.manager.is_unc_path(r"\\?\UNC\server\share\file.txt"))
        self.assertTrue(self.manager.is_unc_path("//?/UNC/server/share/file.txt"))
        self.assertTrue(self.manager.is_unc_path("smb://server/share/folder"))
        self.assertTrue(self.manager.is_unc_path("cifs://storage.lan/eln"))

    def test_unc_path_detection_with_path_objects(self):
        """Verify Path objects representing UNC paths are detected."""
        p = Path(r"\\server\share\sub\data.csv")
        self.assertTrue(self.manager.is_unc_path(p))

    def test_unc_path_detection_negative_cases(self):
        """Verify non-UNC paths return False."""
        self.assertFalse(self.manager.is_unc_path(r"C:\Users\scientist\data"))
        self.assertFalse(self.manager.is_unc_path("/usr/local/bin/python"))
        self.assertFalse(self.manager.is_unc_path("relative/path/to/file"))
        self.assertFalse(self.manager.is_unc_path(""))
        self.assertFalse(self.manager.is_unc_path("   "))
        self.assertFalse(self.manager.is_unc_path(r"\\"))
        self.assertFalse(self.manager.is_unc_path(r"\\server"))  # Missing share component
        self.assertFalse(self.manager.is_unc_path("//server"))

    def test_mapped_drive_detection_default(self):
        """Verify default mapped drive letters (e.g. Z:) are detected."""
        self.assertTrue(self.manager.is_mapped_drive(r"Z:\lab\eln_db.sqlite"))
        self.assertTrue(self.manager.is_mapped_drive(r"z:\lab\eln_db.sqlite"))  # Lowercase
        self.assertTrue(self.manager.is_mapped_drive("Z:/lab/eln_db.sqlite"))
        self.assertTrue(self.manager.is_mapped_drive("Y:\\shared_data"))

    def test_mapped_drive_registration(self):
        """Verify registering and unregistering mapped drive letters."""
        manager = NetworkShareStorageManager(mapped_drives=["X", "W"])
        self.assertTrue(manager.is_mapped_drive(r"X:\experiments"))
        self.assertTrue(manager.is_mapped_drive(r"W:\data"))
        self.assertFalse(manager.is_mapped_drive(r"M:\data"))

        # Register M:
        manager.register_mapped_drive("M")
        self.assertTrue(manager.is_mapped_drive(r"M:\data"))

        # Unregister M:
        manager.unregister_mapped_drive("M:")
        self.assertFalse(manager.is_mapped_drive(r"M:\data"))

    def test_extract_drive_letter(self):
        """Verify drive letter extraction helper."""
        self.assertEqual(NetworkShareStorageManager.extract_drive_letter(r"Z:\dir"), "Z")
        self.assertEqual(NetworkShareStorageManager.extract_drive_letter("c:/windows"), "C")
        self.assertIsNone(NetworkShareStorageManager.extract_drive_letter(r"\\server\share"))
        self.assertIsNone(NetworkShareStorageManager.extract_drive_letter("/home/user"))
        self.assertIsNone(NetworkShareStorageManager.extract_drive_letter(""))

    def test_mapped_drive_detection_os_kernel_query(self):
        """Verify OS kernel drive type query (DRIVE_REMOTE=4) is utilized on Windows."""
        manager = NetworkShareStorageManager(mapped_drives=[])  # Empty default list
        self.assertFalse(manager.is_mapped_drive(r"K:\lab_drive", check_os=False))

        # Mock ctypes.windll.kernel32.GetDriveTypeW returning 4 (DRIVE_REMOTE)
        mock_kernel32 = MagicMock()
        mock_kernel32.GetDriveTypeW.return_value = 4  # DRIVE_REMOTE

        with patch("os.name", "nt"), patch.dict("sys.modules", {"ctypes": MagicMock(windll=MagicMock(kernel32=mock_kernel32))}):
            self.assertTrue(manager.is_mapped_drive(r"K:\lab_drive", check_os=True))
            mock_kernel32.GetDriveTypeW.assert_called_with("K:\\")

    def test_is_network_path_combined(self):
        """Verify combined is_network_path logic."""
        self.assertTrue(self.manager.is_network_path(r"\\server\share\db.sqlite"))
        self.assertTrue(self.manager.is_network_path(r"Z:\eln\db.sqlite"))
        self.assertFalse(self.manager.is_network_path(r"C:\local\db.sqlite"))

    def test_manager_is_network_property(self):
        """Verify is_network property reflects configured shared_dir."""
        mgr_unc = NetworkShareStorageManager(shared_dir=r"\\labserver\eln_data")
        self.assertTrue(mgr_unc.is_network)

        mgr_mapped = NetworkShareStorageManager(shared_dir=r"Z:\eln_data")
        self.assertTrue(mgr_mapped.is_network)

        mgr_local = NetworkShareStorageManager(shared_dir=r"C:\Users\test\data")
        self.assertFalse(mgr_local.is_network)

        mgr_none = NetworkShareStorageManager()
        self.assertFalse(mgr_none.is_network)


class TestNetworkSQLitePragmas(unittest.TestCase):
    """Test suite for network-safe SQLite pragma configurations."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_sqlite_pragmas_")
        self.db_path = Path(self.temp_dir) / "test_eln.sqlite"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_network_sqlite_pragmas_defaults(self):
        """Verify dictionary of default network SQLite pragmas."""
        pragmas = get_network_sqlite_pragmas()
        self.assertEqual(pragmas["journal_mode"], "DELETE")
        self.assertEqual(pragmas["busy_timeout"], 60000)
        self.assertEqual(pragmas["locking_mode"], "NORMAL")

    def test_get_network_sqlite_pragma_statements(self):
        """Verify SQL statements generated for SQLite network configuration."""
        stmts = get_network_sqlite_pragma_statements()
        self.assertIn("PRAGMA journal_mode = DELETE;", stmts)
        self.assertIn("PRAGMA busy_timeout = 60000;", stmts)
        self.assertIn("PRAGMA locking_mode = NORMAL;", stmts)

    def test_apply_network_pragmas_on_disk_database(self):
        """Verify applying network pragmas to an actual on-disk SQLite database connection."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            applied = apply_network_pragmas(conn)
            self.assertEqual(applied["journal_mode"], "DELETE")
            self.assertEqual(applied["busy_timeout"], 60000)
            self.assertEqual(applied["locking_mode"], "NORMAL")

            # Direct verification with cursor queries
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode;")
            self.assertEqual(cur.fetchone()[0].upper(), "DELETE")

            cur.execute("PRAGMA busy_timeout;")
            self.assertEqual(cur.fetchone()[0], 60000)

            cur.execute("PRAGMA locking_mode;")
            self.assertEqual(cur.fetchone()[0].upper(), "NORMAL")
            cur.close()
        finally:
            conn.close()

    def test_apply_network_pragmas_custom_truncate(self):
        """Verify applying custom TRUNCATE journal mode and custom timeout."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            applied = apply_network_pragmas(
                conn,
                journal_mode="TRUNCATE",
                busy_timeout=45000,
                locking_mode="NORMAL",
            )
            self.assertEqual(applied["journal_mode"], "TRUNCATE")
            self.assertEqual(applied["busy_timeout"], 45000)

            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode;")
            self.assertEqual(cur.fetchone()[0].upper(), "TRUNCATE")
            cur.execute("PRAGMA busy_timeout;")
            self.assertEqual(cur.fetchone()[0], 45000)
            cur.close()
        finally:
            conn.close()

    def test_manager_pragma_delegation(self):
        """Verify NetworkShareStorageManager instance pragma methods."""
        manager = NetworkShareStorageManager()
        pragmas = manager.get_sqlite_pragmas()
        self.assertEqual(pragmas["journal_mode"], "DELETE")

        conn = sqlite3.connect(str(self.db_path))
        try:
            res = manager.apply_sqlite_pragmas(conn)
            self.assertEqual(res["journal_mode"], "DELETE")
            self.assertEqual(res["busy_timeout"], 60000)
        finally:
            conn.close()


class TestNetworkFileLock(unittest.TestCase):
    """Test suite for cross-platform advisory file locking (.lock) with timeout and stale recovery."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_network_lock_")
        self.target_file = Path(self.temp_dir) / "experiment_registry.sqlite"
        self.lock_file = Path(self.temp_dir) / "experiment_registry.sqlite.lock"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_basic_acquire_and_release(self):
        """Verify acquiring creates .lock file and releasing unlinks it."""
        lock = NetworkFileLock(self.target_file, timeout=5.0)
        self.assertFalse(lock.is_acquired)
        self.assertFalse(lock.is_locked)

        acquired = lock.acquire()
        self.assertTrue(acquired)
        self.assertTrue(lock.is_acquired)
        self.assertTrue(lock.is_locked)
        self.assertTrue(self.lock_file.exists())

        # Check metadata written to lock file
        content = json.loads(self.lock_file.read_text(encoding="utf-8"))
        self.assertEqual(content["lock_id"], lock.lock_id)
        self.assertEqual(content["pid"], os.getpid())
        self.assertIn("created_at", content)

        # Release lock
        lock.release()
        self.assertFalse(lock.is_acquired)
        self.assertFalse(lock.is_locked)
        self.assertFalse(self.lock_file.exists())

    def test_context_manager_normal_exit(self):
        """Verify context manager syntax automatically acquires and releases lock."""
        lock = NetworkFileLock(self.target_file, timeout=5.0)
        self.assertFalse(self.lock_file.exists())

        with lock:
            self.assertTrue(lock.is_acquired)
            self.assertTrue(self.lock_file.exists())

        self.assertFalse(lock.is_acquired)
        self.assertFalse(self.lock_file.exists())

    def test_context_manager_exception_exit(self):
        """Verify lock is released even if an exception occurs inside with block."""
        lock = NetworkFileLock(self.target_file, timeout=5.0)

        with self.assertRaises(RuntimeError):
            with lock:
                self.assertTrue(self.lock_file.exists())
                raise RuntimeError("Simulated crash in critical section")

        self.assertFalse(lock.is_acquired)
        self.assertFalse(self.lock_file.exists())

    def test_lock_timeout_on_contention(self):
        """Verify LockTimeoutError is raised when another process holds the lock."""
        lock1 = NetworkFileLock(self.target_file, timeout=5.0)
        lock2 = NetworkFileLock(self.target_file, timeout=0.2, initial_delay=0.02)

        self.assertTrue(lock1.acquire())
        try:
            # Second lock should time out
            with self.assertRaises(LockTimeoutError) as ctx:
                lock2.acquire()
            self.assertIn("Timed out", str(ctx.exception))
            # Also verify it is a subclass of standard TimeoutError
            self.assertIsInstance(ctx.exception, TimeoutError)
        finally:
            lock1.release()

        # After lock1 is released, lock2 can now acquire
        self.assertTrue(lock2.acquire())
        lock2.release()

    def test_concurrent_access_threads(self):
        """Verify serialized mutual exclusion across concurrent threads."""
        shared_counter = [0]
        execution_order = []
        lock_path = self.target_file

        def worker(worker_id: int):
            lock = NetworkFileLock(lock_path, timeout=10.0, initial_delay=0.02)
            with lock:
                # Critical section
                current = shared_counter[0]
                time.sleep(0.01)  # Simulate I/O or database write
                shared_counter[0] = current + 1
                execution_order.append(worker_id)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(shared_counter[0], 10)
        self.assertEqual(len(execution_order), 10)
        self.assertFalse(self.lock_file.exists())

    def test_stale_lock_detection_and_recovery(self):
        """Verify an abandoned/stale lock is detected and recovered automatically."""
        # Create a simulated stale lock file created 10 minutes ago
        stale_time = time.time() - 600
        stale_meta = {
            "lock_id": "stale_id_999",
            "pid": 99999,
            "hostname": "dead_worker_node",
            "created_at": stale_time,  # 600s in the past
            "stale_timeout": 60.0,
        }
        self.lock_file.write_text(json.dumps(stale_meta), encoding="utf-8")
        try:
            os.utime(str(self.lock_file), (stale_time, stale_time))
        except OSError:
            pass
        self.assertTrue(self.lock_file.exists())

        # New lock with 2.0s stale_timeout should identify the 600s-old lock as stale and break it
        new_lock = NetworkFileLock(
            self.target_file,
            timeout=5.0,
            stale_timeout=2.0,
            initial_delay=0.02,
        )

        acquired = new_lock.acquire()
        self.assertTrue(acquired)
        self.assertTrue(new_lock.is_acquired)

        # Lock file should now contain the new lock metadata, not the stale one
        current_meta = json.loads(self.lock_file.read_text(encoding="utf-8"))
        self.assertEqual(current_meta["lock_id"], new_lock.lock_id)
        self.assertEqual(current_meta["pid"], os.getpid())

        new_lock.release()
        self.assertFalse(self.lock_file.exists())

    def test_break_lock(self):
        """Verify break_lock force-unlinks an active lock file."""
        lock = NetworkFileLock(self.target_file)
        lock.acquire()
        self.assertTrue(self.lock_file.exists())

        success = lock.break_lock()
        self.assertTrue(success)
        self.assertFalse(self.lock_file.exists())
        self.assertFalse(lock.is_acquired)

    def test_manager_file_lock_helper(self):
        """Verify NetworkShareStorageManager.file_lock helper method."""
        manager = NetworkShareStorageManager()
        with manager.file_lock(self.target_file) as lock:
            self.assertTrue(lock.is_acquired)
            self.assertTrue(self.lock_file.exists())
        self.assertFalse(self.lock_file.exists())


class TestCentralizedCASBlobStorage(unittest.TestCase):
    """Test suite for centralized CAS blob directory management, hashing, and atomic rename."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_cas_blobs_")
        self.shared_dir = Path(self.temp_dir) / "shared_lab"
        self.manager = NetworkShareStorageManager(shared_dir=self.shared_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_store_and_retrieve_blob_bytes(self):
        """Verify storing raw bytes into CAS and retrieving them with integrity check."""
        payload = b"Buffer formulation: 50 mM HEPES, 150 mM NaCl, 5% Glycerol, pH 7.5"
        expected_hash = hashlib.sha256(payload).hexdigest()

        sha256 = self.manager.store_blob(payload)
        self.assertEqual(sha256, expected_hash)

        # Check directory layout: {shared_dir}/blobs/{hash[:2]}/{hash}.blob
        expected_path = self.shared_dir / "blobs" / expected_hash[:2] / f"{expected_hash}.blob"
        self.assertTrue(expected_path.exists())
        self.assertEqual(self.manager.get_blob_path(sha256), expected_path)

        # Retrieve bytes
        retrieved = self.manager.get_blob(sha256, verify=True)
        self.assertEqual(retrieved, payload)

        # Verify temp directory is clean
        tmp_dir = self.shared_dir / "blobs" / ".tmp"
        self.assertEqual(len(list(tmp_dir.glob("*.tmp"))), 0)

    def test_store_blob_string(self):
        """Verify storing a string payload converts to utf-8 bytes and stores in CAS."""
        text = "FASTA sequence header: >sp|P01308|INS_HUMAN Insulin"
        sha256 = self.manager.store_blob(text)
        self.assertEqual(sha256, hashlib.sha256(text.encode("utf-8")).hexdigest())

        retrieved = self.manager.get_blob(sha256)
        self.assertEqual(retrieved.decode("utf-8"), text)

    def test_store_blob_deduplication(self):
        """Verify storing identical content twice is deduplicated without error."""
        payload = b"Deduplicated mass spectrometry peak data: 1250.45, 1342.60, 1500.12"
        hash1 = self.manager.store_blob(payload)
        hash2 = self.manager.store_blob(payload)

        self.assertEqual(hash1, hash2)
        shard_dir = self.shared_dir / "blobs" / hash1[:2]
        blob_files = list(shard_dir.glob("*.blob"))
        self.assertEqual(len(blob_files), 1)

    def test_sha256_verification_and_tamper_detection(self):
        """Verify verify_blob catches modified/corrupted files."""
        payload = b"Immutable calibrated fluorometer standard readings"
        sha256 = self.manager.store_blob(payload)

        # Integrity verified on untampered blob
        self.assertTrue(self.manager.verify_blob(sha256))

        # Tamper with the stored blob file directly on disk
        blob_path = self.manager.get_blob_path(sha256)
        with open(blob_path, "wb") as f:
            f.write(b"CORRUPTED TAMPERED CONTENT")

        # verify_blob must return False
        self.assertFalse(self.manager.verify_blob(sha256))

        # get_blob with verify=True must raise ValueError
        with self.assertRaises(ValueError) as ctx:
            self.manager.get_blob(sha256, verify=True)
        self.assertIn("Integrity check failed", str(ctx.exception))

        # get_blob with verify=False returns corrupted content
        corrupted = self.manager.get_blob(sha256, verify=False)
        self.assertEqual(corrupted, b"CORRUPTED TAMPERED CONTENT")

    def test_store_blob_with_expected_hash(self):
        """Verify expected_hash validation on store_blob."""
        payload = b"Sample qPCR amplification curve raw data"
        valid_hash = hashlib.sha256(payload).hexdigest()
        invalid_hash = "0" * 64

        # Storing with correct expected_hash succeeds
        result = self.manager.store_blob(payload, expected_hash=valid_hash)
        self.assertEqual(result, valid_hash)

        # Storing with incorrect expected_hash raises ValueError and leaves no orphan
        with self.assertRaises(ValueError):
            self.manager.store_blob(b"Different data", expected_hash=valid_hash)

    def test_store_blob_from_file_streaming(self):
        """Verify store_blob_from_file streams data directly into CAS."""
        source_file = Path(self.temp_dir) / "source_nanodrop_run.tsv"
        content = b"Wavelength\tAbsorbance\n260\t1.42\n280\t0.75\n" * 500
        source_file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()
        sha256 = self.manager.store_blob_from_file(source_file)

        self.assertEqual(sha256, expected_hash)
        self.assertTrue(self.manager.has_blob(sha256))
        self.assertEqual(self.manager.get_blob(sha256), content)

    def test_get_blob_stream(self):
        """Verify get_blob_stream yields valid binary chunks."""
        payload = b"Large biochemical protocol dataset" * 1000
        sha256 = self.manager.store_blob(payload)

        chunks = list(self.manager.get_blob_stream(sha256, chunk_size=1024))
        reconstructed = b"".join(chunks)
        self.assertEqual(reconstructed, payload)

    def test_delete_blob(self):
        """Verify deleting a stored blob."""
        sha256 = self.manager.store_blob(b"Transient test asset")
        self.assertTrue(self.manager.has_blob(sha256))

        deleted = self.manager.delete_blob(sha256)
        self.assertTrue(deleted)
        self.assertFalse(self.manager.has_blob(sha256))

        # Deleting non-existent blob returns False
        self.assertFalse(self.manager.delete_blob(sha256))

    def test_storage_backend_adapter(self):
        """Verify NetworkStorageBackend adapter functionality."""
        backend = NetworkStorageBackend(shared_dir=self.shared_dir)
        payload = b"StorageBackend integration payload"
        sha256 = hashlib.sha256(payload).hexdigest()

        # Store through backend
        backend.store(sha256, payload, metadata=None)
        self.assertTrue(backend.exists(sha256))
        self.assertEqual(backend.retrieve(sha256), payload)
        self.assertTrue(Path(backend.get_path(sha256)).exists())

        # Delete through backend
        self.assertTrue(backend.delete(sha256))
        self.assertFalse(backend.exists(sha256))


class TestOptimisticConcurrencyControl(unittest.TestCase):
    """Test suite for Optimistic Concurrency Control (OCC) and diff context generation."""

    def test_generate_version_token(self):
        """Verify version token generation produces valid unique UUID4 tokens."""
        token1 = NetworkShareStorageManager.generate_version_token()
        token2 = NetworkShareStorageManager.generate_version_token()

        self.assertIsInstance(token1, str)
        self.assertEqual(len(token1), 36)
        self.assertEqual(token1.count("-"), 4)
        self.assertNotEqual(token1, token2)

    def test_check_conflict_matching_tokens(self):
        """Verify matching tokens do not raise ConcurrencyConflictError."""
        token = OptimisticConcurrencyControl.generate_version_token()
        # Should execute silently without exception
        OptimisticConcurrencyControl.check_conflict(token, token)
        NetworkShareStorageManager.check_conflict(token, token)

    def test_check_conflict_mismatch_raises_error(self):
        """Verify token mismatch raises ConcurrencyConflictError with tokens populated."""
        token_a = "token-alpha-1234"
        token_b = "token-beta-5678"

        with self.assertRaises(ConcurrencyConflictError) as ctx:
            NetworkShareStorageManager.check_conflict(
                current_token=token_a,
                expected_token=token_b,
                record_id="REC-90210",
            )

        err = ctx.exception
        self.assertEqual(err.current_token, token_a)
        self.assertEqual(err.expected_token, token_b)
        self.assertEqual(err.record_id, "REC-90210")
        self.assertIn("REC-90210", str(err))

    def test_check_conflict_with_structured_dictionary_diff(self):
        """Verify diff context generation for conflicting dictionary records."""
        current_record = {
            "title": "Protein Crystallization Run 1",
            "status": "IN_PROGRESS",
            "temperature_c": 20.0,
            "operator": "Alice",
        }
        proposed_record = {
            "title": "Protein Crystallization Run 1 (Optimized)",
            "status": "COMPLETED",
            "temperature_c": 20.0,  # Unchanged
            "notes": "Added 2% PEG 4000",  # Added
            # 'operator' removed
        }

        token_curr = "v1-uuid"
        token_prop = "v2-uuid"

        with self.assertRaises(ConcurrencyConflictError) as ctx:
            NetworkShareStorageManager.check_conflict(
                current_token=token_curr,
                expected_token=token_prop,
                current_record=current_record,
                proposed_record=proposed_record,
                record_id="EXP-101",
            )

        diff = ctx.exception.diff_context
        self.assertIsNotNone(diff)
        self.assertEqual(diff["type"], "dictionary_diff")

        # Modified fields
        self.assertIn("title", diff["modified_fields"])
        self.assertEqual(diff["modified_fields"]["title"]["current"], "Protein Crystallization Run 1")
        self.assertEqual(diff["modified_fields"]["title"]["proposed"], "Protein Crystallization Run 1 (Optimized)")

        self.assertIn("status", diff["modified_fields"])
        self.assertEqual(diff["modified_fields"]["status"]["current"], "IN_PROGRESS")
        self.assertEqual(diff["modified_fields"]["status"]["proposed"], "COMPLETED")

        # Added fields
        self.assertIn("notes", diff["added_fields"])
        self.assertEqual(diff["added_fields"]["notes"], "Added 2% PEG 4000")

        # Removed fields
        self.assertIn("operator", diff["removed_fields"])
        self.assertEqual(diff["removed_fields"]["operator"], "Alice")

    def test_compute_diff_text(self):
        """Verify unified diff calculation for text records."""
        text_a = "Step 1: Digest plasmid with EcoRI\nStep 2: Incubate at 37C for 1h\n"
        text_b = "Step 1: Digest plasmid with EcoRI and BamHI\nStep 2: Incubate at 37C for 1h\n"

        diff = OptimisticConcurrencyControl.compute_diff(text_a, text_b)
        self.assertEqual(diff["type"], "text_diff")
        self.assertTrue(diff["has_diff"])
        self.assertIn("+Step 1: Digest plasmid with EcoRI and BamHI", diff["unified_diff"])


if __name__ == "__main__":
    unittest.main()
