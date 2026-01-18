"""Developer Agent - The Realist (Technical Feasibility Validator)."""

from typing import Dict, List

from src.domain.interfaces import ILLMProvider
from src.domain.schema import CoreArtifact, UASKnowledgeUnit


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
1. Verify referenced files exist in codebase
2. Assess technical feasibility
3. Identify dependencies and blockers
4. Rate confidence (0.0-1.0)

Format your response as:
FEASIBILITY: [feasible/blocked/requires-changes]

DEPENDENCIES:
- [list of dependencies]

CONCERNS:
- [list of technical concerns]

CONFIDENCE: [0.0-1.0]""",
            },
        ]

        response = await self.llm_provider.chat_completion(messages, temperature=0.5)

        # Parse response
        feasibility = self._extract_feasibility(response)
        dependencies = self._extract_dependencies(response)
        concerns = self._extract_concerns(response)
        confidence = self._extract_confidence(response)

        return {
            "feasibility": feasibility,
            "dependencies": dependencies,
            "concerns": concerns,
            "critique": response,
            "confidence": confidence,
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

    def _extract_feasibility(self, text: str) -> str:
        """Extract feasibility status from assessment.

        Args:
            text: Assessment text.

        Returns:
            Feasibility status string.
        """
        import re

        match = re.search(r"FEASIBILITY:\s*(\w+)", text, re.IGNORECASE)
        if match:
            status = match.group(1).lower()
            if status in ["feasible", "blocked", "requires-changes"]:
                return status

        return "unknown"

    def _extract_dependencies(self, text: str) -> List[str]:
        """Extract dependencies from assessment.

        Args:
            text: Assessment text.

        Returns:
            List of dependency strings.
        """
        dependencies = []
        lines = text.split("\n")
        in_dependencies = False

        for line in lines:
            line = line.strip()
            if "DEPENDENCIES:" in line.upper():
                in_dependencies = True
                continue
            if in_dependencies and line.startswith("-"):
                dependencies.append(line.lstrip("- ").strip())
            if in_dependencies and line and not line.startswith("-") and "CONCERNS:" not in line.upper():
                break

        return dependencies

    def _extract_concerns(self, text: str) -> List[str]:
        """Extract technical concerns from assessment.

        Args:
            text: Assessment text.

        Returns:
            List of concern strings.
        """
        concerns = []
        lines = text.split("\n")
        in_concerns = False

        for line in lines:
            line = line.strip()
            if "CONCERNS:" in line.upper():
                in_concerns = True
                continue
            if in_concerns and line.startswith("-"):
                concerns.append(line.lstrip("- ").strip())
            if in_concerns and line and not line.startswith("-") and "CONFIDENCE:" not in line.upper():
                break

        return concerns

    def _extract_confidence(self, text: str) -> float:
        """Extract confidence score from assessment.

        Args:
            text: Assessment text.

        Returns:
            Confidence score (0.0-1.0).
        """
        import re

        match = re.search(r"CONFIDENCE:\s*([0-9.]+)", text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

        return 0.7  # Default confidence
