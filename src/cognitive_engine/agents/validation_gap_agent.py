"""Validation & Gap Detection Agent.

Prompt Library Integration: Now fetches prompts dynamically from the Prompt Library
"""

from typing import Any, List

from src.domain.interfaces import ILLMProvider
from src.domain.schema import (
    InvestScore,
    PopulatedStory,
    RetrievedContext,
    TechnicalRisk,
    ValidationGap,
    ValidationIssue,
    ValidationResults,
    ValidationResultsDraft,
)
from src.infrastructure.prompt_library import get_prompt_library
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationGapDetectionAgent:
    """Agent that validates story quality and detects gaps."""

    # Prompt ID for fetching from the library
    PROMPT_ID = "validation_gap_agent_system"

    # Default fallback prompt (used if prompt library fetch fails)
    DEFAULT_SYSTEM_PROMPT = """You are a Validation & Gap Detection Agent.

IMPORTANT: Return a JSON object (NOT a list) with this EXACT structure:
{
  "invest_score": {
    "independent": true,
    "negotiable": true,
    "valuable": true,
    "estimable": true,
    "small": true,
    "testable": true,
    "overall": "pass"
  },
  "issues": [{"severity": "warning", "type": "general", "message": "issue description"}],
  "gaps": [{"field": "field_name", "gap": "gap description"}],
  "ungrounded_claims": ["claim without evidence"],
  "technical_risks": [{"risk": "risk description", "mitigation": "how to address"}]
}

Use empty arrays [] if no items exist. Start with { and end with }."""

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
                    "validation_gap_agent.prompt_loaded",
                    prompt_id=self.PROMPT_ID,
                    source="prompt_library",
                )
                return template
        except Exception as e:
            logger.warning(
                "validation_gap_agent.prompt_load_failed",
                prompt_id=self.PROMPT_ID,
                error=str(e),
            )
        
        logger.debug(
            "validation_gap_agent.prompt_loaded",
            prompt_id=self.PROMPT_ID,
            source="fallback",
        )
        return self.DEFAULT_SYSTEM_PROMPT

    async def validate(
        self,
        story: PopulatedStory,
        context: RetrievedContext,
    ) -> ValidationResults:
        # Fetch prompt from library with fallback
        system_prompt = await self._get_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""Validate this story and identify gaps.

Story:
{story.model_dump()}

Context:
{context.model_dump()}

Return a JSON object with:
invest_score, issues, gaps, ungrounded_claims, technical_risks.
""",
            },
        ]

        draft = await self.llm_provider.structured_completion(
            messages=messages,
            response_model=ValidationResultsDraft,
            temperature=0.4,
        )

        return self._normalize_draft(draft)

    def _normalize_draft(self, draft: ValidationResultsDraft) -> ValidationResults:
        invest_score = self._normalize_invest_score(draft.invest_score)
        return ValidationResults(
            invest_score=invest_score,
            issues=self._normalize_issues(draft.issues),
            gaps=self._normalize_gaps(draft.gaps),
            ungrounded_claims=self._normalize_strings(draft.ungrounded_claims),
            technical_risks=self._normalize_risks(draft.technical_risks),
        )

    def _normalize_invest_score(self, raw: Any) -> InvestScore:
        if isinstance(raw, InvestScore):
            return raw
        if isinstance(raw, dict):
            data = dict(raw)
        else:
            data = {}
        overall = data.get("overall")
        if overall is None:
            overall = "pass"
        data["overall"] = overall
        return InvestScore(**data)

    def _normalize_issues(self, raw: List[Any]) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        for entry in raw or []:
            if isinstance(entry, ValidationIssue):
                issues.append(entry)
            elif isinstance(entry, dict):
                issues.append(ValidationIssue(**entry))
            else:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        type="general",
                        message=str(entry),
                    )
                )
        return issues

    def _normalize_gaps(self, raw: List[Any]) -> List[ValidationGap]:
        gaps: List[ValidationGap] = []
        for entry in raw or []:
            if isinstance(entry, ValidationGap):
                gaps.append(entry)
            elif isinstance(entry, dict):
                gaps.append(ValidationGap(**entry))
            else:
                gaps.append(
                    ValidationGap(
                        field="unspecified",
                        gap=str(entry),
                    )
                )
        return gaps

    def _normalize_risks(self, raw: List[Any]) -> List[TechnicalRisk]:
        risks: List[TechnicalRisk] = []
        for entry in raw or []:
            if isinstance(entry, TechnicalRisk):
                risks.append(entry)
            elif isinstance(entry, dict):
                risks.append(TechnicalRisk(**entry))
            else:
                risks.append(TechnicalRisk(risk=str(entry)))
        return risks

    def _normalize_strings(self, raw: List[Any]) -> List[str]:
        return [str(item).strip() for item in raw or [] if str(item).strip()]
