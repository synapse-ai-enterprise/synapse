"""Template Parser Agent.

Prompt Library Integration: Now fetches prompts dynamically from the Prompt Library
"""

from src.domain.interfaces import ILLMProvider
from src.domain.schema import TemplateSchema
from src.infrastructure.prompt_library import get_prompt_library
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TemplateParserAgent:
    """Agent for parsing and validating story templates."""

    # Prompt ID for fetching from the library
    PROMPT_ID = "template_parser_agent_system"

    # Default fallback prompt (used if prompt library fetch fails)
    DEFAULT_SYSTEM_PROMPT = """You are a Template Parser Agent that parses story templates.

IMPORTANT: Return a JSON object (NOT a list) with this EXACT structure:
{
  "required_fields": ["title", "description", "acceptance_criteria"],
  "optional_fields": ["dependencies", "nfrs", "out_of_scope"],
  "format_style": "gherkin",
  "sections": [{"name": "acceptance_criteria", "format": "gherkin", "min_items": 3}]
}

Start your response with { and end with }. Return ALL fields."""

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
                    "template_parser_agent.prompt_loaded",
                    prompt_id=self.PROMPT_ID,
                    source="prompt_library",
                )
                return template
        except Exception as e:
            logger.warning(
                "template_parser_agent.prompt_load_failed",
                prompt_id=self.PROMPT_ID,
                error=str(e),
            )
        
        logger.debug(
            "template_parser_agent.prompt_loaded",
            prompt_id=self.PROMPT_ID,
            source="fallback",
        )
        return self.DEFAULT_SYSTEM_PROMPT

    async def parse(self, template_text: str) -> TemplateSchema:
        """Parse template text into a structured schema."""
        if not template_text or not template_text.strip():
            return TemplateSchema(
                required_fields=["title", "description", "acceptance_criteria"],
                optional_fields=["dependencies", "nfrs", "out_of_scope", "assumptions", "open_questions"],
                format_style="gherkin",
                sections=[
                    {"name": "acceptance_criteria", "format": "gherkin", "min_items": 3},
                ],
            )

        # Fetch prompt from library with fallback
        system_prompt = await self._get_system_prompt()

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""Parse this template:

{template_text}

Return a JSON object with:
- required_fields (list)
- optional_fields (list)
- format_style
- sections: array of {{name, format, min_items}}
""",
            },
        ]

        return await self.llm_provider.structured_completion(
            messages=messages,
            response_model=TemplateSchema,
            temperature=0.3,
        )
