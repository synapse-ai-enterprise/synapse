"""Dependency Injection container."""

from typing import Callable, Optional

from src.adapters.egress.linear_egress import LinearEgressAdapter
from src.adapters.ingress.linear_ingress import LinearIngressAdapter
from src.adapters.llm.litellm_adapter import LiteLLMAdapter
from src.domain.interfaces import IKnowledgeBase, IIssueTracker, ILLMProvider
from src.ingestion.vector_db import LanceDBAdapter


class DIContainer:
    """Simple dependency injection container."""

    def __init__(self):
        """Initialize container with factory functions."""
        self._issue_tracker: Optional[IIssueTracker] = None
        self._knowledge_base: Optional[IKnowledgeBase] = None
        self._llm_provider: Optional[ILLMProvider] = None
        self._linear_ingress: Optional[LinearIngressAdapter] = None

    def get_issue_tracker(self) -> IIssueTracker:
        """Get issue tracker adapter.

        Returns:
            LinearEgressAdapter instance.
        """
        if self._issue_tracker is None:
            self._issue_tracker = LinearEgressAdapter()
        return self._issue_tracker

    def get_knowledge_base(self, embedding_fn: Callable[[str], list[float]]) -> IKnowledgeBase:
        """Get knowledge base adapter.

        Args:
            embedding_fn: Embedding function for vectorization.

        Returns:
            LanceDBAdapter instance.
        """
        if self._knowledge_base is None:
            self._knowledge_base = LanceDBAdapter(embedding_fn)
            # Note: initialize_db() must be awaited by the caller
            # Cannot use asyncio.run() here as it may be called from async context
        return self._knowledge_base

    def get_llm_provider(self) -> ILLMProvider:
        """Get LLM provider adapter.

        Returns:
            LiteLLMAdapter instance.
        """
        if self._llm_provider is None:
            self._llm_provider = LiteLLMAdapter()
        return self._llm_provider

    def get_linear_ingress(self) -> LinearIngressAdapter:
        """Get Linear ingress adapter.

        Returns:
            LinearIngressAdapter instance.
        """
        if self._linear_ingress is None:
            self._linear_ingress = LinearIngressAdapter()
        return self._linear_ingress


# Global container instance
_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """Get global DI container instance.

    Returns:
        DIContainer instance.
    """
    global _container
    if _container is None:
        _container = DIContainer()
    return _container
