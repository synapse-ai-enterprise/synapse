"""LangGraph workflow for Product Story Writing AI."""

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
    splitting_strategy_node,
    story_generation_node,
    story_writer_node,
    template_parser_node,
    validation_node,
)
from src.domain.interfaces import IKnowledgeBase, ILLMProvider


def create_story_writing_graph(
    knowledge_base: IKnowledgeBase,
    llm_provider: ILLMProvider,
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

    async def epic_wrapper(state):
        state["_current_node"] = "epic_analysis"
        return await epic_analysis_node(state, epic_agent)

    async def splitting_wrapper(state):
        state["_current_node"] = "splitting_strategy"
        return await splitting_strategy_node(state, splitting_agent)

    async def generation_wrapper(state):
        state["_current_node"] = "story_generation"
        return await story_generation_node(state, generation_agent)

    async def template_wrapper(state):
        state["_current_node"] = "template_parser"
        return await template_parser_node(state, template_agent)

    async def retrieval_wrapper(state):
        state["_current_node"] = "knowledge_retrieval"
        return await knowledge_retrieval_node(state, retrieval_agent)

    async def writer_wrapper(state):
        state["_current_node"] = "story_writer"
        return await story_writer_node(state, writer_agent)

    async def validation_wrapper(state):
        state["_current_node"] = "validation"
        return await validation_node(state, validation_agent)

    async def critique_loop_wrapper(state):
        state["_current_node"] = "critique_loop"
        return await critique_loop_node(state, qa_agent, developer_agent, po_agent)

    def orchestrator_wrapper(state):
        state["_current_node"] = "orchestrator"
        return orchestrator_node(state, orchestrator)

    graph.add_node("orchestrator", orchestrator_wrapper)
    graph.add_node("epic_analysis", epic_wrapper)
    graph.add_node("splitting_strategy", splitting_wrapper)
    graph.add_node("story_generation", generation_wrapper)
    graph.add_node("template_parser", template_wrapper)
    graph.add_node("knowledge_retrieval", retrieval_wrapper)
    graph.add_node("story_writer", writer_wrapper)
    graph.add_node("validation", validation_wrapper)
    graph.add_node("critique_loop", critique_loop_wrapper)

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
        "__end__",
    ]:
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

    return graph.compile()
