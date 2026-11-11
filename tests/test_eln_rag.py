"""
Unit Tests for State-of-the-Art ELN & LIMS Pipeline: Hybrid-RAG, Local LLM & Knowledge Retrieval Engine
Agent: @agent: eln-rag-agent
"""

import json
import math
import os
import unittest
from unittest.mock import MagicMock, patch

from biolabcalc.eln.rag.chunker import (
    DocumentChunk,
    DocumentChunker,
    LaboratoryEntityExtractor,
    ProvenanceMetadata,
)
from biolabcalc.eln.rag.hybrid_search import (
    BM25Engine,
    HybridSearchEngine,
    SearchResult,
)
from biolabcalc.eln.rag.local_llm import (
    LocalLLMClient,
    OfflineEmbeddingGenerator,
    OfflineHeuristicGenerator,
    cosine_similarity,
)
from biolabcalc.eln.rag.synthesizer import (
    Citation,
    CitationSynthesizer,
    SynthesisResult,
)


class TestLocalLLM(unittest.TestCase):
    """
    Test suite for LocalLLMClient and offline deterministic fallbacks.
    Agent: @agent: eln-rag-agent
    """

    def test_offline_embedding_deterministic_and_normalized(self):
        generator = OfflineEmbeddingGenerator(dimensions=128)
        text1 = "Purification of T7 RNA Polymerase using pET-28a-T7RNAP on Superdex 200"
        text2 = "Purification of T7 RNA Polymerase using pET-28a-T7RNAP on Superdex 200"
        text3 = "Unrelated CRISPR Cas9 guide RNA synthesis in yeast"

        emb1 = generator.embed_text(text1)
        emb2 = generator.embed_text(text2)
        emb3 = generator.embed_text(text3)

        self.assertEqual(len(emb1), 128)
        self.assertEqual(emb1, emb2, "Identical input texts must produce identical deterministic vectors.")

        norm1 = math.sqrt(sum(x * x for x in emb1))
        self.assertAlmostEqual(norm1, 1.0, places=5, msg="Embedding vector must be L2 normalized to unit hypersphere.")

        sim_identical = cosine_similarity(emb1, emb2)
        self.assertAlmostEqual(sim_identical, 1.0, places=5)

        sim_unrelated = cosine_similarity(emb1, emb3)
        self.assertLess(sim_unrelated, 0.7, "Unrelated lab texts should have significantly lower cosine similarity.")

    def test_cosine_similarity_edge_cases(self):
        self.assertEqual(cosine_similarity([], []), 0.0)
        self.assertEqual(cosine_similarity([1.0, 0.0], [0.0, 0.0]), 0.0)
        self.assertEqual(cosine_similarity([1.0, 2.0], [1.0]), 0.0)
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0, places=5)
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0, places=5)

    def test_environment_variable_url_resolution(self):
        with patch.dict(os.environ, {"LOCAL_CLUSTER_URL": "http://slurm-headnode:8000/v1"}, clear=True):
            client = LocalLLMClient()
            self.assertEqual(client.base_url, "http://slurm-headnode:8000/v1")
            self.assertEqual(client.endpoint_type, "openai")

        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://gpu-worker-01:11434/"}, clear=True):
            client = LocalLLMClient()
            self.assertEqual(client.base_url, "http://gpu-worker-01:11434")
            self.assertEqual(client.endpoint_type, "ollama")

        # Explicit argument overrides environment variables
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://cluster:11434"}, clear=True):
            client = LocalLLMClient(base_url="http://custom-node:5000", endpoint_type="openai")
            self.assertEqual(client.base_url, "http://custom-node:5000")
            self.assertEqual(client.endpoint_type, "openai")

    def test_offline_heuristic_generator(self):
        generator = OfflineHeuristicGenerator()
        prompt = (
            "[Ref 1]\n"
            "Author: Dr. Rosalind Franklin (rf_franklin)\n"
            "Date: 2024-05-12\n"
            "Instrument: AKTA pure 25 M1\n"
            "Content: Purified T7 RNA Polymerase using construct pET-28a-T7RNAP on Superdex 200 10/300 GL.\n"
            "Elution Volume Ve = 13.2 mL, observed yield 45.6 mg. Buffer: 50 mM Tris-HCl pH 8.0, 100 mM NaCl, 1 mM DTT.\n"
        )
        response = generator.generate_response(prompt)
        self.assertIn("pET-28a-T7RNAP", response)
        self.assertIn("Superdex 200", response)
        self.assertIn("13.2 mL", response)
        self.assertIn("45.6 mg", response)
        self.assertIn("[Ref 1]", response)

    def test_chat_method_fallback(self):
        client = LocalLLMClient()
        messages = [
            {"role": "system", "content": "You are a laboratory assistant."},
            {"role": "user", "content": "What is the buffer recipe?"},
        ]
        res = client.chat(messages)
        self.assertIsInstance(res, str)
        self.assertTrue(len(res) > 0)


    def test_mock_ollama_remote_inference(self):
        client = LocalLLMClient(base_url="http://fake-ollama:11434", endpoint_type="ollama")

        # Mock is_reachable
        with patch.object(client, "is_reachable", return_value=True):
            # Mock /api/embed
            mock_embed_resp = MagicMock()
            mock_embed_resp.read.return_value = json.dumps({"embeddings": [[0.1] * 128]}).encode("utf-8")
            mock_embed_resp.__enter__.return_value = mock_embed_resp

            # Mock /api/generate
            mock_gen_resp = MagicMock()
            mock_gen_resp.read.return_value = json.dumps({"response": "Mocked Ollama response [Ref 1]"}).encode("utf-8")
            mock_gen_resp.__enter__.return_value = mock_gen_resp

            with patch("urllib.request.urlopen", side_effect=[mock_embed_resp, mock_gen_resp]):
                emb = client.embed("test text")
                self.assertEqual(len(emb), 1)
                self.assertEqual(len(emb[0]), 128)

                gen = client.generate("test prompt")
                self.assertEqual(gen, "Mocked Ollama response [Ref 1]")

    def test_mock_openai_remote_inference(self):
        client = LocalLLMClient(base_url="http://slurm-headnode:8000/v1", endpoint_type="openai")

        with patch.object(client, "is_reachable", return_value=True):
            # Mock /v1/embeddings
            mock_emb_resp = MagicMock()
            mock_emb_resp.read.return_value = json.dumps({
                "data": [{"index": 0, "embedding": [0.2] * 128}]
            }).encode("utf-8")
            mock_emb_resp.__enter__.return_value = mock_emb_resp

            # Mock /v1/chat/completions
            mock_chat_resp = MagicMock()
            mock_chat_resp.read.return_value = json.dumps({
                "choices": [{"message": {"content": "Mocked vLLM response"}}]
            }).encode("utf-8")
            mock_chat_resp.__enter__.return_value = mock_chat_resp

            with patch("urllib.request.urlopen", side_effect=[mock_emb_resp, mock_chat_resp]):
                emb = client.embed(["test input"])
                self.assertEqual(len(emb[0]), 128)

                gen = client.generate("test query")
                self.assertEqual(gen, "Mocked vLLM response")


class TestLaboratoryEntityExtractor(unittest.TestCase):
    """
    Test suite for LaboratoryEntityExtractor and regex pattern matching.
    Agent: @agent: eln-rag-agent
    """

    def test_extract_all_biological_entities(self):
        text = (
            "We transformed BL21(DE3) with construct pET-28a-T7RNAP and pGEX-4T-1-GST. "
            "Primers used were T7-fwd, T7RNAP-rev, and oBR102. "
            "Purification conducted on Superdex 200 10/300 GL and HisTrap HP 5mL columns. "
            "Peak fraction gave Ve=13.2 mL with a final yield of 45.6 mg. "
            "Mutation S65T and D538G were sequenced. "
            "Catalog reagent Cat# 28-9909-44 and #M0273S verified. "
            "Equilibration in 50 mM Tris-HCl pH 8.0, 100 mM NaCl buffer."
        )
        entities = LaboratoryEntityExtractor.extract_entities(text)

        self.assertIn("pET-28a-T7RNAP", entities.get("constructs", []))
        self.assertIn("pGEX-4T-1-GST", entities.get("constructs", []))
        self.assertIn("T7-fwd", entities.get("primers", []))
        self.assertIn("oBR102", entities.get("primers", []))
        self.assertIn("Superdex 200 10/300 GL", entities.get("columns", []))
        self.assertIn("HisTrap HP 5mL", entities.get("columns", []))
        self.assertIn("Ve=13.2 mL", entities.get("elution_volumes", []))
        self.assertIn("45.6 mg", entities.get("yields", []))
        self.assertIn("S65T", entities.get("mutations", []))
        self.assertIn("D538G", entities.get("mutations", []))
        self.assertIn("28-9909-44", entities.get("catalog_numbers", []))
        self.assertIn("50 mM Tris-HCl pH 8.0", entities.get("buffers", []))


class TestDocumentChunker(unittest.TestCase):
    """
    Test suite for Multi-Entity Semantic DocumentChunker across ELN/LIMS modalities.
    Agent: @agent: eln-rag-agent
    """

    def setUp(self):
        self.chunker = DocumentChunker(default_chunk_size=300)
        self.meta = ProvenanceMetadata(
            author_id="rf_franklin",
            author_name="Dr. Rosalind Franklin",
            project_tag="T7RNAP_Expression",
            campaign_id="CAMP-2024-Q3",
            campaign_day=4,
            recorded_at="2024-05-12T14:30:00Z",
            entity_type="daily_entry",
            author_status="current",
            instrument_record="AKTA pure 25 M1",
            source_file="notebooks/2024-05-12_T7RNAP_Purification.eln",
        )

    def test_chunk_daily_entry_preserves_provenance(self):
        text = (
            "## Objective\nPurify recombinant T7RNAP.\n\n"
            "## Method\nLysis in 50 mM Tris-HCl pH 8.0 with Ni-NTA agarose.\n\n"
            "## Results\nElution peak Ve=13.2 mL on Superdex 200. Yield: 45.6 mg."
        )
        chunks = self.chunker.chunk_daily_entry(text, self.meta)
        self.assertTrue(len(chunks) >= 1)
        c0 = chunks[0]
        self.assertEqual(c0.metadata.author_id, "rf_franklin")
        self.assertEqual(c0.metadata.campaign_id, "CAMP-2024-Q3")
        self.assertEqual(c0.metadata.campaign_day, 4)
        self.assertEqual(c0.metadata.instrument_record, "AKTA pure 25 M1")
        self.assertIn("Superdex 200", c0.content)

    def test_chunk_fplc_peaks_structured(self):
        fplc_data = {
            "target_protein": "T7 RNA Polymerase",
            "column": "Superdex 200 10/300 GL",
            "flow_rate": "0.5 mL/min",
            "buffer": "50 mM Tris-HCl pH 8.0, 100 mM NaCl, 1 mM DTT",
            "peaks": [
                {
                    "peak_number": 1,
                    "ve": "13.2 mL",
                    "yield": "45.6 mg",
                    "area": 1284.5,
                    "fractions": "B2-B6",
                }
            ],
        }
        chunks = self.chunker.chunk_fplc_peaks(fplc_data, self.meta)
        self.assertEqual(len(chunks), 1)
        c = chunks[0]
        self.assertEqual(c.metadata.entity_type, "fplc_chromatogram")
        self.assertIn("13.2 mL", c.extracted_entities.get("elution_volumes", []))
        self.assertIn("45.6 mg", c.extracted_entities.get("yields", []))

    def test_chunk_nanodrop_record(self):
        nano_data = {
            "sample_name": "T7RNAP_Eluate_Pool",
            "concentration": "4.56",
            "a280": "0.64",
            "ratio_260_280": "1.78",
            "total_yield": "45.6 mg",
            "extinction_coeff": "140000 M-1 cm-1",
        }
        chunks = self.chunker.chunk_nanodrop_record(nano_data, self.meta)
        self.assertEqual(len(chunks), 1)
        c = chunks[0]
        self.assertEqual(c.metadata.entity_type, "nanodrop_record")
        self.assertIn("45.6 mg", c.content)
        self.assertIn("1.78", c.content)

    def test_chunk_biorad_gel(self):
        gel_data = {
            "gel_type": "4-20% Mini-PROTEAN TGX",
            "staining": "Coomassie R-250",
            "ladder": "Precision Plus Dual Color",
            "lanes": [
                {"lane_number": 1, "sample": "Ladder", "apparent_mw": "10-250 kDa", "purity_percent": 100},
                {"lane_number": 2, "sample": "pET-28a-T7RNAP eluate", "apparent_mw": "99 kDa", "purity_percent": 95},
            ],
        }
        chunks = self.chunker.chunk_biorad_gel(gel_data, self.meta)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].metadata.entity_type, "biorad_gel")
        self.assertIn("99 kDa", chunks[0].content)

    def test_chunk_kinetic_log(self):
        kinetic_data = {
            "assay_name": "In Vitro Transcription Kinetics",
            "enzyme": "T7 RNA Polymerase",
            "substrate": "NTP mix + DNA template",
            "vmax": "12.4 nmol/min",
            "km": "0.15 mM",
            "temperature": "37 C",
            "timepoints": [
                {"time": 0, "od": 0.0},
                {"time": 15, "od": 0.42},
                {"time": 30, "od": 0.85},
            ],
        }
        chunks = self.chunker.chunk_kinetic_log(kinetic_data, self.meta)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].metadata.entity_type, "kinetic_log")
        self.assertIn("12.4 nmol/min", chunks[0].content)

    def test_chunk_dispatcher(self):
        c1 = self.chunker.chunk_document("Sample SOP text", "sop", self.meta)
        self.assertEqual(c1[0].metadata.entity_type, "sop")

        c2 = self.chunker.chunk_document("Daily notebook notes", "daily_entry", self.meta)
        self.assertEqual(c2[0].metadata.entity_type, "daily_entry")

    def test_chunk_and_provenance_serialization(self):
        chunk = self.chunker.chunk_daily_entry(
            "Purification using construct pET-28a-T7RNAP with mutation S65T.",
            self.meta,
        )[0]
        chunk_dict = chunk.to_dict()
        reconstructed = DocumentChunk.from_dict(chunk_dict)

        self.assertEqual(reconstructed.chunk_id, chunk.chunk_id)
        self.assertEqual(reconstructed.metadata.author_id, self.meta.author_id)
        self.assertEqual(reconstructed.metadata.campaign_id, self.meta.campaign_id)
        self.assertEqual(reconstructed.content, chunk.content)
        self.assertEqual(reconstructed.extracted_entities, chunk.extracted_entities)


class TestHybridSearchEngine(unittest.TestCase):
    """
    Test suite for HybridSearchEngine, BM25 scoring, RRF ranking, and provenance filters.
    Agent: @agent: eln-rag-agent
    """

    def setUp(self):
        self.chunker = DocumentChunker()
        self.engine = HybridSearchEngine()

        # Prepare corpus of laboratory entries
        meta_franklin = ProvenanceMetadata(
            author_id="rf_franklin",
            author_name="Dr. Rosalind Franklin",
            project_tag="T7RNAP_Expression",
            campaign_id="CAMP-2024-Q3",
            campaign_day=4,
            recorded_at="2024-05-12T14:30:00Z",
            entity_type="fplc_chromatogram",
            author_status="current",
            instrument_record="AKTA pure 25 M1",
            source_file="notebooks/2024-05-12_T7RNAP_Purification.eln",
        )
        c1 = self.chunker.chunk_fplc_peaks(
            {
                "target_protein": "T7 RNA Polymerase",
                "column": "Superdex 200 10/300 GL",
                "flow_rate": "0.5 mL/min",
                "buffer": "50 mM Tris-HCl pH 8.0, 100 mM NaCl, 1 mM DTT",
                "peaks": [{"peak_number": 1, "ve": "13.2 mL", "yield": "45.6 mg"}],
            },
            meta_franklin,
        )[0]

        meta_alumni = ProvenanceMetadata(
            author_id="jm_watson",
            author_name="Dr. J. Watson",
            project_tag="T7RNAP_Expression",
            campaign_id="CAMP-2022-Q1",
            campaign_day=12,
            recorded_at="2022-03-10T10:00:00Z",
            entity_type="daily_entry",
            author_status="alumni",
            instrument_record="Bio-Rad NGC",
            source_file="notebooks/2022-03-10_Watson_Legacy.eln",
        )
        c2 = self.chunker.chunk_daily_entry(
            "Purified T7 RNA Polymerase using construct pET-28a-T7RNAP. Observed yield 32.0 mg in Tris pH 7.5.",
            meta_alumni,
        )[0]

        meta_unrelated = ProvenanceMetadata(
            author_id="ac_clarke",
            author_name="Dr. Arthur Clarke",
            project_tag="Bacterial_Motility",
            campaign_id="CAMP-2024-Q2",
            campaign_day=1,
            recorded_at="2024-04-01T09:00:00Z",
            entity_type="daily_entry",
            author_status="current",
            instrument_record="Phase Contrast Scope",
            source_file="notebooks/motility.eln",
        )
        c3 = self.chunker.chunk_daily_entry(
            "Bacterial swimming motility assay on soft agar plates at 30 C.",
            meta_unrelated,
        )[0]

        self.engine.index_chunks([c1, c2, c3])

    def test_rrf_scoring_formula(self):
        # Test query matching T7RNAP chromatography
        query = "What elution volume Ve and yield did past members achieve for T7 RNA Polymerase on Superdex 200?"
        results = self.engine.search(query, top_k=3)

        self.assertGreaterEqual(len(results), 2)
        top = results[0]
        # Top result should be the FPLC chromatogram
        self.assertEqual(top.chunk.metadata.author_id, "rf_franklin")
        self.assertGreater(top.rrf_score, 0.0)

        # Mathematical verification of RRF formula: 1 / (60 + r_dense) + 1 / (60 + r_sparse)
        expected_rrf = (1.0 / (60 + top.dense_rank)) + (1.0 / (60 + top.sparse_rank))
        self.assertAlmostEqual(top.rrf_score, expected_rrf, places=6)

    def test_author_status_filtering_current_vs_alumni(self):
        query = "T7 RNA Polymerase yield"

        # Search only current researchers
        current_res = self.engine.search(query, author_status="current")
        for r in current_res:
            self.assertEqual(r.chunk.metadata.author_status, "current")
        self.assertTrue(any(r.chunk.metadata.author_id == "rf_franklin" for r in current_res))
        self.assertFalse(any(r.chunk.metadata.author_id == "jm_watson" for r in current_res))

        # Search only alumni researchers
        alumni_res = self.engine.search(query, author_status="alumni")
        for r in alumni_res:
            self.assertEqual(r.chunk.metadata.author_status, "alumni")
        self.assertTrue(all(r.chunk.metadata.author_id == "jm_watson" for r in alumni_res))

    def test_temporal_date_and_campaign_day_filters(self):
        query = "T7 RNA Polymerase"

        # Filter date range: 2024 only
        res_2024 = self.engine.search(query, date_start="2024-01-01", date_end="2024-12-31")
        self.assertTrue(all("2024" in r.chunk.metadata.recorded_at for r in res_2024))
        self.assertFalse(any("2022" in r.chunk.metadata.recorded_at for r in res_2024))

        # Filter by campaign day range
        res_day = self.engine.search(query, campaign_day_min=10, campaign_day_max=15)
        self.assertEqual(len(res_day), 1)
        self.assertEqual(res_day[0].chunk.metadata.author_id, "jm_watson")

    def test_entity_type_filtering(self):
        query = "T7 RNA Polymerase"
        res_fplc = self.engine.search(query, entity_types=["fplc_chromatogram"])
        self.assertEqual(len(res_fplc), 1)
        self.assertEqual(res_fplc[0].chunk.metadata.entity_type, "fplc_chromatogram")

    def test_exact_entity_match_boost(self):
        # Query containing exact construct pET-28a-T7RNAP
        res = self.engine.search("construct pET-28a-T7RNAP")
        self.assertGreater(len(res), 0)
        # Top hit must contain pET-28a-T7RNAP
        self.assertIn("pET-28a-T7RNAP", res[0].chunk.content)
        self.assertGreater(res[0].sparse_score, 0.0)

    def test_multi_filter_combination(self):
        # Combination of author_ids, project_tag, date range, campaign_day
        res = self.engine.search(
            "T7RNAP",
            author_ids=["rf_franklin"],
            project_tags=["T7RNAP_Expression"],
            date_start="2024-01-01",
            campaign_day_min=1,
            campaign_day_max=10,
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].chunk.metadata.author_id, "rf_franklin")


class TestCitationSynthesizer(unittest.TestCase):
    """
    Test suite for CitationSynthesizer, answering queries with exact citations.
    Agent: @agent: eln-rag-agent
    """

    def setUp(self):
        self.chunker = DocumentChunker()
        self.llm = LocalLLMClient()
        self.engine = HybridSearchEngine(llm_client=self.llm)

        meta = ProvenanceMetadata(
            author_id="rf_franklin",
            author_name="Dr. Rosalind Franklin",
            project_tag="T7RNAP_Expression",
            campaign_id="CAMP-2024-Q3",
            campaign_day=4,
            recorded_at="2024-05-12T14:30:00Z",
            entity_type="fplc_chromatogram",
            instrument_record="AKTA pure 25 M1",
            source_file="notebooks/2024-05-12_T7RNAP_Purification.eln",
        )
        c = self.chunker.chunk_daily_entry(
            "Purified T7 RNA Polymerase (construct pET-28a-T7RNAP) on Superdex 200 10/300 GL column. "
            "Elution peak observed at Ve = 13.2 mL. Yield: 45.6 mg. "
            "Buffer: 50 mM Tris-HCl pH 8.0, 100 mM NaCl, 1 mM DTT.",
            meta,
        )[0]
        self.engine.index_chunks([c])
        self.synthesizer = CitationSynthesizer(llm_client=self.llm, search_engine=self.engine)

    def test_synthesizer_answers_query_with_citations(self):
        query = "What elution volume, buffer, and yield did past members achieve for T7 RNA Polymerase?"
        res: SynthesisResult = self.synthesizer.synthesize(query=query, top_k=2)

        self.assertIsInstance(res, SynthesisResult)
        self.assertEqual(res.query, query)
        self.assertEqual(len(res.citations), 1)

        # Check that answer contains key metrics
        self.assertIn("13.2 mL", res.answer)
        self.assertIn("45.6 mg", res.answer)
        self.assertIn("Superdex 200", res.answer)
        self.assertIn("[Ref 1]", res.answer)

        # Check citation object
        cit = res.citations[0]
        self.assertEqual(cit.ref_id, 1)
        self.assertEqual(cit.author_name, "Dr. Rosalind Franklin")
        self.assertEqual(cit.author_id, "rf_franklin")
        self.assertEqual(cit.campaign_id, "CAMP-2024-Q3")
        self.assertEqual(cit.campaign_day, 4)
        self.assertEqual(cit.instrument_record, "AKTA pure 25 M1")
        self.assertEqual(cit.source_file, "notebooks/2024-05-12_T7RNAP_Purification.eln")

        # Check formatted markdown references block
        self.assertIn("### References & Provenance Traceability", res.citations_markdown)
        self.assertIn("**Dr. Rosalind Franklin**", res.citations_markdown)
        self.assertIn("AKTA pure 25 M1", res.citations_markdown)
        self.assertIn("notebooks/2024-05-12_T7RNAP_Purification.eln", res.citations_markdown)

        # Check full response
        self.assertIn(res.answer, res.full_response)
        self.assertIn(res.citations_markdown, res.full_response)

    def test_synthesizer_empty_search(self):
        empty_synthesizer = CitationSynthesizer(llm_client=self.llm, search_engine=HybridSearchEngine())
        res = empty_synthesizer.synthesize("Nonexistent target")
        self.assertIn("No laboratory notebook records found", res.answer)
        self.assertEqual(len(res.citations), 0)


if __name__ == "__main__":
    unittest.main()
