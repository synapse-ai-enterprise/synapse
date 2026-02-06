"""Story Generation Agent.

Prompt Library Integration: Now fetches prompts dynamically from the Prompt Library
"""

from typing import List, Optional

from src.domain.interfaces import ILLMProvider
from src.domain.schema import StoryGenerationResult
from src.infrastructure.prompt_library import get_prompt_library
from src.utils.logger import get_logger

logger = get_logger(__name__)


class StoryGenerationAgent:
    """Agent for generating user stories from selected techniques."""

    # Prompt ID for fetching from the library
    PROMPT_ID = "story_generation_agent_system"

    # Default fallback prompt (used if prompt library fetch fails)
    DEFAULT_SYSTEM_PROMPT = """You are a Story Generation Agent. Your role is to:
1. Apply the selected splitting techniques to the epic.
2. Generate INVEST-friendly user stories that are small and independent.
3. Use clear titles and descriptions in user story format.
4. Suggest story points using Fibonacci (1,2,3,5,8) when reasonable.
5. Provide initial acceptance criteria that are specific and testable.
6. Maintain traceability to the parent epic.

Quality constraints:
- Focus on user value; avoid implementation details unless required by the epic.
- Each story should represent one coherent outcome or workflow step.
- Avoid duplicates; keep scope tight and explicit.
- If information is missing, keep description concise and add an acceptance criterion that clarifies the needed behavior.

Evidence and citation rules:
- Every factual statement must include an inline citation in the form [source: epic] or [source: <explicit text from epic>].
- If no supporting evidence exists in the epic text, mark the statement with [source: missing].

Return a JSON object matching the requested schema exactly. Do not add extra fields."""

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
                    "story_generation_agent.prompt_loaded",
                    prompt_id=self.PROMPT_ID,
                    source="prompt_library",
                )
                return template
        except Exception as e:
            logger.warning(
                "story_generation_agent.prompt_load_failed",
                prompt_id=self.PROMPT_ID,
                error=str(e),
            )
        
        logger.debug(
            "story_generation_agent.prompt_loaded",
            prompt_id=self.PROMPT_ID,
            source="fallback",
        )
        return self.DEFAULT_SYSTEM_PROMPT

    async def generate_stories(
        self,
        epic_text: str,
        techniques: List[str],
        parent_epic: Optional[str] = None,
    ) -> StoryGenerationResult:
        """Generate stories using selected techniques."""
        techniques_text = ", ".join(techniques) if techniques else "None provided"
        
        # Fetch prompt from library with fallback
        system_prompt = await self._get_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""Generate user stories based on the epic and selected techniques.

Parent Epic: {parent_epic or "unknown"}
Selected Techniques: {techniques_text}

Epic Text:
{epic_text}

Guidelines:
- Produce 3-7 stories unless the epic is very small.
- Title format: "As a <user>, I want <goal>, so that <benefit>."
- Description: 1-3 sentences, user-focused, no solution details.
- technique_applied must be one of the selected techniques.
- story_points use Fibonacci scale when appropriate; omit if unclear.
- initial_acceptance_criteria: 2-5 items, binary pass/fail, prefer Given/When/Then phrasing when possible.
- Add inline citations to description and acceptance criteria statements.
- If evidence is missing in the epic, use [source: missing].

Return a JSON object with:
- stories: array of {{
  "story_id","title","description","technique_applied","parent_epic","story_points","initial_acceptance_criteria"
}}
""",
            },
        ]

        return await self.llm_provider.structured_completion(
            messages=messages,
            response_model=StoryGenerationResult,
            temperature=0.7,
        )
