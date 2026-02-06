"""Story Writer Agent.

Prompt Library Integration: Now fetches prompts dynamically from the Prompt Library
"""

from typing import List

from src.domain.interfaces import ILLMProvider
from src.domain.schema import (
    AcceptanceCriteriaItem,
    PopulatedStory,
    PopulatedStoryDraft,
    RetrievedContext,
    TemplateSchema,
)
from src.infrastructure.prompt_library import get_prompt_library
from src.utils.logger import get_logger

logger = get_logger(__name__)


class StoryWriterAgent:
    """Agent for populating story templates with retrieved knowledge."""

    # Prompt ID for fetching from the library
    PROMPT_ID = "story_writer_agent_system"

    # Default fallback prompt (used if prompt library fetch fails)
    DEFAULT_SYSTEM_PROMPT = """You are a Story Writer Agent. You MUST respond with a valid JSON object.

Your role is to populate a story template with all required fields.

CRITICAL: Your response must be a JSON object starting with { and ending with }.
Do NOT return a list/array. Do NOT return just one field. Return ALL fields together.

You must return a JSON object with this EXACT structure:
{
  "title": "Story title here",
  "description": "Full story description here",
  "acceptance_criteria": [
    {"type": "gherkin", "scenario": "...", "given": "...", "when": "...", "then": "..."}
  ],
  "dependencies": ["dependency 1", "dependency 2"],
  "nfrs": ["non-functional requirement 1"],
  "out_of_scope": ["item not in scope"],
  "assumptions": ["assumption 1"],
  "open_questions": ["question 1"]
}

Rules:
- Include ALL fields in your response, even if empty (use empty arrays [])
- Use Gherkin format for acceptance_criteria
- Cite sources with [source: <title>] in the description"""

    def __init__(self, llm_provider: ILLMProvider):
        self.llm_provider = llm_provider
        self._prompt_library = get_prompt_library()

    async def _get_system_prompt(self) -> str:
        """Fetch system prompt from the Prompt Library with fallback.
        
        Returns:
            The system prompt template string.
        """
        try:
            template = await self._prompt_library.get_prompt_template(self.PROMPT_ID)
            if template:
                logger.debug(
                    "story_writer_agent.prompt_loaded",
                    prompt_id=self.PROMPT_ID,
                    source="prompt_library",
                )
                return template
        except Exception as e:
            logger.warning(
                "story_writer_agent.prompt_load_failed",
                prompt_id=self.PROMPT_ID,
                error=str(e),
            )
        
        logger.debug(
            "story_writer_agent.prompt_loaded",
            prompt_id=self.PROMPT_ID,
            source="fallback",
        )
        return self.DEFAULT_SYSTEM_PROMPT

    async def write(
        self,
        story_text: str,
        template_schema: TemplateSchema,
        context: RetrievedContext,
    ) -> PopulatedStory:
        # Fetch prompt from library with fallback
        system_prompt = await self._get_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""Write a detailed user story based on the following input.

INPUT STORY:
{story_text}

CONTEXT FROM KNOWLEDGE BASE:
{context.model_dump()}

IMPORTANT: Return a COMPLETE JSON object with ALL these fields:
{{
  "title": "A clear title for the story",
  "description": "Detailed description of what the user wants to achieve",
  "acceptance_criteria": [
    {{"type": "gherkin", "scenario": "Scenario name", "given": "precondition", "when": "action", "then": "expected result"}}
  ],
  "dependencies": ["list any dependencies or empty array []"],
  "nfrs": ["list non-functional requirements or empty array []"],
  "out_of_scope": ["what is NOT included or empty array []"],
  "assumptions": ["any assumptions made or empty array []"],
  "open_questions": ["questions that need answers or empty array []"]
}}

Remember: Return ONE JSON object with ALL fields. Start with {{ and end with }}.
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
                items.append(self._coerce_gherkin(entry))
            return items
        return [self._coerce_gherkin(raw)]

    def _coerce_gherkin(self, entry) -> AcceptanceCriteriaItem:
        """Coerce any acceptance criteria entry into Gherkin format."""
        if isinstance(entry, AcceptanceCriteriaItem):
            if entry.type == "gherkin":
                return entry
            return AcceptanceCriteriaItem(
                type="gherkin",
                scenario=entry.scenario or entry.text,
                given=entry.given,
                when=entry.when,
                then=entry.then,
            )
        if isinstance(entry, dict):
            data = dict(entry)
            if data.get("type") != "gherkin":
                data["type"] = "gherkin"
                if not data.get("scenario") and data.get("text"):
                    data["scenario"] = data.get("text")
                data.pop("text", None)
            return AcceptanceCriteriaItem(**data)
        return self._gherkin_from_text(str(entry))

    def _gherkin_from_text(self, text: str) -> AcceptanceCriteriaItem:
        """Build a Gherkin item from a plain text entry."""
        scenario = None
        given = None
        when = None
        then = None
        for line in text.splitlines():
            stripped = line.strip()
            lower = stripped.lower()
            if lower.startswith("scenario:"):
                scenario = stripped.split(":", 1)[1].strip() or scenario
            elif lower.startswith("given "):
                given = stripped[6:].strip()
            elif lower.startswith("when "):
                when = stripped[5:].strip()
            elif lower.startswith("then "):
                then = stripped[5:].strip()
        if not scenario:
            scenario = text.strip() or "Scenario"
        return AcceptanceCriteriaItem(
            type="gherkin",
            scenario=scenario,
            given=given,
            when=when,
            then=then,
        )

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
