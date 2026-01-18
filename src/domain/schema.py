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


class CoreArtifact(BaseModel):
    """The Unified Agile Artifact. Abstracts Linear/GitHub into a common cognitive model."""

    internal_id: UUID = Field(default_factory=uuid4, description="System-local unique identifier")

    # Traceability
    source_system: Literal["linear", "github"] = Field(description="Source system")
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
    source_system: Literal["linear"]
    trigger: Literal["webhook", "manual", "scheduled"]
    dry_run: bool = False
