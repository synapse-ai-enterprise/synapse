"""Splitting Strategy Agent.

Prompt Library Integration: Now fetches prompts dynamically from the Prompt Library
"""

from src.domain.interfaces import ILLMProvider
from src.domain.schema import EpicAnalysis, SplittingStrategyResult
from src.infrastructure.prompt_library import get_prompt_library
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SplittingStrategyAgent:
    """Agent that recommends epic splitting techniques."""

    # Prompt ID for fetching from the library
    PROMPT_ID = "splitting_strategy_agent_system"

    # Default fallback prompt (used if prompt library fetch fails)
    DEFAULT_SYSTEM_PROMPT = """You are a Splitting Strategy Agent. Your role is to:
1. Analyze epic characteristics and recommend splitting techniques.
2. Apply SPIDR framework (Spike, Path, Interface, Data, Rules).
3. Apply Humanizing Work patterns (Simple/Complex, Defer Performance, Break Out Spike, Workflow Steps, Operations, Breaking Conjunctions).
4. Rank techniques by relevance and explain why.

Return a JSON object matching the requested schema exactly."""

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
                    "splitting_strategy_agent.prompt_loaded",
                    prompt_id=self.PROMPT_ID,
                    source="prompt_library",
                )
                return template
        except Exception as e:
            logger.warning(
                "splitting_strategy_agent.prompt_load_failed",
                prompt_id=self.PROMPT_ID,
                error=str(e),
            )
        
        logger.debug(
            "splitting_strategy_agent.prompt_loaded",
            prompt_id=self.PROMPT_ID,
            source="fallback",
        )
        return self.DEFAULT_SYSTEM_PROMPT

    async def recommend(self, epic_text: str, analysis: EpicAnalysis) -> SplittingStrategyResult:
        """Recommend splitting techniques for an epic."""
        # Fetch prompt from library with fallback
        system_prompt = await self._get_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""Recommend splitting techniques for this epic.

Epic Text:
{epic_text}

Analysis:
{analysis.model_dump()}

Return a JSON object with:
- recommendations: array of {{"technique","confidence","rationale","example_splits"}}
""",
            },
        ]

        return await self.llm_provider.structured_completion(
            messages=messages,
            response_model=SplittingStrategyResult,
            temperature=0.6,
        )
