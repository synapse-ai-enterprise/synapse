"""Developer Agent - The Realist (Technical Feasibility Validator)."""

from typing import Dict, List

from src.domain.interfaces import ILLMProvider
from src.domain.schema import CoreArtifact, FeasibilityAssessment, UASKnowledgeUnit


class DeveloperAgent:
    """Developer Agent specializing in technical feasibility assessment."""

    SYSTEM_PROMPT = """You are a Lead Developer Agent specializing in technical feasibility. Your role is to:

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

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
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

        return {
            "feasibility": assessment.status,
            "dependencies": dependency_strings,
            "concerns": concern_strings,
            "critique": assessment.assessment_text,
            "confidence": assessment.confidence,
        }

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

