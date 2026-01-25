"""Tests for agent implementations."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.cognitive_engine.agents.developer_agent import DeveloperAgent
from src.cognitive_engine.agents.po_agent import ProductOwnerAgent
from src.cognitive_engine.agents.qa_agent import QAAgent
from src.cognitive_engine.agents.supervisor import SupervisorAgent
from src.domain.schema import (
    CoreArtifact,
    NormalizedPriority,
    UASKnowledgeUnit,
    WorkItemStatus,
    ArtifactRefinement,
    InvestCritique,
    FeasibilityAssessment,
    SupervisorDecision,
)


class TestProductOwnerAgent:
    """Tests for ProductOwnerAgent."""

    @pytest.mark.asyncio
    async def test_draft_artifact(self, mock_llm_provider, sample_artifact, sample_context):
        """Test that PO agent can draft an artifact."""
        agent = ProductOwnerAgent(mock_llm_provider)
        
        # Mock structured completion to return ArtifactRefinement
        mock_llm_provider.structured_completion = AsyncMock(
            return_value=ArtifactRefinement(
                title="Refined Test Title",
                description="As a user, I want refined functionality, so that I can achieve better results.",
                acceptance_criteria=["AC1: Refined criterion 1", "AC2: Refined criterion 2"],
                rationale="Refined based on context",
            )
        )
        
        result = await agent.draft_artifact(sample_artifact, sample_context)
        
        assert result is not None
        assert isinstance(result, CoreArtifact)
        assert result.source_id == sample_artifact.source_id
        assert result.title == "Refined Test Title"
        assert len(result.acceptance_criteria) > 0
        mock_llm_provider.structured_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_feedback(self, mock_llm_provider, sample_artifact):
        """Test that PO agent can synthesize feedback."""
        agent = ProductOwnerAgent(mock_llm_provider)
        
        critiques = [
            "The acceptance criteria need to be more specific.",
            "Consider adding error handling scenarios.",
        ]
        
        # Mock structured completion
        mock_llm_provider.structured_completion = AsyncMock(
            return_value=ArtifactRefinement(
                title="Synthesized Title",
                description="Synthesized description incorporating feedback",
                acceptance_criteria=[
                    "AC1: Specific criterion with error handling",
                    "AC2: Another specific criterion",
                ],
                rationale="Synthesized from critiques",
            )
        )
        
        result = await agent.synthesize_feedback(sample_artifact, critiques)
        
        assert result is not None
        assert isinstance(result, CoreArtifact)
        assert result.title == "Synthesized Title"
        mock_llm_provider.structured_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_synthesize_feedback_with_violations(self, mock_llm_provider, sample_artifact):
        """Test synthesis with INVEST violations."""
        agent = ProductOwnerAgent(mock_llm_provider)
        
        critiques = ["Missing 'so that' clause"]
        violations = ["Valuable: Missing value proposition"]
        
        mock_llm_provider.structured_completion = AsyncMock(
            return_value=ArtifactRefinement(
                title="Fixed Title",
                description="As a user, I want X, so that Y",
                acceptance_criteria=["AC1: Fixed"],
                rationale="Fixed violations",
            )
        )
        
        result = await agent.synthesize_feedback(sample_artifact, critiques, violations=violations)
        
        assert result is not None
        assert "so that" in result.description.lower()

    def test_format_context(self, mock_llm_provider, sample_context):
        """Test context formatting."""
        agent = ProductOwnerAgent(mock_llm_provider)
        formatted = agent._format_context(sample_context)
        
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        # Should include source information
        assert "github" in formatted.lower() or "notion" in formatted.lower()

    # Note: _extract_acceptance_criteria method doesn't exist - agent uses structured outputs
    # No need to test non-existent private methods


class TestQAAgent:
    """Tests for QAAgent."""

    @pytest.mark.asyncio
    async def test_critique_artifact(self, mock_llm_provider, sample_artifact):
        """Test that QA agent can critique an artifact."""
        agent = QAAgent(mock_llm_provider)
        
        # Mock structured completion
        mock_llm_provider.structured_completion = AsyncMock(
            return_value=InvestCritique(
                violations=[],
                critique_text="The artifact is well-structured and meets INVEST criteria.",
                confidence=0.85,
                overall_assessment="good",
            )
        )
        
        result = await agent.critique_artifact(sample_artifact)
        
        assert result is not None
        assert isinstance(result, dict)
        assert "critique" in result
        assert "confidence" in result
        assert "violations" in result
        assert isinstance(result["violations"], list)
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0
        assert "overall_assessment" in result
        mock_llm_provider.structured_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_critique_artifact_with_violations(self, mock_llm_provider, sample_artifact):
        """Test critique with INVEST violations."""
        from src.domain.schema import InvestViolation
        
        agent = QAAgent(mock_llm_provider)
        
        mock_llm_provider.structured_completion = AsyncMock(
            return_value=InvestCritique(
                violations=[
                    InvestViolation(
                        criterion="T",  # Must be single letter: I, N, V, E, S, or T
                        severity="major",
                        description="Acceptance criteria are not binary",
                    )
                ],
                critique_text="The acceptance criteria need to be more specific and binary.",
                confidence=0.65,
                overall_assessment="needs_improvement",
            )
        )
        
        result = await agent.critique_artifact(sample_artifact)
        
        assert result is not None
        assert len(result.get("violations", [])) > 0
        assert len(result.get("structured_violations", [])) > 0
        assert result["confidence"] < 0.8  # Lower confidence with violations

    # Note: _extract_violations and _extract_confidence methods don't exist - agent uses structured outputs
    # No need to test non-existent private methods


class TestDeveloperAgent:
    """Tests for DeveloperAgent."""

    @pytest.mark.asyncio
    async def test_assess_feasibility(self, mock_llm_provider, sample_artifact, sample_context):
        """Test that developer agent can assess feasibility."""
        from src.domain.schema import TechnicalDependency, TechnicalConcern
        
        agent = DeveloperAgent(mock_llm_provider)
        
        # Mock structured completion with proper TechnicalDependency and TechnicalConcern objects
        mock_llm_provider.structured_completion = AsyncMock(
            return_value=FeasibilityAssessment(
                status="feasible",
                dependencies=[
                    TechnicalDependency(
                        dependency_type="infrastructure",
                        description="API v2 deployment",
                        blocking=False,
                    )
                ],
                concerns=[
                    TechnicalConcern(
                        severity="medium",
                        description="Performance might be impacted",
                        recommendation="Monitor performance metrics",
                    )
                ],
                confidence=0.75,
                assessment_text="The artifact is feasible with minor concerns.",
            )
        )
        
        result = await agent.assess_feasibility(sample_artifact, sample_context)
        
        assert result is not None
        assert isinstance(result, dict)
        assert "feasibility" in result
        assert "dependencies" in result
        assert "concerns" in result
        assert "critique" in result
        assert "confidence" in result
        assert result["feasibility"] in ["feasible", "blocked", "requires_changes"]
        assert isinstance(result["dependencies"], list)
        assert isinstance(result["concerns"], list)
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0
        mock_llm_provider.structured_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_assess_feasibility_blocked(self, mock_llm_provider, sample_artifact, sample_context):
        """Test feasibility assessment when blocked."""
        from src.domain.schema import TechnicalDependency, TechnicalConcern
        
        agent = DeveloperAgent(mock_llm_provider)
        
        mock_llm_provider.structured_completion = AsyncMock(
            return_value=FeasibilityAssessment(
                status="blocked",
                dependencies=[
                    TechnicalDependency(
                        dependency_type="external_service",
                        description="Missing API",
                        blocking=True,
                    ),
                    TechnicalDependency(
                        dependency_type="data",
                        description="Database migration required",
                        blocking=True,
                    ),
                ],
                concerns=[
                    TechnicalConcern(
                        severity="blocker",
                        description="Critical dependency missing",
                        recommendation="Resolve dependencies before proceeding",
                    )
                ],
                confidence=0.3,
                assessment_text="Blocked by missing dependencies.",
            )
        )
        
        result = await agent.assess_feasibility(sample_artifact, sample_context)
        
        assert result["feasibility"] == "blocked"
        assert len(result["dependencies"]) > 0
        assert result["confidence"] < 0.5  # Lower confidence when blocked

    # Note: _extract_feasibility, _extract_dependencies, and _extract_concerns methods don't exist
    # Agent uses structured outputs, so no need to test non-existent private methods

    def test_format_context(self, mock_llm_provider, sample_context):
        """Test codebase context formatting."""
        agent = DeveloperAgent(mock_llm_provider)
        formatted = agent._format_context(sample_context)
        
        assert isinstance(formatted, str)
        assert len(formatted) > 0


class TestSupervisorAgent:
    """Tests for SupervisorAgent."""

    @pytest.mark.asyncio
    async def test_decide_next_action_initial(self, mock_llm_provider, cognitive_state_dict):
        """Test supervisor decision for initial state."""
        supervisor = SupervisorAgent(mock_llm_provider)
        
        # Mock structured completion for initial draft
        mock_llm_provider.structured_completion = AsyncMock(
            return_value=SupervisorDecision(
                next_action="draft",
                reasoning="Initial draft needed",
                should_continue=True,
                priority_focus="quality",
                confidence=0.9,
            )
        )
        
        decision = await supervisor.decide_next_action(cognitive_state_dict, max_iterations=3)
        
        assert isinstance(decision, SupervisorDecision)
        assert decision.next_action == "draft"
        assert decision.should_continue is True
        assert decision.confidence > 0.0

    @pytest.mark.asyncio
    async def test_decide_next_action_with_draft(self, mock_llm_provider, cognitive_state_dict, sample_artifact):
        """Test supervisor decision when draft exists."""
        supervisor = SupervisorAgent(mock_llm_provider)
        
        cognitive_state_dict["draft_artifact"] = sample_artifact.model_dump()
        
        mock_llm_provider.structured_completion = AsyncMock(
            return_value=SupervisorDecision(
                next_action="qa_critique",
                reasoning="QA critique needed after draft",
                should_continue=True,
                priority_focus="quality",
                confidence=0.9,
            )
        )
        
        decision = await supervisor.decide_next_action(cognitive_state_dict, max_iterations=3)
        
        assert decision.next_action == "qa_critique"

    @pytest.mark.asyncio
    async def test_decide_next_action_max_iterations(self, mock_llm_provider, cognitive_state_dict):
        """Test supervisor decision when max iterations reached."""
        supervisor = SupervisorAgent(mock_llm_provider)
        
        cognitive_state_dict["iteration_count"] = 3
        
        mock_llm_provider.structured_completion = AsyncMock(
            return_value=SupervisorDecision(
                next_action="execute",
                reasoning="Max iterations reached, execute regardless",
                should_continue=False,
                priority_focus="none",
                confidence=0.8,
            )
        )
        
        decision = await supervisor.decide_next_action(cognitive_state_dict, max_iterations=3)
        
        assert decision.next_action == "execute"
        assert decision.should_continue is False

    @pytest.mark.asyncio
    async def test_decide_next_action_high_confidence(self, mock_llm_provider, cognitive_state_dict, sample_artifact):
        """Test supervisor decision with high confidence."""
        supervisor = SupervisorAgent(mock_llm_provider)
        
        cognitive_state_dict["refined_artifact"] = sample_artifact.model_dump()
        cognitive_state_dict["confidence_score"] = 0.9
        cognitive_state_dict["invest_violations"] = []
        
        mock_llm_provider.structured_completion = AsyncMock(
            return_value=SupervisorDecision(
                next_action="execute",
                reasoning="High confidence, ready to execute",
                should_continue=False,
                priority_focus="none",
                confidence=0.95,
            )
        )
        
        decision = await supervisor.decide_next_action(cognitive_state_dict, max_iterations=3)
        
        assert decision.next_action == "execute"

    def test_analyze_trends(self, mock_llm_provider):
        """Test trend analysis."""
        supervisor = SupervisorAgent(mock_llm_provider)
        
        debate_history = [
            {"confidence_score": 0.5, "invest_violations": [1, 2, 3]},
            {"confidence_score": 0.7, "invest_violations": [1, 2]},
            {"confidence_score": 0.8, "invest_violations": [1]},
        ]
        
        trends = supervisor._analyze_trends(debate_history)
        
        assert trends["confidence_trend"] == "improving"
        assert trends["violation_trend"] == "improving"
        assert trends["improving"] is True

    def test_build_decision_context(self, mock_llm_provider):
        """Test decision context building."""
        supervisor = SupervisorAgent(mock_llm_provider)
        
        context = supervisor._build_decision_context(
            iteration_count=1,
            confidence_score=0.75,
            violation_count=2,
            qa_confidence=0.8,
            developer_confidence=0.7,
            developer_feasibility="feasible",
            qa_assessment="good",
            trend_analysis={"improving": True, "confidence_trend": "improving"},
            max_iterations=3,
        )
        
        assert isinstance(context, str)
        assert "Iteration: 1/3" in context
        assert "Confidence: 0.75" in context
        assert "Violations: 2" in context
