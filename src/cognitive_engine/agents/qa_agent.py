"""QA Agent - The Skeptic (INVEST validator)."""

from typing import Dict, List

from src.domain.interfaces import ILLMProvider
from src.domain.schema import CoreArtifact


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
1. Check each INVEST criterion
2. Analyze acceptance criteria quality
3. Identify specific violations
4. Provide constructive suggestions
5. Rate confidence (0.0-1.0)

Format your response as:
VIOLATIONS:
- [list of violations]

CRITIQUE:
[detailed critique]

CONFIDENCE: [0.0-1.0]""",
            },
        ]

        response = await self.llm_provider.chat_completion(messages, temperature=0.5)

        # Parse response
        violations = self._extract_violations(response)
        confidence = self._extract_confidence(response)

        return {
            "violations": violations,
            "critique": response,
            "confidence": confidence,
        }

    def _extract_violations(self, text: str) -> List[str]:
        """Extract INVEST violations from critique text.

        Args:
            text: Critique text.

        Returns:
            List of violation strings.
        """
        violations = []
        lines = text.split("\n")
        in_violations = False

        for line in lines:
            line = line.strip()
            if "VIOLATIONS:" in line.upper():
                in_violations = True
                continue
            if in_violations and line.startswith("-"):
                violations.append(line.lstrip("- ").strip())
            if in_violations and line and not line.startswith("-"):
                break

        return violations

    def _extract_confidence(self, text: str) -> float:
        """Extract confidence score from critique text.

        Args:
            text: Critique text.

        Returns:
            Confidence score (0.0-1.0).
        """
        import re

        # Look for "CONFIDENCE: 0.8" pattern
        match = re.search(r"CONFIDENCE:\s*([0-9.]+)", text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

        # Default confidence based on violations
        violations = self._extract_violations(text)
        if not violations:
            return 0.9
        elif len(violations) <= 2:
            return 0.7
        else:
            return 0.5
