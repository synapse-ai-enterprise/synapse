"""Splitting Strategy Agent."""

from src.domain.interfaces import ILLMProvider
from src.domain.schema import EpicAnalysis, SplittingStrategyResult


class SplittingStrategyAgent:
    """Agent that recommends epic splitting techniques."""

    SYSTEM_PROMPT = """You are a Splitting Strategy Agent. Your role is to:
1. Analyze epic characteristics and recommend splitting techniques.
2. Apply SPIDR framework (Spike, Path, Interface, Data, Rules).
3. Apply Humanizing Work patterns (Simple/Complex, Defer Performance, Break Out Spike, Workflow Steps, Operations, Breaking Conjunctions).
4. Rank techniques by relevance and explain why.

Return a JSON object matching the requested schema exactly."""

    def __init__(self, llm_provider: ILLMProvider):
        self.llm_provider = llm_provider

    async def recommend(self, epic_text: str, analysis: EpicAnalysis) -> SplittingStrategyResult:
        """Recommend splitting techniques for an epic."""
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
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
