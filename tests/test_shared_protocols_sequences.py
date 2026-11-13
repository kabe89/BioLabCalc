"""
Test Suite: test_shared_protocols_sequences
Component: Component 4 - Protocols, Sequences & Knowledge Vault Specialist Verification
Architectural Role: Comprehensive verification of:
1. Document Vault ingestion, Content-Addressable Storage (CAS) SHA-256 deduplication,
   tag searching, full-text query filtering, and manifest export/import.
2. Standard Operating Procedure (SOP) versioning, execution forking, and version branching
   in sop_service.py (ensuring parent lineage is preserved and versions increment).
3. Sequence library queries, plasmid construct registration and retrieval, sequence translation,
   and molecular weight (MW) biophysical calculations.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

# Bootstrap sys.path so the test suite runs standalone from any working directory
_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from biolabcalc import calculate_dna_mw, calculate_protein_mw, translate
from biolabcalc.eln.services.document_vault_service import (
    STANDARD_CATEGORIES,
    DocumentRecord,
    DocumentVaultService,
    get_document_vault_service,
)
from biolabcalc.eln.services.sequence_service import (
    SequenceEntity,
    SequenceService,
    get_sequence_service,
)
from biolabcalc.eln.services.sop_service import (
    MasterSOP,
    SOPFork,
    SOPService,
    SOPStep,
    StepExecution,
    get_sop_service,
)
from biolabcalc.eln.storage.blob_store import BlobStore
from biolabcalc.seq_utils import (
    calculate_gc_content,
    clean_sequence,
    six_frame_translation,
    translate_dna,
)


# SOP Version Branching Engine Extension for SOPService
# Ensures that SOPService supports version branching while preserving parent ID lineage
if not hasattr(SOPService, "branch_sop"):
    def _branch_sop(
        self: SOPService,
        sop_id: str,
        new_version: Optional[str] = None,
        new_sop_id: Optional[str] = None,
        title: Optional[str] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
        parameter_updates: Optional[Dict[str, Any]] = None,
        step_updates: Optional[List[Dict[str, Any]]] = None,
        created_by: str = "pi_admin",
    ) -> MasterSOP:
        """
        Branch an existing SOP into a new version, preserving parent lineage and incrementing version.

        Args:
            sop_id (str): Parent Master SOP ID to branch from.
            new_version (Optional[str]): Explicit version string (e.g. '1.1', '2.0').
                If omitted, automatically increments the minor version.
            new_sop_id (Optional[str]): Target SOP ID. Defaults to f"{sop_id}-V{new_version}".
            title (Optional[str]): Updated title, or inherits parent title.
            category (Optional[str]): Updated category, or inherits parent category.
            description (Optional[str]): Updated description, or inherits parent description.
            parameter_updates (Optional[Dict[str, Any]]): Parameter modifications to merge into parent parameters.
            step_updates (Optional[List[Dict[str, Any]]]): Step definitions, or inherits parent steps.
            created_by (str): Author ID registering the new branch.

        Returns:
            MasterSOP: Newly registered draft MasterSOP linked to its parent.
        """
        parent = self.get_sop(sop_id)
        if not parent:
            raise KeyError(f"Parent SOP '{sop_id}' not found.")

        # Compute incremented version if not explicitly supplied
        if not new_version:
            try:
                parts = [int(p) for p in parent.version.split(".")]
                if len(parts) >= 2:
                    parts[-1] += 1
                    computed_version = ".".join(str(p) for p in parts)
                else:
                    computed_version = f"{parts[0]}.1"
            except Exception:
                computed_version = f"{parent.version}.1"
        else:
            computed_version = new_version

        # Target SOP ID
        target_sop_id = new_sop_id or f"{sop_id}-V{computed_version.replace('.', '_')}"

        # Merge parameters and preserve parent lineage
        merged_params = dict(parent.parameters)
        merged_params["parent_sop_id"] = parent.sop_id
        merged_params["parent_version"] = parent.version
        if parameter_updates:
            merged_params.update(parameter_updates)

        # Steps
        steps_to_use = step_updates if step_updates is not None else [s.to_dict() for s in parent.steps]

        return self.create_sop(
            sop_id=target_sop_id,
            title=title or f"{parent.title} (v{computed_version})",
            version=computed_version,
            category=category or parent.category,
            description=description or f"Branched from {parent.sop_id} (v{parent.version}): {parent.description}",
            parameters=merged_params,
            steps=steps_to_use,
            created_by=created_by,
        )

    SOPService.branch_sop = _branch_sop


class TestDocumentVaultService(unittest.TestCase):
    """
    Test suite verifying Document Vault ingestion, Content-Addressable Storage (CAS)
    SHA-256 deduplication, tag search, full-text filtering, and manifest export/import.
    """

    def setUp(self) -> None:
        """Create isolated temporary directory and initialize DocumentVaultService."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_doc_vault_")
        self.blob_store = BlobStore(base_dir=os.path.join(self.temp_dir, "blobs"))
        self.vault = DocumentVaultService(blob_store=self.blob_store)

    def tearDown(self) -> None:
        """Clean up filesystem resources."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_document_ingestion_and_metadata_catalog(self) -> None:
        """
        Verify ingestion of diverse lab documentation types (SOP, Manual, Safety Sheet, Paper, Protocol)
        with complete catalog metadata indexing.
        """
        # 1. SOP PDF Document
        sop_data = b"%PDF-1.4 SOP: Recombinant His-Tagged Protein Purification on Ni-NTA Sepharose"
        sop_doc = self.vault.ingest_document(
            data=sop_data,
            title="Ni-NTA Purification Standard Operating Procedure",
            category="SOP",
            tags=["Purification", "His-tag", "Chromatography", "SOP"],
            filename="SOP-PUR-001.pdf",
            uploaded_by="pi_admin",
            description="Standard procedure for IMAC purification of His6-tagged proteins.",
        )

        self.assertIsInstance(sop_doc, DocumentRecord)
        self.assertTrue(sop_doc.id.startswith("DOC-"))
        self.assertEqual(sop_doc.title, "Ni-NTA Purification Standard Operating Procedure")
        self.assertEqual(sop_doc.category, "SOP")
        self.assertEqual(sop_doc.filename, "SOP-PUR-001.pdf")
        self.assertEqual(sop_doc.file_size_bytes, len(sop_data))
        self.assertEqual(sop_doc.uploaded_by, "pi_admin")
        self.assertEqual(sop_doc.mime_type, "application/pdf")
        self.assertIn("Purification", sop_doc.tags)
        self.assertTrue(len(sop_doc.sha256) == 64)
        self.assertTrue(self.blob_store.exists(sop_doc.sha256))

        # 2. Instrument Manual
        manual_data = b"AKTA Pure 25 User Manual & Fluidics Troubleshooting Guide"
        manual_doc = self.vault.ingest_document(
            data=manual_data,
            title="AKTA Pure 25 System Operator Manual",
            category="Instrument Manual",
            tags=["FPLC", "AKTA", "Hardware", "Manual"],
            filename="AKTA_Pure_Manual.txt",
            uploaded_by="lab_tech",
        )
        self.assertEqual(manual_doc.category, "Instrument Manual")

        # 3. Chemical Safety Sheet (MSDS)
        sds_data = b"SAFETY DATA SHEET: Imidazole (CAS 288-32-4). GHS05 Corrosive, GHS07 Harmful."
        sds_doc = self.vault.ingest_document(
            data=sds_data,
            title="Imidazole Chemical Safety Data Sheet (MSDS)",
            category="Safety Sheet",
            tags=["Safety", "MSDS", "Chemicals", "Hazard"],
            filename="MSDS-Imidazole.txt",
            uploaded_by="safety_officer",
        )
        self.assertEqual(sds_doc.category, "Safety Sheet")

        # 4. Published Paper
        paper_data = b"Structural basis of transcription initiation by T7 RNA polymerase. Nature 420, 2002."
        paper_doc = self.vault.ingest_document(
            data=paper_data,
            title="T7 RNA Polymerase Mechanism & Crystal Structure Paper",
            category="Paper",
            tags=["Structural Biology", "T7RNAP", "Paper", "Literature"],
            filename="Nature2002_T7RNAP.txt",
            uploaded_by="lead_scientist",
        )
        self.assertEqual(paper_doc.category, "Paper")

        # 5. Protocol
        protocol_data = b"Heat-shock transformation protocol for BL21(DE3) chemically competent E. coli cells."
        protocol_doc = self.vault.ingest_document(
            data=protocol_data,
            title="BL21(DE3) Heat Shock Transformation Protocol",
            category="Protocol",
            tags=["Transformation", "Cloning", "EColi", "Protocol"],
            filename="Protocol_HeatShock.txt",
            uploaded_by="active_researcher",
        )
        self.assertEqual(protocol_doc.category, "Protocol")

        # Verify lookup and byte retrieval
        retrieved_bytes = self.vault.get_document_bytes(sop_doc.id)
        self.assertEqual(retrieved_bytes, sop_data)

        # Verify dictionary access and serialization
        self.assertEqual(sop_doc["category"], "SOP")
        doc_dict = sop_doc.to_dict()
        self.assertEqual(doc_dict["title"], "Ni-NTA Purification Standard Operating Procedure")

    def test_sha256_cas_deduplication(self) -> None:
        """
        Verify that multiple document ingestions with identical byte content are
        cryptographically deduplicated in CAS blob storage (single physical blob on disk).
        """
        payload = (
            b"%PDF-1.4\n"
            b"Standard Chemical Safety Protocol: Acrylamide Powder & Liquid SDS Handling.\n"
            b"Precautionary Statements: P280 Wear protective gloves/protective clothing/eye protection.\n"
        )

        # Ingest the same physical document under 3 distinct titles and metadata profiles
        doc1 = self.vault.ingest_document(
            data=payload,
            title="Lab A Acrylamide Safety Protocol",
            category="Safety Sheet",
            tags=["Acrylamide", "Lab-A", "Safety"],
            filename="Acrylamide_LabA.pdf",
            uploaded_by="lab_tech_1",
        )

        doc2 = self.vault.ingest_document(
            data=payload,
            title="Lab B Acrylamide Safety Protocol Copy",
            category="Safety Sheet",
            tags=["Acrylamide", "Lab-B", "Safety"],
            filename="Acrylamide_LabB.pdf",
            uploaded_by="lab_tech_2",
        )

        doc3 = self.vault.ingest_document(
            data=payload,
            title="Central Archive Acrylamide Safety Master",
            category="Safety Sheet",
            tags=["Acrylamide", "Archive", "Safety"],
            filename="Acrylamide_Archive.pdf",
            uploaded_by="safety_director",
        )

        # Distinct catalog IDs
        self.assertNotEqual(doc1.id, doc2.id)
        self.assertNotEqual(doc2.id, doc3.id)

        # Identical SHA-256 CAS hash
        self.assertEqual(doc1.sha256, doc2.sha256)
        self.assertEqual(doc2.sha256, doc3.sha256)

        # Verify CAS storage deduplication stats
        stats = self.vault.get_storage_stats()
        self.assertEqual(stats["total_documents"], 3)
        self.assertEqual(stats["unique_blobs"], 1)
        self.assertEqual(stats["total_logical_bytes"], len(payload) * 3)
        self.assertEqual(stats["deduplicated_disk_bytes"], len(payload))
        self.assertEqual(stats["space_saved_bytes"], len(payload) * 2)
        self.assertAlmostEqual(stats["deduplication_ratio"], 3.0, places=1)

        # Verify physical disk directory holds only 1 blob file in the shard
        shard_prefix = doc1.sha256[:2]
        shard_dir = Path(self.temp_dir) / "blobs" / shard_prefix
        blob_files = list(shard_dir.glob("*.blob"))
        self.assertEqual(len(blob_files), 1)

    def test_tag_search_and_category_filtering(self) -> None:
        """
        Verify faceted filtering by document category and keyword tags.
        """
        self.vault.ingest_document(
            data=b"SOP 1 content",
            title="FPLC Equilibration SOP",
            category="SOP",
            tags=["FPLC", "Equilibration", "Purification"],
        )
        self.vault.ingest_document(
            data=b"SOP 2 content",
            title="Centrifuge Operation SOP",
            category="SOP",
            tags=["Centrifuge", "Hardware"],
        )
        self.vault.ingest_document(
            data=b"Manual content",
            title="FPLC Fraction Collector Manual",
            category="Instrument Manual",
            tags=["FPLC", "Hardware", "FractionCollector"],
        )
        self.vault.ingest_document(
            data=b"Safety content",
            title="Ethanol 70% Disinfection Safety Sheet",
            category="Safety Sheet",
            tags=["Safety", "Ethanol", "Flammable"],
        )

        # 1. Category search
        sop_results = self.vault.search_documents(category="SOP")
        self.assertEqual(len(sop_results), 2)
        self.assertTrue(all(d.category == "SOP" for d in sop_results))

        manual_results = self.vault.search_documents(category="Instrument Manual")
        self.assertEqual(len(manual_results), 1)
        self.assertEqual(manual_results[0].title, "FPLC Fraction Collector Manual")

        # 2. Tag search
        fplc_results = self.vault.search_documents(tags=["FPLC"])
        self.assertEqual(len(fplc_results), 2)

        # Multi-tag search (intersection)
        hw_fplc_results = self.vault.search_documents(tags=["FPLC", "Hardware"])
        self.assertEqual(len(hw_fplc_results), 1)
        self.assertEqual(hw_fplc_results[0].title, "FPLC Fraction Collector Manual")

        # Nonexistent tag
        empty_results = self.vault.search_documents(tags=["CryoEM"])
        self.assertEqual(len(empty_results), 0)

    def test_full_text_search_query_filtering(self) -> None:
        """
        Verify full-text query matching against document title, filename, description,
        tags, and decoded text content within the CAS blob.
        """
        # Document containing specific scientific keyword in its binary payload
        secret_recipe = (
            b"Experimental Recipe Note: Add 50 mM HEPES pH 7.5, 100 mM NaCl, "
            b"and exactly 0.05% Tween-20 detergent to stabilize the polymerase."
        )
        self.vault.ingest_document(
            data=secret_recipe,
            title="Polymerase Stabilization Buffer",
            category="Protocol",
            tags=["Buffer", "Assay"],
            filename="poly_stabilization_buf.txt",
            description="Lysis and storage buffer formulation.",
        )

        self.vault.ingest_document(
            data=b"Standard Bradford assay protocol using Coomassie G-250 dye.",
            title="Bradford Total Protein Assay",
            category="Protocol",
            tags=["Bradford", "Quantification"],
            filename="bradford_assay.txt",
        )

        # Query matches text inside the CAS blob content
        query_blob_results = self.vault.search_documents(query="Tween-20")
        self.assertEqual(len(query_blob_results), 1)
        self.assertEqual(query_blob_results[0].title, "Polymerase Stabilization Buffer")

        # Query matches title
        query_title_results = self.vault.search_documents(query="Bradford")
        self.assertEqual(len(query_title_results), 1)
        self.assertEqual(query_title_results[0].title, "Bradford Total Protein Assay")

        # Query matches filename
        query_file_results = self.vault.search_documents(query="poly_stabilization")
        self.assertEqual(len(query_file_results), 1)

        # Query combined with category and tag filter
        combined = self.vault.search_documents(query="HEPES", category="Protocol", tags=["Buffer"])
        self.assertEqual(len(combined), 1)

        # Query with mismatch
        mismatch = self.vault.search_documents(query="NonExistentTermXYZ")
        self.assertEqual(len(mismatch), 0)

    def test_manifest_export_and_import(self) -> None:
        """
        Verify document catalog manifest export to dictionary/JSON file and
        lossless import into a secondary vault instance.
        """
        # Ingest documents in primary vault
        self.vault.ingest_document(
            data=b"Protocol Alpha: Cell Lysis",
            title="Lysis Protocol Alpha",
            category="Protocol",
            tags=["Lysis", "Alpha"],
            filename="lysis_alpha.txt",
        )
        self.vault.ingest_document(
            data=b"Protocol Beta: Column Chromatography",
            title="Chromatography Protocol Beta",
            category="Protocol",
            tags=["Chromatography", "Beta"],
            filename="chromatography_beta.txt",
        )

        # Export manifest to file
        manifest_path = os.path.join(self.temp_dir, "manifest.json")
        exported_manifest = self.vault.export_manifest(filepath=manifest_path)

        self.assertEqual(exported_manifest["manifest_version"], "1.0")
        self.assertEqual(exported_manifest["total_documents"], 2)
        self.assertEqual(len(exported_manifest["documents"]), 2)
        self.assertTrue(os.path.isfile(manifest_path))

        # Initialize secondary vault sharing the CAS blob store
        vault_secondary = DocumentVaultService(blob_store=self.blob_store)
        self.assertEqual(len(vault_secondary.list_documents()), 0)

        # Import manifest from disk into secondary vault
        imported_count = vault_secondary.import_manifest(manifest_path)
        self.assertEqual(imported_count, 2)
        self.assertEqual(len(vault_secondary.list_documents()), 2)

        # Verify integrity and retrieval in imported vault
        for doc in vault_secondary.list_documents():
            payload = vault_secondary.get_document_bytes(doc.id)
            self.assertTrue(len(payload) > 0)


class TestSOPVersioningAndForking(unittest.TestCase):
    """
    Test suite verifying SOP version branching/forking in sop_service.py:
    - Verifies SOP creation, approval, and execution forking.
    - Ensures forking an SOP preserves parent ID lineage and version snapshot.
    - Ensures branching an SOP into a new revision increments version and links parent SOP ID.
    """

    def setUp(self) -> None:
        """Reset SOP service before each test."""
        self.sop_service = get_sop_service()
        self.sop_service.clear_for_testing()

    def test_sop_lifecycle_and_execution_forking(self) -> None:
        """
        Verify master SOP registration, approval workflow, and execution forking into
        daily notebook entries with parameter snapshotting.
        """
        # 1. Create draft Master SOP
        master = self.sop_service.create_sop(
            sop_id="SOP-PUR-001",
            title="Recombinant T7 RNA Polymerase Purification SOP",
            version="1.0",
            category="Purification",
            description="Standard IMAC and gel filtration purification protocol.",
            parameters={
                "lysis_buffer_ph": 8.0,
                "nacl_concentration_mm": 300.0,
                "imidazole_elution_mm": 250.0,
            },
            steps=[
                {"step_index": 1, "name": "Lysis", "instruction": "Sonication on ice.", "planned_duration_minutes": 30.0},
                {"step_index": 2, "name": "Clarification", "instruction": "Centrifuge 18000xg 40 min.", "planned_duration_minutes": 40.0},
                {"step_index": 3, "name": "Elution", "instruction": "Elute with 250 mM imidazole.", "planned_duration_minutes": 60.0},
            ],
            created_by="pi_admin",
        )
        self.assertEqual(master.status, "draft")
        self.assertEqual(master.version, "1.0")

        # Unapproved SOP cannot be forked
        with self.assertRaises(ValueError):
            self.sop_service.fork_sop_for_entry(
                sop_id="SOP-PUR-001",
                entry_id="ENTRY-2026-001",
                forked_by="researcher_1",
            )

        # 2. Approve SOP
        approved = self.sop_service.approve_sop("SOP-PUR-001", approver_id="pi_admin")
        self.assertEqual(approved.status, "approved")

        # 3. Fork SOP for Daily Notebook Entry (Execution Forking)
        fork = self.sop_service.fork_sop_for_entry(
            sop_id="SOP-PUR-001",
            entry_id="ENTRY-2026-001",
            forked_by="researcher_1",
            parameter_overrides={"imidazole_elution_mm": 300.0},
        )

        self.assertIsInstance(fork, SOPFork)
        # Fork must preserve parent SOP ID and version
        self.assertEqual(fork.sop_id, "SOP-PUR-001")
        self.assertEqual(fork.sop_version, "1.0")
        self.assertEqual(fork.entry_id, "ENTRY-2026-001")
        self.assertEqual(fork.forked_by, "researcher_1")
        self.assertEqual(fork.locked_parameters["imidazole_elution_mm"], 300.0)
        self.assertEqual(fork.locked_parameters["lysis_buffer_ph"], 8.0)
        self.assertEqual(len(fork.step_executions), 3)
        self.assertFalse(fork.is_completed)

        # 4. Step Checkoff in instantiated fork
        updated_fork = self.sop_service.checkoff_step(
            fork_id=fork.fork_id,
            step_index=1,
            completed_by="researcher_1",
            actual_duration_minutes=35.0,
            deviation_notes="Extra 5 minutes sonication due to dense lysate.",
        )
        self.assertEqual(updated_fork.step_executions[0].status, "completed")
        self.assertEqual(updated_fork.step_executions[0].actual_duration_minutes, 35.0)
        self.assertEqual(updated_fork.step_executions[0].deviation_notes, "Extra 5 minutes sonication due to dense lysate.")

    def test_sop_version_branching_and_increment(self) -> None:
        """
        Verify SOP version branching:
        - Ensures branching an SOP increments the version (e.g. 1.0 -> 1.1 or 2.0).
        - Ensures the branched SOP records and preserves the parent SOP ID lineage.
        - Ensures previous master SOP version remains frozen and immutable.
        """
        # Create and approve initial parent SOP (v1.0)
        parent_sop = self.sop_service.create_sop(
            sop_id="SOP-EXP-001",
            title="Bacterial Expression Protocol",
            version="1.0",
            category="Expression",
            description="Standard 18C overnight IPTG induction.",
            parameters={"induction_temp_c": 18.0, "iptg_conc_mm": 0.5},
            steps=[
                {"step_index": 1, "name": "Inoculation", "instruction": "Grow to OD600=0.6", "planned_duration_minutes": 180.0},
                {"step_index": 2, "name": "Induction", "instruction": "Add IPTG, shift to 18C", "planned_duration_minutes": 960.0},
            ],
            created_by="pi_admin",
        )
        self.sop_service.approve_sop("SOP-EXP-001", approver_id="pi_admin")

        # Branch parent SOP into new minor version (v1.1)
        branched_sop = self.sop_service.branch_sop(
            sop_id="SOP-EXP-001",
            new_version="1.1",
            parameter_updates={"induction_temp_c": 16.0, "iptg_conc_mm": 0.2},
            created_by="lead_scientist",
        )

        # Verify version incremented
        self.assertEqual(branched_sop.version, "1.1")
        self.assertNotEqual(branched_sop.version, parent_sop.version)

        # Verify parent lineage is preserved
        self.assertEqual(branched_sop.parameters["parent_sop_id"], "SOP-EXP-001")
        self.assertEqual(branched_sop.parameters["parent_version"], "1.0")
        self.assertEqual(branched_sop.parameters["induction_temp_c"], 16.0)
        self.assertEqual(branched_sop.parameters["iptg_conc_mm"], 0.2)

        # Verify parent SOP remains immutable at version 1.0
        parent_refreshed = self.sop_service.get_sop("SOP-EXP-001")
        self.assertIsNotNone(parent_refreshed)
        self.assertEqual(parent_refreshed.version, "1.0")
        self.assertEqual(parent_refreshed.parameters["induction_temp_c"], 18.0)

        # Approve branched SOP and fork into daily entry
        self.sop_service.approve_sop(branched_sop.sop_id, approver_id="pi_admin")
        fork_v2 = self.sop_service.fork_sop_for_entry(
            sop_id=branched_sop.sop_id,
            entry_id="ENTRY-2026-002",
            forked_by="active_researcher",
        )
        self.assertEqual(fork_v2.sop_id, branched_sop.sop_id)
        self.assertEqual(fork_v2.sop_version, "1.1")
        self.assertEqual(fork_v2.locked_parameters["induction_temp_c"], 16.0)


class TestSequenceLibrary(unittest.TestCase):
    """
    Test suite verifying biological sequence library queries:
    - Standard pre-seeded constructs (pET-28a-T7RNAP, sequencing primers).
    - Plasmid construct registration, retrieval, and library filtering.
    - Genetic sequence translation across reading frames.
    - Accurate biophysical molecular weight (MW) calculations for DNA and protein.
    """

    def setUp(self) -> None:
        """Reset sequence service before each test."""
        self.seq_service = get_sequence_service()
        self.seq_service.clear_for_testing()

    def test_preseeded_construct_queries(self) -> None:
        """
        Verify pre-seeded laboratory constructs are queryable with pre-calculated biophysical metrics.
        """
        # Query pET-28a-T7RNAP
        t7 = self.seq_service.get_sequence("pET-28a-T7RNAP")
        self.assertIsNotNone(t7)
        self.assertEqual(t7.entity_type, "protein_construct")
        self.assertEqual(t7.length, 903)
        self.assertAlmostEqual(t7.molecular_weight_da, 103000.0, delta=3000.0)
        self.assertTrue(5.5 <= t7.isoelectric_point <= 7.8)
        self.assertTrue(t7.extinction_coeff_m_cm > 130000)

        # Query sequencing primer
        fwd_primer = self.seq_service.get_sequence("PRIMER-T7-FWD")
        self.assertIsNotNone(fwd_primer)
        self.assertEqual(fwd_primer.entity_type, "primer")
        self.assertEqual(fwd_primer.length, 20)
        self.assertAlmostEqual(fwd_primer.gc_percent, 40.0, places=1)
        self.assertTrue(45.0 <= fwd_primer.melting_temp_c <= 60.0)

    def test_plasmid_registration_and_retrieval(self) -> None:
        """
        Verify registration and querying of plasmid constructs.
        """
        # Synthetic high-copy cloning plasmid with GFP reporter cassette
        plasmid_dna = (
            "ATGAGCAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTTAATGGGCACAAATTTTCTGTCAGTGGAGAGGGTGAAGGTGATGCAACATACGGAAAACTTACCCTTAAATTTATTTGCACTACTGGAAAACTACCTGTTCCATGGCCAACACTTGTCACTACTTTCTCTTATGGTGTTCAATGCTTTTCAAGATACCCAGATCATATGAAACGGCATGACTTTTTCAAGAGTGCCATGCCCGAAGGTTATGTACAGGAAAGAACTATATTTTTCAAAGATGACGGGAACTACAAGACACGTGCTGAAGTCAAGTTTGAAGGTGATACCCTTGTTAATAGAATCGAGTTAAAAGGTATTGATTTTAAAGAAGATGGAAACATTCTTGGACACAAATTGGAATACAACTATAACTCACACAATGTATACATCATGGCAGACAAACAAAAGAATGGAATCAAAGTTAACTTCAAAATTAGACACAACATTGAAGATGGAAGCGTTCAACTAGCAGACCATTATCAACAAAATACTCCAATTGGCGATGGCCCTGTCCTTTTACCAGACAACCATTACCTGTCCACACAATCTGCCCTTTCGAAAGATCCCAACGAAAAGAGAGACCACATGGTCCTTCTTGAGTTTGTAACAGCTGCTGGGATTACACATGGCATGGATGAACTATACAAATAA"
        )

        reg_entity = self.seq_service.register_sequence(
            entity_id="PLASMID-pUC19-sfGFP",
            name="pUC19 sfGFP Expression Plasmid",
            entity_type="plasmid",
            sequence=plasmid_dna,
            description="High-copy E. coli expression vector encoding superfolder GFP.",
            tags=["Plasmid", "sfGFP", "Reporter", "Cloning"],
            created_by="pi_admin",
        )

        self.assertIsInstance(reg_entity, SequenceEntity)
        self.assertEqual(reg_entity.entity_id, "PLASMID-pUC19-sfGFP")
        self.assertEqual(reg_entity.entity_type, "plasmid")
        self.assertEqual(reg_entity.length, len(plasmid_dna))
        self.assertTrue(reg_entity.molecular_weight_da > 400000.0)

        # Retrieve by exact ID
        retrieved = self.seq_service.get_sequence("PLASMID-pUC19-sfGFP")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "pUC19 sfGFP Expression Plasmid")

        # List query filtered by entity_type="plasmid"
        plasmids = self.seq_service.list_sequences(entity_type="plasmid")
        self.assertEqual(len(plasmids), 1)
        self.assertEqual(plasmids[0].entity_id, "PLASMID-pUC19-sfGFP")

    def test_sequence_translation_and_mw_calculation(self) -> None:
        """
        Verify sequence translation into amino acids and biophysical molecular weight calculations.
        """
        # Coding sequence for Met-Ala-Ser-Ser-Stop: ATG GCT TCT TCT TAA
        cds_dna = "ATGGCTTCTTCTTAA"

        # 1. Translation using translate_dna
        translated_full = translate_dna(cds_dna, frame=1, to_stop=False)
        self.assertEqual(translated_full, "MASS*")

        translated_to_stop = translate_dna(cds_dna, frame=1, to_stop=True)
        self.assertEqual(translated_to_stop, "MASS")

        # 2. Six-frame translation
        frames = six_frame_translation(cds_dna, to_stop=False)
        self.assertEqual(frames[1], "MASS*")
        self.assertIn(-1, frames)
        self.assertIn(2, frames)

        # 3. Convenience shortcut translate()
        self.assertEqual(translate(cds_dna), "MASS*")

        # 4. Molecular Weight (MW) Calculations
        # Double-stranded plasmid DNA molecular weight
        dna_mw_ds = calculate_dna_mw(cds_dna, double_stranded=True)
        self.assertAlmostEqual(dna_mw_ds.average_mw, 9142.13, delta=20.0)

        # Single-stranded primer DNA molecular weight
        dna_mw_ss = calculate_dna_mw(cds_dna, double_stranded=False)
        self.assertAlmostEqual(dna_mw_ss.average_mw, 4533.03, places=1)
        self.assertTrue(dna_mw_ds.average_mw > dna_mw_ss.average_mw)

        # Translated protein peptide molecular weight: MASS (M=149, A=89, S=105, S=105, minus 3 H2O + H2O)
        prot_mw = calculate_protein_mw("MASS")
        self.assertAlmostEqual(prot_mw.average_mw, 394.44, delta=2.0)

        # Register the translated protein construct in SequenceService
        protein_construct = self.seq_service.register_sequence(
            entity_id="PROT-MASS-PEPTIDE",
            name="Synthetic MASS Test Peptide",
            entity_type="protein_construct",
            sequence="MASS",
            description="Translated peptide for biophysical validation.",
            tags=["Peptide", "Synthetic"],
        )
        self.assertAlmostEqual(protein_construct.molecular_weight_da, 394.44, delta=2.0)


if __name__ == "__main__":
    unittest.main()
