"""Knowledge Retrieval Agent.

Prompt Library Integration: Now fetches prompts dynamically from the Prompt Library
"""

import asyncio
from typing import List, Optional

from src.domain.interfaces import IKnowledgeBase, ILLMProvider
from src.domain.schema import IntentExtraction, RetrievedContext, RetrievedDoc, UASKnowledgeUnit
from src.infrastructure.prompt_library import get_prompt_library
from src.utils.logger import get_logger

logger = get_logger(__name__)


class KnowledgeRetrievalAgent:
    """Agent that gathers relevant context from knowledge sources."""

    # Minimum relevance threshold - filter out low-quality results
    MIN_RELEVANCE_THRESHOLD = 0.25

    # Maximum results per source before global ranking
    MAX_RESULTS_PER_SOURCE = 10

    # Maximum total results after global ranking
    MAX_TOTAL_RESULTS = 15

    # Prompt IDs for fetching from the library
    INTENT_PROMPT_ID = "knowledge_retrieval_agent_intent"
    CONTEXT_PROMPT_ID = "knowledge_retrieval_agent_context"

    # Default fallback prompts (used if prompt library fetch fails)
    DEFAULT_INTENT_PROMPT = """You are a Knowledge Retrieval Agent. Extract intent and keywords for search.

IMPORTANT: Return a JSON object (NOT a list) with this EXACT structure:
{
  "feature": "main feature or null",
  "integration": "integration system or null",
  "domain": "domain area or null",
  "user_type": "type of user or null",
  "keywords": ["keyword1", "keyword2", "keyword3"]
}

Start your response with { and end with }. Return ALL fields."""

    DEFAULT_CONTEXT_PROMPT = """You are a Knowledge Retrieval Agent. Convert retrieved documents into structured context.

IMPORTANT: Return a JSON object (NOT a list) with this EXACT structure:
{
  "decisions": [{"id": null, "text": "decision text", "source": "source name", "confidence": 0.8}],
  "constraints": [{"id": null, "text": "constraint text", "source": "source name"}],
  "relevant_docs": [{"title": "doc title", "excerpt": "relevant text", "source": "source", "url": "url if available", "relevance": 0.8}],
  "code_context": []
}

Use empty arrays [] if no items exist. Start with { and end with }.
Do not invent sources; only use provided documents."""

    def __init__(self, llm_provider: ILLMProvider, knowledge_base: IKnowledgeBase):
        self.llm_provider = llm_provider
        self.knowledge_base = knowledge_base
        self._prompt_library = get_prompt_library()

    async def _get_intent_prompt(self) -> str:
        """Fetch intent extraction prompt from the Prompt Library with fallback.
        
        Returns:
            The intent prompt template string.
        """
        try:
            template = await self._prompt_library.get_prompt_template(self.INTENT_PROMPT_ID)
            if template:
                logger.debug(
                    "knowledge_retrieval_agent.intent_prompt_loaded",
                    prompt_id=self.INTENT_PROMPT_ID,
                    source="prompt_library",
                )
                return template
        except Exception as e:
            logger.warning(
                "knowledge_retrieval_agent.intent_prompt_load_failed",
                prompt_id=self.INTENT_PROMPT_ID,
                error=str(e),
            )
        
        logger.debug(
            "knowledge_retrieval_agent.intent_prompt_loaded",
            prompt_id=self.INTENT_PROMPT_ID,
            source="fallback",
        )
        return self.DEFAULT_INTENT_PROMPT

    async def _get_context_prompt(self) -> str:
        """Fetch context structuring prompt from the Prompt Library with fallback.
        
        Returns:
            The context prompt template string.
        """
        try:
            template = await self._prompt_library.get_prompt_template(self.CONTEXT_PROMPT_ID)
            if template:
                logger.debug(
                    "knowledge_retrieval_agent.context_prompt_loaded",
                    prompt_id=self.CONTEXT_PROMPT_ID,
                    source="prompt_library",
                )
                return template
        except Exception as e:
            logger.warning(
                "knowledge_retrieval_agent.context_prompt_load_failed",
                prompt_id=self.CONTEXT_PROMPT_ID,
                error=str(e),
            )
        
        logger.debug(
            "knowledge_retrieval_agent.context_prompt_loaded",
            prompt_id=self.CONTEXT_PROMPT_ID,
            source="fallback",
        )
        return self.DEFAULT_CONTEXT_PROMPT

    async def retrieve(
        self,
        story_text: str,
        sources: Optional[List[str]] = None,
        direct_sources: Optional[List[str]] = None,
    ) -> RetrievedContext:
        """Retrieve context using intent extraction and parallel vector search.
        
        Improvements:
        - Parallel retrieval across all sources using asyncio.gather
        - Similarity scores used for global ranking
        - Minimum relevance threshold to filter low-quality results
        """
        intent = await self._extract_intent(story_text)
        query = self._build_query(story_text, intent.keywords)

        requested_sources = [s.lower() for s in (sources or [])]
        if not requested_sources:
            requested_sources = ["github", "notion", "jira", "confluence"]

        # Parallel retrieval across all sources
        logger.info(
            "knowledge_retrieval_start",
            sources=requested_sources,
            query_length=len(query),
        )
        
        search_tasks = [
            self.knowledge_base.search(
                query, source=source, limit=self.MAX_RESULTS_PER_SOURCE
            )
            for source in requested_sources
        ]
        
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Flatten results and handle any errors
        units: List[UASKnowledgeUnit] = []
        for source, result in zip(requested_sources, results):
            if isinstance(result, Exception):
                logger.warning(
                    "knowledge_retrieval_source_error",
                    source=source,
                    error=str(result),
                )
                continue
            units.extend(result)

        logger.info(
            "knowledge_retrieval_raw_results",
            total_units=len(units),
            sources_searched=len(requested_sources),
        )

        # Apply minimum relevance threshold
        units = self._filter_by_relevance(units)
        
        # Global ranking by score across all sources
        units = self._rank_globally(units)

        logger.info(
            "knowledge_retrieval_filtered_results",
            filtered_units=len(units),
            threshold=self.MIN_RELEVANCE_THRESHOLD,
        )

        context = await self._structure_context(units, intent)
        if direct_sources:
            context.relevant_docs.extend(
                [
                    RetrievedDoc(
                        title=direct_source,
                        excerpt="Direct source reference provided by requester.",
                        source="direct",
                        url=direct_source,
                        relevance=0.5,
                    )
                    for direct_source in direct_sources
                ]
            )
        return context

    def _filter_by_relevance(self, units: List[UASKnowledgeUnit]) -> List[UASKnowledgeUnit]:
        """Filter out units below the minimum relevance threshold."""
        filtered = [
            unit for unit in units
            if (unit.score or 0.5) >= self.MIN_RELEVANCE_THRESHOLD
        ]
        return filtered

    def _rank_globally(self, units: List[UASKnowledgeUnit]) -> List[UASKnowledgeUnit]:
        """Rank all units globally by score and return top results."""
        # Sort by score descending (higher is better)
        sorted_units = sorted(
            units,
            key=lambda u: u.score or 0.5,
            reverse=True,
        )
        # Return top N results
        return sorted_units[:self.MAX_TOTAL_RESULTS]

    async def _extract_intent(self, story_text: str) -> IntentExtraction:
        # Fetch prompt from library with fallback
        intent_prompt = await self._get_intent_prompt()
        
        messages = [
            {"role": "system", "content": intent_prompt},
            {
                "role": "user",
                "content": f"""Extract intent and keywords from this story:

{story_text}
""",
            },
        ]
        return await self.llm_provider.structured_completion(
            messages=messages,
            response_model=IntentExtraction,
            temperature=0.2,
        )

    def _build_query(self, story_text: str, keywords: List[str]) -> str:
        keyword_text = " ".join(keywords)
        return f"{story_text}\n\nKeywords: {keyword_text}".strip()

    async def _structure_context(
        self,
        units: List[UASKnowledgeUnit],
        intent: IntentExtraction,
    ) -> RetrievedContext:
        if not units:
            return RetrievedContext()

        docs_text = "\n\n".join(
            f"[{u.source}] {u.location}\n{u.summary}\n{u.content[:800]}"
            for u in units
        )

        # Fetch prompt from library with fallback
        context_prompt = await self._get_context_prompt()

        messages = [
            {"role": "system", "content": context_prompt},
            {
                "role": "user",
                "content": f"""Use the retrieved documents to build structured context.

Intent:
{intent.model_dump()}

Documents:
{docs_text}
""",
            },
        ]

        context = await self.llm_provider.structured_completion(
            messages=messages,
            response_model=RetrievedContext,
            temperature=0.3,
        )
        return self._hydrate_context(context, units)

    def _hydrate_context(
        self,
        context: RetrievedContext,
        units: List[UASKnowledgeUnit],
    ) -> RetrievedContext:
        if not context:
            return RetrievedContext()

        docs = context.relevant_docs or []
        for index, doc in enumerate(docs):
            unit = units[index] if index < len(units) else None
            source_value = (doc.source or "").strip().lower()
            if not source_value or source_value in {"unknown", "n/a"}:
                if unit:
                    doc.source = unit.source
            title_value = (doc.title or "").strip().lower()
            if not title_value or title_value in {"unknown", "untitled"}:
                if unit:
                    doc.title = unit.location or unit.id
            if not doc.url and unit and unit.location.startswith("http"):
                doc.url = unit.location
            if doc.relevance is None:
                doc.relevance = 0.5

        for decision in context.decisions or []:
            source_value = (decision.source or "").strip().lower()
            if not source_value or source_value in {"unknown", "n/a"}:
                decision.source = "derived"

        for constraint in context.constraints or []:
            source_value = (constraint.source or "").strip().lower()
            if not source_value or source_value in {"unknown", "n/a"}:
                constraint.source = "derived"        return context
