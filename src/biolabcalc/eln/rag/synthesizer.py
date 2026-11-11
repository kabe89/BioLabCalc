"""
Module: biolabcalc.eln.rag.synthesizer
Component: Contextual Citation Synthesizer for Laboratory ELN & LIMS Pipeline
Agent: @agent: eln-rag-agent
Architectural Role: Executes hybrid retrieval for laboratory queries, formats
provenance context blocks, invokes the Local LLM client (with heuristic fallback),
and appends structured Markdown citations referencing exact authors, dates,
campaigns, instruments, and source notebook files.
"""

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List, Optional, Union

from .chunker import DocumentChunk
from .hybrid_search import HybridSearchEngine, SearchResult
from .local_llm import LocalLLMClient


@dataclass
class Citation:
    """
    Structured laboratory reference citation tracing a factual finding to its
    source notebook, researcher, date, campaign day, and instrument run.

    Parameters
    ----------
    ref_id : int
        1-based reference index (e.g. 1 -> [Ref 1]).
    author_name : str
        Name of the recording researcher.
    author_id : str
        Researcher identifier.
    recorded_at : str
        ISO 8601 recording timestamp.
    campaign_id : str
        Campaign or project identifier.
    campaign_day : Union[int, str]
        Campaign day index.
    entity_type : str
        Type of laboratory record.
    instrument_record : Optional[str]
        Instrument identifier.
    source_file : Optional[str]
        Notebook or export file path.
    chunk_id : str
        Unique ID of the document chunk.
    summary_excerpt : str
        Brief excerpt of the referenced content.

    Agent
    -----
    @agent: eln-rag-agent
    """

    ref_id: int
    author_name: str
    author_id: str
    recorded_at: str
    campaign_id: str
    campaign_day: Union[int, str]
    entity_type: str
    instrument_record: Optional[str]
    source_file: Optional[str]
    chunk_id: str
    summary_excerpt: str = ""

    def to_markdown(self) -> str:
        """
        Format citation into standardized Markdown bibliography item.

        Returns
        -------
        str
            Markdown formatted citation string.
        """
        inst_part = f" | Instrument: *{self.instrument_record}*" if self.instrument_record else ""
        src_part = f" | Source: `{self.source_file}`" if self.source_file else ""
        date_str = self.recorded_at[:10] if len(self.recorded_at) >= 10 else self.recorded_at

        return (
            f"- **[Ref {self.ref_id}]** **{self.author_name}** (`{self.author_id}`) — "
            f"*{date_str}* | Campaign: {self.campaign_id} (Day {self.campaign_day}) | "
            f"Entity: `{self.entity_type}`{inst_part}{src_part}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert citation to dictionary."""
        return {
            "ref_id": self.ref_id,
            "author_name": self.author_name,
            "author_id": self.author_id,
            "recorded_at": self.recorded_at,
            "campaign_id": self.campaign_id,
            "campaign_day": self.campaign_day,
            "entity_type": self.entity_type,
            "instrument_record": self.instrument_record,
            "source_file": self.source_file,
            "chunk_id": self.chunk_id,
            "summary_excerpt": self.summary_excerpt,
        }


@dataclass
class SynthesisResult:
    """
    Comprehensive laboratory synthesis response containing narrative answer,
    provenance citations, source chunks, and formatted Markdown output.

    Parameters
    ----------
    query : str
        Original laboratory query.
    answer : str
        Synthesized authoritative narrative answer with inline citations.
    citations : List[Citation]
        Structured citation records.
    citations_markdown : str
        Formatted Markdown reference list.
    full_response : str
        Complete Markdown string combining answer and citation bibliography.
    source_chunks : List[DocumentChunk]
        Document chunks utilized in context.
    search_results : List[SearchResult]
        Raw hybrid search ranking results.

    Agent
    -----
    @agent: eln-rag-agent
    """

    query: str
    answer: str
    citations: List[Citation]
    citations_markdown: str
    full_response: str
    source_chunks: List[DocumentChunk] = field(default_factory=list)
    search_results: List[SearchResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert SynthesisResult to serializable dictionary."""
        return {
            "query": self.query,
            "answer": self.answer,
            "citations": [c.to_dict() for c in self.citations],
            "citations_markdown": self.citations_markdown,
            "full_response": self.full_response,
            "source_chunks_count": len(self.source_chunks),
        }


class CitationSynthesizer:
    """
    Contextual synthesis engine that answers laboratory questions using hybrid
    retrieval, builds structured context with provenance markers, invokes the
    Local LLM client, and formats exact source citations.

    Parameters
    ----------
    llm_client : Optional[LocalLLMClient]
        Local LLM inference client.
    search_engine : Optional[HybridSearchEngine]
        Search engine initialized with indexed notebook chunks.

    Agent
    -----
    @agent: eln-rag-agent
    """

    def __init__(
        self,
        llm_client: Optional[LocalLLMClient] = None,
        search_engine: Optional[HybridSearchEngine] = None,
    ) -> None:
        self.llm_client = llm_client or LocalLLMClient()
        self.search_engine = search_engine or HybridSearchEngine(llm_client=self.llm_client)

    def _build_context_block(self, results: List[SearchResult]) -> tuple[str, List[Citation]]:
        """
        Build formatted laboratory context blocks and citation objects from search results.

        Parameters
        ----------
        results : List[SearchResult]
            Hybrid search results.

        Returns
        -------
        tuple[str, List[Citation]]
            (formatted_context_string, list_of_citations)
        """
        context_lines: List[str] = []
        citations: List[Citation] = []

        for idx, res in enumerate(results, 1):
            chunk = res.chunk
            meta = chunk.metadata
            excerpt = chunk.content[:150].replace("\n", " ") + ("..." if len(chunk.content) > 150 else "")

            citation = Citation(
                ref_id=idx,
                author_name=meta.author_name,
                author_id=meta.author_id,
                recorded_at=meta.recorded_at,
                campaign_id=meta.campaign_id,
                campaign_day=meta.campaign_day,
                entity_type=meta.entity_type,
                instrument_record=meta.instrument_record,
                source_file=meta.source_file,
                chunk_id=chunk.chunk_id,
                summary_excerpt=excerpt,
            )
            citations.append(citation)

            block = (
                f"[Ref {idx}]\n"
                f"Author: {meta.author_name} ({meta.author_id})\n"
                f"Date: {meta.recorded_at}\n"
                f"Campaign: {meta.campaign_id} (Day {meta.campaign_day})\n"
                f"Entity Type: {meta.entity_type}\n"
                f"Instrument: {meta.instrument_record or 'Not specified'}\n"
                f"Source File: {meta.source_file or 'ELN Core'}\n"
                f"Content: {chunk.content}\n"
            )
            context_lines.append(block)

        return "\n\n".join(context_lines), citations

    def synthesize(
        self,
        query: str,
        top_k: int = 5,
        search_filters: Optional[Dict[str, Any]] = None,
        system_instruction: Optional[str] = None,
    ) -> SynthesisResult:
        """
        Retrieve relevant laboratory chunks and synthesize an authoritative answer
        with exact provenance citations.

        Parameters
        ----------
        query : str
            Laboratory question (e.g. 'What elution volume, buffer, and yield did
            past members achieve for T7 RNA Polymerase?').
        top_k : int
            Number of chunks to retrieve and include in synthesis context.
        search_filters : Optional[Dict[str, Any]]
            Optional filtering dict containing author_ids, author_status,
            project_tags, date_start, date_end, campaign_day_min, entity_types, etc.
        system_instruction : Optional[str]
            Custom system prompt override.

        Returns
        -------
        SynthesisResult
            Structured result containing answer, citations, and full markdown.
        """
        filters = search_filters or {}
        search_results = self.search_engine.search(query=query, top_k=top_k, **filters)

        if not search_results:
            empty_answer = (
                f"No laboratory notebook records found matching the query: '{query}' "
                f"under the specified filters."
            )
            return SynthesisResult(
                query=query,
                answer=empty_answer,
                citations=[],
                citations_markdown="*No citations available.*",
                full_response=empty_answer,
                source_chunks=[],
                search_results=[],
            )

        context_str, citations = self._build_context_block(search_results)
        source_chunks = [r.chunk for r in search_results]

        default_system = (
            "You are the State-of-the-Art Laboratory Knowledge Retrieval Engine (ELN & LIMS Pipeline).\n"
            "Synthesize an authoritative, precise biochemical and laboratory answer based strictly "
            "on the provided notebook records.\n"
            "Extract and state exact parameters: construct IDs, column names, elution volumes (Ve), "
            "yields, buffer components, temperatures, and mutation codes.\n"
            "Cite source findings using bracketed references like [Ref 1], [Ref 2]."
        )

        prompt = (
            f"Laboratory Query:\n{query}\n\n"
            f"Relevant Experimental Notebook Records:\n"
            f"----------------------------------------\n"
            f"{context_str}\n"
            f"----------------------------------------\n\n"
            f"Provide an authoritative scientific synthesis answering the query, "
            f"explicitly referencing the record numbers [Ref X] for every metric stated."
        )

        raw_answer = self.llm_client.generate(
            prompt=prompt,
            system=system_instruction or default_system,
        )

        # Build Markdown citations section
        cite_lines = ["\n### References & Provenance Traceability\n"]
        for cit in citations:
            cite_lines.append(cit.to_markdown())
        citations_md = "\n".join(cite_lines)

        full_output = f"{raw_answer.strip()}\n\n{citations_md}"

        return SynthesisResult(
            query=query,
            answer=raw_answer.strip(),
            citations=citations,
            citations_markdown=citations_md,
            full_response=full_output,
            source_chunks=source_chunks,
            search_results=search_results,
        )

    # Alias for API compatibility
    answer_query = synthesize
