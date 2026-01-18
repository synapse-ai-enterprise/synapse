"""LangGraph node implementations."""

from typing import Any, Dict

from src.cognitive_engine.agents.developer_agent import DeveloperAgent
from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
from src.cognitive_engine.agents.qa_agent import QAAgent
from src.cognitive_engine.invest import InvestValidator
from src.cognitive_engine.state import CognitiveState
from src.domain.interfaces import IKnowledgeBase, IIssueTracker, ILLMProvider


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
    if not state.current_artifact:
        return state_dict

    draft = await po_agent.draft_artifact(
        state.current_artifact,
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

    # Get critique from QA agent
    critique_result = await qa_agent.critique_artifact(state.draft_artifact)

    # Get programmatic INVEST violations
    violations = invest_validator.validate(state.draft_artifact)

    state.qa_critique = critique_result["critique"]
    state.invest_violations = violations + critique_result["violations"]
    
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

    refined = await po_agent.synthesize_feedback(
        state.draft_artifact,
        critiques,
    )

    state.refined_artifact = refined
    return _state_to_dict(state)


async def validation_node(
    state_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Validation node: Check confidence and INVEST violations.

    Args:
        state_dict: Current cognitive state dictionary.

    Returns:
        Updated state dictionary with confidence score and iteration count.
    """
    state = _state_from_dict(state_dict)
    
    # Calculate confidence based on critiques
    confidence = 0.5  # Default

    # Increase confidence if no violations
    if not state.invest_violations:
        confidence = 0.8

    # Increase confidence if critiques are positive
    if state.qa_critique and "good" in state.qa_critique.lower():
        confidence += 0.1
    if state.developer_critique and "feasible" in state.developer_critique.lower():
        confidence += 0.1

    confidence = min(1.0, confidence)

    state.confidence_score = confidence
    state.iteration_count = state.iteration_count + 1

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
