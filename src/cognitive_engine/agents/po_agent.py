"""Product Owner Agent - Value Architect."""

from typing import List

from src.domain.interfaces import ILLMProvider
from src.domain.schema import ArtifactRefinement, CoreArtifact, UASKnowledgeUnit


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
Acceptance Criteria: {chr(10).join(f"- {ac}" for ac in artifact.acceptance_criteria) if artifact.acceptance_criteria else "None"}

**Context from Knowledge Base:**
{context_text}

**Task:**
1. Refine the title to follow user story format if it's a story (e.g., "As a [user], I want [goal], so that [benefit]")
2. Improve the description with clear value proposition and user story format
3. Generate specific, testable acceptance criteria (binary pass/fail)
4. Ensure alignment with business goals
5. Keep acceptance criteria small and focused

You must return a JSON object with these exact fields:
- "title": string (the refined title)
- "description": string (the refined description)
- "acceptance_criteria": array of strings (list of specific, testable criteria)
- "rationale": string or null (optional explanation of changes)

Example format:
{{
  "title": "As a user, I want to log in securely so that my data is protected",
  "description": "As a registered user, I want to securely authenticate...",
  "acceptance_criteria": ["User can log in with valid credentials", "Invalid credentials are rejected"],
  "rationale": "Clarified user story format and added security focus"
}}""",
            },
        ]

        # Use structured output
        refinement = await self.llm_provider.structured_completion(
            messages=messages,
            response_model=ArtifactRefinement,
            temperature=0.7,
        )

        # Apply refinement to artifact
        refined_artifact = artifact.model_copy()
        refined_artifact.title = refinement.title
        refined_artifact.description = refinement.description
        refined_artifact.acceptance_criteria = refinement.acceptance_criteria

        return refined_artifact

    async def synthesize_feedback(
        self, artifact: CoreArtifact, critiques: List[str], violations: List[str] = None
    ) -> CoreArtifact:
        """Synthesize feedback from QA and Developer agents.

        Args:
            artifact: Current artifact draft.
            critiques: List of critique strings from other agents.
            violations: List of INVEST violations to address.

        Returns:
            Refined artifact incorporating feedback.
        """
        critiques_text = "\n\n".join(f"Critique {i+1}:\n{critique}" for i, critique in enumerate(critiques))
        violations_text = ""
        if violations:
            violations_text = f"\n\n**CRITICAL: INVEST Violations to Address (MUST FIX):**\n" + "\n".join(f"- {v}" for v in violations)
            violations_text += "\n\n**IMPORTANT:** For each violation above, you MUST:\n"
            violations_text += "- If violation starts with 'S:' (Small), break the story into smaller pieces or remove features\n"
            violations_text += "- If violation starts with 'T:' (Testable), make acceptance criteria binary and specific\n"
            violations_text += "- If violation starts with 'V:' (Valuable), ensure 'so that' clause shows user value\n"
            violations_text += "- If violation starts with 'E:' (Estimable), remove vague terms like 'fast', 'better', 'user-friendly'\n"
            violations_text += "- If violation starts with 'N:' (Negotiable), make details less prescriptive\n"
            violations_text += "- If violation starts with 'I:' (Independent), remove dependencies\n"

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Synthesize feedback from QA and Developer agents to refine this artifact:

**Current Artifact:**
Title: {artifact.title}
Description: {artifact.description}
Acceptance Criteria: {chr(10).join(f"- {ac}" for ac in artifact.acceptance_criteria) if artifact.acceptance_criteria else "None"}

**Critiques:**
{critiques_text}
{violations_text}

**Task (PRIORITY ORDER):**
1. **FIRST**: Address EVERY INVEST violation listed above. Each violation must be explicitly fixed.
2. Address all valid concerns raised in critiques
3. Break down large stories into smaller, focused ones if needed (especially for 'S:' violations)
4. Make acceptance criteria specific, testable, and binary (pass/fail) - remove vague terms
5. Ensure 'so that' clause shows genuine user value (for 'V:' violations)
6. Maintain business value focus
7. Ensure technical feasibility
8. Ensure each acceptance criterion is independently testable

You must return a JSON object with these exact fields:
- "title": string (the refined title)
- "description": string (the refined description)
- "acceptance_criteria": array of strings (list of specific, testable criteria)
- "rationale": string or null (optional explanation of changes)

Example format:
{{
  "title": "As a user, I want to log in securely so that my data is protected",
  "description": "As a registered user, I want to securely authenticate...",
  "acceptance_criteria": ["User can log in with valid credentials", "Invalid credentials are rejected"],
  "rationale": "Addressed INVEST violations: made story smaller and more testable"
}}""",
            },
        ]

        # Use structured output
        refinement = await self.llm_provider.structured_completion(
            messages=messages,
            response_model=ArtifactRefinement,
            temperature=0.7,
        )

        refined_artifact = artifact.model_copy()
        refined_artifact.title = refinement.title
        refined_artifact.description = refinement.description
        refined_artifact.acceptance_criteria = refinement.acceptance_criteria

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

