"""LangGraph workflow for Product Story Writing AI.

FIXES APPLIED (Feb 5, 2026):
- Issue 2: Added infinite loop protection with MAX_ITERATIONS cap
- Issue 4: Fixed sync/async mismatch in orchestrator_wrapper
- Issue 8: Fixed state mutation in wrappers (use immutable updates)
"""

from typing import Dict, Literal

from langgraph.graph import END, StateGraph

from src.cognitive_engine.agents.developer_agent import DeveloperAgent
from src.cognitive_engine.agents.epic_analysis_agent import EpicAnalysisAgent
from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
from src.cognitive_engine.agents.qa_agent import QAAgent
from src.cognitive_engine.agents.orchestrator_agent import OrchestratorAgent
from src.cognitive_engine.agents.splitting_strategy_agent import SplittingStrategyAgent
from src.cognitive_engine.agents.story_generation_agent import StoryGenerationAgent
from src.cognitive_engine.agents.story_writer_agent import StoryWriterAgent
from src.cognitive_engine.agents.template_parser_agent import TemplateParserAgent
from src.cognitive_engine.agents.validation_gap_agent import ValidationGapDetectionAgent
from src.cognitive_engine.story_nodes import (
    critique_loop_node,
    build_knowledge_retrieval_agent,
    epic_analysis_node,
    knowledge_retrieval_node,
    orchestrator_node,
    split_proposal_node,
    splitting_strategy_node,
    story_generation_node,
    story_writer_node,
    template_parser_node,
    validation_node,
)
from src.domain.interfaces import IContextGraphStore, IKnowledgeBase, ILLMProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)

# FIX Issue 2: Hard cap on workflow iterations to prevent infinite loops
MAX_STORY_WORKFLOW_ITERATIONS = 15


def create_story_writing_graph(
    knowledge_base: IKnowledgeBase,
    llm_provider: ILLMProvider,
    context_graph_store: IContextGraphStore | None = None,
) -> StateGraph:
    """Create and compile the story writing graph."""
    orchestrator = OrchestratorAgent()
    epic_agent = EpicAnalysisAgent(llm_provider)
    splitting_agent = SplittingStrategyAgent(llm_provider)
    generation_agent = StoryGenerationAgent(llm_provider)
    template_agent = TemplateParserAgent(llm_provider)
    retrieval_agent = build_knowledge_retrieval_agent(llm_provider, knowledge_base)
    writer_agent = StoryWriterAgent(llm_provider)
    validation_agent = ValidationGapDetectionAgent(llm_provider)
    qa_agent = QAAgent(llm_provider)
    developer_agent = DeveloperAgent(llm_provider)
    po_agent = ProductOwnerAgent(llm_provider)

    graph = StateGraph(dict)

    # FIX Issue 8: Add nodes with IMMUTABLE state updates (don't mutate input state)
    async def epic_wrapper(state):
        state_copy = {**state, "_current_node": "epic_analysis"}
        result = await epic_analysis_node(state_copy, epic_agent)
        return {**result, "_current_node": "epic_analysis"}

    async def splitting_wrapper(state):
        state_copy = {**state, "_current_node": "splitting_strategy"}
        result = await splitting_strategy_node(state_copy, splitting_agent)
        return {**result, "_current_node": "splitting_strategy"}

    async def generation_wrapper(state):
        state_copy = {**state, "_current_node": "story_generation"}
        result = await story_generation_node(state_copy, generation_agent)
        return {**result, "_current_node": "story_generation"}

    async def template_wrapper(state):
        state_copy = {**state, "_current_node": "template_parser"}
        result = await template_parser_node(state_copy, template_agent)
        return {**result, "_current_node": "template_parser"}

    async def retrieval_wrapper(state):
        state_copy = {**state, "_current_node": "knowledge_retrieval"}
        result = await knowledge_retrieval_node(
            state_copy,
            retrieval_agent,
            context_graph_store=context_graph_store,
        )
        return {**result, "_current_node": "knowledge_retrieval"}

    async def writer_wrapper(state):
        state_copy = {**state, "_current_node": "story_writer"}
        result = await story_writer_node(state_copy, writer_agent)
        return {**result, "_current_node": "story_writer"}

    async def validation_wrapper(state):
        state_copy = {**state, "_current_node": "validation"}
        result = await validation_node(state_copy, validation_agent)
        return {**result, "_current_node": "validation"}

    async def critique_loop_wrapper(state):
        state_copy = {**state, "_current_node": "critique_loop"}
        result = await critique_loop_node(state_copy, qa_agent, developer_agent, po_agent)
        return {**result, "_current_node": "critique_loop"}

    async def split_proposal_wrapper(state):
        state_copy = {**state, "_current_node": "split_proposal"}
        result = await split_proposal_node(state_copy, po_agent)
        return {**result, "_current_node": "split_proposal"}

    # FIX Issue 4: Made orchestrator_wrapper async for consistency
    async def orchestrator_wrapper(state):
        # Increment routing count for infinite loop protection
        routing_count = state.get("_routing_count", 0) + 1
        state_copy = {**state, "_current_node": "orchestrator", "_routing_count": routing_count}
        result = orchestrator_node(state_copy, orchestrator)
        return {**result, "_current_node": "orchestrator", "_routing_count": routing_count}

    graph.add_node("orchestrator", orchestrator_wrapper)
    graph.add_node("epic_analysis", epic_wrapper)
    graph.add_node("splitting_strategy", splitting_wrapper)
    graph.add_node("story_generation", generation_wrapper)
    graph.add_node("template_parser", template_wrapper)
    graph.add_node("knowledge_retrieval", retrieval_wrapper)
    graph.add_node("story_writer", writer_wrapper)
    graph.add_node("validation", validation_wrapper)
    graph.add_node("critique_loop", critique_loop_wrapper)
    graph.add_node("split_proposal", split_proposal_wrapper)

    graph.set_entry_point("orchestrator")

    def route(state: Dict) -> Literal[
        "epic_analysis",
        "splitting_strategy",
        "story_generation",
        "template_parser",
        "knowledge_retrieval",
        "story_writer",
        "validation",
        "critique_loop",
        "split_proposal",
        "__end__",
    ]:
        # FIX Issue 2: Hard cap on routing iterations to prevent infinite loops
        routing_count = state.get("_routing_count", 0)
        
        if routing_count >= MAX_STORY_WORKFLOW_ITERATIONS:
            logger.warning(
                "story_workflow_max_iterations_reached",
                routing_count=routing_count,
                forcing_termination=True,
            )
            return "__end__"  # Force termination
        
        action = state.get("_next_action", "end")
        mapping = {
            "epic_analysis": "epic_analysis",
            "splitting_strategy": "splitting_strategy",
            "story_generation": "story_generation",
            "template_parser": "template_parser",
            "knowledge_retrieval": "knowledge_retrieval",
            "story_writer": "story_writer",
            "validation": "validation",
            "critique_loop": "critique_loop",
            "split_proposal": "split_proposal",
            "end": "__end__",
        }
        return mapping.get(action, "__end__")

    graph.add_conditional_edges(
        "orchestrator",
        route,
        {
            "epic_analysis": "epic_analysis",
            "splitting_strategy": "splitting_strategy",
            "story_generation": "story_generation",
            "template_parser": "template_parser",
            "knowledge_retrieval": "knowledge_retrieval",
            "story_writer": "story_writer",
            "validation": "validation",
            "critique_loop": "critique_loop",
            "split_proposal": "split_proposal",
            "__end__": END,
        },
    )

    graph.add_edge("epic_analysis", "orchestrator")
    graph.add_edge("splitting_strategy", "orchestrator")
    graph.add_edge("story_generation", "orchestrator")
    graph.add_edge("template_parser", "orchestrator")
    graph.add_edge("knowledge_retrieval", "orchestrator")
    graph.add_edge("story_writer", "orchestrator")
    graph.add_edge("validation", "orchestrator")
    graph.add_edge("critique_loop", "orchestrator")
    graph.add_edge("split_proposal", "orchestrator")

    return graph.compile()
