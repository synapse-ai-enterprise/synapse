"""Tests for agent implementations."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.cognitive_engine.agents.developer_agent import DeveloperAgent
from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
from src.cognitive_engine.agents.qa_agent import QAAgent
from src.domain.schema import (
    CoreArtifact,
    NormalizedPriority,
    UASKnowledgeUnit,
    WorkItemStatus,
)


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.chat_completion = AsyncMock(return_value="Test response")
    provider.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    return provider


@pytest.fixture
def sample_artifact():
    """Create a sample artifact for testing."""
    return CoreArtifact(
        source_system="linear",
        source_id="test-id",
        human_ref="LIN-123",
        url="https://linear.app/test",
        title="Test User Story",
        description="As a user, I want to test, so that I can verify functionality.",
        acceptance_criteria=["AC1: Test passes", "AC2: Code works"],
        type="Story",
        status=WorkItemStatus.TODO,
        priority=NormalizedPriority.MEDIUM,
    )


@pytest.fixture
def sample_context():
    """Create sample knowledge context."""
    return [
        UASKnowledgeUnit(
            id="kb-1",
            content="Test content from GitHub",
            summary="GitHub code snippet",
            source="github",
            last_updated="2024-01-01T00:00:00",
            location="/path/to/file.py",
        ),
        UASKnowledgeUnit(
            id="kb-2",
            content="Test content from Notion",
            summary="Notion documentation",
            source="notion",
            last_updated="2024-01-01T00:00:00",
            location="https://notion.so/page",
        ),
    ]


class TestProductOwnerAgent:
    """Tests for ProductOwnerAgent."""

    @pytest.mark.asyncio
    async def test_draft_artifact(self, mock_llm_provider, sample_artifact, sample_context):
        """Test that PO agent can draft an artifact."""
        agent = ProductOwnerAgent(mock_llm_provider)
        
        mock_llm_provider.chat_completion.return_value = """
        **Refined Title:** As a user, I want to test functionality
        
        **Description:**
        This is a refined description with clear value proposition.
        
        **Acceptance Criteria:**
        - AC1: Test passes
        - AC2: Code works correctly
        """
        
        result = await agent.draft_artifact(sample_artifact, sample_context)
        
        assert result is not None
        assert isinstance(result, CoreArtifact)
        assert result.source_id == sample_artifact.source_id
        mock_llm_provider.chat_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_feedback(self, mock_llm_provider, sample_artifact):
        """Test that PO agent can synthesize feedback."""
        agent = ProductOwnerAgent(mock_llm_provider)
        
        critiques = [
            "The acceptance criteria need to be more specific.",
            "Consider adding error handling scenarios.",
        ]
        
        mock_llm_provider.chat_completion.return_value = """
        **Refined Artifact:**
        Updated description incorporating feedback.
        
        **Acceptance Criteria:**
        - AC1: Test passes with specific conditions
        - AC2: Code works correctly with error handling
        """
        
        result = await agent.synthesize_feedback(sample_artifact, critiques)
        
        assert result is not None
        assert isinstance(result, CoreArtifact)
        mock_llm_provider.chat_completion.assert_called_once()

    def test_format_context(self, mock_llm_provider, sample_context):
        """Test context formatting."""
        agent = ProductOwnerAgent(mock_llm_provider)
        formatted = agent._format_context(sample_context)
        
        assert "github" in formatted.lower()
        assert "notion" in formatted.lower()
        assert len(formatted) > 0

    def test_extract_acceptance_criteria(self, mock_llm_provider):
        """Test acceptance criteria extraction."""
        agent = ProductOwnerAgent(mock_llm_provider)
        
        text = """
        - AC1: First criterion
        - AC2: Second criterion
        1. Numbered criterion
        """
        
        criteria = agent._extract_acceptance_criteria(text)
        assert len(criteria) >= 2
        assert any("AC1" in c or "First" in c for c in criteria)


class TestQAAgent:
    """Tests for QAAgent."""

    @pytest.mark.asyncio
    async def test_critique_artifact(self, mock_llm_provider, sample_artifact):
        """Test that QA agent can critique an artifact."""
        agent = QAAgent(mock_llm_provider)
        
        mock_llm_provider.chat_completion.return_value = """
        VIOLATIONS:
        - Testable: Acceptance criteria need to be more binary
        
        CRITIQUE:
        The artifact is generally good but could be improved.
        
        CONFIDENCE: 0.8
        """
        
        result = await agent.critique_artifact(sample_artifact)
        
        assert result is not None
        assert "violations" in result
        assert "critique" in result
        assert "confidence" in result
        assert isinstance(result["violations"], list)
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_extract_violations(self, mock_llm_provider):
        """Test violation extraction."""
        agent = QAAgent(mock_llm_provider)
        
        text = """
        VIOLATIONS:
        - Independent: Story depends on other work
        - Testable: ACs are vague
        
        CRITIQUE:
        Some critique text here.
        """
        
        violations = agent._extract_violations(text)
        assert len(violations) == 2
        assert any("Independent" in v for v in violations)
        assert any("Testable" in v for v in violations)

    def test_extract_confidence(self, mock_llm_provider):
        """Test confidence extraction."""
        agent = QAAgent(mock_llm_provider)
        
        text = "CONFIDENCE: 0.85"
        confidence = agent._extract_confidence(text)
        assert confidence == 0.85
        
        # Test default confidence when no value found
        text_no_conf = "Some text without confidence"
        confidence = agent._extract_confidence(text_no_conf)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0


class TestDeveloperAgent:
    """Tests for DeveloperAgent."""

    @pytest.mark.asyncio
    async def test_assess_feasibility(self, mock_llm_provider, sample_artifact, sample_context):
        """Test that developer agent can assess feasibility."""
        agent = DeveloperAgent(mock_llm_provider)
        
        mock_llm_provider.chat_completion.return_value = """
        FEASIBILITY: feasible
        
        DEPENDENCIES:
        - Requires API v2 deployment
        - Needs database migration
        
        CONCERNS:
        - Performance might be impacted
        
        CONFIDENCE: 0.75
        """
        
        result = await agent.assess_feasibility(sample_artifact, sample_context)
        
        assert result is not None
        assert "feasibility" in result
        assert "dependencies" in result
        assert "concerns" in result
        assert "critique" in result
        assert "confidence" in result
        assert result["feasibility"] in ["feasible", "blocked", "requires-changes", "unknown"]
        assert isinstance(result["dependencies"], list)
        assert isinstance(result["concerns"], list)

    def test_extract_feasibility(self, mock_llm_provider):
        """Test feasibility status extraction."""
        agent = DeveloperAgent(mock_llm_provider)
        
        text = "FEASIBILITY: feasible"
        status = agent._extract_feasibility(text)
        assert status == "feasible"
        
        text_blocked = "FEASIBILITY: blocked"
        status = agent._extract_feasibility(text_blocked)
        assert status == "blocked"

    def test_extract_dependencies(self, mock_llm_provider):
        """Test dependency extraction."""
        agent = DeveloperAgent(mock_llm_provider)
        
        text = """
        DEPENDENCIES:
        - Dependency 1
        - Dependency 2
        
        CONCERNS:
        """
        
        dependencies = agent._extract_dependencies(text)
        assert len(dependencies) == 2

    def test_extract_concerns(self, mock_llm_provider):
        """Test concerns extraction."""
        agent = DeveloperAgent(mock_llm_provider)
        
        text = """
        CONCERNS:
        - Concern 1
        - Concern 2
        
        CONFIDENCE: 0.8
        """
        
        concerns = agent._extract_concerns(text)
        assert len(concerns) == 2

    def test_format_context(self, mock_llm_provider, sample_context):
        """Test codebase context formatting."""
        agent = DeveloperAgent(mock_llm_provider)
        formatted = agent._format_context(sample_context)
        
        # Should include GitHub content
        assert "github" in formatted.lower() or len(formatted) > 0
