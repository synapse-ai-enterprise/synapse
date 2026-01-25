"""Unified Agile Schema (UAS) - Canonical data models."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class NormalizedPriority(str, Enum):
    """Normalized priority enum across all systems."""

    CRITICAL = "critical"  # Linear: 1, GitHub: "priority:critical"
    HIGH = "high"  # Linear: 2, GitHub: "priority:high"
    MEDIUM = "medium"  # Linear: 3, GitHub: "priority:medium"
    LOW = "low"  # Linear: 4, GitHub: "priority:low"
    NONE = "none"  # Linear: 0, Default/Triage


class WorkItemStatus(str, Enum):
    """Work item status enum."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


SourceSystem = str


class CoreArtifact(BaseModel):
    """The Unified Agile Artifact. Abstracts Linear/GitHub into a common cognitive model."""

    internal_id: UUID = Field(default_factory=uuid4, description="System-local unique identifier")

    # Traceability
    source_system: SourceSystem = Field(description="Source system identifier")
    source_id: str = Field(description="The immutable ID from the source (e.g., Linear UUID)")
    human_ref: str = Field(description="The readable ID (e.g., 'LIN-123')")
    url: str = Field(description="Direct link to the artifact")

    # Content
    title: str = Field(description="Summary or Title of the work")
    description: str = Field(description="The body content, normalized to Markdown")
    acceptance_criteria: List[str] = Field(default_factory=list, description="Explicit list of ACs")

    # Meta
    type: str = Field(description="Story, Bug, Epic, Task")
    status: WorkItemStatus
    priority: NormalizedPriority

    # Context (RAG)
    related_files: List[str] = Field(default_factory=list, description="Codebase files relevant to this story")
    parent_ref: Optional[str] = Field(None, description="Reference to the parent Epic/Project")

    # Lineage tracking
    lineage: List[str] = Field(default_factory=list, description="Tracks source (e.g., derived from Notion doc X)")

    # Extension Bag
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="Store tool-specific fields")


class UASKnowledgeUnit(BaseModel):
    """Canonical representation of documentation."""

    id: str
    content: str = Field(description="Markdown content")
    summary: str = Field(description="LLM-generated summary")
    source: Literal["notion", "github"]
    last_updated: str  # ISO format datetime string
    topics: List[str] = Field(default_factory=list, description="Semantic tags derived during ingestion")
    location: str = Field(description="File path (GitHub) or Page URL (Notion)")


class UASSignal(BaseModel):
    """A trigger event requiring cognitive attention."""

    source_actor: str
    content: str
    context_url: Optional[str] = None
    intent_classification: Optional[str] = None
    webhook_payload: Dict[str, Any] = Field(default_factory=dict, description="Raw webhook data")


class OptimizationRequest(BaseModel):
    """Request to optimize an artifact."""

    artifact_id: str
    artifact_type: Literal["issue", "epic", "story"]
    source_system: SourceSystem
    trigger: Literal["webhook", "manual", "scheduled"]
    dry_run: bool = False


# Structured Agent Output Models


class ArtifactRefinement(BaseModel):
    """Structured output from PO Agent for artifact refinement."""

    title: str = Field(description="Refined title following user story format")
    description: str = Field(description="Refined description with clear value proposition")
    acceptance_criteria: List[str] = Field(description="Specific, testable acceptance criteria")
    rationale: Optional[str] = Field(None, description="Explanation of key changes made")


class InvestViolation(BaseModel):
    """Structured INVEST violation from QA Agent."""

    criterion: Literal["I", "N", "V", "E", "S", "T"] = Field(
        description="INVEST criterion violated: I=Independent, N=Negotiable, V=Valuable, E=Estimable, S=Small, T=Testable"
    )
    severity: Literal["critical", "major", "minor"] = Field(description="Severity of violation")
    description: str = Field(description="Description of the violation")
    evidence: Optional[str] = Field(None, description="Specific evidence from artifact")
    suggestion: Optional[str] = Field(None, description="Suggestion for how to fix")

    @classmethod
    def from_llm_response(cls, data: dict) -> "InvestViolation":
        """Convert LLM response with different field names to InvestViolation.
        
        Handles variations like INVEST_criterion -> criterion, Evidence -> description, etc.
        """
        normalized = {}
        
        # Map criterion
        if "INVEST_criterion" in data:
            criterion_value = data["INVEST_criterion"]
            # Map full names to letters
            criterion_map = {
                "Independent": "I",
                "Negotiable": "N",
                "Valuable": "V",
                "Estimable": "E",
                "Small": "S",
                "Testable": "T",
            }
            normalized["criterion"] = criterion_map.get(criterion_value, criterion_value)
        elif "criterion" in data:
            criterion_value = data["criterion"]
            # Normalize to uppercase (handle lowercase 'i', 'n', 'v', 'e', 's', 't')
            if isinstance(criterion_value, str):
                criterion_value = criterion_value.upper()
            normalized["criterion"] = criterion_value
        
        # Map severity (case-insensitive)
        if "Severity" in data:
            normalized["severity"] = data["Severity"].lower()
        elif "severity" in data:
            normalized["severity"] = data["severity"].lower()
        
        # Map description/evidence
        if "Evidence" in data:
            normalized["description"] = data["Evidence"]
        elif "description" in data:
            normalized["description"] = data["description"]
        
        # Map suggestion
        if "Suggestion" in data:
            normalized["suggestion"] = data["Suggestion"]
        elif "suggestion" in data:
            normalized["suggestion"] = data["suggestion"]
        
        # Evidence field (optional)
        if "evidence" in data:
            normalized["evidence"] = data["evidence"]
        
        return cls(**normalized)


class InvestCritique(BaseModel):
    """Structured critique from QA Agent."""

    violations: List[InvestViolation] = Field(default_factory=list, description="List of INVEST violations")
    critique_text: str = Field(description="Detailed critique text")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in critique (0.0-1.0)")
    overall_assessment: Literal["excellent", "good", "needs_improvement", "poor"] = Field(
        description="Overall quality assessment"
    )


class TechnicalDependency(BaseModel):
    """Technical dependency identified by Developer Agent."""

    dependency_type: Literal["code", "infrastructure", "external_service", "data", "other"] = Field(
        description="Type of dependency"
    )
    description: str = Field(description="Description of dependency")
    blocking: bool = Field(description="Whether this is a blocking dependency")

    @classmethod
    def from_llm_response(cls, data: dict) -> "TechnicalDependency":
        """Transform LLM response with different field names."""
        normalized = {}
        
        # Map dependency_type (might be "type")
        if "dependency_type" in data:
            normalized["dependency_type"] = data["dependency_type"]
        elif "type" in data:
            normalized["dependency_type"] = data["type"]
        else:
            normalized["dependency_type"] = "other"
        
        # Map description (required field)
        if "description" in data:
            normalized["description"] = data["description"]
        elif "detail" in data:
            normalized["description"] = data["detail"]
        else:
            # Fallback: create description from type
            dep_type = normalized.get("dependency_type", "dependency")
            normalized["description"] = f"{dep_type.replace('_', ' ').title()} dependency required"
        
        # Map blocking
        normalized["blocking"] = data.get("blocking", False)
        
        return cls(**normalized)


class TechnicalConcern(BaseModel):
    """Technical concern identified by Developer Agent."""

    severity: Literal["blocker", "high", "medium", "low"] = Field(description="Severity of concern")
    description: str = Field(description="Description of the concern")
    recommendation: Optional[str] = Field(None, description="Recommendation for addressing")

    @classmethod
    def from_llm_response(cls, data: dict) -> "TechnicalConcern":
        """Transform LLM response with different field names."""
        normalized = {}
        
        # Map severity
        if "severity" in data:
            normalized["severity"] = data["severity"].lower()
        
        # Map description (might be "detail")
        if "description" in data:
            normalized["description"] = data["description"]
        elif "detail" in data:
            normalized["description"] = data["detail"]
        else:
            normalized["description"] = "Technical concern"
        
        # Map recommendation
        if "recommendation" in data:
            normalized["recommendation"] = data["recommendation"]
        elif "suggestion" in data:
            normalized["recommendation"] = data["suggestion"]


class SupervisorDecision(BaseModel):
    """Supervisor routing decision for multi-agent debate."""

    next_action: Literal[
        "draft",
        "qa_critique",
        "developer_critique",
        "synthesize",
        "validate",
        "execute",
        "end"
    ] = Field(description="Next action to take in the workflow")
    reasoning: str = Field(description="Explanation for the routing decision")
    should_continue: bool = Field(description="Whether to continue the debate loop")
    priority_focus: Optional[Literal["quality", "feasibility", "business_value", "none"]] = Field(
        None, description="Primary focus area for next iteration"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the routing decision")


class FeasibilityAssessment(BaseModel):
    """Structured feasibility assessment from Developer Agent."""

    status: Literal["feasible", "blocked", "requires_changes"] = Field(description="Feasibility status")
    dependencies: List[TechnicalDependency] = Field(default_factory=list, description="List of dependencies")
    concerns: List[TechnicalConcern] = Field(default_factory=list, description="List of technical concerns")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in assessment (0.0-1.0)")
    assessment_text: str = Field(description="Detailed assessment text")
