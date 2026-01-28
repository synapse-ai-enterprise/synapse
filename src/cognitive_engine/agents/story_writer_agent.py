"""Story Writer Agent."""

from typing import List

from src.domain.interfaces import ILLMProvider
from src.domain.schema import (
    AcceptanceCriteriaItem,
    PopulatedStory,
    PopulatedStoryDraft,
    RetrievedContext,
    TemplateSchema,
)


class StoryWriterAgent:
    """Agent for populating story templates with retrieved knowledge."""

    SYSTEM_PROMPT = """You are a Story Writer Agent. Your role is to:
1. Populate the provided template schema.
2. Use retrieved context (decisions, constraints, docs, code).
3. Write clear descriptions and actionable acceptance criteria.
4. Identify dependencies, NFRs, scope, assumptions, and open questions.
5. Do not invent facts; cite context from sources when possible.

Return a JSON object matching the requested schema exactly."""

    def __init__(self, llm_provider: ILLMProvider):
        self.llm_provider = llm_provider

    async def write(
        self,
        story_text: str,
        template_schema: TemplateSchema,
        context: RetrievedContext,
    ) -> PopulatedStory:
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Populate the story template using the retrieved context.

Story:
{story_text}

Template Schema:
{template_schema.model_dump()}

Retrieved Context:
{context.model_dump()}

Return a JSON object with:
title, description, acceptance_criteria (gherkin or free_form),
dependencies, nfrs, out_of_scope, assumptions, open_questions.
""",
            },
        ]

        draft = await self.llm_provider.structured_completion(
            messages=messages,
            response_model=PopulatedStoryDraft,
            temperature=0.5,
        )

        return self._normalize_draft(draft)

    def _normalize_draft(self, draft: PopulatedStoryDraft) -> PopulatedStory:
        """Normalize loose draft into strict PopulatedStory."""
        acceptance = self._normalize_acceptance_criteria(draft.acceptance_criteria)
        return PopulatedStory(
            title=draft.title,
            description=draft.description,
            acceptance_criteria=acceptance,
            dependencies=self._normalize_list(draft.dependencies),
            nfrs=self._normalize_list(draft.nfrs),
            out_of_scope=self._normalize_list(draft.out_of_scope),
            assumptions=self._normalize_list(draft.assumptions),
            open_questions=self._normalize_list(draft.open_questions),
        )

    def _normalize_acceptance_criteria(
        self, raw
    ) -> List[AcceptanceCriteriaItem]:
        if raw is None:
            return []
        if isinstance(raw, list):
            items = []
            for entry in raw:
                if isinstance(entry, AcceptanceCriteriaItem):
                    items.append(entry)
                elif isinstance(entry, dict):
                    items.append(AcceptanceCriteriaItem(**entry))
                else:
                    items.append(AcceptanceCriteriaItem(type="free_form", text=str(entry)))
            return items
        return [AcceptanceCriteriaItem(type="free_form", text=str(raw))]

    def _normalize_list(self, value) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            parts = [part.strip() for part in value.splitlines() if part.strip()]
            if len(parts) <= 1 and ";" in value:
                parts = [part.strip() for part in value.split(";") if part.strip()]
            return parts
        return [str(value).strip()]
