"""Shared pytest fixtures and configuration."""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.domain.schema import (
    CoreArtifact,
    OptimizationRequest,
    UASKnowledgeUnit,
    NormalizedPriority,
    WorkItemStatus,
    ArtifactRefinement,
    InvestCritique,
    FeasibilityAssessment,
    SupervisorDecision,
    InvestViolation,
)


@pytest.fixture
def sample_artifact() -> CoreArtifact:
    """Create a sample artifact for testing."""
    return CoreArtifact(
        source_system="linear",
        source_id="test-id-123",
        human_ref="LIN-123",
        url="https://linear.app/test/123",
        title="Test User Story",
        description="As a user, I want to test functionality, so that I can verify the system works correctly.",
        acceptance_criteria=[
            "AC1: User can successfully log in",
            "AC2: User receives confirmation message",
        ],
        type="Story",
        status=WorkItemStatus.TODO,
        priority=NormalizedPriority.MEDIUM,
    )


@pytest.fixture
def sample_request() -> OptimizationRequest:
    """Create a sample optimization request."""
    return OptimizationRequest(
        artifact_id="test-id-123",
        artifact_type="issue",
        source_system="linear",
        trigger="manual",
        dry_run=True,
    )


@pytest.fixture
def sample_context() -> list[UASKnowledgeUnit]:
    """Create sample knowledge context."""
    return [
        UASKnowledgeUnit(
            id="kb-1",
            content="def test_function():\n    return True",
            summary="Test function implementation",
            source="github",
            last_updated="2024-01-01T00:00:00Z",
            location="/path/to/test.py",
        ),
        UASKnowledgeUnit(
            id="kb-2",
            content="# Documentation\n\nThis is test documentation.",
            summary="Test documentation page",
            source="notion",
            last_updated="2024-01-01T00:00:00Z",
            location="https://notion.so/test-page",
        ),
    ]


@pytest.fixture
def mock_llm_provider() -> MagicMock:
    """Create a mock LLM provider with structured completion support."""
    provider = MagicMock()
    provider.chat_completion = AsyncMock(return_value="Mock LLM response")
    provider.get_embedding = AsyncMock(return_value=[0.1] * 1536)
    
    # Default structured completion responses
    async def mock_structured_completion(messages, response_model, temperature=0.7):
        """Mock structured completion that returns appropriate response models."""
        model_name = response_model.__name__
        
        if model_name == "ArtifactRefinement":
            return ArtifactRefinement(
                title="Refined Test Title",
                description="Refined description with clear value proposition",
                acceptance_criteria=["AC1: Refined criterion 1", "AC2: Refined criterion 2"],
                rationale="Test refinement rationale",
            )
        elif model_name == "InvestCritique":
            return InvestCritique(
                violations=[],
                critique_text="Test critique text",
                confidence=0.85,
                overall_assessment="good",
            )
        elif model_name == "FeasibilityAssessment":
            return FeasibilityAssessment(
                status="feasible",
                dependencies=[],
                concerns=[],
                confidence=0.80,
                assessment_text="Test feasibility assessment",
            )
        elif model_name == "SupervisorDecision":
            return SupervisorDecision(
                next_action="draft",
                reasoning="Test routing decision",
                should_continue=True,
                priority_focus="quality",
                confidence=0.9,
            )
        else:
            # Fallback: try to create with minimal fields
            try:
                return response_model()
            except Exception:
                return {}
    
    provider.structured_completion = AsyncMock(side_effect=mock_structured_completion)
    return provider


@pytest.fixture
def mock_issue_tracker() -> MagicMock:
    """Create a mock issue tracker."""
    tracker = MagicMock()
    tracker.get_issue = AsyncMock(
        return_value=CoreArtifact(
            source_system="linear",
            source_id="test-id-123",
            human_ref="LIN-123",
            url="https://linear.app/test/123",
            title="Test Issue",
            description="Test description",
            type="Story",
            status=WorkItemStatus.TODO,
            priority=NormalizedPriority.MEDIUM,
        )
    )
    tracker.update_issue = AsyncMock(return_value=True)
    tracker.post_comment = AsyncMock(return_value=True)
    return tracker


@pytest.fixture
def mock_knowledge_base() -> MagicMock:
    """Create a mock knowledge base."""
    kb = MagicMock()
    kb.search = AsyncMock(
        return_value=[
            UASKnowledgeUnit(
                id="kb-1",
                content="Test content from GitHub",
                summary="GitHub code snippet",
                source="github",
                last_updated="2024-01-01T00:00:00Z",
                location="/path/to/file.py",
            )
        ]
    )
    kb.add_documents = AsyncMock(return_value=None)
    return kb


@pytest.fixture
def cognitive_state_dict(sample_request, sample_artifact) -> Dict[str, Any]:
    """Create a sample cognitive state dictionary."""
    return {
        "request": sample_request.model_dump(),
        "current_artifact": sample_artifact.model_dump(),
        "retrieved_context": [],
        "draft_artifact": None,
        "qa_critique": None,
        "qa_confidence": None,
        "qa_overall_assessment": None,
        "structured_qa_violations": [],
        "developer_critique": None,
        "developer_confidence": None,
        "developer_feasibility": None,
        "refined_artifact": None,
        "invest_violations": [],
        "confidence_score": 0.0,
        "iteration_count": 0,
        "debate_history": [],
        "supervisor_decision": None,
        "trace_id": None,
    }
