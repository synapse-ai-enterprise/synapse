"""LangGraph node implementations."""

from typing import Any, Dict, List

from src.cognitive_engine.agents.developer_agent import DeveloperAgent
from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
from src.cognitive_engine.agents.qa_agent import QAAgent
from src.cognitive_engine.agents.supervisor import SupervisorAgent
from src.cognitive_engine.invest import InvestValidator
from src.cognitive_engine.state import CognitiveState
from src.domain.interfaces import IKnowledgeBase, IIssueTracker, ILLMProvider
from src.domain.schema import InvestViolation


def _state_from_dict(state_dict: Dict[str, Any]) -> CognitiveState:
    """Convert state dictionary to CognitiveState."""
    return CognitiveState(**state_dict)


def _state_to_dict(state: CognitiveState) -> Dict[str, Any]:
    """Convert CognitiveState to dictionary."""
    return state.model_dump()


async def ingress_node(
    state_dict: Dict[str, Any],
    issue_tracker: IIssueTracker,
) -> Dict[str, Any]:
    """Ingress node: Fetch artifact from issue tracker.

    Args:
        state_dict: Current cognitive state dictionary.
        issue_tracker: Issue tracker adapter.

    Returns:
        Updated state dictionary.
    """
    state = _state_from_dict(state_dict)
    artifact = await issue_tracker.get_issue(state.request.artifact_id)
    state.current_artifact = artifact
    return _state_to_dict(state)


async def context_assembly_node(
    state_dict: Dict[str, Any],
    knowledge_base: IKnowledgeBase,
) -> Dict[str, Any]:
    """Context assembly node: RAG search for relevant context.

    Args:
        state_dict: Current cognitive state dictionary.
        knowledge_base: Knowledge base adapter.

    Returns:
        Updated state dictionary.
    """
    state = _state_from_dict(state_dict)
    if not state.current_artifact:
        return state_dict

    # Search for relevant context
    query = f"{state.current_artifact.title} {state.current_artifact.description}"
    
    # Search both GitHub and Notion
    github_context = await knowledge_base.search(query, source="github", limit=5)
    notion_context = await knowledge_base.search(query, source="notion", limit=5)
    
    state.retrieved_context = github_context + notion_context
    
    return _state_to_dict(state)


async def drafting_node(
    state_dict: Dict[str, Any],
    po_agent: ProductOwnerAgent,
) -> Dict[str, Any]:
    """Drafting node: PO Agent generates draft artifact.

    Args:
        state_dict: Current cognitive state dictionary.
        po_agent: Product Owner agent.

    Returns:
        Updated state dictionary.
    """
    state = _state_from_dict(state_dict)
    
    # Use refined_artifact if available (from previous iteration), otherwise current_artifact
    artifact_to_draft = state.refined_artifact if state.refined_artifact else state.current_artifact
    
    if not artifact_to_draft:
        return state_dict

    draft = await po_agent.draft_artifact(
        artifact_to_draft,
        state.retrieved_context,
    )

    state.draft_artifact = draft
    return _state_to_dict(state)


async def qa_critique_node(
    state_dict: Dict[str, Any],
    qa_agent: QAAgent,
    invest_validator: InvestValidator,
) -> Dict[str, Any]:
    """QA critique node: QA Agent validates INVEST criteria.

    Args:
        state_dict: Current cognitive state dictionary.
        qa_agent: QA agent.
        invest_validator: INVEST validator.

    Returns:
        Updated state dictionary.
    """
    state = _state_from_dict(state_dict)
    if not state.draft_artifact:
        return state_dict

    try:
        # Get critique from QA agent
        critique_result = await qa_agent.critique_artifact(state.draft_artifact)

        # Get programmatic INVEST violations
        violations = invest_validator.validate(state.draft_artifact)

        state.qa_critique = critique_result["critique"]
        state.qa_confidence = critique_result.get("confidence")
        state.qa_overall_assessment = critique_result.get("overall_assessment")
        state.structured_qa_violations = critique_result.get("structured_violations", [])
        state.invest_violations = violations + critique_result["violations"]
    except Exception as e:
        raise
    
    return _state_to_dict(state)


async def developer_critique_node(
    state_dict: Dict[str, Any],
    developer_agent: DeveloperAgent,
) -> Dict[str, Any]:
    """Developer critique node: Developer Agent assesses feasibility.

    Args:
        state_dict: Current cognitive state dictionary.
        developer_agent: Developer agent.

    Returns:
        Updated state dictionary.
    """
    state = _state_from_dict(state_dict)
    if not state.draft_artifact:
        return state_dict

    assessment = await developer_agent.assess_feasibility(
        state.draft_artifact,
        state.retrieved_context,
    )

    state.developer_critique = assessment["critique"]
    state.developer_confidence = assessment.get("confidence")
    state.developer_feasibility = assessment.get("feasibility")
    return _state_to_dict(state)


async def synthesis_node(
    state_dict: Dict[str, Any],
    po_agent: ProductOwnerAgent,
) -> Dict[str, Any]:
    """Synthesis node: PO Agent synthesizes critiques.

    Args:
        state_dict: Current cognitive state dictionary.
        po_agent: Product Owner agent.

    Returns:
        Updated state dictionary.
    """
    state = _state_from_dict(state_dict)
    if not state.draft_artifact:
        return state_dict

    critiques = []
    if state.qa_critique:
        critiques.append(state.qa_critique)
    if state.developer_critique:
        critiques.append(state.developer_critique)

    if not critiques:
        return state_dict

    # Pass violations explicitly to help PO Agent address them
    refined = await po_agent.synthesize_feedback(
        state.draft_artifact,
        critiques,
        violations=state.invest_violations,
    )

    state.refined_artifact = refined
    
    # Record debate history entry for this iteration
    debate_entry = {
        "iteration": state.iteration_count + 1,
        "draft": {
            "title": state.draft_artifact.title,
            "description": state.draft_artifact.description[:500] + "..." if len(state.draft_artifact.description) > 500 else state.draft_artifact.description,
            "acceptance_criteria": state.draft_artifact.acceptance_criteria,
        },
        "qa_critique": state.qa_critique,
        "qa_confidence": state.qa_confidence,
        "qa_overall_assessment": state.qa_overall_assessment,
        "developer_critique": state.developer_critique,
        "developer_confidence": state.developer_confidence,
        "developer_feasibility": state.developer_feasibility,
        "invest_violations": state.invest_violations.copy(),
        "structured_violations": [
            v.model_dump() if hasattr(v, "model_dump") else v
            for v in state.structured_qa_violations
        ],
        "refined": {
            "title": refined.title,
            "description": refined.description[:500] + "..." if len(refined.description) > 500 else refined.description,
            "acceptance_criteria": refined.acceptance_criteria,
        },
    }
    state.debate_history.append(debate_entry)
    
    return _state_to_dict(state)


def validation_node(
    state_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Validation node: Check confidence and INVEST violations.

    Enhanced multi-factor confidence calculation using:
    - Agent confidence scores (QA and Developer)
    - Violation severity weighting
    - Critique quality analysis
    - Iteration improvement trends
    - Artifact quality indicators
    - Feasibility status
    
    Note: Routing decisions after validation are made by supervisor.
    """
    state_dict["_current_node"] = "validation"
    """Validation node: Check confidence and INVEST violations.

    Enhanced multi-factor confidence calculation using:
    - Agent confidence scores (QA and Developer)
    - Violation severity weighting
    - Critique quality analysis
    - Iteration improvement trends
    - Artifact quality indicators
    - Feasibility status

    Args:
        state_dict: Current cognitive state dictionary.

    Returns:
        Updated state dictionary with confidence score and iteration count.
    """
    state = _state_from_dict(state_dict)
    
    # Multi-factor confidence calculation
    factors = {
        "agent_confidence": 0.0,
        "violations": 0.0,
        "critique_quality": 0.0,
        "iteration_improvement": 0.0,
        "artifact_quality": 0.0,
        "feasibility": 0.0,
    }
    
    # Factor 1: Agent Confidence Scores (25% weight)
    # Use structured confidence from agents if available, otherwise default
    qa_conf = state.qa_confidence if state.qa_confidence is not None else 0.5
    dev_conf = state.developer_confidence if state.developer_confidence is not None else 0.5
    factors["agent_confidence"] = (qa_conf + dev_conf) / 2.0
    
    # Factor 2: Violation Resolution with Severity Weighting (30% weight)
    # Calculate weighted violation score based on severity
    severity_weights = {"critical": 1.0, "major": 0.6, "minor": 0.3}
    
    # Get previous violations from debate history or state_dict
    previous_violations = []
    if state.debate_history:
        prev_entry = state.debate_history[-1]
        if "structured_violations" in prev_entry:
            previous_violations = prev_entry["structured_violations"]
        elif "invest_violations" in prev_entry:
            # Fallback: try to reconstruct from string violations
            previous_violations = prev_entry["invest_violations"]
    
    # Calculate weighted violation scores
    def calculate_weighted_score(violations: List) -> float:
        """Calculate weighted violation score (0.0 = no violations, 1.0 = many critical violations)."""
        if not violations:
            return 0.0
        
        total_weight = 0.0
        for v in violations:
            # Handle InvestViolation objects
            if isinstance(v, InvestViolation):
                total_weight += severity_weights.get(v.severity, 0.3)
            # Handle dict representations
            elif isinstance(v, dict):
                severity = v.get("severity", "minor")
                if isinstance(severity, str):
                    total_weight += severity_weights.get(severity.lower(), 0.3)
                else:
                    total_weight += 0.3  # Default for unknown format
            else:
                # Fallback: assume medium severity for string violations
                total_weight += 0.3
        
        # Normalize: max possible is 6 critical violations (one per INVEST criterion)
        return min(1.0, total_weight / 6.0)
    
    current_weighted_score = calculate_weighted_score(state.structured_qa_violations)
    previous_weighted_score = calculate_weighted_score(previous_violations)
    
    if previous_weighted_score > 0:
        # Improvement ratio: how much did we reduce violations?
        improvement = (previous_weighted_score - current_weighted_score) / previous_weighted_score
        factors["violations"] = max(0.0, min(1.0, 0.5 + improvement))
    else:
        # First iteration or no previous violations
        if current_weighted_score == 0:
            factors["violations"] = 1.0  # Perfect: no violations
        else:
            factors["violations"] = 0.3  # New violations introduced
    
    # Factor 3: Critique Quality (20% weight)
    # Analyze critique text for quality indicators
    critique_indicators = {
        "positive": ["good", "excellent", "feasible", "clear", "specific", "well-defined", "comprehensive", "thorough"],
        "negative": ["vague", "unclear", "missing", "incomplete", "unfeasible", "ambiguous", "insufficient", "lacks"],
    }
    
    qa_text = (state.qa_critique or "").lower()
    dev_text = (state.developer_critique or "").lower()
    combined_text = qa_text + " " + dev_text
    
    positive_count = sum(1 for word in critique_indicators["positive"] if word in combined_text)
    negative_count = sum(1 for word in critique_indicators["negative"] if word in combined_text)
    
    # Also consider structured assessments
    if state.qa_overall_assessment:
        assessment_scores = {"excellent": 1.0, "good": 0.75, "needs_improvement": 0.5, "poor": 0.25}
        assessment_score = assessment_scores.get(state.qa_overall_assessment.lower(), 0.5)
    else:
        assessment_score = 0.5
    
    if positive_count + negative_count > 0:
        keyword_score = positive_count / (positive_count + negative_count)
        factors["critique_quality"] = (keyword_score * 0.6 + assessment_score * 0.4)
    else:
        factors["critique_quality"] = assessment_score
    
    # Factor 4: Iteration Improvement Trend (15% weight)
    if state.iteration_count > 0 and len(state.debate_history) >= 2:
        # Check if violations are decreasing over iterations
        violation_scores = []
        for entry in state.debate_history:
            if "structured_violations" in entry:
                violation_scores.append(calculate_weighted_score(entry["structured_violations"]))
            elif "invest_violations" in entry:
                violation_scores.append(calculate_weighted_score(entry["invest_violations"]))
        
        if len(violation_scores) >= 2:
            # Calculate trend: negative trend means violations decreasing (good)
            trend = violation_scores[0] - violation_scores[-1]
            # Normalize trend to 0-1 range (assuming max 6 violations)
            normalized_trend = max(0.0, min(1.0, (trend + 1.0) / 2.0))
            factors["iteration_improvement"] = normalized_trend
        else:
            factors["iteration_improvement"] = 0.5
    else:
        factors["iteration_improvement"] = 0.5
    
    # Factor 5: Artifact Quality Indicators (5% weight)
    artifact = state.refined_artifact or state.draft_artifact
    if artifact:
        quality_score = 0.5  # Base score
        
        # Check acceptance criteria quality
        if artifact.acceptance_criteria:
            ac_count = len(artifact.acceptance_criteria)
            if ac_count >= 3:
                quality_score += 0.2
            elif ac_count >= 1:
                quality_score += 0.1
        
        # Check for user story format ("so that" indicates value proposition)
        if "so that" in artifact.description.lower() or "as a" in artifact.description.lower():
            quality_score += 0.2
        
        # Check description length (not too short, not too long)
        desc_len = len(artifact.description)
        if 100 <= desc_len <= 1000:
            quality_score += 0.1
        
        factors["artifact_quality"] = min(1.0, quality_score)
    else:
        factors["artifact_quality"] = 0.0
    
    # Factor 6: Feasibility Status (5% weight)
    if state.developer_feasibility:
        feasibility_scores = {
            "feasible": 1.0,
            "requires_changes": 0.6,
            "blocked": 0.2,
        }
        factors["feasibility"] = feasibility_scores.get(state.developer_feasibility.lower(), 0.5)
    else:
        factors["feasibility"] = 0.5
    
    # Weighted combination
    confidence = (
        factors["agent_confidence"] * 0.25 +
        factors["violations"] * 0.30 +
        factors["critique_quality"] * 0.20 +
        factors["iteration_improvement"] * 0.15 +
        factors["artifact_quality"] * 0.05 +
        factors["feasibility"] * 0.05
    )
    
    # Ensure confidence is in valid range
    confidence = min(1.0, max(0.0, confidence))
    
    state.confidence_score = confidence
    state.iteration_count = state.iteration_count + 1
    
    # Update the latest debate entry with validation results
    if state.debate_history:
        state.debate_history[-1]["confidence_score"] = confidence
        state.debate_history[-1]["invest_violations"] = state.invest_violations.copy()
        state.debate_history[-1]["structured_violations"] = [
            v.model_dump() if hasattr(v, "model_dump") else v
            for v in state.structured_qa_violations
        ]

    return _state_to_dict(state)


async def execution_node(
    state_dict: Dict[str, Any],
    issue_tracker: IIssueTracker,
) -> Dict[str, Any]:
    """Execution node: Update Linear via adapter.

    Args:
        state_dict: Current cognitive state dictionary.
        issue_tracker: Issue tracker adapter.

    Returns:
        Updated state dictionary.
    """
    state = _state_from_dict(state_dict)
    if not state.refined_artifact:
        return state_dict

    # Use refined artifact if available, otherwise use draft
    artifact_to_update = state.refined_artifact or state.draft_artifact
    if not artifact_to_update:
        return state_dict

    # Update issue
    success = await issue_tracker.update_issue(
        state.request.artifact_id,
        artifact_to_update,
    )

    return {"execution_success": success, **_state_to_dict(state)}


async def supervisor_node(
    state_dict: Dict[str, Any],
    supervisor: SupervisorAgent,
    max_iterations: int = 3,
) -> Dict[str, Any]:
    """Supervisor node: Make intelligent routing decision.

    Args:
        state_dict: Current cognitive state dictionary.
        supervisor: Supervisor agent instance.
        max_iterations: Maximum number of debate iterations.

    Returns:
        Updated state dictionary with supervisor decision.
    """
    state = _state_from_dict(state_dict)
    
    # Track last node for context
    state_dict["_last_node"] = state_dict.get("_current_node", "unknown")
    
    # Make routing decision
    decision = await supervisor.decide_next_action(state_dict, max_iterations=max_iterations)
    
    # Store decision in state
    state_dict["supervisor_decision"] = decision.model_dump()
    state_dict["_next_action"] = decision.next_action
    state_dict["_should_continue"] = decision.should_continue
    state_dict["_priority_focus"] = decision.priority_focus
    
    return state_dict
