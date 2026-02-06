"""Developer Agent - The Realist (Technical Feasibility Validator).

FIXES APPLIED (Feb 5, 2026):
- Issue 3: Added error handling around LLM calls with structured logging
- Issue 7: Added observability with structured logging and tracing
- Prompt Library Integration: Now fetches prompts dynamically from the Prompt Library
"""

from typing import Dict, List

from src.domain.interfaces import ILLMProvider
from src.domain.schema import CoreArtifact, FeasibilityAssessment, UASKnowledgeUnit
from src.infrastructure.prompt_library import get_prompt_library
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AgentError(Exception):
    """Exception raised when an agent operation fails."""
    pass


class DeveloperAgent:
    """Developer Agent specializing in technical feasibility assessment."""

    # Prompt ID for fetching from the library
    PROMPT_ID = "developer_agent_system"

    # Default fallback prompt (used if prompt library fetch fails)
    DEFAULT_SYSTEM_PROMPT = """You are a Lead Developer Agent specializing in technical feasibility.

CRITICAL: You MUST respond with a JSON object starting with { and ending with }.
Do NOT return a list/array. Return a complete JSON object with ALL required fields.

Your role is to:

1. Assess technical feasibility:
   - Can this be implemented with current architecture?
   - Are referenced code files/components accurate?
   - Are there technical blockers?

2. Identify dependencies:
   - Does this depend on other work items?
   - Are there external system dependencies?
   - Are there infrastructure requirements?

3. Verify implementation details:
   - Do referenced GitHub files/paths exist?
   - Are code snippets accurate?
   - Are architectural assumptions valid?

4. Output structured assessment with:
   - Feasibility status (feasible/blocked/requires-changes)
   - List of dependencies
   - Technical concerns
   - Confidence score (0.0-1.0)

You have access to the full codebase via RAG. Always verify that referenced code actually exists.

Do not invent new files or features. If something is required but doesn't exist, explicitly state 'Requires Implementation'."""

    def __init__(self, llm_provider: ILLMProvider):
        """Initialize agent with LLM provider.

        Args:
            llm_provider: LLM provider for generating assessments.
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
                    "developer_agent.prompt_loaded",
                    prompt_id=self.PROMPT_ID,
                    source="prompt_library",
                )
                return template
        except Exception as e:
            logger.warning(
                "developer_agent.prompt_load_failed",
                prompt_id=self.PROMPT_ID,
                error=str(e),
            )
        
        logger.debug(
            "developer_agent.prompt_loaded",
            prompt_id=self.PROMPT_ID,
            source="fallback",
        )
        return self.DEFAULT_SYSTEM_PROMPT

    async def assess_feasibility(
        self, artifact: CoreArtifact, context: List[UASKnowledgeUnit]
    ) -> Dict[str, any]:
        """Assess technical feasibility of artifact.

        Args:
            artifact: Artifact to assess.
            context: Retrieved knowledge units from codebase.

        Returns:
            Dictionary with feasibility status, dependencies, concerns, and confidence.
        """
        # Format context
        context_text = self._format_context(context)

        ac_text = "\n".join(f"- {ac}" for ac in artifact.acceptance_criteria) if artifact.acceptance_criteria else "None specified"

        # Fetch prompt from library with fallback
        system_prompt = await self._get_system_prompt()

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""Assess the technical feasibility of this artifact:

**Artifact:**
Title: {artifact.title}
Description: {artifact.description}
Acceptance Criteria:
{ac_text}
Related Files: {', '.join(artifact.related_files) if artifact.related_files else 'None'}

**Codebase Context:**
{context_text}

**Task:**
1. Verify referenced files exist in codebase (check context above)
2. Assess technical feasibility:
   - "feasible": Can be implemented with current architecture
   - "blocked": Cannot proceed due to blockers
   - "requires_changes": Needs architectural changes first (use underscore, not hyphen)
3. Identify dependencies:
   - Type: code, infrastructure, external_service, data, other
   - Whether blocking or not
4. Identify technical concerns with severity (blocker/high/medium/low)
5. Rate confidence in assessment (0.0-1.0)

Return a JSON object with this EXACT structure:
{{
  "status": "requires_changes",
  "dependencies": [
    {{
      "dependency_type": "code",
      "description": "Description of the dependency",
      "blocking": true
    }}
  ],
  "concerns": [
    {{
      "severity": "high",
      "description": "Description of the concern",
      "recommendation": "Optional recommendation"
    }}
  ],
  "confidence": 0.8,
  "assessment_text": "Detailed assessment text"
}}

IMPORTANT: Use these EXACT field names:
- For dependencies: "dependency_type" (not "type"), "description" (required), "blocking"
- For concerns: "severity", "description" (not "detail"), "recommendation" (optional)""",
            },
        ]

        # FIX Issue 3: Add error handling with retries
        # FIX Issue 7: Add observability logging
        logger.info(
            "developer_agent.assess_feasibility.start",
            artifact_id=artifact.source_id,
            context_count=len(context),
        )
        
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Use structured output
                assessment = await self.llm_provider.structured_completion(
                    messages=messages,
                    response_model=FeasibilityAssessment,
                    temperature=0.5,
                )

                # Convert to string format for backward compatibility
                dependency_strings = [
                    f"{d.dependency_type}: {d.description}" + (" (BLOCKING)" if d.blocking else "")
                    for d in assessment.dependencies
                ]
                concern_strings = [
                    f"[{c.severity.upper()}] {c.description}" + (f" (Recommendation: {c.recommendation})" if c.recommendation else "")
                    for c in assessment.concerns
                ]

                logger.info(
                    "developer_agent.assess_feasibility.complete",
                    artifact_id=artifact.source_id,
                    feasibility=assessment.status,
                    dependencies_count=len(dependency_strings),
                    concerns_count=len(concern_strings),
                    attempt=attempt + 1,
                )

                return {
                    "feasibility": assessment.status,
                    "dependencies": dependency_strings,
                    "concerns": concern_strings,
                    "critique": assessment.assessment_text,
                    "confidence": assessment.confidence,
                }
                
            except TimeoutError as e:
                last_error = e
                logger.warning(
                    "developer_agent.assess_feasibility.timeout",
                    artifact_id=artifact.source_id,
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                last_error = e
                logger.error(
                    "developer_agent.assess_feasibility.error",
                    artifact_id=artifact.source_id,
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
        
        logger.error(
            "developer_agent.assess_feasibility.failed",
            artifact_id=artifact.source_id,
            error=str(last_error),
        )
        raise AgentError(f"Assess feasibility failed after {max_retries} attempts: {last_error}")

    def _format_context(self, context: List[UASKnowledgeUnit]) -> str:
        """Format knowledge units as codebase context.

        Args:
            context: List of knowledge units.

        Returns:
            Formatted context string.
        """
        if not context:
            return "No codebase context available."

        formatted = []
        for unit in context:
            if unit.source == "github":
                formatted.append(f"**File: {unit.location}**\n```\n{unit.content[:1000]}...\n```")

        return "\n\n---\n\n".join(formatted)

