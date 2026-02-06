"""Supervisor orchestrator for multi-agent debate.

FIXES APPLIED (Feb 5, 2026):
- Issue 3: Added error handling around LLM calls with structured logging
- Issue 7: Added observability with structured logging and tracing
- Prompt Library Integration: Now fetches prompts dynamically from the Prompt Library
"""

from typing import Dict, List

from src.domain.interfaces import ILLMProvider
from src.domain.schema import CoreArtifact, SupervisorDecision
from src.infrastructure.prompt_library import get_prompt_library
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AgentError(Exception):
    """Exception raised when an agent operation fails."""
    pass


class SupervisorAgent:
    """Supervisor agent that orchestrates the multi-agent debate pattern.
    
    The supervisor monitors debate progress, makes intelligent routing decisions,
    and handles edge cases like agent disagreements or stagnation.
    """

    # Prompt ID for fetching from the library
    PROMPT_ID = "supervisor_system"

    # Default fallback prompt (used if prompt library fetch fails)
    DEFAULT_SYSTEM_PROMPT = """You are a Supervisor Agent orchestrating a multi-agent debate workflow for Agile artifact optimization.

Your role is to:
1. Monitor debate progress across Product Owner, QA, and Developer agents
2. Make intelligent routing decisions based on current state
3. Determine when to continue iterations or terminate the debate
4. Handle edge cases (agent disagreements, stagnation, quality issues)

Available actions:
- "draft": Route to Product Owner Agent to create/refine artifact
- "qa_critique": Route to QA Agent for INVEST validation
- "developer_critique": Route to Developer Agent for technical feasibility assessment
- "synthesize": Route to Product Owner Agent to synthesize feedback
- "validate": Route to validation node to check confidence and violations
- "execute": Route to execution node to update the issue tracker
- "propose_split": Route to split proposal when story is TOO LARGE (INVEST "S" violation) or covers MULTIPLE distinct features/models
- "end": Terminate the workflow (use only for critical failures)

Workflow pattern:
1. Initial: draft → qa_critique → developer_critique → synthesize → validate
2. If validation fails (low confidence or violations): loop back to draft
3. If validation succeeds: execute
4. Maximum 3 iterations before forced execution

Considerations:
- If QA and Developer agents strongly disagree, prioritize QA (quality over feasibility)
- If confidence is improving but slowly, allow more iterations
- If violations are increasing, route back to draft immediately
- If max iterations reached, route to execute even if not perfect
- If critical blocking issues found, consider ending early
- **IMPORTANT - STORY SPLITTING:** If there are persistent "S" (Small) violations indicating the story is TOO LARGE, 
  or the story covers MULTIPLE distinct features/models/entities that should be separate stories,
  route to "propose_split" instead of continuing the debate loop. Signs to split:
  * QA critique mentions "too large", "multiple features", "covers too much scope"
  * Violation mentions "S:" criterion failures
  * Story description mentions 3+ distinct models/entities (e.g., Order, Frame, Glasses)
  * After 2+ iterations, "S" violations persist despite refinement attempts

Be decisive but thoughtful. Your goal is efficient convergence to high-quality artifacts."""

    def __init__(self, llm_provider: ILLMProvider):
        """Initialize supervisor with LLM provider.

        Args:
            llm_provider: LLM provider for making routing decisions.
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
                    "supervisor.prompt_loaded",
                    prompt_id=self.PROMPT_ID,
                    source="prompt_library",
                )
                return template
        except Exception as e:
            logger.warning(
                "supervisor.prompt_load_failed",
                prompt_id=self.PROMPT_ID,
                error=str(e),
            )
        
        logger.debug(
            "supervisor.prompt_loaded",
            prompt_id=self.PROMPT_ID,
            source="fallback",
        )
        return self.DEFAULT_SYSTEM_PROMPT

    async def decide_next_action(
        self,
        state: Dict,
        max_iterations: int = 3,
    ) -> SupervisorDecision:
        """Make routing decision based on current state.

        Args:
            state: Current cognitive state dictionary.
            max_iterations: Maximum number of debate iterations allowed.

        Returns:
            SupervisorDecision with next action and reasoning.
        """
        # Extract key state information
        iteration_count = state.get("iteration_count", 0)
        confidence_score = state.get("confidence_score", 0.0)
        violations = state.get("invest_violations", [])
        structured_violations = state.get("structured_qa_violations", [])
        qa_confidence = state.get("qa_confidence")
        developer_confidence = state.get("developer_confidence")
        developer_feasibility = state.get("developer_feasibility")
        qa_assessment = state.get("qa_overall_assessment")
        debate_history = state.get("debate_history", [])
        
        # Count violations (both string and structured)
        violation_count = len(violations) + len(structured_violations)
        
        # Check for "S" (Small) violations specifically - indicates story too large
        has_small_violation = any(
            ("S:" in str(v) or "Small" in str(v) or "too large" in str(v).lower())
            for v in (violations + [sv.get("description", "") if isinstance(sv, dict) else str(sv) for sv in structured_violations])
        )
        
        # Analyze debate history for trends
        trend_analysis = self._analyze_trends(debate_history)
        
        # Build context for decision
        context = self._build_decision_context(
            iteration_count=iteration_count,
            confidence_score=confidence_score,
            violation_count=violation_count,
            qa_confidence=qa_confidence,
            developer_confidence=developer_confidence,
            developer_feasibility=developer_feasibility,
            qa_assessment=qa_assessment,
            trend_analysis=trend_analysis,
            max_iterations=max_iterations,
            has_small_violation=has_small_violation,
        )
        
        # Fetch prompt from library with fallback
        system_prompt = await self._get_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"""Analyze the current debate state and decide the next action:

**Current State:**
{context}

**Current Workflow Position:**
- Iteration: {iteration_count}/{max_iterations}
- Last completed node: {state.get('_last_node', 'unknown')}

**Task:**
1. Analyze the current state and debate progress
2. Determine the most appropriate next action
3. Decide whether to continue the debate loop
4. Identify priority focus area if continuing

Consider:
- If this is the first iteration, route to "draft"
- If draft exists but no QA critique, route to "qa_critique"
- If QA critique exists but no developer critique, route to "developer_critique"
- If both critiques exist but no synthesis, route to "synthesize"
- If synthesis exists, route to "validate"
- If validation shows low confidence/violations and iterations < max, route to "draft"
- If validation shows high confidence and no violations, route to "execute"
- If max iterations reached, route to "execute" regardless
- **SPLIT DECISION:** If "S" (Small) violations persist after 1+ iterations, OR the story covers 
  multiple distinct features/models, route to "propose_split" instead of continuing refinement.
  This is the RIGHT choice when the story scope is fundamentally too large to fix with rewording.

Return a JSON object with:
- "next_action": one of the action literals
- "reasoning": detailed explanation of your decision
- "should_continue": boolean indicating if debate should continue
- "priority_focus": optional focus area ("quality", "feasibility", "business_value", or "none")
- "confidence": your confidence in this routing decision (0.0-1.0)""",
            },
        ]
        
        # FIX Issue 3: Add error handling with retries
        # FIX Issue 7: Add observability logging
        logger.info(
            "supervisor.decide_next_action.start",
            iteration_count=iteration_count,
            max_iterations=max_iterations,
            violation_count=violation_count,
            has_small_violation=has_small_violation,
        )
        
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Use structured output
                decision = await self.llm_provider.structured_completion(
                    messages=messages,
                    response_model=SupervisorDecision,
                    temperature=0.3,  # Lower temperature for more consistent routing
                )
                
                logger.info(
                    "supervisor.decide_next_action.complete",
                    next_action=decision.next_action,
                    should_continue=decision.should_continue,
                    confidence=decision.confidence,
                    attempt=attempt + 1,
                )
                
                return decision
                
            except TimeoutError as e:
                last_error = e
                logger.warning(
                    "supervisor.decide_next_action.timeout",
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                last_error = e
                logger.error(
                    "supervisor.decide_next_action.error",
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
        
        # Fallback: If all retries fail, return a safe default decision
        logger.error(
            "supervisor.decide_next_action.failed_fallback",
            error=str(last_error),
            fallback_action="execute",
        )
        
        # Return a fallback decision to prevent workflow crash
        return SupervisorDecision(
            next_action="execute",
            reasoning=f"Fallback decision due to LLM error: {last_error}",
            should_continue=False,
            priority_focus="none",
            confidence=0.5,
        )

    def _analyze_trends(self, debate_history: List[Dict]) -> Dict[str, any]:
        """Analyze trends in debate history.

        Args:
            debate_history: List of debate iteration entries.

        Returns:
            Dictionary with trend analysis.
        """
        if not debate_history or len(debate_history) < 2:
            return {
                "confidence_trend": "unknown",
                "violation_trend": "unknown",
                "improving": False,
            }
        
        # Get confidence scores
        confidences = [
            entry.get("confidence_score", 0.0) for entry in debate_history
        ]
        
        # Get violation counts
        violation_counts = []
        for entry in debate_history:
            violations = entry.get("invest_violations", [])
            structured = entry.get("structured_violations", [])
            violation_counts.append(len(violations) + len(structured))
        
        # Calculate trends
        confidence_trend = "improving" if confidences[-1] > confidences[0] else "declining" if confidences[-1] < confidences[0] else "stable"
        violation_trend = "improving" if violation_counts[-1] < violation_counts[0] else "worsening" if violation_counts[-1] > violation_counts[0] else "stable"
        
        improving = confidence_trend == "improving" and violation_trend in ("improving", "stable")
        
        return {
            "confidence_trend": confidence_trend,
            "violation_trend": violation_trend,
            "improving": improving,
            "confidence_delta": confidences[-1] - confidences[0] if len(confidences) >= 2 else 0.0,
            "violation_delta": violation_counts[0] - violation_counts[-1] if len(violation_counts) >= 2 else 0,
        }

    def _build_decision_context(
        self,
        iteration_count: int,
        confidence_score: float,
        violation_count: int,
        qa_confidence: float | None,
        developer_confidence: float | None,
        developer_feasibility: str | None,
        qa_assessment: str | None,
        trend_analysis: Dict,
        max_iterations: int,
        has_small_violation: bool = False,
    ) -> str:
        """Build context string for decision making.

        Args:
            iteration_count: Current iteration number.
            confidence_score: Current confidence score.
            violation_count: Number of INVEST violations.
            qa_confidence: QA agent confidence.
            developer_confidence: Developer agent confidence.
            developer_feasibility: Developer feasibility assessment.
            qa_assessment: QA overall assessment.
            trend_analysis: Trend analysis dictionary.
            max_iterations: Maximum iterations allowed.
            has_small_violation: Whether "S" (Small) violations exist.

        Returns:
            Formatted context string.
        """
        lines = [
            f"- Iteration: {iteration_count}/{max_iterations}",
            f"- Overall Confidence: {confidence_score:.2f}",
            f"- INVEST Violations: {violation_count}",
        ]
        
        # Highlight "S" violations - important for split decision
        if has_small_violation:
            lines.append("- ⚠️ **SMALL VIOLATION DETECTED**: Story may be TOO LARGE - consider 'propose_split'")
        
        if qa_confidence is not None:
            lines.append(f"- QA Agent Confidence: {qa_confidence:.2f}")
        if developer_confidence is not None:
            lines.append(f"- Developer Agent Confidence: {developer_confidence:.2f}")
        if qa_assessment:
            lines.append(f"- QA Assessment: {qa_assessment}")
        if developer_feasibility:
            lines.append(f"- Developer Feasibility: {developer_feasibility}")
        
        if trend_analysis.get("improving") is not False:
            lines.append(f"- Trend: Confidence {trend_analysis.get('confidence_trend', 'unknown')}, "
                        f"Violations {trend_analysis.get('violation_trend', 'unknown')}")
            if trend_analysis.get("improving"):
                lines.append("- Status: Improving ✓")
            else:
                lines.append("- Status: Not improving ⚠️")
        
        return "\n".join(lines)
