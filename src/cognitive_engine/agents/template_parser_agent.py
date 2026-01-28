"""Template Parser Agent."""

from src.domain.interfaces import ILLMProvider
from src.domain.schema import TemplateSchema


class TemplateParserAgent:
    """Agent for parsing and validating story templates."""

    SYSTEM_PROMPT = """You are a Template Parser Agent. Your role is to:
1. Parse an uploaded story template.
2. Extract required vs optional fields.
3. Detect formatting expectations (gherkin vs free-form).
4. Create a schema for filling.

Return a JSON object matching the requested schema exactly."""

    def __init__(self, llm_provider: ILLMProvider):
        self.llm_provider = llm_provider

    async def parse(self, template_text: str) -> TemplateSchema:
        """Parse template text into a structured schema."""
        if not template_text or not template_text.strip():
            return TemplateSchema(
                required_fields=["title", "description", "acceptance_criteria"],
                optional_fields=["dependencies", "nfrs", "out_of_scope", "assumptions", "open_questions"],
                format_style="free_form",
                sections=[
                    {"name": "acceptance_criteria", "format": "free_form", "min_items": 3},
                ],
            )

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
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
