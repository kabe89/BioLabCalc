"""
Test Suite: test_eln_storage
Component: Content-Addressable Storage (CAS) and Web Preview Tests
Architectural Role: Comprehensive verification of CAS deduplication, integrity,
local directory sharding, S3 backend abstraction, and scientific preview generation.
"""

import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

try:
    from PIL import Image
except ImportError:
    Image = None

from biolabcalc.eln.storage.blob_store import (
    BlobMetadata,
    BlobStore,
    LocalStorageBackend,
    S3StorageBackend,
)
from biolabcalc.eln.storage.preview_generator import (
    PreviewGenerator,
    PreviewResult,
)


class TestBlobStore(unittest.TestCase):
    """Unit tests for CAS Blob Storage."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_cas_")
        self.store = BlobStore(base_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_store_and_retrieve_bytes(self):
        payload = b"Sample biochemical protocol: 50 mM Tris pH 8.0, 150 mM NaCl"
        meta = self.store.store_bytes(payload, filename="protocol.txt")

        self.assertIsInstance(meta, BlobMetadata)
        self.assertEqual(meta.size_bytes, len(payload))
        self.assertEqual(meta.filename, "protocol.txt")
        self.assertTrue(self.store.exists(meta.sha256))

        # Retrieve bytes
        retrieved = self.store.get_bytes(meta.sha256)
        self.assertEqual(retrieved, payload)

        # Verify integrity
        self.assertTrue(self.store.verify_integrity(meta.sha256))

    def test_deduplication(self):
        payload = b"Duplicated protein sequence data: MKVLE...*EQ"
        meta1 = self.store.store_bytes(payload, filename="seq1.fasta")
        meta2 = self.store.store_bytes(payload, filename="seq2.fasta")

        self.assertEqual(meta1.sha256, meta2.sha256)
        # Should only be one blob on disk in shard
        shard_dir = Path(self.temp_dir) / meta1.sha256[:2]
        blob_files = list(shard_dir.glob("*.blob"))
        self.assertEqual(len(blob_files), 1)

    def test_store_file(self):
        test_file = Path(self.temp_dir) / "test_input.csv"
        test_file.write_text("Time,UV280\n0,10\n1,250\n2,20\n", encoding="utf-8")

        meta = self.store.store_file(test_file)
        self.assertEqual(meta.filename, "test_input.csv")
        self.assertEqual(meta.mime_type, "text/csv")
        self.assertTrue(self.store.exists(meta.sha256))

    def test_delete(self):
        payload = b"Temporary ephemeral blob"
        meta = self.store.store_bytes(payload)
        self.assertTrue(self.store.exists(meta.sha256))

        deleted = self.store.delete(meta.sha256)
        self.assertTrue(deleted)
        self.assertFalse(self.store.exists(meta.sha256))

        with self.assertRaises(FileNotFoundError):
            self.store.get_bytes(meta.sha256)

    def test_list_blobs(self):
        for i in range(3):
            self.store.store_bytes(f"Payload number {i}".encode("utf-8"), filename=f"f{i}.txt")
        blobs = self.store.list_blobs()
        self.assertEqual(len(blobs), 3)

    def test_s3_backend_simulation(self):
        s3_backend = S3StorageBackend(bucket_name="lims-test-bucket")
        s3_store = BlobStore(backend=s3_backend)

        data = b"S3 object contents"
        meta = s3_store.store_bytes(data, filename="data.bin")

        self.assertEqual(meta.backend, "s3")
        self.assertTrue(meta.storage_path.startswith("s3://lims-test-bucket/"))
        self.assertTrue(s3_store.exists(meta.sha256))

        retrieved = s3_store.get_bytes(meta.sha256)
        self.assertEqual(retrieved, data)

        blobs = s3_store.list_blobs()
        self.assertEqual(len(blobs), 1)

        deleted = s3_store.delete(meta.sha256)
        self.assertTrue(deleted)
        self.assertFalse(s3_store.exists(meta.sha256))


class TestPreviewGenerator(unittest.TestCase):
    """Unit tests for web preview generation."""

    @unittest.skipIf(Image is None, "Pillow is required for image tests")
    def test_generate_image_preview(self):
        # Create synthetic test image
        img = Image.new("RGB", (2000, 1000), color=(100, 150, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw_bytes = buf.getvalue()

        preview = PreviewGenerator.generate_image_preview(raw_bytes, max_dim=800)
        self.assertIsInstance(preview, PreviewResult)
        self.assertEqual(preview.preview_type, "image")
        self.assertEqual(preview.mime_type, "image/png")
        self.assertLessEqual(max(preview.width, preview.height), 800)
        self.assertTrue(len(preview.preview_bytes) > 0)

    @unittest.skipIf(Image is None, "Pillow is required for image tests")
    def test_generate_gel_preview_16bit(self):
        # Create 16-bit grayscale image simulating gel band
        img = Image.new("I;16", (100, 200), color=500)
        # Add high-intensity band in center
        pixels = list(img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata())
        for y in range(80, 120):
            for x in range(30, 70):
                pixels[y * 100 + x] = 45000
        img.putdata(pixels)

        buf = io.BytesIO()
        img.save(buf, format="TIFF")
        raw_bytes = buf.getvalue()

        preview = PreviewGenerator.generate_gel_preview(raw_bytes, auto_contrast=True, invert=True)
        self.assertEqual(preview.preview_type, "gel_scan")
        self.assertEqual(preview.mime_type, "image/png")
        self.assertTrue(len(preview.preview_bytes) > 0)

    def test_generate_trace_preview_svg(self):
        x = [i * 0.1 for i in range(100)]
        y = {"UV280": [10.0 + 50.0 * (1.0 if 40 <= i <= 60 else 0.0) for i in range(100)]}

        preview = PreviewGenerator.generate_trace_preview_svg(
            x_data=x,
            y_series=y,
            title="SEC Trace",
            x_label="Volume (mL)",
            y_label="mAU",
            markers=[{"x": 5.0, "label": "A2"}],
        )

        self.assertEqual(preview.preview_type, "trace_svg")
        self.assertEqual(preview.mime_type, "image/svg+xml")
        svg_text = preview.preview_bytes.decode("utf-8")
        self.assertIn("<svg", svg_text)
        self.assertIn("SEC Trace", svg_text)
        self.assertIn("A2", svg_text)

    @unittest.skipIf(Image is None, "Pillow is required for image tests")
    def test_generate_trace_preview_png(self):
        x = [0.0, 1.0, 2.0, 3.0]
        y = {"Signal": [5.0, 25.0, 100.0, 15.0]}

        preview = PreviewGenerator.generate_trace_preview_png(x, y, title="Test Trace")
        self.assertEqual(preview.preview_type, "trace_png")
        self.assertEqual(preview.mime_type, "image/png")
        self.assertTrue(len(preview.preview_bytes) > 0)


if __name__ == "__main__":
    unittest.main()
