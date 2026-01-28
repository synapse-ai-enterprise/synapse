"""State for Product Story Writing workflow."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.domain.schema import (
    EpicAnalysis,
    InvestViolation,
    PopulatedStory,
    RetrievedContext,
    SplittingRecommendation,
    StoryCandidate,
    StoryWritingRequest,
    TemplateSchema,
    ValidationResults,
)


class StoryWritingState(BaseModel):
    """State passed through the story writing workflow."""

    request: StoryWritingRequest
    epic_analysis: Optional[EpicAnalysis] = None
    splitting_recommendations: List[SplittingRecommendation] = Field(default_factory=list)
    generated_stories: List[StoryCandidate] = Field(default_factory=list)
    template_schema: Optional[TemplateSchema] = None
    retrieved_context: Optional[RetrievedContext] = None
    populated_story: Optional[PopulatedStory] = None
    refined_story: Optional[PopulatedStory] = None
    validation_results: Optional[ValidationResults] = None
    qa_critique: Optional[str] = None
    qa_confidence: Optional[float] = None
    qa_overall_assessment: Optional[str] = None
    structured_qa_violations: List[InvestViolation] = Field(default_factory=list)
    developer_critique: Optional[str] = None
    developer_confidence: Optional[float] = None
    developer_feasibility: Optional[str] = None
    developer_dependencies: List[str] = Field(default_factory=list)
    developer_concerns: List[str] = Field(default_factory=list)
    critique_history: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
