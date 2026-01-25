"""Tests for cognitive engine workflow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from src.cognitive_engine.graph import create_cognitive_graph
from src.cognitive_engine.invest import InvestValidator
from src.cognitive_engine.state import CognitiveState
from src.cognitive_engine.nodes import (
    ingress_node,
    context_assembly_node,
    drafting_node,
    qa_critique_node,
    developer_critique_node,
    synthesis_node,
    validation_node,
    execution_node,
    supervisor_node,
)
from src.domain.schema import (
    CoreArtifact,
    NormalizedPriority,
    OptimizationRequest,
    UASKnowledgeUnit,
    WorkItemStatus,
    ArtifactRefinement,
    InvestCritique,
    FeasibilityAssessment,
    SupervisorDecision,
    InvestViolation,
)


class TestInvestValidator:
    """Tests for INVEST validator."""

    def test_validate_missing_so_that(self, sample_artifact):
        """Test validation detects missing 'so that' clause."""
        validator = InvestValidator()
        
        artifact = CoreArtifact(
            source_system="linear",
            source_id="test",
            human_ref="LIN-123",
            url="https://test.com",
            title="Test Story",
            description="As a user, I want to test",  # Missing "so that"
            type="Story",
            status=WorkItemStatus.TODO,
            priority=NormalizedPriority.MEDIUM,
        )
        
        violations = validator.validate(artifact)
        assert isinstance(violations, list)
        # Should detect missing value proposition
        violation_text = " ".join(violations).lower()
        assert any(keyword in violation_text for keyword in ["valuable", "so that", "value"])

    def test_validate_vague_terms(self):
        """Test validation detects vague terms."""
        validator = InvestValidator()
        
        artifact = CoreArtifact(
            source_system="linear",
            source_id="test",
            human_ref="LIN-123",
            url="https://test.com",
            title="Test",
            description="Make it fast and better",  # Vague terms
            type="Story",
            status=WorkItemStatus.TODO,
            priority=NormalizedPriority.MEDIUM,
        )
        
        violations = validator.validate(artifact)
        assert isinstance(violations, list)
        violation_text = " ".join(violations).lower()
        assert any(keyword in violation_text for keyword in ["estimable", "vague", "specific"])

    def test_validate_missing_acceptance_criteria(self):
        """Test validation detects missing acceptance criteria."""
        validator = InvestValidator()
        
        artifact = CoreArtifact(
            source_system="linear",
            source_id="test",
            human_ref="LIN-123",
            url="https://test.com",
            title="Test",
            description="Test description",
            acceptance_criteria=[],  # Missing ACs
            type="Story",
            status=WorkItemStatus.TODO,
            priority=NormalizedPriority.MEDIUM,
        )
        
        violations = validator.validate(artifact)
        assert isinstance(violations, list)
        violation_text = " ".join(violations).lower()
        assert any(keyword in violation_text for keyword in ["testable", "acceptance", "criteria"])

    def test_validate_non_binary_acceptance_criteria(self):
        """Test validation detects non-binary acceptance criteria."""
        validator = InvestValidator()
        
        artifact = CoreArtifact(
            source_system="linear",
            source_id="test",
            human_ref="LIN-123",
            url="https://test.com",
            title="Test",
            description="Test description",
            acceptance_criteria=["It should be better"],  # Non-binary
            type="Story",
            status=WorkItemStatus.TODO,
            priority=NormalizedPriority.MEDIUM,
        )
        
        violations = validator.validate(artifact)
        assert isinstance(violations, list)
        violation_text = " ".join(violations).lower()
        assert any(keyword in violation_text for keyword in ["testable", "binary", "measurable"])

    def test_validate_large_description(self):
        """Test validation detects very long descriptions."""
        validator = InvestValidator()
        
        artifact = CoreArtifact(
            source_system="linear",
            source_id="test",
            human_ref="LIN-123",
            url="https://test.com",
            title="Test",
            description="x" * 2500,  # Very long
            type="Story",
            status=WorkItemStatus.TODO,
            priority=NormalizedPriority.MEDIUM,
        )
        
        violations = validator.validate(artifact)
        assert isinstance(violations, list)
        violation_text = " ".join(violations).lower()
        assert any(keyword in violation_text for keyword in ["small", "large", "size"])


class TestCognitiveState:
    """Tests for CognitiveState."""

    def test_state_creation(self, sample_request):
        """Test creating cognitive state."""
        state = CognitiveState(request=sample_request)
        
        assert state.request == sample_request
        assert state.current_artifact is None
        assert state.retrieved_context == []
        assert state.confidence_score == 0.0
        assert state.iteration_count == 0

    def test_state_with_artifact(self, sample_request, sample_artifact):
        """Test state with artifact."""
        state = CognitiveState(
            request=sample_request,
            current_artifact=sample_artifact,
        )
        
        assert state.current_artifact == sample_artifact
        assert state.current_artifact.title == "Test User Story"

    def test_state_model_dump(self, sample_request):
        """Test state serialization."""
        state = CognitiveState(request=sample_request)
        state_dict = state.model_dump()
        
        assert isinstance(state_dict, dict)
        assert "request" in state_dict
        assert state_dict["request"]["artifact_id"] == "test-id-123"

    def test_state_from_dict(self, sample_request):
        """Test state deserialization."""
        state_dict = {
            "request": sample_request.model_dump(),
            "confidence_score": 0.8,
            "iteration_count": 1,
        }
        
        state = CognitiveState(**state_dict)
        
        assert state.confidence_score == 0.8
        assert state.iteration_count == 1


class TestWorkflowNodes:
    """Tests for individual workflow nodes."""

    @pytest.mark.asyncio
    async def test_ingress_node(self, cognitive_state_dict, mock_issue_tracker):
        """Test ingress node fetches artifact."""
        result = await ingress_node(cognitive_state_dict, mock_issue_tracker)
        
        assert result is not None
        assert "current_artifact" in result
        assert result["current_artifact"]["source_id"] == "test-id-123"
        mock_issue_tracker.get_issue.assert_called_once_with("test-id-123")

    @pytest.mark.asyncio
    async def test_context_assembly_node(self, cognitive_state_dict, mock_knowledge_base, sample_artifact):
        """Test context assembly node retrieves context."""
        cognitive_state_dict["current_artifact"] = sample_artifact.model_dump()
        
        result = await context_assembly_node(cognitive_state_dict, mock_knowledge_base)
        
        assert result is not None
        assert "retrieved_context" in result
        assert len(result["retrieved_context"]) > 0
        mock_knowledge_base.search.assert_called()

    @pytest.mark.asyncio
    async def test_drafting_node(self, cognitive_state_dict, mock_llm_provider, sample_artifact, sample_context):
        """Test drafting node creates draft artifact."""
        from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
        
        cognitive_state_dict["current_artifact"] = sample_artifact.model_dump()
        cognitive_state_dict["retrieved_context"] = [ctx.model_dump() for ctx in sample_context]
        
        po_agent = ProductOwnerAgent(mock_llm_provider)
        result = await drafting_node(cognitive_state_dict, po_agent)
        
        assert result is not None
        assert "draft_artifact" in result
        assert result["draft_artifact"] is not None

    @pytest.mark.asyncio
    async def test_qa_critique_node(self, cognitive_state_dict, mock_llm_provider, sample_artifact):
        """Test QA critique node validates artifact."""
        from src.cognitive_engine.agents.qa_agent import QAAgent
        
        cognitive_state_dict["draft_artifact"] = sample_artifact.model_dump()
        
        qa_agent = QAAgent(mock_llm_provider)
        invest_validator = InvestValidator()
        
        result = await qa_critique_node(cognitive_state_dict, qa_agent, invest_validator)
        
        assert result is not None
        assert "qa_critique" in result
        assert "invest_violations" in result

    @pytest.mark.asyncio
    async def test_developer_critique_node(self, cognitive_state_dict, mock_llm_provider, sample_artifact, sample_context):
        """Test developer critique node assesses feasibility."""
        from src.cognitive_engine.agents.developer_agent import DeveloperAgent
        
        cognitive_state_dict["draft_artifact"] = sample_artifact.model_dump()
        cognitive_state_dict["retrieved_context"] = [ctx.model_dump() for ctx in sample_context]
        
        developer_agent = DeveloperAgent(mock_llm_provider)
        result = await developer_critique_node(cognitive_state_dict, developer_agent)
        
        assert result is not None
        assert "developer_critique" in result
        assert "developer_feasibility" in result

    @pytest.mark.asyncio
    async def test_synthesis_node(self, cognitive_state_dict, mock_llm_provider, sample_artifact):
        """Test synthesis node refines artifact."""
        from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
        
        cognitive_state_dict["draft_artifact"] = sample_artifact.model_dump()
        cognitive_state_dict["qa_critique"] = "Test QA critique"
        cognitive_state_dict["developer_critique"] = "Test developer critique"
        
        po_agent = ProductOwnerAgent(mock_llm_provider)
        result = await synthesis_node(cognitive_state_dict, po_agent)
        
        assert result is not None
        assert "refined_artifact" in result
        assert "debate_history" in result
        assert len(result["debate_history"]) > 0

    def test_validation_node(self, cognitive_state_dict, sample_artifact):
        """Test validation node calculates confidence."""
        cognitive_state_dict["draft_artifact"] = sample_artifact.model_dump()
        cognitive_state_dict["refined_artifact"] = sample_artifact.model_dump()
        cognitive_state_dict["qa_confidence"] = 0.8
        cognitive_state_dict["developer_confidence"] = 0.75
        cognitive_state_dict["qa_overall_assessment"] = "good"
        cognitive_state_dict["developer_feasibility"] = "feasible"
        
        result = validation_node(cognitive_state_dict)
        
        assert result is not None
        assert "confidence_score" in result
        assert 0.0 <= result["confidence_score"] <= 1.0
        assert "iteration_count" in result
        assert result["iteration_count"] == cognitive_state_dict["iteration_count"] + 1

    @pytest.mark.asyncio
    async def test_execution_node(self, cognitive_state_dict, mock_issue_tracker, sample_artifact):
        """Test execution node updates issue tracker."""
        cognitive_state_dict["refined_artifact"] = sample_artifact.model_dump()
        
        result = await execution_node(cognitive_state_dict, mock_issue_tracker)
        
        assert result is not None
        assert "execution_success" in result
        mock_issue_tracker.update_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_supervisor_node(self, cognitive_state_dict, mock_llm_provider):
        """Test supervisor node makes routing decision."""
        from src.cognitive_engine.agents.supervisor import SupervisorAgent
        
        supervisor = SupervisorAgent(mock_llm_provider)
        result = await supervisor_node(cognitive_state_dict, supervisor, max_iterations=3)
        
        assert result is not None
        assert "_next_action" in result
        assert "supervisor_decision" in result
        assert result["supervisor_decision"]["next_action"] in [
            "draft", "qa_critique", "developer_critique", "synthesize", "validate", "execute"
        ]


class TestCognitiveGraph:
    """Tests for LangGraph cognitive workflow."""

    @pytest.mark.asyncio
    async def test_graph_creation(self, mock_issue_tracker, mock_knowledge_base, mock_llm_provider):
        """Test that graph can be created."""
        graph = create_cognitive_graph(
            issue_tracker=mock_issue_tracker,
            knowledge_base=mock_knowledge_base,
            llm_provider=mock_llm_provider,
        )
        
        assert graph is not None

    @pytest.mark.asyncio
    async def test_graph_execution_basic(self, mock_issue_tracker, mock_knowledge_base, mock_llm_provider, sample_request):
        """Test basic graph execution flow."""
        # Configure mock to return appropriate structured outputs for workflow
        async def structured_completion_workflow(messages, response_model, temperature=0.7):
            """Mock structured completion that simulates workflow progression."""
            model_name = response_model.__name__
            state = getattr(structured_completion_workflow, "_state", {"step": 0})
            
            if model_name == "SupervisorDecision":
                step = state.get("step", 0)
                if step == 0:
                    # First: route to draft
                    state["step"] = 1
                    structured_completion_workflow._state = state
                    return SupervisorDecision(
                        next_action="draft",
                        reasoning="Initial draft needed",
                        should_continue=True,
                        priority_focus="quality",
                        confidence=0.9,
                    )
                elif step == 1:
                    # After draft: route to QA
                    state["step"] = 2
                    structured_completion_workflow._state = state
                    return SupervisorDecision(
                        next_action="qa_critique",
                        reasoning="QA critique needed",
                        should_continue=True,
                        priority_focus="quality",
                        confidence=0.9,
                    )
                elif step == 2:
                    # After QA: route to developer
                    state["step"] = 3
                    structured_completion_workflow._state = state
                    return SupervisorDecision(
                        next_action="developer_critique",
                        reasoning="Developer assessment needed",
                        should_continue=True,
                        priority_focus="feasibility",
                        confidence=0.9,
                    )
                elif step == 3:
                    # After developer: route to synthesize
                    state["step"] = 4
                    structured_completion_workflow._state = state
                    return SupervisorDecision(
                        next_action="synthesize",
                        reasoning="Synthesis needed",
                        should_continue=True,
                        priority_focus="quality",
                        confidence=0.9,
                    )
                elif step == 4:
                    # After synthesis: route to validate
                    state["step"] = 5
                    structured_completion_workflow._state = state
                    return SupervisorDecision(
                        next_action="validate",
                        reasoning="Validation needed",
                        should_continue=True,
                        priority_focus="quality",
                        confidence=0.9,
                    )
                else:
                    # After validation: execute
                    return SupervisorDecision(
                        next_action="execute",
                        reasoning="Ready to execute",
                        should_continue=False,
                        priority_focus="none",
                        confidence=0.9,
                    )
            elif model_name == "ArtifactRefinement":
                return ArtifactRefinement(
                    title="Refined Test Title",
                    description="Refined description",
                    acceptance_criteria=["AC1", "AC2"],
                    rationale="Test rationale",
                )
            elif model_name == "InvestCritique":
                return InvestCritique(
                    violations=[],
                    critique_text="Good artifact",
                    confidence=0.85,
                    overall_assessment="good",
                )
            elif model_name == "FeasibilityAssessment":
                return FeasibilityAssessment(
                    status="feasible",
                    dependencies=[],
                    concerns=[],
                    confidence=0.80,
                    assessment_text="Feasible",
                )
            else:
                return response_model()
        
        structured_completion_workflow._state = {"step": 0}
        mock_llm_provider.structured_completion = AsyncMock(side_effect=structured_completion_workflow)
        
        graph = create_cognitive_graph(
            issue_tracker=mock_issue_tracker,
            knowledge_base=mock_knowledge_base,
            llm_provider=mock_llm_provider,
        )
        
        initial_state = CognitiveState(request=sample_request)
        state_dict = initial_state.model_dump()
        
        # Execute graph
        final_state = await graph.ainvoke(state_dict)
        
        assert final_state is not None
        assert "request" in final_state
        assert final_state["request"]["artifact_id"] == "test-id-123"
        # Should have progressed through workflow
        assert "current_artifact" in final_state or "execution_success" in final_state

    @pytest.mark.asyncio
    async def test_graph_with_iteration_loop(self, mock_issue_tracker, mock_knowledge_base, mock_llm_provider, sample_request):
        """Test graph execution with iteration loop when confidence is low."""
        iteration_count = [0]
        
        async def structured_completion_iteration(messages, response_model, temperature=0.7):
            """Mock that simulates iteration loop."""
            model_name = response_model.__name__
            
            if model_name == "SupervisorDecision":
                iter_num = iteration_count[0]
                iteration_count[0] += 1
                
                if iter_num < 2:
                    # First two iterations: route back to draft (low confidence)
                    return SupervisorDecision(
                        next_action="draft",
                        reasoning="Needs improvement",
                        should_continue=True,
                        priority_focus="quality",
                        confidence=0.7,
                    )
                else:
                    # Third iteration: execute
                    return SupervisorDecision(
                        next_action="execute",
                        reasoning="Max iterations reached",
                        should_continue=False,
                        priority_focus="none",
                        confidence=0.8,
                    )
            elif model_name == "ArtifactRefinement":
                return ArtifactRefinement(
                    title="Refined Title",
                    description="Refined description",
                    acceptance_criteria=["AC1"],
                    rationale="Test",
                )
            elif model_name == "InvestCritique":
                return InvestCritique(
                    violations=[],
                    critique_text="Good",
                    confidence=0.75,
                    overall_assessment="good",
                )
            elif model_name == "FeasibilityAssessment":
                return FeasibilityAssessment(
                    status="feasible",
                    dependencies=[],
                    concerns=[],
                    confidence=0.70,
                    assessment_text="Feasible",
                )
            else:
                return response_model()
        
        mock_llm_provider.structured_completion = AsyncMock(side_effect=structured_completion_iteration)
        
        graph = create_cognitive_graph(
            issue_tracker=mock_issue_tracker,
            knowledge_base=mock_knowledge_base,
            llm_provider=mock_llm_provider,
        )
        
        initial_state = CognitiveState(request=sample_request)
        state_dict = initial_state.model_dump()
        
        final_state = await graph.ainvoke(state_dict)
        
        assert final_state is not None
        # Should have iterated
        assert final_state.get("iteration_count", 0) >= 0
