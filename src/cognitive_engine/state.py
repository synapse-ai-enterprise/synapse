"""Cognitive State definition for LangGraph workflow."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.domain.schema import (
    CoreArtifact,
    FeasibilityAssessment,
    InvestCritique,
    InvestViolation,
    OptimizationRequest,
    UASKnowledgeUnit,
)


class CognitiveState(BaseModel):
    """State passed through the LangGraph workflow."""

    request: OptimizationRequest
    current_artifact: Optional[CoreArtifact] = None
    retrieved_context: List[UASKnowledgeUnit] = Field(default_factory=list)
    draft_artifact: Optional[CoreArtifact] = None
    qa_critique: Optional[str] = None
    qa_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="QA agent confidence score")
    qa_overall_assessment: Optional[str] = Field(None, description="QA overall assessment (excellent/good/needs_improvement/poor)")
    structured_qa_violations: List[InvestViolation] = Field(default_factory=list, description="Structured INVEST violations from QA agent")
    developer_critique: Optional[str] = None
    developer_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Developer agent confidence score")
    developer_feasibility: Optional[str] = Field(None, description="Developer feasibility status (feasible/blocked/requires_changes)")
    refined_artifact: Optional[CoreArtifact] = None
    invest_violations: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    iteration_count: int = 0
    debate_history: List[Dict[str, Any]] = Field(default_factory=list)
    supervisor_decision: Optional[Dict[str, Any]] = Field(None, description="Latest supervisor routing decision")
    trace_id: Optional[str] = None  # For OpenTelemetry
    proposed_artifacts: List[CoreArtifact] = Field(
        default_factory=list,
        description="Proposed split artifacts when story is too large (INVEST S violation)"
    )