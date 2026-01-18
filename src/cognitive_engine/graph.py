"""LangGraph workflow definition."""

from typing import Dict, Literal

from langgraph.graph import END, StateGraph

from src.cognitive_engine.agents.developer_agent import DeveloperAgent
from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
from src.cognitive_engine.agents.qa_agent import QAAgent
from src.cognitive_engine.invest import InvestValidator
from src.cognitive_engine.nodes import (
    context_assembly_node,
    developer_critique_node,
    drafting_node,
    execution_node,
    ingress_node,
    qa_critique_node,
    synthesis_node,
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
    invest_validator = InvestValidator()

    # Create graph with dict state (LangGraph works with dicts)
    graph = StateGraph(dict)

    # Add nodes with proper state conversion
    graph.add_node("ingress", lambda state: ingress_node(state, issue_tracker))
    graph.add_node("context_assembly", lambda state: context_assembly_node(state, knowledge_base))
    graph.add_node("drafting", lambda state: drafting_node(state, po_agent))
    graph.add_node("qa_critique", lambda state: qa_critique_node(state, qa_agent, invest_validator))
    graph.add_node("developer_critique", lambda state: developer_critique_node(state, developer_agent))
    graph.add_node("synthesis", lambda state: synthesis_node(state, po_agent))
    graph.add_node("validation", validation_node)
    graph.add_node("execution", lambda state: execution_node(state, issue_tracker))

    # Add edges
    graph.set_entry_point("ingress")
    graph.add_edge("ingress", "context_assembly")
    graph.add_edge("context_assembly", "drafting")
    graph.add_edge("drafting", "qa_critique")
    graph.add_edge("qa_critique", "developer_critique")
    graph.add_edge("developer_critique", "synthesis")
    graph.add_edge("synthesis", "validation")

    # Conditional edge from validation
    def should_execute(state: Dict) -> Literal["execution", "drafting"]:
        """Determine next step based on validation results.

        Args:
            state: Current state dictionary.

        Returns:
            Next node name.
        """
        confidence = state.get("confidence_score", 0.0)
        violations = state.get("invest_violations", [])
        iteration = state.get("iteration_count", 0)

        # High confidence and no violations -> execute
        if confidence > 0.8 and not violations:
            return "execution"

        # Low confidence or violations, and iterations < 3 -> retry
        if iteration < 3:
            return "drafting"

        # Max iterations reached -> execute with warning
        return "execution"

    graph.add_conditional_edges(
        "validation",
        should_execute,
        {
            "execution": "execution",
            "drafting": "drafting",
        },
    )
    graph.add_edge("execution", END)

    # Compile graph
    return graph.compile()
