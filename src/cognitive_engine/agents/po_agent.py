"""Product Owner Agent - Value Architect."""

from typing import List

from src.domain.interfaces import ILLMProvider
from src.domain.schema import CoreArtifact, UASKnowledgeUnit


class ProductOwnerAgent:
    """Product Owner Agent specializing in Agile user stories."""

    SYSTEM_PROMPT = """You are a Product Owner Agent specializing in Agile user stories. Your role is to:

1. Generate user stories in the format: "As a [user type], I want [goal], so that [benefit]."
2. Ensure the "So that" clause represents genuine user value, not just technical functionality.
3. Verify alignment with parent Epic or project goals.
4. Synthesize feedback from QA and Developer agents into refined artifacts.
5. Maintain clarity and business focus throughout.

You have access to:
- Business documentation from Notion (PRDs, meeting notes, roadmaps)
- Codebase context from GitHub (for technical feasibility awareness)

Always cite your sources using markdown links: [description](url)

Do not invent new files or features. If something is required but doesn't exist, explicitly state 'Requires Implementation'."""

    def __init__(self, llm_provider: ILLMProvider):
        """Initialize agent with LLM provider.

        Args:
            llm_provider: LLM provider for generating responses.
        """
        self.llm_provider = llm_provider

    async def draft_artifact(
        self, artifact: CoreArtifact, context: List[UASKnowledgeUnit]
    ) -> CoreArtifact:
        """Generate initial draft artifact.

        Args:
            artifact: Raw artifact to refine.
            context: Retrieved knowledge units for context.

        Returns:
            Draft artifact with improved title, description, and acceptance criteria.
        """
        # Format context
        context_text = self._format_context(context)

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Generate a refined user story based on the following artifact and context:

**Current Artifact:**
Title: {artifact.title}
Description: {artifact.description}
Type: {artifact.type}
Priority: {artifact.priority.value}

**Context from Knowledge Base:**
{context_text}

**Task:**
1. Refine the title to follow user story format if it's a story
2. Improve the description with clear value proposition
3. Generate specific, testable acceptance criteria
4. Ensure alignment with business goals

Return the refined artifact in the same structure.""",
            },
        ]

        response = await self.llm_provider.chat_completion(messages, temperature=0.7)

        # Parse response and update artifact
        # In a real implementation, you'd parse structured output
        # For now, we'll update description and extract ACs
        refined_artifact = artifact.model_copy()
        refined_artifact.description = response
        # Extract acceptance criteria from response (simplified)
        refined_artifact.acceptance_criteria = self._extract_acceptance_criteria(response)

        return refined_artifact

    async def synthesize_feedback(
        self, artifact: CoreArtifact, critiques: List[str]
    ) -> CoreArtifact:
        """Synthesize feedback from QA and Developer agents.

        Args:
            artifact: Current artifact draft.
            critiques: List of critique strings from other agents.

        Returns:
            Refined artifact incorporating feedback.
        """
        critiques_text = "\n\n".join(f"Critique {i+1}:\n{critique}" for i, critique in enumerate(critiques))

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Synthesize feedback from QA and Developer agents to refine this artifact:

**Current Artifact:**
Title: {artifact.title}
Description: {artifact.description}
Acceptance Criteria: {chr(10).join(f"- {ac}" for ac in artifact.acceptance_criteria)}

**Critiques:**
{critiques_text}

**Task:**
1. Address all valid concerns raised in critiques
2. Maintain business value focus
3. Ensure technical feasibility
4. Refine acceptance criteria to be specific and testable

Return the refined artifact.""",
            },
        ]

        response = await self.llm_provider.chat_completion(messages, temperature=0.7)

        refined_artifact = artifact.model_copy()
        refined_artifact.description = response
        refined_artifact.acceptance_criteria = self._extract_acceptance_criteria(response)

        return refined_artifact

    def _format_context(self, context: List[UASKnowledgeUnit]) -> str:
        """Format knowledge units as context text.

        Args:
            context: List of knowledge units.

        Returns:
            Formatted context string.
        """
        if not context:
            return "No additional context available."

        formatted = []
        for unit in context:
            formatted.append(
                f"**Source: {unit.source}** ({unit.location})\n{unit.summary}\n\n{unit.content[:500]}..."
            )

        return "\n\n---\n\n".join(formatted)

    def _extract_acceptance_criteria(self, text: str) -> List[str]:
        """Extract acceptance criteria from text.

        Args:
            text: Text containing acceptance criteria.

        Returns:
            List of acceptance criteria strings.
        """
        # Simple extraction - look for bullet points or numbered lists
        criteria = []
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("- ") or line.startswith("* ") or (line[0].isdigit() and ". " in line[:3]):
                criteria.append(line.lstrip("- *").lstrip("0123456789. "))

        return criteria if criteria else ["Acceptance criteria to be defined"]
