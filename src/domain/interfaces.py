"""Port interfaces using Python Protocol for structural subtyping."""

from typing import Any, Awaitable, Callable, Dict, List, Literal, Mapping, Optional, Protocol

from src.domain.schema import (
    CoreArtifact,
    ContextGraphSnapshot,
    DomainEvent,
    MemoryItem,
    MemoryScope,
    MemoryTier,
    OptimizationRequest,
    PromptCategory,
    PromptExecutionRecord,
    PromptLibrarySummary,
    PromptTemplate,
    UASKnowledgeUnit,
)


class IIssueTracker(Protocol):
    """Port for issue tracker operations."""

    async def get_issue(self, issue_id: str) -> CoreArtifact:
        """Fetch an issue by ID."""
        ...

    async def update_issue(self, issue_id: str, artifact: CoreArtifact) -> bool:
        """Update an issue. Returns True if successful."""
        ...

    async def create_issue(self, artifact: CoreArtifact) -> str:
        """Create a new issue. Returns the issue URL."""
        ...

    async def post_comment(self, issue_id: str, comment: str) -> bool:
        """Post a comment to an issue."""
        ...


class IKnowledgeBase(Protocol):
    """Port for knowledge base (vector store) operations."""

    async def search(
        self,
        query: str,
        source: Optional[str] = None,
        limit: int = 10,
    ) -> List[UASKnowledgeUnit]:
        """Search the knowledge base. Filter by source if provided."""
        ...


class ILLMProvider(Protocol):
    """Port for LLM operations."""

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Generate a chat completion."""
        ...

    async def structured_completion(
        self,
        messages: List[Dict[str, str]],
        response_model: type,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> object:
        """Generate a structured completion using JSON schema.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            response_model: Pydantic model class for structured output.
            model: Model name (overrides default).
            temperature: Sampling temperature.
            
        Returns:
            Instance of response_model with parsed structured data.
        """
        ...

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text."""
        ...


class IWebhookIngress(Protocol):
    """Port for webhook ingress adapters."""

    def handle_webhook(
        self,
        payload: Dict,
        headers: Mapping[str, str],
    ) -> Optional[OptimizationRequest]:
        """Normalize a webhook payload into an optimization request."""
        ...


class IOptimizationRequest(Protocol):
    """Driving port for triggering optimization."""

    async def handle_request(self, request: OptimizationRequest) -> None:
        """Process an optimization request."""
        ...


class IEventBus(Protocol):
    """Port for publishing domain events."""

    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event."""
        ...

    async def publish_many(self, events: List[DomainEvent]) -> None:
        """Publish multiple domain events."""
        ...

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None:
        """Subscribe a handler to an event type."""
        ...


class IMemoryStore(Protocol):
    """Port for agent memory storage."""

    async def write(self, item: MemoryItem) -> None:
        """Persist a memory item."""
        ...

    async def read(
        self,
        tier: MemoryTier,
        scope: MemoryScope,
        key: str,
    ) -> Optional[MemoryItem]:
        """Read a memory item by key."""
        ...

    async def search(
        self,
        query: str,
        tier: Optional[MemoryTier] = None,
        scope: Optional[MemoryScope] = None,
        limit: int = 10,
    ) -> List[MemoryItem]:
        """Search memory items by query."""
        ...

    async def delete(self, tier: MemoryTier, scope: MemoryScope, key: str) -> bool:
        """Delete a memory item by key."""
        ...


class IContextGraphStore(Protocol):
    """Port for context graph snapshot storage."""

    async def write(self, snapshot: ContextGraphSnapshot) -> None:
        """Persist a context graph snapshot."""
        ...

    async def read(self, story_id: str) -> Optional[ContextGraphSnapshot]:
        """Read a context graph snapshot by story id."""
        ...


class IProgressCallback(Protocol):
    """Port for progress callbacks during workflow execution."""

    async def on_node_start(self, node_name: str, state: Dict) -> None:
        """Called when a node starts execution.
        
        Args:
            node_name: Name of the node starting.
            state: Current state dictionary.
        """
        ...

    async def on_node_complete(self, node_name: str, state: Dict) -> None:
        """Called when a node completes execution.
        
        Args:
            node_name: Name of the node that completed.
            state: Updated state dictionary after node execution.
        """
        ...

    async def on_iteration_update(self, iteration: int, state: Dict) -> None:
        """Called when debate iteration updates.
        
        Args:
            iteration: Current iteration number.
            state: Current state dictionary with debate history.
        """
        ...


class IPromptLibrary(Protocol):
    """Port for prompt library operations.
    
    The Prompt Library provides centralized management of prompt templates with:
    - Version control and rollback
    - Model-specific variants
    - Performance-based prompt selection
    - A/B testing capabilities
    - Collaborative editing
    """

    async def get_prompt(
        self,
        prompt_id: str,
        version: Optional[str] = None,
    ) -> Optional[PromptTemplate]:
        """Get a prompt template by ID.
        
        Args:
            prompt_id: Unique prompt identifier.
            version: Specific version to retrieve (defaults to current).
            
        Returns:
            PromptTemplate if found, None otherwise.
        """
        ...

    async def get_prompt_for_agent(
        self,
        agent_type: str,
        task: str,
        model: Optional[str] = None,
    ) -> Optional[PromptTemplate]:
        """Get the best prompt for an agent and task.
        
        Args:
            agent_type: Agent type (e.g., 'po_agent', 'qa_agent').
            task: Task identifier (e.g., 'critique', 'synthesize').
            model: Target model for variant selection.
            
        Returns:
            Best matching PromptTemplate, None if not found.
        """
        ...

    async def render_prompt(
        self,
        prompt_id: str,
        model: str,
        variables: Dict[str, Any],
        version: Optional[str] = None,
    ) -> str:
        """Render a prompt with variable substitution.
        
        Args:
            prompt_id: Unique prompt identifier.
            model: Target model for variant selection.
            variables: Variable values to substitute.
            version: Specific version to use (defaults to current).
            
        Returns:
            Rendered prompt string.
            
        Raises:
            ValueError: If prompt not found or required variable missing.
        """
        ...

    async def list_prompts(
        self,
        category: Optional[PromptCategory] = None,
        agent_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[PromptTemplate]:
        """List prompts with optional filtering.
        
        Args:
            category: Filter by category.
            agent_type: Filter by agent type.
            tags: Filter by tags (any match).
            
        Returns:
            List of matching PromptTemplates.
        """
        ...

    async def save_prompt(self, prompt: PromptTemplate) -> None:
        """Save or update a prompt template.
        
        Args:
            prompt: PromptTemplate to save.
        """
        ...

    async def delete_prompt(self, prompt_id: str) -> bool:
        """Delete a prompt template.
        
        Args:
            prompt_id: Unique prompt identifier.
            
        Returns:
            True if deleted, False if not found.
        """
        ...

    async def add_version(
        self,
        prompt_id: str,
        version: str,
        template: str,
        changelog: Optional[str] = None,
        set_active: bool = True,
    ) -> bool:
        """Add a new version to a prompt template.
        
        Args:
            prompt_id: Unique prompt identifier.
            version: New version string.
            template: Template text.
            changelog: Description of changes.
            set_active: Whether to set as current version.
            
        Returns:
            True if version added, False if prompt not found.
        """
        ...

    async def rollback_version(self, prompt_id: str, version: str) -> bool:
        """Rollback to a previous prompt version.
        
        Args:
            prompt_id: Unique prompt identifier.
            version: Version to rollback to.
            
        Returns:
            True if rolled back, False if prompt or version not found.
        """
        ...

    async def record_execution(self, record: PromptExecutionRecord) -> None:
        """Record a prompt execution for monitoring.
        
        Args:
            record: Execution record with metrics.
        """
        ...

    async def get_summary(self) -> PromptLibrarySummary:
        """Get summary statistics for the prompt library.
        
        Returns:
            PromptLibrarySummary with aggregate metrics.
        """
        ...

    async def select_ab_variant(
        self,
        prompt_id: str,
        session_id: Optional[str] = None,
    ) -> str:
        """Select a version based on A/B test configuration.
        
        Args:
            prompt_id: Unique prompt identifier.
            session_id: Session ID for consistent selection.
            
        Returns:
            Selected version string.
        """
        ...
