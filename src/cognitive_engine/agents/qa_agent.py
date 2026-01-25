"""QA Agent - The Skeptic (INVEST validator)."""

from typing import Dict, List

from src.domain.interfaces import ILLMProvider
from src.domain.schema import CoreArtifact, InvestCritique, InvestViolation


class QAAgent:
    """QA Agent specializing in Agile artifact quality validation."""

    SYSTEM_PROMPT = """You are a QA Agent specializing in Agile artifact quality. Your role is to:

1. Validate user stories against INVEST criteria:
   - **Independent:** Can this be developed independently?
   - **Negotiable:** Are details negotiable with stakeholders?
   - **Valuable:** Does this deliver user value?
   - **Estimable:** Can the team estimate effort?
   - **Small:** Is this appropriately sized (1-3 days)?
   - **Testable:** Are acceptance criteria binary (pass/fail)?

2. Analyze Acceptance Criteria:
   - Are they specific and measurable?
   - Do they cover negative scenarios?
   - Identify vague terms (e.g., "fast", "user-friendly", "better")
   - Ensure testability

3. Output structured critique with:
   - List of INVEST violations
   - Specific issues with acceptance criteria
   - Suggestions for improvement
   - Confidence score (0.0-1.0)

Be thorough but constructive. Your goal is to improve quality, not block progress.

Flag vague or unverifiable claims. Do not invent new files or features."""

    def __init__(self, llm_provider: ILLMProvider):
        """Initialize agent with LLM provider.

        Args:
            llm_provider: LLM provider for generating critiques.
        """
        self.llm_provider = llm_provider

    async def critique_artifact(self, artifact: CoreArtifact) -> Dict[str, any]:
        """Critique artifact against INVEST criteria.

        Args:
            artifact: Artifact to critique.

        Returns:
            Dictionary with violations, critique text, and confidence score.
        """
        ac_text = "\n".join(f"- {ac}" for ac in artifact.acceptance_criteria) if artifact.acceptance_criteria else "None specified"

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Critique this artifact against INVEST criteria:

**Artifact:**
Title: {artifact.title}
Description: {artifact.description}
Type: {artifact.type}
Acceptance Criteria:
{ac_text}

**Task:**
1. Check each INVEST criterion:
   - **I (Independent):** Can this be developed independently without blocking other work?
   - **N (Negotiable):** Are details negotiable with stakeholders, or overly prescriptive?
   - **V (Valuable):** Does this deliver clear user/business value?
   - **E (Estimable):** Can the team estimate effort? (Avoid vague terms like "fast", "better", "enhance")
   - **S (Small):** Is this appropriately sized (1-3 days of work)?
   - **T (Testable):** Are acceptance criteria binary (pass/fail) and specific?

2. For each violation, return a JSON object with these EXACT field names (lowercase):
   - "criterion": string - one of "I", "N", "V", "E", "S", or "T"
   - "severity": string - one of "critical", "major", or "minor"
   - "description": string - description of the violation
   - "evidence": string (optional) - specific evidence from artifact
   - "suggestion": string (optional) - suggestion for how to fix

3. Provide overall assessment (excellent/good/needs_improvement/poor)
4. Rate confidence in your critique (0.0-1.0)

Return a JSON object with this structure:
{{
  "violations": [
    {{
      "criterion": "S",
      "severity": "critical",
      "description": "Story is too large",
      "evidence": "Covers multiple features",
      "suggestion": "Break into smaller stories"
    }}
  ],
  "critique_text": "Detailed critique...",
  "confidence": 0.9,
  "overall_assessment": "needs_improvement"
}}

IMPORTANT: Use lowercase field names: "criterion", "severity", "description", "evidence", "suggestion" (not "INVEST_criterion", "Severity", "Evidence", "Suggestion").""",
            },
        ]

        # Use structured output (transformation is handled in adapter)
        critique = await self.llm_provider.structured_completion(
            messages=messages,
            response_model=InvestCritique,
            temperature=0.5,
        )

        # Convert violations to string format for backward compatibility
        violation_strings = [
            f"{v.criterion}: {v.description}" + (f" (Evidence: {v.evidence})" if v.evidence else "")
            for v in critique.violations
        ]

        return {
            "violations": violation_strings,
            "structured_violations": critique.violations,
            "critique": critique.critique_text,
            "confidence": critique.confidence,
            "overall_assessment": critique.overall_assessment,
        }

