"""QA Agent - The Skeptic (INVEST validator).

FIXES APPLIED (Feb 5, 2026):
- Issue 3: Added error handling around LLM calls with structured logging
- Issue 7: Added observability with structured logging and tracing
- Prompt Library Integration: Now fetches prompts dynamically from the Prompt Library
"""

from typing import Dict, List

from src.domain.interfaces import ILLMProvider
from src.domain.schema import CoreArtifact, InvestCritique, InvestViolation
from src.infrastructure.prompt_library import get_prompt_library
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AgentError(Exception):
    """Exception raised when an agent operation fails."""
    pass


class QAAgent:
    """QA Agent specializing in Agile artifact quality validation."""

    # Prompt ID for fetching from the library
    PROMPT_ID = "qa_agent_system"

    # Default fallback prompt (used if prompt library fetch fails)
    DEFAULT_SYSTEM_PROMPT = """You are a QA Agent specializing in Agile artifact quality.

CRITICAL: You MUST respond with a JSON object starting with { and ending with }.
Do NOT return a list/array. Return a complete JSON object with ALL required fields.

Your role is to:

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
                    "qa_agent.prompt_loaded",
                    prompt_id=self.PROMPT_ID,
                    source="prompt_library",
                )
                return template
        except Exception as e:
            logger.warning(
                "qa_agent.prompt_load_failed",
                prompt_id=self.PROMPT_ID,
                error=str(e),
            )
        
        logger.debug(
            "qa_agent.prompt_loaded",
            prompt_id=self.PROMPT_ID,
            source="fallback",
        )
        return self.DEFAULT_SYSTEM_PROMPT

    async def critique_artifact(self, artifact: CoreArtifact) -> Dict[str, any]:
        """Critique artifact against INVEST criteria.

        Args:
            artifact: Artifact to critique.

        Returns:
            Dictionary with violations, critique text, and confidence score.
        """
        ac_text = "\n".join(f"- {ac}" for ac in artifact.acceptance_criteria) if artifact.acceptance_criteria else "None specified"

        # Fetch prompt from library with fallback
        system_prompt = await self._get_system_prompt()

        messages = [
            {"role": "system", "content": system_prompt},
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

        # FIX Issue 3: Add error handling with retries
        # FIX Issue 7: Add observability logging
        logger.info(
            "qa_agent.critique_artifact.start",
            artifact_id=artifact.source_id,
        )
        
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
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

                logger.info(
                    "qa_agent.critique_artifact.complete",
                    artifact_id=artifact.source_id,
                    violations_count=len(violation_strings),
                    overall_assessment=critique.overall_assessment,
                    attempt=attempt + 1,
                )

                return {
                    "violations": violation_strings,
                    "structured_violations": critique.violations,
                    "critique": critique.critique_text,
                    "confidence": critique.confidence,
                    "overall_assessment": critique.overall_assessment,
                }
                
            except TimeoutError as e:
                last_error = e
                logger.warning(
                    "qa_agent.critique_artifact.timeout",
                    artifact_id=artifact.source_id,
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                last_error = e
                logger.error(
                    "qa_agent.critique_artifact.error",
                    artifact_id=artifact.source_id,
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
        
        logger.error(
            "qa_agent.critique_artifact.failed",
            artifact_id=artifact.source_id,
            error=str(last_error),
        )
        raise AgentError(f"Critique artifact failed after {max_retries} attempts: {last_error}")

