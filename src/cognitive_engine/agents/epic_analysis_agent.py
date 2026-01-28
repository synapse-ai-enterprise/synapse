"""Epic Analysis Agent."""

from typing import Optional

from src.domain.interfaces import ILLMProvider
from src.domain.schema import EpicAnalysis


class EpicAnalysisAgent:
    """Agent for understanding and analyzing epic content."""

    SYSTEM_PROMPT = """You are an Epic Analysis Agent. Your role is to:
1. Parse the epic description and extract key entities (user, capability, benefit, constraints).
2. Classify the epic type (feature, technical, architectural).
3. Assess complexity (0.0-1.0).
4. Flag ambiguities and missing information.
5. Identify the most likely domain.

Return a JSON object matching the requested schema exactly."""

    def __init__(self, llm_provider: ILLMProvider):
        self.llm_provider = llm_provider

    async def analyze_epic(
        self,
        epic_text: str,
        epic_id: Optional[str] = None,
    ) -> EpicAnalysis:
        """Analyze epic text and return structured analysis."""
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
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
