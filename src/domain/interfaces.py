"""Port interfaces using Python Protocol for structural subtyping."""

from typing import Dict, List, Literal, Optional, Protocol

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

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text."""
        ...


class IOptimizationRequest(Protocol):
    """Driving port for triggering optimization."""

    async def handle_request(self, request: OptimizationRequest) -> None:
        """Process an optimization request."""
        ...
