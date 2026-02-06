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
    source: Literal["notion", "github", "jira", "confluence", "direct", "codebase"]
    last_updated: str  # ISO format datetime string
    topics: List[str] = Field(default_factory=list, description="Semantic tags derived during ingestion")
    location: str = Field(description="File path (GitHub) or Page URL (Notion)")
    score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Similarity score from vector search")


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


class SplitArtifactItem(BaseModel):
    """One artifact in a split proposal (multiple smaller stories from one large one)."""

    title: str = Field(description="User story title for this artifact")
    description: str = Field(description="Description for this artifact")
    acceptance_criteria: List[str] = Field(description="Acceptance criteria for this artifact")
    suggested_ref_suffix: Optional[str] = Field(
        None,
        description="Optional short label for traceability, e.g. Order, Frame, Glasses",
    )


class ArtifactSplitProposal(BaseModel):
    """PO Agent output when proposing to split one large artifact into multiple smaller ones."""

    artifacts: List[SplitArtifactItem] = Field(
        description="List of smaller artifacts that together preserve original scope"
    )
    rationale: Optional[str] = Field(None, description="Why the split was proposed")


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
        "propose_split",
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
    retrieval_sources: List[str] = Field(
        default_factory=list,
        description="Preferred evidence sources (e.g., jira, confluence, github, notion, direct)",
    )
    direct_sources: List[str] = Field(
        default_factory=list,
        description="Direct URLs or source identifiers to include as evidence",
    )
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
    url: Optional[str] = Field(None, description="Source URL if available")
    relevance: float = Field(ge=0.0, le=1.0, description="Relevance score")


class EvidenceItem(BaseModel):
    """Normalized evidence item for UI and references."""

    id: str = Field(description="Evidence identifier")
    source: str = Field(description="Source system or type")
    title: str = Field(description="Evidence title")
    excerpt: Optional[str] = Field(None, description="Short excerpt")
    url: Optional[str] = Field(None, description="Source URL if available")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score")
    doc_id: Optional[str] = Field(None, description="Document identifier if known")
    chunk_id: Optional[str] = Field(None, description="Chunk identifier if known")
    section: Optional[str] = Field(None, description="Story section supported by this evidence")


class ContextGraphNode(BaseModel):
    """Node in the lightweight context graph."""

    id: str = Field(description="Unique node identifier")
    type: Literal[
        "source",
        "document",
        "chunk",
        "entity",
        "story",
        "story_section",
        "decision",
    ] = Field(description="Node type")
    label: str = Field(description="Human-readable label")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextGraphEdge(BaseModel):
    """Edge in the lightweight context graph."""

    source: str = Field(description="Source node id")
    target: str = Field(description="Target node id")
    type: Literal[
        "SOURCE_OF",
        "PART_OF",
        "MENTIONS",
        "DERIVED_FROM",
        "SUPPORTS",
        "CONFLICTS_WITH",
    ] = Field(description="Edge type")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextGraphSnapshot(BaseModel):
    """Context graph snapshot for a workflow run."""

    run_id: Optional[str] = Field(None, description="Workflow run identifier")
    story_id: Optional[str] = Field(None, description="Story identifier if available")
    nodes: List[ContextGraphNode] = Field(default_factory=list)
    edges: List[ContextGraphEdge] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
        "split_proposal",
        "end",
    ]
    reasoning: str = Field(description="Explanation for routing decision")


class IntegrationDetail(BaseModel):
    """Detail entry for an integration."""

    label: str = Field(description="Detail label")
    value: str = Field(description="Detail value")


class IntegrationAction(BaseModel):
    """Action metadata for integration controls."""

    label: str = Field(description="Action label")
    action_type: Literal["connect", "scopes", "workspace", "repos", "test", "sync"] = Field(
        description="Action type"
    )


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
    footer_actions: List[IntegrationAction] = Field(
        default_factory=list, description="Footer action list"
    )


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


# =============================================================================
# Prompt Library & Management Models
# =============================================================================


class PromptCategory(str, Enum):
    """Categories for prompt templates."""

    AGENT_SYSTEM = "agent_system"  # System prompts for agents
    AGENT_TASK = "agent_task"  # Task-specific prompts
    CRITIQUE = "critique"  # Critique and validation prompts
    EXTRACTION = "extraction"  # Entity/intent extraction prompts
    GENERATION = "generation"  # Content generation prompts
    SYNTHESIS = "synthesis"  # Synthesis and summarization prompts
    ROUTING = "routing"  # Orchestrator routing prompts


class PromptModelVariant(BaseModel):
    """Model-specific variant of a prompt template.
    
    Different LLM providers may require different prompt formats or
    optimizations for best performance.
    """

    model_pattern: str = Field(
        description="Model name pattern (e.g., 'ollama/*', 'gpt-4*', 'claude-3*')"
    )
    template: str = Field(description="Model-specific prompt template")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Recommended temperature")
    max_tokens: Optional[int] = Field(None, description="Recommended max tokens")
    notes: Optional[str] = Field(None, description="Notes about this variant")


class PromptVariable(BaseModel):
    """Variable definition for prompt templates."""

    name: str = Field(description="Variable name (used in template as {name})")
    description: str = Field(description="What this variable represents")
    required: bool = Field(default=True, description="Whether variable is required")
    default: Optional[str] = Field(None, description="Default value if not provided")
    example: Optional[str] = Field(None, description="Example value for documentation")


class PromptPerformanceMetrics(BaseModel):
    """Performance metrics for a prompt template version."""

    total_uses: int = Field(default=0, description="Total number of times used")
    success_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="Success rate (0-1)")
    avg_latency_ms: float = Field(default=0.0, ge=0.0, description="Average latency in ms")
    avg_input_tokens: float = Field(default=0.0, ge=0.0, description="Average input tokens")
    avg_output_tokens: float = Field(default=0.0, ge=0.0, description="Average output tokens")
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Quality score if evaluated")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Error rate")


class PromptVersion(BaseModel):
    """A specific version of a prompt template."""

    version: str = Field(description="Version string (semver format, e.g., '1.0.0')")
    template: str = Field(description="The prompt template text with {variables}")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(None, description="Author identifier")
    changelog: Optional[str] = Field(None, description="Description of changes in this version")
    is_active: bool = Field(default=True, description="Whether this version is active")
    metrics: PromptPerformanceMetrics = Field(
        default_factory=PromptPerformanceMetrics,
        description="Performance metrics for this version"
    )
    model_variants: List[PromptModelVariant] = Field(
        default_factory=list,
        description="Model-specific variants of this prompt"
    )


class PromptTemplate(BaseModel):
    """A prompt template with versioning, metadata, and performance tracking.
    
    This is the core entity for the Prompt Library, supporting:
    - Version control for prompt iterations
    - Model-specific variants
    - Performance metrics tracking
    - Variable substitution
    - Agent/category tagging
    """

    id: str = Field(description="Unique identifier for this prompt template")
    name: str = Field(description="Human-readable name")
    description: str = Field(description="Description of what this prompt does")
    category: PromptCategory = Field(description="Prompt category")
    agent_type: Optional[str] = Field(
        None, 
        description="Agent type this prompt is for (e.g., 'po_agent', 'qa_agent')"
    )
    tags: List[str] = Field(default_factory=list, description="Tags for filtering and search")
    
    # Variables
    variables: List[PromptVariable] = Field(
        default_factory=list,
        description="Variable definitions for this template"
    )
    
    # Versioning
    current_version: str = Field(description="Current active version")
    versions: List[PromptVersion] = Field(
        default_factory=list,
        description="All versions of this prompt"
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = Field(None, description="Author identifier")
    
    # Feature flags
    enable_ab_testing: bool = Field(default=False, description="Enable A/B testing")
    ab_test_config: Optional["ABTestConfig"] = Field(None, description="A/B test configuration")

    def get_current_template(self) -> str:
        """Get the template text for the current version."""
        for v in self.versions:
            if v.version == self.current_version:
                return v.template
        return ""

    def get_template_for_model(self, model_name: str) -> str:
        """Get the best template for a specific model.
        
        First checks for model-specific variants, falls back to default template.
        """
        for v in self.versions:
            if v.version == self.current_version:
                # Check for model-specific variant
                for variant in v.model_variants:
                    import fnmatch
                    if fnmatch.fnmatch(model_name, variant.model_pattern):
                        return variant.template
                # Fall back to default template
                return v.template
        return ""

    def render(self, model_name: str, **kwargs: Any) -> str:
        """Render the template with variable substitution.
        
        Args:
            model_name: Model name for selecting variant
            **kwargs: Variable values to substitute
            
        Returns:
            Rendered prompt string
        """
        template = self.get_template_for_model(model_name)
        
        # Apply defaults for missing variables
        for var in self.variables:
            if var.name not in kwargs and var.default is not None:
                kwargs[var.name] = var.default
        
        # Substitute variables
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required variable: {e}")


class ABTestConfig(BaseModel):
    """Configuration for A/B testing between prompt versions."""

    test_id: str = Field(description="Unique identifier for this A/B test")
    name: str = Field(description="Test name")
    description: Optional[str] = Field(None, description="Test description")
    
    # Variants
    control_version: str = Field(description="Control version (baseline)")
    treatment_versions: List[str] = Field(description="Treatment versions to test")
    traffic_split: Dict[str, float] = Field(
        description="Traffic split by version (must sum to 1.0)"
    )
    
    # Configuration
    start_time: Optional[datetime] = Field(None, description="Test start time")
    end_time: Optional[datetime] = Field(None, description="Test end time")
    min_sample_size: int = Field(default=100, description="Minimum samples per variant")
    
    # Metrics to track
    primary_metric: str = Field(
        default="success_rate",
        description="Primary metric for evaluation"
    )
    secondary_metrics: List[str] = Field(
        default_factory=lambda: ["latency", "quality_score"],
        description="Secondary metrics to track"
    )
    
    # State
    is_active: bool = Field(default=False, description="Whether test is currently active")
    results: Dict[str, PromptPerformanceMetrics] = Field(
        default_factory=dict,
        description="Results by version"
    )


class PromptExecutionRecord(BaseModel):
    """Record of a single prompt execution for monitoring."""

    id: str = Field(description="Unique execution identifier")
    prompt_id: str = Field(description="Prompt template identifier")
    version: str = Field(description="Version used")
    model: str = Field(description="Model used")
    
    # Timing
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: float = Field(description="Execution latency in ms")
    
    # Tokens
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    
    # Result
    success: bool = Field(description="Whether execution succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")
    
    # Quality (optional, may be filled later by evaluation)
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    quality_feedback: Optional[str] = Field(None, description="Quality evaluation feedback")
    
    # Context
    agent_type: Optional[str] = Field(None, description="Agent that used this prompt")
    workflow_id: Optional[str] = Field(None, description="Workflow run identifier")
    trace_id: Optional[str] = Field(None, description="Trace identifier for observability")
    
    # A/B Testing
    ab_test_id: Optional[str] = Field(None, description="A/B test identifier if in test")
    is_control: Optional[bool] = Field(None, description="Whether this is control variant")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PromptLibrarySummary(BaseModel):
    """Summary statistics for the prompt library."""

    total_prompts: int = Field(default=0)
    prompts_by_category: Dict[str, int] = Field(default_factory=dict)
    prompts_by_agent: Dict[str, int] = Field(default_factory=dict)
    total_executions: int = Field(default=0)
    avg_success_rate: float = Field(default=1.0)
    avg_latency_ms: float = Field(default=0.0)
    active_ab_tests: int = Field(default=0)
    top_performing_prompts: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
