"""Validation & Gap Detection Agent."""

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


class ValidationGapDetectionAgent:
    """Agent that validates story quality and detects gaps."""

    SYSTEM_PROMPT = """You are a Validation & Gap Detection Agent. Your role is to:
1. Validate the story against INVEST criteria.
2. Identify missing information and gaps.
3. Flag ungrounded assumptions or claims.
4. Identify technical risks or conflicts.
5. Ensure acceptance criteria are testable.

Return a JSON object matching the requested schema exactly."""

    def __init__(self, llm_provider: ILLMProvider):
        self.llm_provider = llm_provider

    async def validate(
        self,
        story: PopulatedStory,
        context: RetrievedContext,
    ) -> ValidationResults:
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
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
