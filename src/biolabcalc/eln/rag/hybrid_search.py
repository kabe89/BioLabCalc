"""
Module: biolabcalc.eln.rag.hybrid_search
Component: Hybrid Dense-Sparse Search Engine with Reciprocal Rank Fusion (RRF)
Agent: @agent: eln-rag-agent
Architectural Role: Executes multi-modal laboratory search combining cosine vector
similarity and BM25 lexical ranking with laboratory entity boosts and multi-user
temporal provenance filtering.
"""

from dataclasses import dataclass
import math
import re
from typing import Any, Dict, List, Optional, Set, Union

from .chunker import DocumentChunk, LaboratoryEntityExtractor
from .local_llm import LocalLLMClient, cosine_similarity


@dataclass
class SearchResult:
    """
    Scored and ranked laboratory search result containing provenance chunk,
    individual dense and sparse scores, and fused RRF metric.

    Parameters
    ----------
    chunk : DocumentChunk
        Matched laboratory document chunk.
    rrf_score : float
        Combined Reciprocal Rank Fusion score.
    dense_score : float
        Vector cosine similarity score in [-1.0, 1.0].
    sparse_score : float
        BM25 and lexical entity match score.
    dense_rank : int
        1-based rank in dense vector candidate list.
    sparse_rank : int
        1-based rank in sparse lexical candidate list.

    Agent
    -----
    @agent: eln-rag-agent
    """

    chunk: DocumentChunk
    rrf_score: float
    dense_score: float
    sparse_score: float
    dense_rank: int
    sparse_rank: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert SearchResult to dictionary."""
        return {
            "chunk_id": self.chunk.chunk_id,
            "rrf_score": round(self.rrf_score, 6),
            "dense_score": round(self.dense_score, 6),
            "sparse_score": round(self.sparse_score, 6),
            "dense_rank": self.dense_rank,
            "sparse_rank": self.sparse_rank,
            "metadata": self.chunk.metadata.to_dict(),
            "extracted_entities": self.chunk.extracted_entities,
            "content": self.chunk.content,
        }


class BM25Engine:
    """
    Okapi BM25 ranking engine enhanced with exact laboratory entity matching.

    Parameters
    ----------
    k1 : float
        Term frequency saturation parameter (default: 1.5).
    b : float
        Document length normalization parameter (default: 0.75).

    Agent
    -----
    @agent: eln-rag-agent
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_count: int = 0
        self.avg_doc_len: float = 0.0
        self.doc_lens: List[int] = []
        self.doc_freqs: Dict[str, int] = {}
        self.term_idfs: Dict[str, float] = {}

    def fit(self, chunks: List[DocumentChunk]) -> None:
        """
        Fit document frequencies, lengths, and IDFs on corpus chunks.

        Parameters
        ----------
        chunks : List[DocumentChunk]
            Document chunks in the search index.
        """
        self.doc_count = len(chunks)
        self.doc_freqs.clear()
        self.doc_lens.clear()

        total_len = 0
        for chunk in chunks:
            # Document length based on sum of token frequencies
            d_len = sum(chunk.sparse_tokens.values()) if chunk.sparse_tokens else 1
            self.doc_lens.append(d_len)
            total_len += d_len

            # Track unique terms in chunk
            for token in chunk.sparse_tokens.keys():
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        self.avg_doc_len = (total_len / self.doc_count) if self.doc_count > 0 else 1.0

        # Compute Robertson-Spärck Jones IDF for each vocabulary term
        self.term_idfs.clear()
        for term, df in self.doc_freqs.items():
            # Standard positive IDF formula
            idf = math.log(((self.doc_count - df + 0.5) / (df + 0.5)) + 1.0)
            self.term_idfs[term] = max(idf, 0.05)

    def score(
        self,
        query_tokens: Dict[str, int],
        chunk: DocumentChunk,
        chunk_idx: int,
        query_entities: Optional[Dict[str, List[str]]] = None,
    ) -> float:
        """
        Compute BM25 score for a chunk against query tokens and entities.

        Parameters
        ----------
        query_tokens : Dict[str, int]
            Query token frequencies.
        chunk : DocumentChunk
            Target document chunk.
        chunk_idx : int
            Index of chunk in corpus.
        query_entities : Optional[Dict[str, List[str]]]
            Extracted entities from query to apply exact match boosts.

        Returns
        -------
        float
            BM25 lexical relevance score.
        """
        if self.doc_count == 0 or not chunk.sparse_tokens:
            return 0.0

        doc_len = self.doc_lens[chunk_idx] if chunk_idx < len(self.doc_lens) else sum(chunk.sparse_tokens.values())
        len_norm = 1.0 - self.b + (self.b * (doc_len / self.avg_doc_len))

        score = 0.0
        for term, q_tf in query_tokens.items():
            tf = chunk.sparse_tokens.get(term, 0)
            if tf <= 0:
                continue

            idf = self.term_idfs.get(term, math.log(self.doc_count + 1.0))
            numerator = tf * (self.k1 + 1.0)
            denominator = tf + (self.k1 * len_norm)
            score += idf * (numerator / denominator) * q_tf

        # Exact biological entity matching boost
        if query_entities and chunk.extracted_entities:
            for cat, q_vals in query_entities.items():
                chunk_vals = [v.lower() for v in chunk.extracted_entities.get(cat, [])]
                for qv in q_vals:
                    if qv.lower() in chunk_vals:
                        # Significant boost for exact constructs, columns, primers, mutation codes
                        score += 5.0
                    elif qv.lower() in chunk.content.lower():
                        score += 2.5

        return score


class HybridSearchEngine:
    """
    Hybrid laboratory search engine integrating Dense Vector Similarity and
    Sparse BM25 ranking via Reciprocal Rank Fusion (RRF), supporting multi-user
    provenance, temporal bounds, and entity filtering.

    Parameters
    ----------
    llm_client : Optional[LocalLLMClient]
        Local inference client for generating query and chunk embeddings.
    rrf_k : int
        RRF smoothing constant (default: 60).

    Agent
    -----
    @agent: eln-rag-agent
    """

    def __init__(
        self,
        llm_client: Optional[LocalLLMClient] = None,
        rrf_k: int = 60,
        client: Optional[LocalLLMClient] = None,
    ) -> None:
        self.llm_client = llm_client or client or LocalLLMClient()
        self.rrf_k = rrf_k
        self.chunks: List[DocumentChunk] = []
        self.bm25 = BM25Engine()
        self.extractor = LaboratoryEntityExtractor()

    def index_chunks(self, chunks: List[DocumentChunk]) -> None:
        """
        Index a collection of chunks, ensuring vector embeddings and BM25 index are built.

        Parameters
        ----------
        chunks : List[DocumentChunk]
            Document chunks to index.
        """
        self.chunks = list(chunks)
        # Compute embeddings for chunks missing them
        missing_embeddings = [c for c in self.chunks if c.embedding is None]
        if missing_embeddings:
            texts = [c.content for c in missing_embeddings]
            embs = self.llm_client.embed(texts)
            for c, emb in zip(missing_embeddings, embs):
                c.embedding = emb

        # Build BM25 index
        self.bm25.fit(self.chunks)

    def add_chunk(self, chunk: DocumentChunk) -> None:
        """
        Dynamically add a single chunk to the index.

        Parameters
        ----------
        chunk : DocumentChunk
            Chunk to add.
        """
        if chunk.embedding is None:
            chunk.embedding = self.llm_client.embed(chunk.content)[0]
        self.chunks.append(chunk)
        self.bm25.fit(self.chunks)

    def _matches_filters(
        self,
        chunk: DocumentChunk,
        author_ids: Optional[List[str]] = None,
        author_names: Optional[List[str]] = None,
        author_status: Optional[str] = None,
        project_tags: Optional[List[str]] = None,
        campaign_id: Optional[str] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        campaign_day_min: Optional[int] = None,
        campaign_day_max: Optional[int] = None,
        entity_types: Optional[List[str]] = None,
    ) -> bool:
        """
        Evaluate chunk against multi-user, provenance, and temporal constraints.

        Parameters
        ----------
        chunk : DocumentChunk
            Target chunk to inspect.

        Returns
        -------
        bool
            True if chunk passes all active filters, False otherwise.
        """
        meta = chunk.metadata

        # Filter by author_ids
        if author_ids:
            clean_ids = {a.strip().lower() for a in author_ids}
            if meta.author_id.strip().lower() not in clean_ids:
                return False

        # Filter by author_names (substring or exact)
        if author_names:
            author_lower = meta.author_name.lower()
            if not any(an.lower() in author_lower for an in author_names):
                return False

        # Filter by author_status ('current' vs 'alumni')
        if author_status:
            if meta.author_status.strip().lower() != author_status.strip().lower():
                return False

        # Filter by project_tags
        if project_tags:
            tags_set = {t.strip().lower() for t in project_tags}
            if meta.project_tag.strip().lower() not in tags_set:
                return False

        # Filter by campaign_id
        if campaign_id:
            if meta.campaign_id.strip().lower() != campaign_id.strip().lower():
                return False

        # Filter by date range (ISO string comparison)
        rec_date = meta.recorded_at[:10] if len(meta.recorded_at) >= 10 else meta.recorded_at
        if date_start and rec_date < date_start[:10]:
            return False
        if date_end and rec_date > date_end[:10]:
            return False

        # Filter by campaign day range
        try:
            day_num = int(re.sub(r"\D", "", str(meta.campaign_day)))
            if campaign_day_min is not None and day_num < campaign_day_min:
                return False
            if campaign_day_max is not None and day_num > campaign_day_max:
                return False
        except (ValueError, TypeError):
            pass

        # Filter by entity_types
        if entity_types:
            clean_types = {et.strip().lower() for et in entity_types}
            if meta.entity_type.strip().lower() not in clean_types:
                return False

        return True

    def search(
        self,
        query: str,
        top_k: int = 5,
        author_ids: Optional[List[str]] = None,
        author_names: Optional[List[str]] = None,
        author_status: Optional[str] = None,
        project_tags: Optional[List[str]] = None,
        campaign_id: Optional[str] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        campaign_day_min: Optional[int] = None,
        campaign_day_max: Optional[int] = None,
        entity_types: Optional[List[str]] = None,
        rrf_k: Optional[int] = None,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
    ) -> List[SearchResult]:
        """
        Execute hybrid search combining Dense Vector Similarity and Sparse BM25
        with Reciprocal Rank Fusion (RRF).

        Parameters
        ----------
        query : str
            Laboratory search query.
        top_k : int
            Number of top results to return (default: 5).
        author_ids : Optional[List[str]]
            Filter by researcher IDs.
        author_names : Optional[List[str]]
            Filter by researcher names.
        author_status : Optional[str]
            Filter by 'current' or 'alumni' researchers.
        project_tags : Optional[List[str]]
            Filter by project tags.
        campaign_id : Optional[str]
            Filter by campaign ID.
        date_start : Optional[str]
            Inclusive ISO start date.
        date_end : Optional[str]
            Inclusive ISO end date.
        campaign_day_min : Optional[int]
            Minimum campaign day index.
        campaign_day_max : Optional[int]
            Maximum campaign day index.
        entity_types : Optional[List[str]]
            Filter by lab entity types (e.g. ['fplc_chromatogram', 'sop']).
        rrf_k : Optional[int]
            Custom RRF k parameter, default self.rrf_k (60).
        dense_weight : float
            Weight multiplier for dense RRF contribution (default: 1.0).
        sparse_weight : float
            Weight multiplier for sparse RRF contribution (default: 1.0).

        Returns
        -------
        List[SearchResult]
            Top matching results sorted by descending RRF score.
        """
        if not self.chunks:
            return []

        effective_k = rrf_k or self.rrf_k

        # 1. Filter candidates
        candidate_indices: List[int] = []
        for idx, chunk in enumerate(self.chunks):
            if self._matches_filters(
                chunk,
                author_ids=author_ids,
                author_names=author_names,
                author_status=author_status,
                project_tags=project_tags,
                campaign_id=campaign_id,
                date_start=date_start,
                date_end=date_end,
                campaign_day_min=campaign_day_min,
                campaign_day_max=campaign_day_max,
                entity_types=entity_types,
            ):
                candidate_indices.append(idx)

        if not candidate_indices:
            return []

        # 2. Extract query features
        query_entities = self.extractor.extract_entities(query)
        query_tokens = self.extractor.compute_sparse_tokens(query, query_entities)
        query_vector = self.llm_client.embed(query)[0]

        # 3. Compute dense scores
        dense_scores: Dict[int, float] = {}
        for idx in candidate_indices:
            chunk = self.chunks[idx]
            c_vec = chunk.embedding or []
            dense_scores[idx] = cosine_similarity(query_vector, c_vec)

        # 4. Compute sparse scores (BM25 + entity boost)
        sparse_scores: Dict[int, float] = {}
        for idx in candidate_indices:
            chunk = self.chunks[idx]
            sparse_scores[idx] = self.bm25.score(
                query_tokens,
                chunk,
                idx,
                query_entities=query_entities,
            )

        # 5. Rank lists (1-based ranks)
        sorted_by_dense = sorted(candidate_indices, key=lambda i: dense_scores[i], reverse=True)
        sorted_by_sparse = sorted(candidate_indices, key=lambda i: sparse_scores[i], reverse=True)

        dense_ranks: Dict[int, int] = {idx: rank + 1 for rank, idx in enumerate(sorted_by_dense)}
        sparse_ranks: Dict[int, int] = {idx: rank + 1 for rank, idx in enumerate(sorted_by_sparse)}

        # 6. Reciprocal Rank Fusion (RRF)
        # score = sum(1.0 / (k + rank_dense), 1.0 / (k + rank_sparse))
        rrf_scores: Dict[int, float] = {}
        for idx in candidate_indices:
            r_dense = dense_ranks[idx]
            r_sparse = sparse_ranks[idx]
            rrf = (dense_weight / (effective_k + r_dense)) + (sparse_weight / (effective_k + r_sparse))
            rrf_scores[idx] = rrf

        # 7. Sort by final fused RRF score
        sorted_final = sorted(candidate_indices, key=lambda i: rrf_scores[i], reverse=True)

        results: List[SearchResult] = []
        for idx in sorted_final[:top_k]:
            results.append(
                SearchResult(
                    chunk=self.chunks[idx],
                    rrf_score=rrf_scores[idx],
                    dense_score=dense_scores[idx],
                    sparse_score=sparse_scores[idx],
                    dense_rank=dense_ranks[idx],
                    sparse_rank=sparse_ranks[idx],
                )
            )

        return results
