"""Port interfaces using Python Protocol for structural subtyping."""

from typing import Dict, List, Literal, Mapping, Optional, Protocol

from src.domain.schema import CoreArtifact, OptimizationRequest, UASKnowledgeUnit


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
        source: Optional[Literal["github", "notion"]] = None,
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
