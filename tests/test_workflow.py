"""Tests for cognitive engine workflow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.cognitive_engine.graph import create_cognitive_graph
from src.cognitive_engine.invest import InvestValidator
from src.cognitive_engine.state import CognitiveState
from src.domain.schema import (
    CoreArtifact,
    NormalizedPriority,
    OptimizationRequest,
    UASKnowledgeUnit,
    WorkItemStatus,
)


@pytest.fixture
def mock_issue_tracker():
    """Create a mock issue tracker."""
    tracker = MagicMock()
    tracker.get_issue = AsyncMock(
        return_value=CoreArtifact(
            source_system="linear",
            source_id="test-id",
            human_ref="LIN-123",
            url="https://test.com",
            title="Test Issue",
            description="Test description",
            type="Story",
            status=WorkItemStatus.TODO,
            priority=NormalizedPriority.MEDIUM,
        )
    )
    tracker.update_issue = AsyncMock(return_value=True)
    return tracker


@pytest.fixture
def mock_knowledge_base():
    """Create a mock knowledge base."""
    kb = MagicMock()
    kb.search = AsyncMock(
        return_value=[
            UASKnowledgeUnit(
                id="kb-1",
                content="Test content",
                summary="Test summary",
                source="github",
                last_updated="2024-01-01T00:00:00",
                location="/path/to/file.py",
            )
        ]
    )
    return kb


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.chat_completion = AsyncMock(return_value="Test LLM response")
    provider.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    return provider


@pytest.fixture
def sample_request():
    """Create a sample optimization request."""
    return OptimizationRequest(
        artifact_id="test-id",
        artifact_type="issue",
        source_system="linear",
        trigger="manual",
        dry_run=True,
    )


class TestInvestValidator:
    """Tests for INVEST validator."""

    def test_validate_missing_so_that(self):
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
        assert any("Valuable" in v or "so that" in v.lower() for v in violations)

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
        assert any("Estimable" in v or "vague" in v.lower() for v in violations)

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
        assert any("Testable" in v or "acceptance criteria" in v.lower() for v in violations)

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
        assert any("Testable" in v or "binary" in v.lower() for v in violations)

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
        assert any("Small" in v or "large" in v.lower() for v in violations)


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
    async def test_graph_execution(self, mock_issue_tracker, mock_knowledge_base, mock_llm_provider, sample_request):
        """Test full graph execution."""
        # Mock agent responses
        mock_llm_provider.chat_completion.return_value = """
        **Refined Title:** Test Issue
        
        **Description:**
        Refined description with value proposition.
        
        **Acceptance Criteria:**
        - AC1: Test passes
        - AC2: Code works
        """
        
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
        assert final_state["request"]["artifact_id"] == "test-id"

    @pytest.mark.asyncio
    async def test_graph_with_high_confidence(self, mock_issue_tracker, mock_knowledge_base, mock_llm_provider, sample_request):
        """Test graph execution with high confidence leads to execution."""
        mock_llm_provider.chat_completion.return_value = "Perfect artifact"
        
        graph = create_cognitive_graph(
            issue_tracker=mock_issue_tracker,
            knowledge_base=mock_knowledge_base,
            llm_provider=mock_llm_provider,
        )
        
        initial_state = CognitiveState(request=sample_request)
        state_dict = initial_state.model_dump()
        
        final_state = await graph.ainvoke(state_dict)
        
        # Should have executed (or attempted to)
        assert final_state is not None
        # Execution node should have been reached
        assert "execution_success" in final_state or "refined_artifact" in final_state


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

    def test_state_with_artifact(self, sample_request):
        """Test state with artifact."""
        artifact = CoreArtifact(
            source_system="linear",
            source_id="test-id",
            human_ref="LIN-123",
            url="https://test.com",
            title="Test",
            description="Test",
            type="Story",
            status=WorkItemStatus.TODO,
            priority=NormalizedPriority.MEDIUM,
        )
        
        state = CognitiveState(
            request=sample_request,
            current_artifact=artifact,
        )
        
        assert state.current_artifact == artifact
        assert state.current_artifact.title == "Test"

    def test_state_model_dump(self, sample_request):
        """Test state serialization."""
        state = CognitiveState(request=sample_request)
        state_dict = state.model_dump()
        
        assert isinstance(state_dict, dict)
        assert "request" in state_dict
        assert state_dict["request"]["artifact_id"] == "test-id"

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
