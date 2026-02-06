"""Dependency Injection container."""

import importlib
from typing import Callable, Optional

from src.adapters.llm.litellm_adapter import LiteLLMAdapter
from src.application.workflows.registry import WorkflowRegistry
from src.config import settings
from src.domain.interfaces import (
    IEventBus,
    IKnowledgeBase,
    ILLMProvider,
    IMemoryStore,
    IIssueTracker,
    IWebhookIngress,
    IContextGraphStore,
)
from src.infrastructure.admin_store import AdminStore
from src.infrastructure.messaging.event_bus import InMemoryEventBus
from src.infrastructure.memory.context_graph_store import InMemoryContextGraphStore
from src.infrastructure.memory.in_memory_store import InMemoryStore
from src.ingestion.vector_db import InMemoryKnowledgeBase, LanceDBAdapter


def _load_adapter_class(adapter_path: str) -> type:
    """Load an adapter class from a module path.

    Args:
        adapter_path: Import path in the form "module.path:ClassName".

    Returns:
        Adapter class object.
    """
    module_path, _, class_name = adapter_path.partition(":")
    if not module_path or not class_name:
        raise ValueError(
            f"Invalid adapter path '{adapter_path}'. Expected 'module.path:ClassName'."
        )
    module = importlib.import_module(module_path)
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise ValueError(
            f"Adapter class '{class_name}' not found in module '{module_path}'."
        ) from exc


class DIContainer:
    """Simple dependency injection container."""

    def __init__(self):
        """Initialize container with factory functions."""
        self._issue_tracker: Optional[IIssueTracker] = None
        self._knowledge_base: Optional[IKnowledgeBase] = None
        self._llm_provider: Optional[ILLMProvider] = None
        self._webhook_ingress: Optional[IWebhookIngress] = None
        self._admin_store: Optional[AdminStore] = None
        self._event_bus: Optional[IEventBus] = None
        self._memory_store: Optional[IMemoryStore] = None
        self._context_graph_store: Optional[IContextGraphStore] = None
        self._workflow_registry: Optional[WorkflowRegistry] = None

    def get_issue_tracker(self) -> IIssueTracker:
        """Get issue tracker adapter.

        Returns:
            Configured issue tracker adapter instance.
        """
        if self._issue_tracker is None:
            provider = settings.issue_tracker_provider.strip().lower()
            adapter_path = settings.issue_tracker_adapter_path.strip()
            if not adapter_path:
                adapter_path = settings.issue_tracker_adapters.get(provider, "")
            if not adapter_path:
                raise ValueError(f"Unsupported issue tracker provider: {provider}")
            adapter_cls = _load_adapter_class(adapter_path)
            self._issue_tracker = adapter_cls()
        return self._issue_tracker

    def get_knowledge_base(self, embedding_fn: Callable[[str], list[float]]) -> IKnowledgeBase:
        """Get knowledge base adapter.

        Args:
            embedding_fn: Embedding function for vectorization.

        Returns:
            LanceDBAdapter instance.
        """
        if self._knowledge_base is None:
            if settings.knowledge_base_backend == "memory":
                self._knowledge_base = InMemoryKnowledgeBase(embedding_fn)
            else:
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

    def get_webhook_ingress(self) -> IWebhookIngress:
        """Get webhook ingress adapter.

        Returns:
            Configured webhook ingress adapter instance.
        """
        if self._webhook_ingress is None:
            provider = settings.webhook_provider.strip().lower()
            adapter_path = settings.webhook_ingress_adapter_path.strip()
            if not adapter_path:
                adapter_path = settings.webhook_ingress_adapters.get(provider, "")
            if not adapter_path:
                raise ValueError(f"Unsupported webhook provider: {provider}")
            adapter_cls = _load_adapter_class(adapter_path)
            self._webhook_ingress = adapter_cls()
        return self._webhook_ingress

    def get_admin_store(self) -> AdminStore:
        """Get admin configuration store.

        Returns:
            AdminStore instance.
        """
        if self._admin_store is None:
            self._admin_store = AdminStore()
        return self._admin_store

    def get_event_bus(self) -> IEventBus:
        """Get event bus instance."""
        if self._event_bus is None:
            self._event_bus = InMemoryEventBus()
        return self._event_bus

    def get_memory_store(self) -> IMemoryStore:
        """Get memory store instance."""
        if self._memory_store is None:
            self._memory_store = InMemoryStore()
        return self._memory_store

    def get_context_graph_store(self) -> IContextGraphStore:
        """Get context graph store instance."""
        if self._context_graph_store is None:
            self._context_graph_store = InMemoryContextGraphStore()
        return self._context_graph_store

    def get_workflow_registry(self) -> WorkflowRegistry:
        """Get workflow registry instance."""
        if self._workflow_registry is None:
            self._workflow_registry = WorkflowRegistry()
        return self._workflow_registry


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
