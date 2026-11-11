"""
Module: biolabcalc.eln.rag
Component: Hybrid-RAG, Local LLM & Knowledge Retrieval Engine
Agent: @agent: eln-rag-agent
Architectural Role: Core package initialization for State-of-the-Art Electronic Lab
Notebook (ELN) and Multi-Modal LIMS Knowledge Retrieval Engine. Exports local inference
clients, semantic chunkers, hybrid search engines, and citation synthesizers.
"""

from .chunker import (
    DocumentChunk,
    DocumentChunker,
    LaboratoryEntityExtractor,
    ProvenanceMetadata,
)
from .hybrid_search import (
    BM25Engine,
    HybridSearchEngine,
    SearchResult,
)
from .local_llm import (
    LocalLLMClient,
    OfflineEmbeddingGenerator,
    OfflineHeuristicGenerator,
    cosine_similarity,
)
from .synthesizer import (
    Citation,
    CitationSynthesizer,
    SynthesisResult,
)

__all__ = [
    # Inference & Fallback
    "LocalLLMClient",
    "OfflineEmbeddingGenerator",
    "OfflineHeuristicGenerator",
    "cosine_similarity",
    # Chunking & Entities
    "DocumentChunk",
    "DocumentChunker",
    "LaboratoryEntityExtractor",
    "ProvenanceMetadata",
    # Search Engine
    "HybridSearchEngine",
    "SearchResult",
    "BM25Engine",
    # Synthesis & Citations
    "CitationSynthesizer",
    "SynthesisResult",
    "Citation",
]

__version__ = "1.0.0"
