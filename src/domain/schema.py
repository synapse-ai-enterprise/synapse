"""Unified Agile Schema (UAS) - Canonical data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
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


class MemoryTier(str, Enum):
    """Memory tier for agent context."""

    CONVERSATION = "conversation"
    WORKING = "working"
    LONG_TERM = "long_term"


class MemoryScope(str, Enum):
    """Scope for memory isolation."""

    ORGANIZATION = "organization"
    PROJECT = "project"
    USER = "user"
    SESSION = "session"


class MemoryItem(BaseModel):
    """A memory record for agents."""

    id: UUID = Field(default_factory=uuid4, description="Unique memory identifier")
    tier: MemoryTier = Field(description="Memory tier")
    scope: MemoryScope = Field(description="Memory scope")
    key: str = Field(description="Lookup key for memory retrieval")
    content: str = Field(description="Memory content")
    source: Optional[str] = Field(None, description="Source system or origin")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Optional expiry timestamp")


class DomainEvent(BaseModel):
    """Domain event emitted during workflows."""

    id: UUID = Field(default_factory=uuid4, description="Event identifier")
    event_type: str = Field(description="Event type")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event payload")
    trace_id: Optional[str] = Field(None, description="Trace identifier")
    occurred_at: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")


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


# Product Story Writing AI models


class StoryWritingRequest(BaseModel):
    """Request for product story writing workflow."""

    flow: Literal["epic_to_stories", "story_to_detail"] = Field(
        description="Which module flow to run"
    )
    epic_id: Optional[str] = Field(None, description="Epic identifier if available")
    epic_text: Optional[str] = Field(None, description="Epic description text")
    selected_techniques: List[str] = Field(default_factory=list, description="Chosen splitting techniques")
    story_text: Optional[str] = Field(None, description="Story text to detail")
    template_text: Optional[str] = Field(None, description="Story template text (if provided)")
    project_id: Optional[str] = Field(None, description="Project identifier for context")
    requester_id: Optional[str] = Field(None, description="User identifier for preference lookup")


class EpicEntities(BaseModel):
    """Key entities extracted from an epic."""

    user_persona: Optional[str] = Field(None, description="Primary user persona")
    capability: Optional[str] = Field(None, description="Primary capability")
    benefit: Optional[str] = Field(None, description="Primary user or business benefit")
    constraints: List[str] = Field(default_factory=list, description="Constraints mentioned in epic")


class EpicAnalysis(BaseModel):
    """Structured output from Epic Analysis Agent."""

    epic_id: Optional[str] = Field(None, description="Epic identifier")
    entities: EpicEntities = Field(description="Extracted key entities")
    complexity_score: float = Field(ge=0.0, le=1.0, description="Complexity score (0.0-1.0)")
    ambiguities: List[str] = Field(default_factory=list, description="Missing info or ambiguous areas")
    domain: Optional[str] = Field(None, description="Domain classification")
    epic_type: Optional[str] = Field(None, description="Epic type classification")


class SplittingRecommendation(BaseModel):
    """Splitting technique recommendation."""

    technique: str = Field(description="Recommended splitting technique")
    confidence: float = Field(ge=0.0, le=1.0, description="Recommendation confidence")
    rationale: str = Field(description="Why this technique applies")
    example_splits: List[str] = Field(default_factory=list, description="Example split ideas")


class SplittingStrategyResult(BaseModel):
    """Structured output for splitting strategy recommendations."""

    recommendations: List[SplittingRecommendation] = Field(default_factory=list)


class StoryCandidate(BaseModel):
    """Generated story candidate from an epic."""

    story_id: Optional[str] = Field(None, description="Story identifier if generated")
    title: str = Field(description="Story title")
    description: str = Field(description="Story description")
    technique_applied: Optional[str] = Field(None, description="Technique used to generate story")
    parent_epic: Optional[str] = Field(None, description="Parent epic reference")
    story_points: Optional[int] = Field(None, description="Estimated story points")
    initial_acceptance_criteria: List[str] = Field(default_factory=list, description="Draft ACs")


class StoryGenerationResult(BaseModel):
    """Structured output for story generation."""

    stories: List[StoryCandidate] = Field(default_factory=list)


class TemplateSection(BaseModel):
    """Section in a story template."""

    name: str = Field(description="Section name")
    format: str = Field(description="Section format (gherkin, free_form, etc.)")
    min_items: Optional[int] = Field(None, description="Minimum required items")


class TemplateSchema(BaseModel):
    """Parsed template schema."""

    required_fields: List[str] = Field(default_factory=list)
    optional_fields: List[str] = Field(default_factory=list)
    format_style: str = Field(description="Template format style")
    sections: List[TemplateSection] = Field(default_factory=list)


class IntentExtraction(BaseModel):
    """Intent extraction for knowledge retrieval."""

    feature: Optional[str] = Field(None, description="Primary feature or capability")
    integration: Optional[str] = Field(None, description="Integration or external system")
    domain: Optional[str] = Field(None, description="Domain classification")
    user_type: Optional[str] = Field(None, description="User persona or role")
    keywords: List[str] = Field(default_factory=list, description="Search keywords")


class RetrievedDecision(BaseModel):
    """Decision retrieved from knowledge sources."""

    id: Optional[str] = Field(None, description="Decision identifier if known")
    text: str = Field(description="Decision text")
    source: str = Field(description="Source reference")
    confidence: float = Field(ge=0.0, le=1.0, description="Decision confidence")


class RetrievedConstraint(BaseModel):
    """Constraint retrieved from knowledge sources."""

    id: Optional[str] = Field(None, description="Constraint identifier if known")
    text: str = Field(description="Constraint text")
    source: str = Field(description="Source reference")


class RetrievedDoc(BaseModel):
    """Relevant document snippet."""

    title: str = Field(description="Document title")
    excerpt: str = Field(description="Relevant excerpt")
    source: str = Field(description="Source reference")
    relevance: float = Field(ge=0.0, le=1.0, description="Relevance score")


class CodeContextSnippet(BaseModel):
    """Relevant code context snippet."""

    file: str = Field(description="File path")
    snippet: str = Field(description="Code snippet")
    note: Optional[str] = Field(None, description="Additional note")


class RetrievedContext(BaseModel):
    """Aggregated retrieved context across sources."""

    decisions: List[RetrievedDecision] = Field(default_factory=list)
    constraints: List[RetrievedConstraint] = Field(default_factory=list)
    relevant_docs: List[RetrievedDoc] = Field(default_factory=list)
    code_context: List[CodeContextSnippet] = Field(default_factory=list)


class AcceptanceCriteriaItem(BaseModel):
    """Acceptance criteria entry."""

    type: Literal["gherkin", "free_form"] = Field(description="AC format type")
    scenario: Optional[str] = Field(None, description="Scenario title for gherkin")
    given: Optional[str] = Field(None, description="Given clause")
    when: Optional[str] = Field(None, description="When clause")
    then: Optional[str] = Field(None, description="Then clause")
    text: Optional[str] = Field(None, description="Free-form acceptance criterion")


class PopulatedStory(BaseModel):
    """Populated story based on template and context."""

    title: str = Field(description="Story title")
    description: str = Field(description="Story description")
    acceptance_criteria: List[AcceptanceCriteriaItem] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    nfrs: List[str] = Field(default_factory=list)
    out_of_scope: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)


class PopulatedStoryDraft(BaseModel):
    """Loose LLM output for populated story."""

    title: str = Field(description="Story title")
    description: str = Field(description="Story description")
    acceptance_criteria: Union[List[AcceptanceCriteriaItem], List[str], str] = Field(
        default_factory=list
    )
    dependencies: Union[List[str], str] = Field(default_factory=list)
    nfrs: Union[List[str], str] = Field(default_factory=list)
    out_of_scope: Union[List[str], str] = Field(default_factory=list)
    assumptions: Union[List[str], str] = Field(default_factory=list)
    open_questions: Union[List[str], str] = Field(default_factory=list)


class InvestScore(BaseModel):
    """INVEST scoring results."""

    independent: bool
    negotiable: bool
    valuable: bool
    estimable: bool
    small: bool
    testable: bool
    overall: Literal["pass", "warning", "fail"]


class ValidationIssue(BaseModel):
    """Validation issue entry."""

    severity: Literal["warning", "error"] = Field(description="Issue severity")
    type: str = Field(description="Issue type")
    message: str = Field(description="Issue description")
    suggestion: Optional[str] = Field(None, description="Suggested fix")


class ValidationGap(BaseModel):
    """Validation gap entry."""

    field: str = Field(description="Field with gap")
    gap: str = Field(description="Gap description")
    suggestion: Optional[str] = Field(None, description="Suggested fix")


class TechnicalRisk(BaseModel):
    """Technical risk entry."""

    risk: str = Field(description="Risk description")
    mitigation: Optional[str] = Field(None, description="Mitigation suggestion")


class ValidationResults(BaseModel):
    """Validation and gap detection results."""

    invest_score: InvestScore
    issues: List[ValidationIssue] = Field(default_factory=list)
    gaps: List[ValidationGap] = Field(default_factory=list)
    ungrounded_claims: List[str] = Field(default_factory=list)
    technical_risks: List[TechnicalRisk] = Field(default_factory=list)


class ValidationResultsDraft(BaseModel):
    """Loose LLM output for validation results."""

    invest_score: Dict[str, Any] = Field(default_factory=dict)
    issues: List[Any] = Field(default_factory=list)
    gaps: List[Any] = Field(default_factory=list)
    ungrounded_claims: List[Any] = Field(default_factory=list)
    technical_risks: List[Any] = Field(default_factory=list)


class OrchestratorDecision(BaseModel):
    """Routing decision for story writing orchestrator."""

    next_action: Literal[
        "epic_analysis",
        "splitting_strategy",
        "story_generation",
        "template_parser",
        "knowledge_retrieval",
        "story_writer",
        "validation",
        "critique_loop",
        "end",
    ]
    reasoning: str = Field(description="Explanation for routing decision")


class IntegrationDetail(BaseModel):
    """Detail entry for an integration."""

    label: str = Field(description="Detail label")
    value: str = Field(description="Detail value")


class IntegrationInfo(BaseModel):
    """Summary information for an integration."""

    name: str = Field(description="Integration display name")
    status: Literal["connected", "not_connected", "error"] = Field(description="Connection status")
    action: str = Field(description="Primary action label")
    action_type: Literal["connect", "scopes", "workspace", "repos"] = Field(
        description="Primary action type"
    )
    details: List[IntegrationDetail] = Field(default_factory=list)
    footer_action: Optional[str] = Field(None, description="Optional footer action label")


class IntegrationConnectRequest(BaseModel):
    """Request to connect an integration."""

    token: Optional[str] = Field(None, description="OAuth token or API key")


class IntegrationScopeUpdate(BaseModel):
    """Request to update integration scopes."""

    scopes: List[str] = Field(default_factory=list, description="Allowed projects or scopes")


class IntegrationTestResult(BaseModel):
    """Result for testing an integration connection."""

    success: bool = Field(description="Test result")
    message: str = Field(description="Result message")
