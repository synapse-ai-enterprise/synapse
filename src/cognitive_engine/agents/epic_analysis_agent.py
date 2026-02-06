"""Epic Analysis Agent.

Prompt Library Integration: Now fetches prompts dynamically from the Prompt Library
"""

from typing import Optional

from src.domain.interfaces import ILLMProvider
from src.domain.schema import EpicAnalysis
from src.infrastructure.prompt_library import get_prompt_library
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EpicAnalysisAgent:
    """Agent for understanding and analyzing epic content."""

    # Prompt ID for fetching from the library
    PROMPT_ID = "epic_analysis_agent_system"

    # Default fallback prompt (used if prompt library fetch fails)
    DEFAULT_SYSTEM_PROMPT = """You are an Epic Analysis Agent. Your role is to:
1. Parse the epic description and extract key entities (user, capability, benefit, constraints).
2. Classify the epic type (feature, technical, architectural).
3. Assess complexity (0.0-1.0).
4. Flag ambiguities and missing information.
5. Identify the most likely domain.

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
                    "epic_analysis_agent.prompt_loaded",
                    prompt_id=self.PROMPT_ID,
                    source="prompt_library",
                )
                return template
        except Exception as e:
            logger.warning(
                "epic_analysis_agent.prompt_load_failed",
                prompt_id=self.PROMPT_ID,
                error=str(e),
            )
        
        logger.debug(
            "epic_analysis_agent.prompt_loaded",
            prompt_id=self.PROMPT_ID,
            source="fallback",
        )
        return self.DEFAULT_SYSTEM_PROMPT

    async def analyze_epic(
        self,
        epic_text: str,
        epic_id: Optional[str] = None,
    ) -> EpicAnalysis:
        """Analyze epic text and return structured analysis."""
        # Fetch prompt from library with fallback
        system_prompt = await self._get_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""Analyze this epic:

Epic ID: {epic_id or "unknown"}
Epic Text:
{epic_text}

Return a JSON object with:
- epic_id
- entities: {{ user_persona, capability, benefit, constraints }}
- complexity_score (0.0-1.0)
- ambiguities (list)
- domain
- epic_type
""",
            },
        ]

        return await self.llm_provider.structured_completion(
            messages=messages,
            response_model=EpicAnalysis,
            temperature=0.4,
        )
