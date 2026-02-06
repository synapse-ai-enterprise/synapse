"""Product Owner Agent - Value Architect.

FIXES APPLIED (Feb 5, 2026):
- Issue 3: Added error handling around LLM calls with structured logging
- Issue 7: Added observability with structured logging and tracing
- Prompt Library Integration: Now fetches prompts dynamically from the Prompt Library
"""

from typing import List, Optional

from src.domain.interfaces import ILLMProvider
from src.domain.schema import (
    ArtifactRefinement,
    ArtifactSplitProposal,
    CoreArtifact,
    UASKnowledgeUnit,
)
from src.infrastructure.prompt_library import get_prompt_library
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AgentError(Exception):
    """Exception raised when an agent operation fails."""
    pass


class ProductOwnerAgent:
    """Product Owner Agent specializing in Agile user stories."""

    # Prompt ID for fetching from the library
    PROMPT_ID = "po_agent_system"

    # Default fallback prompt (used if prompt library fetch fails)
    DEFAULT_SYSTEM_PROMPT = """You are a Product Owner Agent specializing in Agile user stories. Your role is to:

1. Generate user stories in the format: "As a [user type], I want [goal], so that [benefit]."
2. Ensure the "So that" clause represents genuine user value, not just technical functionality.
3. Verify alignment with parent Epic or project goals.
4. Synthesize feedback from QA and Developer agents into refined artifacts.
5. Maintain clarity and business focus throughout.

You have access to:
- Business documentation from Notion (PRDs, meeting notes, roadmaps)
- Codebase context from GitHub (for technical feasibility awareness)

Evidence and citation rules:
- Every factual statement must include an inline citation in the form [source: <title or url>].
- If no supporting evidence exists, mark the statement with [source: missing] and note it in rationale.

Always cite your sources using markdown links when a URL is available: [description](url)

Do not invent new files or features. If something is required but doesn't exist, explicitly state 'Requires Implementation'."""

    def __init__(self, llm_provider: ILLMProvider):
        """Initialize agent with LLM provider.

        Args:
            llm_provider: LLM provider for generating responses.
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
                    "po_agent.prompt_loaded",
                    prompt_id=self.PROMPT_ID,
                    source="prompt_library",
                )
                return template
        except Exception as e:
            logger.warning(
                "po_agent.prompt_load_failed",
                prompt_id=self.PROMPT_ID,
                error=str(e),
            )
        
        logger.debug(
            "po_agent.prompt_loaded",
            prompt_id=self.PROMPT_ID,
            source="fallback",
        )
        return self.DEFAULT_SYSTEM_PROMPT

    async def draft_artifact(
        self,
        artifact: CoreArtifact,
        context: List[UASKnowledgeUnit],
        feedback_summary: Optional[str] = None,
    ) -> CoreArtifact:
        """Generate initial or re-draft artifact.

        Args:
            artifact: Raw or refined artifact to improve.
            context: Retrieved knowledge units for context.
            feedback_summary: Optional summary of QA/Developer feedback to address (for re-drafts).

        Returns:
            Draft artifact with improved title, description, and acceptance criteria.
            
        Raises:
            AgentError: If LLM call fails after retries.
        """
        # FIX Issue 7: Add observability logging
        logger.info(
            "po_agent.draft_artifact.start",
            artifact_id=artifact.source_id,
            has_feedback=bool(feedback_summary),
            context_count=len(context),
        )
        
        # Format context
        context_text = self._format_context(context)

        # Build feedback section for re-drafts
        feedback_section = ""
        if feedback_summary:
            feedback_section = f"""
**Feedback from previous round (address these):**
{feedback_summary}

"""

        # Fetch prompt from library with fallback
        system_prompt = await self._get_system_prompt()

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""Generate a refined user story based on the following artifact and context.{feedback_section}

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
6. Add inline citations for every factual statement using [source: <title or url>]
7. If evidence is missing, use [source: missing] and explain in rationale

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

        # FIX Issue 3: Add error handling with retries
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
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
                
                logger.info(
                    "po_agent.draft_artifact.complete",
                    artifact_id=artifact.source_id,
                    attempt=attempt + 1,
                )
                return refined_artifact
                
            except TimeoutError as e:
                last_error = e
                logger.warning(
                    "po_agent.draft_artifact.timeout",
                    artifact_id=artifact.source_id,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                last_error = e
                logger.error(
                    "po_agent.draft_artifact.error",
                    artifact_id=artifact.source_id,
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
        
        # All retries exhausted
        logger.error(
            "po_agent.draft_artifact.failed",
            artifact_id=artifact.source_id,
            error=str(last_error),
        )
        raise AgentError(f"Draft artifact failed after {max_retries} attempts: {last_error}")

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
            
        Raises:
            AgentError: If LLM call fails after retries.
        """
        # FIX Issue 7: Add observability logging
        logger.info(
            "po_agent.synthesize_feedback.start",
            artifact_id=artifact.source_id,
            critiques_count=len(critiques),
            violations_count=len(violations) if violations else 0,
        )
        
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

        # Fetch prompt from library with fallback
        system_prompt = await self._get_system_prompt()

        messages = [
            {"role": "system", "content": system_prompt},
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
9. Add inline citations for every factual statement using [source: <title or url>]
10. If evidence is missing, use [source: missing] and explain in rationale

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

        # FIX Issue 3: Add error handling with retries
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                refinement = await self.llm_provider.structured_completion(
                    messages=messages,
                    response_model=ArtifactRefinement,
                    temperature=0.7,
                )

                refined_artifact = artifact.model_copy()
                refined_artifact.title = refinement.title
                refined_artifact.description = refinement.description
                refined_artifact.acceptance_criteria = refinement.acceptance_criteria

                logger.info(
                    "po_agent.synthesize_feedback.complete",
                    artifact_id=artifact.source_id,
                    attempt=attempt + 1,
                )
                return refined_artifact
                
            except TimeoutError as e:
                last_error = e
                logger.warning(
                    "po_agent.synthesize_feedback.timeout",
                    artifact_id=artifact.source_id,
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                last_error = e
                logger.error(
                    "po_agent.synthesize_feedback.error",
                    artifact_id=artifact.source_id,
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
        
        logger.error(
            "po_agent.synthesize_feedback.failed",
            artifact_id=artifact.source_id,
            error=str(last_error),
        )
        raise AgentError(f"Synthesize feedback failed after {max_retries} attempts: {last_error}")

    async def propose_artifact_split(
        self,
        artifact: CoreArtifact,
        qa_critique: Optional[str] = None,
        violations_summary: Optional[List[str]] = None,
        developer_critique: Optional[str] = None,
        evidence_summary: Optional[str] = None,
        refined_story_context: Optional[str] = None,
    ) -> List[CoreArtifact]:
        """Propose splitting one large artifact into multiple smaller ones.

        Use when the story is too large (INVEST S) or covers multiple distinct
        features/models; the result preserves original scope as multiple artifacts.

        Args:
            artifact: Current (large) artifact to split.
            qa_critique: Optional QA critique text.
            violations_summary: Optional list of violation descriptions (e.g. "S: Story too large").
            developer_critique: Optional Developer critique with technical feasibility concerns.
            evidence_summary: Optional summary of evidence/context from knowledge retrieval.
            refined_story_context: Optional context from the refined/generated story.

        Returns:
            List of CoreArtifact proposals (2 or more) that together cover the original scope.
        """
        # Build QA critique section
        critique_section = ""
        if qa_critique:
            critique_section = f"\n**QA Critique:**\n{qa_critique[:600]}{'...' if len(qa_critique) > 600 else ''}\n"
        
        # Build Developer critique section
        dev_critique_section = ""
        if developer_critique:
            dev_critique_section = f"\n**Developer Critique (Technical Feasibility):**\n{developer_critique[:600]}{'...' if len(developer_critique) > 600 else ''}\n"
        
        # Build violations section
        violations_section = ""
        if violations_summary:
            violations_section = "\n**INVEST violations (e.g. Story too large):**\n" + "\n".join(
                f"- {v}" for v in violations_summary[:15]
            ) + "\n"
        
        # Build evidence section
        evidence_section = ""
        if evidence_summary:
            evidence_section = f"\n**Retrieved Evidence/Context:**\n{evidence_summary[:800]}{'...' if len(evidence_summary) > 800 else ''}\n"
        
        # Build refined story context section
        refined_section = ""
        if refined_story_context:
            refined_section = f"\n**Refined Story Context (from critique loop):**\n{refined_story_context[:600]}{'...' if len(refined_story_context) > 600 else ''}\n"

        ac_block = chr(10).join(f"- {ac}" for ac in artifact.acceptance_criteria) if artifact.acceptance_criteria else "None"
        
        # Fetch prompt from library with fallback
        system_prompt = await self._get_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""The following artifact has been assessed as too large or covering multiple distinct features. Your task is to propose splitting it into MULTIPLE smaller artifacts that TOGETHER preserve the FULL original scope. You MUST NOT drop any model or entity that appears in the original.

**Current artifact:**
Title: {artifact.title}
Description: {artifact.description}
Acceptance Criteria:
{ac_block}
{critique_section}{dev_critique_section}{violations_section}{evidence_section}{refined_section}

**CRITICAL RULES (follow strictly):**
1. **One artifact per model/entity when the original names multiple.** If the original mentions Order, Frame, and Glasses (or any other distinct models/entities), you MUST output one artifact for EACH of them (e.g. suggested_ref_suffix: "Order", "Frame", "Glasses"). Do NOT merge them into fewer artifacts (e.g. do NOT output only "Order" + "Migration" and drop Frame and Glasses).
2. **Preserve every acceptance criterion.** Each original AC must appear in exactly one of the proposed artifacts. If the original has "Order model can store...", "Frame model can store...", "Glasses model can store...", then you need at least three artifacts covering those.
3. **Use evidence and technical context.** Consider the developer's technical concerns and available evidence when designing the splits. Each split should be technically feasible and independently implementable.
4. Output at least 2 artifacts. Use suggested_ref_suffix for each (e.g. "Order", "Frame", "Glasses", or "Migration") for traceability.
5. Each proposed artifact must be a valid user story (title, description, acceptance criteria) and pass INVEST (Small, Independent, Testable).

Output your split proposal as JSON. Put your final JSON after FINAL_JSON:

FINAL_JSON:
{{
  "artifacts": [
    {{ "title": "...", "description": "...", "acceptance_criteria": ["..."], "suggested_ref_suffix": "Order" }},
    {{ "title": "...", "description": "...", "acceptance_criteria": ["..."], "suggested_ref_suffix": "Frame" }},
    {{ "title": "...", "description": "...", "acceptance_criteria": ["..."], "suggested_ref_suffix": "Glasses" }},
    ...
  ],
  "rationale": "Brief explanation of the split"
}}""",
            },
        ]

        # FIX Issue 3: Add error handling with retries
        # FIX Issue 7: Add observability logging
        logger.info(
            "po_agent.propose_artifact_split.start",
            artifact_id=artifact.source_id,
            has_qa_critique=bool(qa_critique),
            has_developer_critique=bool(developer_critique),
            violations_count=len(violations_summary) if violations_summary else 0,
        )
        
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                proposal = await self.llm_provider.structured_completion(
                    messages=messages,
                    response_model=ArtifactSplitProposal,
                    temperature=0.5,
                )
                
                logger.info(
                    "po_agent.propose_artifact_split.complete",
                    artifact_id=artifact.source_id,
                    proposed_count=len(proposal.artifacts) if proposal.artifacts else 0,
                    attempt=attempt + 1,
                )
                break
                
            except TimeoutError as e:
                last_error = e
                logger.warning(
                    "po_agent.propose_artifact_split.timeout",
                    artifact_id=artifact.source_id,
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise AgentError(f"Propose artifact split failed after {max_retries} attempts: {last_error}")
            except Exception as e:
                last_error = e
                logger.error(
                    "po_agent.propose_artifact_split.error",
                    artifact_id=artifact.source_id,
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise AgentError(f"Propose artifact split failed after {max_retries} attempts: {last_error}")

        # Build full CoreArtifact list from template artifact + each split item
        result: List[CoreArtifact] = []
        for i, item in enumerate(proposal.artifacts):
            ref_suffix = item.suggested_ref_suffix or str(i + 1)
            human_ref = f"{artifact.human_ref}-{ref_suffix}" if artifact.human_ref else f"split-{i + 1}"
            url = f"{artifact.url.rstrip('/')}-{ref_suffix}" if artifact.url else ""
            proposed = artifact.model_copy()
            proposed.title = item.title
            proposed.description = item.description
            proposed.acceptance_criteria = item.acceptance_criteria
            proposed.human_ref = human_ref
            proposed.url = url or proposed.url
            result.append(proposed)

        return result

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

