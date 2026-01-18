"""Cognitive State definition for LangGraph workflow."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.domain.schema import CoreArtifact, OptimizationRequest, UASKnowledgeUnit


class CognitiveState(BaseModel):
    """State passed through the LangGraph workflow."""

    request: OptimizationRequest
    current_artifact: Optional[CoreArtifact] = None
    retrieved_context: List[UASKnowledgeUnit] = Field(default_factory=list)
    draft_artifact: Optional[CoreArtifact] = None
    qa_critique: Optional[str] = None
    developer_critique: Optional[str] = None
    refined_artifact: Optional[CoreArtifact] = None
    invest_violations: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    iteration_count: int = 0
    debate_history: List[Dict[str, Any]] = Field(default_factory=list)
    trace_id: Optional[str] = None  # For OpenTelemetry
