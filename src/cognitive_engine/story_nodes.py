"""LangGraph node implementations for story writing workflow."""

from typing import Any, Dict, List

from src.cognitive_engine.agents.developer_agent import DeveloperAgent
from src.cognitive_engine.agents.epic_analysis_agent import EpicAnalysisAgent
from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
from src.cognitive_engine.agents.qa_agent import QAAgent
from src.cognitive_engine.agents.knowledge_retrieval_agent import KnowledgeRetrievalAgent
from src.cognitive_engine.agents.orchestrator_agent import OrchestratorAgent
from src.cognitive_engine.agents.splitting_strategy_agent import SplittingStrategyAgent
from src.cognitive_engine.agents.story_generation_agent import StoryGenerationAgent
from src.cognitive_engine.agents.story_writer_agent import StoryWriterAgent
from src.cognitive_engine.agents.template_parser_agent import TemplateParserAgent
from src.cognitive_engine.agents.validation_gap_agent import ValidationGapDetectionAgent
from src.cognitive_engine.story_state import StoryWritingState
from src.domain.interfaces import IKnowledgeBase, ILLMProvider
from src.domain.schema import (
    AcceptanceCriteriaItem,
    CoreArtifact,
    NormalizedPriority,
    PopulatedStory,
    RetrievedContext,
    RetrievedDoc,
    UASKnowledgeUnit,
    WorkItemStatus,
)


def _state_from_dict(state_dict: Dict[str, Any]) -> StoryWritingState:
    return StoryWritingState(**state_dict)


def _state_to_dict(state: StoryWritingState) -> Dict[str, Any]:
    return state.model_dump()


async def epic_analysis_node(
    state_dict: Dict[str, Any],
    agent: EpicAnalysisAgent,
) -> Dict[str, Any]:
    state = _state_from_dict(state_dict)
    if not state.request.epic_text:
        state.warnings.append("Epic text missing; cannot analyze.")
        return _state_to_dict(state)

    analysis = await agent.analyze_epic(
        epic_text=state.request.epic_text,
        epic_id=state.request.epic_id,
    )
    state.epic_analysis = analysis
    return _state_to_dict(state)


async def splitting_strategy_node(
    state_dict: Dict[str, Any],
    agent: SplittingStrategyAgent,
) -> Dict[str, Any]:
    state = _state_from_dict(state_dict)
    if not state.request.epic_text or not state.epic_analysis:
        state.warnings.append("Epic analysis missing; cannot recommend splits.")
        return _state_to_dict(state)

    result = await agent.recommend(state.request.epic_text, state.epic_analysis)
    state.splitting_recommendations = result.recommendations
    return _state_to_dict(state)


async def story_generation_node(
    state_dict: Dict[str, Any],
    agent: StoryGenerationAgent,
) -> Dict[str, Any]:
    state = _state_from_dict(state_dict)
    if not state.request.epic_text:
        state.warnings.append("Epic text missing; cannot generate stories.")
        return _state_to_dict(state)

    techniques = state.request.selected_techniques
    if not techniques and state.splitting_recommendations:
        techniques = [rec.technique for rec in state.splitting_recommendations[:3]]
        state.warnings.append("No techniques selected; defaulted to top recommendations.")

    result = await agent.generate_stories(
        epic_text=state.request.epic_text,
        techniques=techniques,
        parent_epic=state.request.epic_id,
    )
    state.generated_stories = result.stories
    return _state_to_dict(state)


async def template_parser_node(
    state_dict: Dict[str, Any],
    agent: TemplateParserAgent,
) -> Dict[str, Any]:
    state = _state_from_dict(state_dict)
    schema = await agent.parse(state.request.template_text or "")
    state.template_schema = schema
    return _state_to_dict(state)


async def knowledge_retrieval_node(
    state_dict: Dict[str, Any],
    agent: KnowledgeRetrievalAgent,
) -> Dict[str, Any]:
    state = _state_from_dict(state_dict)
    if not state.request.story_text:
        state.warnings.append("Story text missing; cannot retrieve context.")
        return _state_to_dict(state)

    context = await agent.retrieve(state.request.story_text)
    state.retrieved_context = context
    return _state_to_dict(state)


async def story_writer_node(
    state_dict: Dict[str, Any],
    agent: StoryWriterAgent,
) -> Dict[str, Any]:
    state = _state_from_dict(state_dict)
    if not state.request.story_text or not state.template_schema:
        state.warnings.append("Story or template schema missing; cannot write story.")
        return _state_to_dict(state)

    context = state.retrieved_context
    if context is None:
        state.warnings.append("Retrieved context missing; proceeding with empty context.")
        context = _empty_context()

    populated = await agent.write(
        story_text=state.request.story_text,
        template_schema=state.template_schema,
        context=context,
    )
    state.populated_story = populated
    return _state_to_dict(state)


async def validation_node(
    state_dict: Dict[str, Any],
    agent: ValidationGapDetectionAgent,
) -> Dict[str, Any]:
    state = _state_from_dict(state_dict)
    if not state.populated_story or not state.retrieved_context:
        state.warnings.append("Story or context missing; cannot validate.")
        return _state_to_dict(state)

    results = await agent.validate(state.populated_story, state.retrieved_context)
    state.validation_results = results
    return _state_to_dict(state)


async def critique_loop_node(
    state_dict: Dict[str, Any],
    qa_agent: QAAgent,
    developer_agent: DeveloperAgent,
    po_agent: ProductOwnerAgent,
) -> Dict[str, Any]:
    state = _state_from_dict(state_dict)
    if not state.populated_story:
        state.warnings.append("Story missing; cannot run critique loop.")
        return _state_to_dict(state)

    artifact = _core_artifact_from_story(state)
    qa_result = await qa_agent.critique_artifact(artifact)
    dev_context = _docs_to_knowledge_units(state.retrieved_context)
    dev_result = await developer_agent.assess_feasibility(artifact, dev_context)

    critiques = [qa_result.get("critique", ""), dev_result.get("critique", "")]
    refined_artifact = await po_agent.synthesize_feedback(
        artifact,
        critiques=[c for c in critiques if c],
        violations=qa_result.get("violations", []),
    )

    refined_story = _merge_refined_story(state.populated_story, refined_artifact)

    state.qa_critique = qa_result.get("critique")
    state.qa_confidence = qa_result.get("confidence")
    state.qa_overall_assessment = qa_result.get("overall_assessment")
    state.structured_qa_violations = qa_result.get("structured_violations", [])
    state.developer_critique = dev_result.get("critique")
    state.developer_confidence = dev_result.get("confidence")
    state.developer_feasibility = dev_result.get("feasibility")
    state.developer_dependencies = dev_result.get("dependencies", [])
    state.developer_concerns = dev_result.get("concerns", [])
    state.refined_story = refined_story
    state.populated_story = refined_story
    state.critique_history.append(
        {
            "qa_critique": state.qa_critique,
            "qa_confidence": state.qa_confidence,
            "qa_overall_assessment": state.qa_overall_assessment,
            "qa_violations": [
                v.model_dump() if hasattr(v, "model_dump") else v
                for v in state.structured_qa_violations
            ],
            "developer_critique": state.developer_critique,
            "developer_confidence": state.developer_confidence,
            "developer_feasibility": state.developer_feasibility,
            "developer_dependencies": state.developer_dependencies,
            "developer_concerns": state.developer_concerns,
        }
    )
    state.metadata.setdefault("critique_completed", True)
    state.metadata.setdefault("agent_confidence", {})
    state.metadata["agent_confidence"]["qa"] = state.qa_confidence
    state.metadata["agent_confidence"]["developer"] = state.developer_confidence
    return _state_to_dict(state)


def orchestrator_node(
    state_dict: Dict[str, Any],
    agent: OrchestratorAgent,
) -> Dict[str, Any]:
    decision = agent.decide_next_action(state_dict)
    state_dict["orchestrator_decision"] = decision.model_dump()
    state_dict["_next_action"] = decision.next_action
    return state_dict


def _empty_context() -> Any:
    from src.domain.schema import RetrievedContext

    return RetrievedContext()


def _core_artifact_from_story(state: StoryWritingState) -> CoreArtifact:
    story = state.populated_story
    title = story.title if story else "Untitled Story"
    description = story.description if story else state.request.story_text or ""
    acceptance_criteria = _acceptance_criteria_to_strings(
        story.acceptance_criteria if story else []
    )
    source_id = state.request.epic_id or state.request.project_id or "story_detail"
    human_ref = state.request.epic_id or "STORY-DETAIL"
    return CoreArtifact(
        source_system="story_detailing",
        source_id=source_id,
        human_ref=human_ref,
        url="",
        title=title,
        description=description,
        acceptance_criteria=acceptance_criteria,
        type="story",
        status=WorkItemStatus.TODO,
        priority=NormalizedPriority.MEDIUM,
        related_files=[],
        parent_ref=state.request.epic_id,
    )


def _acceptance_criteria_to_strings(
    items: List[AcceptanceCriteriaItem],
) -> List[str]:
    results: List[str] = []
    for item in items or []:
        if item.type == "gherkin":
            parts = []
            if item.scenario:
                parts.append(f"Scenario: {item.scenario}")
            if item.given:
                parts.append(f"Given {item.given}")
            if item.when:
                parts.append(f"When {item.when}")
            if item.then:
                parts.append(f"Then {item.then}")
            if parts:
                results.append(" ".join(parts))
        elif item.text:
            results.append(item.text)
    return results


def _merge_refined_story(
    story: PopulatedStory,
    refined: CoreArtifact,
) -> PopulatedStory:
    return PopulatedStory(
        title=refined.title,
        description=refined.description,
        acceptance_criteria=[
            AcceptanceCriteriaItem(type="free_form", text=item)
            for item in refined.acceptance_criteria or []
        ],
        dependencies=story.dependencies,
        nfrs=story.nfrs,
        out_of_scope=story.out_of_scope,
        assumptions=story.assumptions,
        open_questions=story.open_questions,
    )


def _docs_to_knowledge_units(context: RetrievedContext) -> List[UASKnowledgeUnit]:
    if not context:
        return []
    units: List[UASKnowledgeUnit] = []
    for doc in context.relevant_docs:
        units.append(_doc_to_unit(doc))
    return units


def _doc_to_unit(doc: RetrievedDoc) -> UASKnowledgeUnit:
    return UASKnowledgeUnit(
        id=doc.title,
        content=doc.excerpt,
        summary=doc.excerpt[:200],
        source="notion" if "notion" in doc.source.lower() else "github",
        last_updated="",
        topics=[],
        location=doc.source,
    )


def build_knowledge_retrieval_agent(
    llm_provider: ILLMProvider,
    knowledge_base: IKnowledgeBase,
) -> KnowledgeRetrievalAgent:
    return KnowledgeRetrievalAgent(llm_provider=llm_provider, knowledge_base=knowledge_base)
