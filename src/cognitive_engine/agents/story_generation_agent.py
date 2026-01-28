"""Story Generation Agent."""

from typing import List, Optional

from src.domain.interfaces import ILLMProvider
from src.domain.schema import StoryGenerationResult


class StoryGenerationAgent:
    """Agent for generating user stories from selected techniques."""

    SYSTEM_PROMPT = """You are a Story Generation Agent. Your role is to:
1. Apply the selected splitting techniques to the epic.
2. Generate user stories with clear titles and descriptions.
3. Suggest story points where reasonable.
4. Provide initial acceptance criteria.
5. Maintain traceability to the parent epic.

Return a JSON object matching the requested schema exactly."""

    def __init__(self, llm_provider: ILLMProvider):
        self.llm_provider = llm_provider

    async def generate_stories(
        self,
        epic_text: str,
        techniques: List[str],
        parent_epic: Optional[str] = None,
    ) -> StoryGenerationResult:
        """Generate stories using selected techniques."""
        techniques_text = ", ".join(techniques) if techniques else "None provided"
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Generate user stories based on the epic and selected techniques.

Parent Epic: {parent_epic or "unknown"}
Selected Techniques: {techniques_text}

Epic Text:
{epic_text}

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
