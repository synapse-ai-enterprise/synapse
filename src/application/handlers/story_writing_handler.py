"""Command handler for story writing workflow."""

from typing import Dict

from src.application.workflows.registry import WorkflowRegistry
from src.domain.interfaces import IEventBus, IKnowledgeBase, ILLMProvider, IMemoryStore, IProgressCallback
from src.domain.schema import DomainEvent, MemoryItem, MemoryScope, MemoryTier, StoryWritingRequest
from src.domain.use_cases import StoryWritingUseCase
from src.utils.tracing import get_trace_id


class StoryWritingHandler:
    """Handle story writing requests and emit events."""

    def __init__(
        self,
        knowledge_base: IKnowledgeBase,
        llm_provider: ILLMProvider,
        event_bus: IEventBus,
        memory_store: IMemoryStore,
        workflow_registry: WorkflowRegistry,
        progress_callback: IProgressCallback | None = None,
    ) -> None:
        self._use_case = StoryWritingUseCase(
            knowledge_base=knowledge_base,
            llm_provider=llm_provider,
            progress_callback=progress_callback,
        )
        self._event_bus = event_bus
        self._memory_store = memory_store
        self._workflow_registry = workflow_registry

    async def handle(self, request: StoryWritingRequest) -> Dict[str, object]:
        """Execute story writing and publish lifecycle events."""
        trace_id = get_trace_id()
        workflow_version = self._workflow_registry.get_version("story_writing")
        await self._event_bus.publish(
            DomainEvent(
                event_type="story_writing_started",
                trace_id=trace_id,
                payload={
                    "flow": request.flow,
                    "workflow_version": workflow_version,
                },
            )
        )

        await self._memory_store.write(
            MemoryItem(
                tier=MemoryTier.WORKING,
                scope=MemoryScope.SESSION,
                key=f"story_writing:{request.flow}",
                content=f"Story writing started for {request.flow}",
                metadata={"workflow_version": workflow_version},
            )
        )

        result = await self._use_case.execute(request)
        await self._event_bus.publish(
            DomainEvent(
                event_type="story_writing_completed",
                trace_id=trace_id,
                payload={
                    "flow": request.flow,
                    "workflow_version": workflow_version,
                    "success": result.get("success", False),
                },
            )
        )
        return result
