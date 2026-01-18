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

    # Add nodes with proper state conversion (async nodes need proper wrapping)
    async def ingress_wrapper(state):
        return await ingress_node(state, issue_tracker)
    
    async def context_assembly_wrapper(state):
        return await context_assembly_node(state, knowledge_base)
    
    async def drafting_wrapper(state):
        return await drafting_node(state, po_agent)
    
    async def qa_critique_wrapper(state):
        return await qa_critique_node(state, qa_agent, invest_validator)
    
    async def developer_critique_wrapper(state):
        return await developer_critique_node(state, developer_agent)
    
    async def synthesis_wrapper(state):
        return await synthesis_node(state, po_agent)
    
    async def execution_wrapper(state):
        return await execution_node(state, issue_tracker)
    
    graph.add_node("ingress", ingress_wrapper)
    graph.add_node("context_assembly", context_assembly_wrapper)
    graph.add_node("drafting", drafting_wrapper)
    graph.add_node("qa_critique", qa_critique_wrapper)
    graph.add_node("developer_critique", developer_critique_wrapper)
    graph.add_node("synthesis", synthesis_wrapper)
    graph.add_node("validation", validation_node)
    graph.add_node("execution", execution_wrapper)

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
