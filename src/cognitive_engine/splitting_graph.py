"""LangGraph workflow for Story Splitting with full multi-agent debate.

This matches the migush-repo flow with a deterministic path:
1. Drafting (PO creates artifact from story text)
2. QA Critique (INVEST validation)
3. Developer Critique (technical feasibility)
4. Synthesis (PO synthesizes feedback)
5. Validation (check confidence and violations)
6. Split Proposal (generate domain-specific splits)

Uses a deterministic flow (not supervisor-controlled) for reliability and speed.
"""

from typing import Any, Dict, List

from langgraph.graph import END, StateGraph

from src.cognitive_engine.agents.developer_agent import DeveloperAgent
from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
from src.cognitive_engine.agents.qa_agent import QAAgent
from src.cognitive_engine.state import CognitiveState
from src.domain.interfaces import ILLMProvider
from src.domain.schema import (
    CoreArtifact,
    NormalizedPriority,
    UASKnowledgeUnit,
    WorkItemStatus,
)


def _state_from_dict(state_dict: Dict[str, Any]) -> CognitiveState:
    """Convert state dictionary to CognitiveState."""
    return CognitiveState(**state_dict)


def _state_to_dict(state: CognitiveState) -> Dict[str, Any]:
    """Convert CognitiveState to dictionary."""
    return state.model_dump()


async def drafting_node(
    state_dict: Dict[str, Any],
    po_agent: ProductOwnerAgent,
) -> Dict[str, Any]:
    """Drafting node: PO Agent creates/refines artifact from story text."""
    state = _state_from_dict(state_dict)
    
    artifact_to_draft = state.current_artifact
    if not artifact_to_draft:
        return state_dict
    
    # Empty context for splitting flow
    context: List[UASKnowledgeUnit] = []
    
    draft = await po_agent.draft_artifact(artifact_to_draft, context)
    state.draft_artifact = draft
    state_dict = _state_to_dict(state)
    state_dict["_current_node"] = "drafting"
    return state_dict


async def qa_critique_node(
    state_dict: Dict[str, Any],
    qa_agent: QAAgent,
) -> Dict[str, Any]:
    """QA critique node: QA Agent validates INVEST criteria."""
    state = _state_from_dict(state_dict)
    if not state.draft_artifact:
        state_dict["_current_node"] = "qa_critique"
        return state_dict
    
    critique_result = await qa_agent.critique_artifact(state.draft_artifact)
    
    state.qa_critique = critique_result.get("critique")
    state.qa_confidence = critique_result.get("confidence")
    state.qa_overall_assessment = critique_result.get("overall_assessment")
    state.structured_qa_violations = critique_result.get("structured_violations", [])
    state.invest_violations = critique_result.get("violations", [])
    
    state_dict = _state_to_dict(state)
    state_dict["_current_node"] = "qa_critique"
    return state_dict


async def developer_critique_node(
    state_dict: Dict[str, Any],
    developer_agent: DeveloperAgent,
) -> Dict[str, Any]:
    """Developer critique node: Developer Agent assesses feasibility."""
    state = _state_from_dict(state_dict)
    if not state.draft_artifact:
        state_dict["_current_node"] = "developer_critique"
        return state_dict
    
    # Empty context for splitting flow
    context: List[UASKnowledgeUnit] = []
    
    assessment = await developer_agent.assess_feasibility(
        state.draft_artifact,
        context,
    )
    
    state.developer_critique = assessment.get("critique")
    state.developer_confidence = assessment.get("confidence")
    state.developer_feasibility = assessment.get("feasibility")
    
    state_dict = _state_to_dict(state)
    state_dict["_current_node"] = "developer_critique"
    return state_dict


async def synthesis_node(
    state_dict: Dict[str, Any],
    po_agent: ProductOwnerAgent,
) -> Dict[str, Any]:
    """Synthesis node: PO Agent synthesizes critiques into refined artifact."""
    state = _state_from_dict(state_dict)
    if not state.draft_artifact:
        state_dict["_current_node"] = "synthesis"
        return state_dict
    
    critiques = []
    if state.qa_critique:
        critiques.append(state.qa_critique)
    if state.developer_critique:
        critiques.append(state.developer_critique)
    
    if critiques:
        refined = await po_agent.synthesize_feedback(
            state.draft_artifact,
            critiques,
            violations=state.invest_violations,
        )
        state.refined_artifact = refined
    else:
        state.refined_artifact = state.draft_artifact
    
    # Record debate history
    debate_entry = {
        "iteration": 1,
        "qa_critique": state.qa_critique,
        "qa_confidence": state.qa_confidence,
        "developer_critique": state.developer_critique,
        "developer_confidence": state.developer_confidence,
        "invest_violations": list(state.invest_violations) if state.invest_violations else [],
    }
    state.debate_history.append(debate_entry)
    
    state_dict = _state_to_dict(state)
    state_dict["_current_node"] = "synthesis"
    return state_dict


def validation_node(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Validation node: Check confidence and INVEST violations."""
    state = _state_from_dict(state_dict)
    
    # Multi-factor confidence calculation
    qa_conf = state.qa_confidence if state.qa_confidence is not None else 0.5
    dev_conf = state.developer_confidence if state.developer_confidence is not None else 0.5
    
    # Base confidence from agents
    confidence = (qa_conf + dev_conf) / 2.0
    
    # Adjust for violations
    violation_count = len(state.invest_violations) + len(state.structured_qa_violations)
    if violation_count > 0:
        confidence *= max(0.3, 1.0 - (violation_count * 0.1))
    
    state.confidence_score = min(1.0, max(0.0, confidence))
    state.iteration_count = 1
    
    state_dict = _state_to_dict(state)
    state_dict["_current_node"] = "validation"
    return state_dict


async def split_proposal_node(
    state_dict: Dict[str, Any],
    po_agent: ProductOwnerAgent,
) -> Dict[str, Any]:
    """Split proposal node: Propose splitting into multiple smaller artifacts.
    
    Uses the ORIGINAL artifact to preserve full scope, not the refined one
    which may have been narrowed during synthesis.
    """
    state = _state_from_dict(state_dict)
    
    # Use original artifact to preserve full scope
    artifact = state.current_artifact or state.refined_artifact or state.draft_artifact
    if not artifact:
        state_dict["_current_node"] = "split_proposal"
        return state_dict
    
    # Build violations summary
    violations_summary: List[str] = []
    for v in state.structured_qa_violations:
        if hasattr(v, "criterion") and hasattr(v, "description"):
            violations_summary.append(f"{v.criterion}: {v.description}")
        elif isinstance(v, dict):
            violations_summary.append(f"{v.get('criterion', '?')}: {v.get('description', '')}")
    
    if state.invest_violations:
        for v in state.invest_violations:
            if isinstance(v, str) and v not in violations_summary:
                violations_summary.append(v)
    
    # Always add S violation for splitting
    violations_summary.append("S: Story covers multiple models/features and should be split")
    
    proposed = await po_agent.propose_artifact_split(
        artifact,
        qa_critique=state.qa_critique,
        violations_summary=violations_summary or None,
        developer_critique=state.developer_critique,
    )
    
    state.proposed_artifacts = proposed
    state_dict = _state_to_dict(state)
    state_dict["_current_node"] = "split_proposal"
    return state_dict


def create_splitting_graph(llm_provider: ILLMProvider) -> StateGraph:
    """Create and compile the multi-agent debate graph for story splitting.
    
    Uses a deterministic linear flow for reliability:
    drafting → qa_critique → dev_critique → synthesis → validation → split_proposal → END
    """
    # Initialize agents
    po_agent = ProductOwnerAgent(llm_provider)
    qa_agent = QAAgent(llm_provider)
    developer_agent = DeveloperAgent(llm_provider)
    
    graph = StateGraph(dict)
    
    # Node wrappers with agent closures
    async def drafting_wrapper(state):
        return await drafting_node(state, po_agent)
    
    async def qa_critique_wrapper(state):
        return await qa_critique_node(state, qa_agent)
    
    async def developer_critique_wrapper(state):
        return await developer_critique_node(state, developer_agent)
    
    async def synthesis_wrapper(state):
        return await synthesis_node(state, po_agent)
    
    def validation_wrapper(state):
        return validation_node(state)
    
    async def split_proposal_wrapper(state):
        return await split_proposal_node(state, po_agent)
    
    # Add nodes
    graph.add_node("drafting", drafting_wrapper)
    graph.add_node("qa_critique", qa_critique_wrapper)
    graph.add_node("developer_critique", developer_critique_wrapper)
    graph.add_node("synthesis", synthesis_wrapper)
    graph.add_node("validation", validation_wrapper)
    graph.add_node("split_proposal", split_proposal_wrapper)
    
    # Set entry point
    graph.set_entry_point("drafting")
    
    # Linear flow: each node leads to the next
    graph.add_edge("drafting", "qa_critique")
    graph.add_edge("qa_critique", "developer_critique")
    graph.add_edge("developer_critique", "synthesis")
    graph.add_edge("synthesis", "validation")
    graph.add_edge("validation", "split_proposal")
    graph.add_edge("split_proposal", END)
    
    return graph.compile()
