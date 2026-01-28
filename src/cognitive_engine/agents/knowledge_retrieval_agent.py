"""Knowledge Retrieval Agent."""

from typing import List

from src.domain.interfaces import IKnowledgeBase, ILLMProvider
from src.domain.schema import IntentExtraction, RetrievedContext, UASKnowledgeUnit


class KnowledgeRetrievalAgent:
    """Agent that gathers relevant context from knowledge sources."""

    INTENT_PROMPT = """You are a Knowledge Retrieval Agent. Extract intent and keywords for search.
Return a JSON object with: feature, integration, domain, user_type, keywords."""

    CONTEXT_PROMPT = """You are a Knowledge Retrieval Agent. Convert retrieved documents into a structured context:
- decisions
- constraints
- relevant_docs
- code_context
Return a JSON object matching the requested schema exactly.
Do not invent sources; only use provided documents."""

    def __init__(self, llm_provider: ILLMProvider, knowledge_base: IKnowledgeBase):
        self.llm_provider = llm_provider
        self.knowledge_base = knowledge_base

    async def retrieve(self, story_text: str) -> RetrievedContext:
        """Retrieve context using intent extraction and vector search."""
        intent = await self._extract_intent(story_text)
        query = self._build_query(story_text, intent.keywords)

        github_context = await self.knowledge_base.search(query, source="github", limit=8)
        notion_context = await self.knowledge_base.search(query, source="notion", limit=8)

        return await self._structure_context(github_context + notion_context, intent)

    async def _extract_intent(self, story_text: str) -> IntentExtraction:
        messages = [
            {"role": "system", "content": self.INTENT_PROMPT},
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

        messages = [
            {"role": "system", "content": self.CONTEXT_PROMPT},
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

        return await self.llm_provider.structured_completion(
            messages=messages,
            response_model=RetrievedContext,
            temperature=0.3,
        )
