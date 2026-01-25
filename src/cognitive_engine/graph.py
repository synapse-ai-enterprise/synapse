"""LangGraph workflow definition."""

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
    synthesis_node,
    supervisor_node,
    validation_node,
)
from src.cognitive_engine.state import CognitiveState
from src.domain.interfaces import IKnowledgeBase, IIssueTracker, ILLMProvider


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

    # Add nodes with proper state conversion (async nodes need proper wrapping)
    async def ingress_wrapper(state):
        state["_current_node"] = "ingress"
        return await ingress_node(state, issue_tracker)
    
    async def context_assembly_wrapper(state):
        state["_current_node"] = "context_assembly"
        return await context_assembly_node(state, knowledge_base)
    
    async def drafting_wrapper(state):
        state["_current_node"] = "drafting"
        return await drafting_node(state, po_agent)
    
    async def qa_critique_wrapper(state):
        state["_current_node"] = "qa_critique"
        return await qa_critique_node(state, qa_agent, invest_validator)
    
    async def developer_critique_wrapper(state):
        state["_current_node"] = "developer_critique"
        return await developer_critique_node(state, developer_agent)
    
    async def synthesis_wrapper(state):
        state["_current_node"] = "synthesize"
        return await synthesis_node(state, po_agent)
    
    async def supervisor_wrapper(state):
        state["_current_node"] = "supervisor"
        return await supervisor_node(state, supervisor, max_iterations=3)
    
    async def execution_wrapper(state):
        state["_current_node"] = "execution"
        return await execution_node(state, issue_tracker)
    
    graph.add_node("ingress", ingress_wrapper)
    graph.add_node("context_assembly", context_assembly_wrapper)
    graph.add_node("drafting", drafting_wrapper)
    graph.add_node("qa_critique", qa_critique_wrapper)
    graph.add_node("developer_critique", developer_critique_wrapper)
    graph.add_node("synthesize", synthesis_wrapper)
    graph.add_node("supervisor", supervisor_wrapper)
    graph.add_node("validation", validation_node)
    graph.add_node("execution", execution_wrapper)

    # Add edges - initial flow uses supervisor for routing
    graph.set_entry_point("ingress")
    graph.add_edge("ingress", "context_assembly")
    graph.add_edge("context_assembly", "supervisor")
    
    # Supervisor routes to appropriate agent based on state
    def supervisor_route(state: Dict) -> Literal["drafting", "qa_critique", "developer_critique", "synthesize", "validate", "execution"]:
        """Route based on supervisor decision.

        Args:
            state: Current state dictionary.

        Returns:
            Next node name based on supervisor decision.
        """
        next_action = state.get("_next_action")
        
        # Map supervisor actions to node names
        action_map = {
            "draft": "drafting",
            "qa_critique": "qa_critique",
            "developer_critique": "developer_critique",
            "synthesize": "synthesize",
            "validate": "validate",
            "execute": "execution",
        }
        
        # Default routing logic if supervisor hasn't decided yet
        if not next_action:
            # Initial flow: draft -> qa -> developer -> synthesize -> validate
            if not state.get("draft_artifact"):
                return "drafting"
            elif not state.get("qa_critique"):
                return "qa_critique"
            elif not state.get("developer_critique"):
                return "developer_critique"
            elif not state.get("refined_artifact"):
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
        },
    )
    
    # After each agent completes, route back to supervisor for next decision
    graph.add_edge("drafting", "supervisor")
    graph.add_edge("qa_critique", "supervisor")
    graph.add_edge("developer_critique", "supervisor")
    graph.add_edge("synthesize", "supervisor")
    
    # After validation, route to supervisor for final decision
    graph.add_edge("validation", "supervisor")
    
    # Execution is terminal
    graph.add_edge("execution", END)

    # Compile graph
    return graph.compile()
