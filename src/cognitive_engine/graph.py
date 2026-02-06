"""LangGraph workflow definition.

FIXES APPLIED (Feb 5, 2026):
- Issue 2: Added infinite loop protection with MAX_ITERATIONS cap
- Issue 8: Fixed state mutation in wrappers (use immutable updates)
"""

from typing import Dict, Literal

from langgraph.graph import END, StateGraph

from src.cognitive_engine.agents.developer_agent import DeveloperAgent
from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
from src.cognitive_engine.agents.qa_agent import QAAgent
from src.cognitive_engine.agents.supervisor import SupervisorAgent
from src.cognitive_engine.invest import InvestValidator
from src.cognitive_engine.nodes import (
    context_assembly_node,
    developer_critique_node,
    drafting_node,
    execution_node,
    ingress_node,
    qa_critique_node,
    split_proposal_node,
    synthesis_node,
    supervisor_node,
    validation_node,
)
from src.cognitive_engine.state import CognitiveState
from src.domain.interfaces import IKnowledgeBase, IIssueTracker, ILLMProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)

# FIX Issue 2: Hard cap on workflow iterations to prevent infinite loops
MAX_WORKFLOW_ITERATIONS = 10


def create_cognitive_graph(
    issue_tracker: IIssueTracker,
    knowledge_base: IKnowledgeBase,
    llm_provider: ILLMProvider,
) -> StateGraph:
    """Create and compile the cognitive engine graph.

    Args:
        issue_tracker: Issue tracker adapter.
        knowledge_base: Knowledge base adapter.
        llm_provider: LLM provider adapter.

    Returns:
        Compiled LangGraph StateGraph.
    """
    # Initialize agents
    po_agent = ProductOwnerAgent(llm_provider)
    qa_agent = QAAgent(llm_provider)
    developer_agent = DeveloperAgent(llm_provider)
    supervisor = SupervisorAgent(llm_provider)
    invest_validator = InvestValidator()

    # Create graph with dict state (LangGraph works with dicts)
    graph = StateGraph(dict)

    # FIX Issue 8: Add nodes with IMMUTABLE state updates (don't mutate input state)
    async def ingress_wrapper(state):
        state_copy = {**state, "_current_node": "ingress"}
        result = await ingress_node(state_copy, issue_tracker)
        return {**result, "_current_node": "ingress"}
    
    async def context_assembly_wrapper(state):
        state_copy = {**state, "_current_node": "context_assembly"}
        result = await context_assembly_node(state_copy, knowledge_base)
        return {**result, "_current_node": "context_assembly"}
    
    async def drafting_wrapper(state):
        state_copy = {**state, "_current_node": "drafting"}
        result = await drafting_node(state_copy, po_agent)
        return {**result, "_current_node": "drafting", "_last_node": "drafting"}
    
    async def qa_critique_wrapper(state):
        state_copy = {**state, "_current_node": "qa_critique"}
        result = await qa_critique_node(state_copy, qa_agent, invest_validator)
        return {**result, "_current_node": "qa_critique", "_last_node": "qa_critique"}
    
    async def developer_critique_wrapper(state):
        state_copy = {**state, "_current_node": "developer_critique"}
        result = await developer_critique_node(state_copy, developer_agent)
        return {**result, "_current_node": "developer_critique", "_last_node": "developer_critique"}
    
    async def synthesis_wrapper(state):
        state_copy = {**state, "_current_node": "synthesize"}
        result = await synthesis_node(state_copy, po_agent)
        return {**result, "_current_node": "synthesize", "_last_node": "synthesize"}
    
    async def supervisor_wrapper(state):
        state_copy = {**state, "_current_node": "supervisor"}
        # Increment routing count for infinite loop protection
        routing_count = state.get("_routing_count", 0) + 1
        state_copy["_routing_count"] = routing_count
        result = await supervisor_node(state_copy, supervisor, max_iterations=3)
        return {**result, "_current_node": "supervisor", "_routing_count": routing_count}
    
    async def execution_wrapper(state):
        state_copy = {**state, "_current_node": "execution"}
        result = await execution_node(state_copy, issue_tracker)
        return {**result, "_current_node": "execution"}
    
    async def split_proposal_wrapper(state):
        state_copy = {**state, "_current_node": "split_proposal"}
        result = await split_proposal_node(state_copy, po_agent)
        return {**result, "_current_node": "split_proposal"}
    
    graph.add_node("ingress", ingress_wrapper)
    graph.add_node("context_assembly", context_assembly_wrapper)
    graph.add_node("drafting", drafting_wrapper)
    graph.add_node("qa_critique", qa_critique_wrapper)
    graph.add_node("developer_critique", developer_critique_wrapper)
    graph.add_node("synthesize", synthesis_wrapper)
    graph.add_node("supervisor", supervisor_wrapper)
    graph.add_node("validation", validation_node)
    graph.add_node("execution", execution_wrapper)
    graph.add_node("split_proposal", split_proposal_wrapper)

    # Add edges - initial flow uses supervisor for routing
    graph.set_entry_point("ingress")
    graph.add_edge("ingress", "context_assembly")
    graph.add_edge("context_assembly", "supervisor")
    
    # Supervisor routes to appropriate agent based on state
    def supervisor_route(state: Dict) -> Literal["drafting", "qa_critique", "developer_critique", "synthesize", "validate", "execution", "split_proposal"]:
        """Route based on supervisor decision and full-round enforcement.

        Enforces full debate round (qa → developer → synthesize → validate) before
        allowing re-draft, so quality improves via full multi-agent input.

        FIX Issue 2: Added hard cap on iterations to prevent infinite loops.

        Args:
            state: Current state dictionary.

        Returns:
            Next node name based on supervisor decision.
        """
        # FIX Issue 2: Hard cap on routing iterations to prevent infinite loops
        routing_count = state.get("_routing_count", 0)
        iteration_count = state.get("iteration_count", 0)
        
        if routing_count >= MAX_WORKFLOW_ITERATIONS:
            logger.warning(
                "workflow_max_iterations_reached",
                routing_count=routing_count,
                iteration_count=iteration_count,
                forcing_termination=True,
            )
            return "execution"  # Force termination
        
        next_action = state.get("_next_action")
        last_node = state.get("_last_node", "unknown")
        draft_present = bool(state.get("draft_artifact"))
        qa_present = bool(state.get("qa_critique"))
        developer_present = bool(state.get("developer_critique"))
        refined_present = bool(state.get("refined_artifact"))

        # Enforce full debate round: complete qa → developer → synthesize → validate
        # before allowing another draft (improves quality by using all agent input).
        if last_node == "qa_critique" and qa_present and not developer_present:
            return "developer_critique"
        if last_node == "developer_critique" and developer_present and not refined_present:
            return "synthesize"
        if last_node == "synthesize" and refined_present:
            return "validate"

        # Safety cap: if supervisor chose "draft" but we just finished drafting,
        # route to qa_critique to start the round.
        if next_action == "draft" and draft_present and last_node == "drafting":
            return "qa_critique"
        
        # Map supervisor actions to node names
        action_map = {
            "draft": "drafting",
            "qa_critique": "qa_critique",
            "developer_critique": "developer_critique",
            "synthesize": "synthesize",
            "validate": "validate",
            "execute": "execution",
            "propose_split": "split_proposal",
        }
        
        # Default routing logic if supervisor hasn't decided yet
        if not next_action:
            # Initial flow: draft -> qa -> developer -> synthesize -> validate
            if not draft_present:
                return "drafting"
            elif not qa_present:
                return "qa_critique"
            elif not developer_present:
                return "developer_critique"
            elif not refined_present:
                return "synthesize"
            else:
                return "validate"
        
        # Handle "end" action by routing to execution (graceful termination)
        if next_action == "end":
            return "execution"
        
        return action_map.get(next_action, "validate")
    
    graph.add_conditional_edges(
        "supervisor",
        supervisor_route,
        {
            "drafting": "drafting",
            "qa_critique": "qa_critique",
            "developer_critique": "developer_critique",
            "synthesize": "synthesize",
            "validate": "validation",
            "execution": "execution",
            "split_proposal": "split_proposal",
        },
    )
    
    # After each agent completes, route back to supervisor for next decision
    graph.add_edge("drafting", "supervisor")
    graph.add_edge("qa_critique", "supervisor")
    graph.add_edge("developer_critique", "supervisor")
    graph.add_edge("synthesize", "supervisor")
    
    # After validation, route to supervisor for final decision
    graph.add_edge("validation", "supervisor")
    
    # Terminal nodes
    graph.add_edge("execution", END)
    graph.add_edge("split_proposal", END)

    # Compile graph
    return graph.compile()
