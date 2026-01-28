"""Command handler for optimization workflow."""

from typing import Dict

from src.application.workflows.registry import WorkflowRegistry
from src.domain.interfaces import IEventBus, IKnowledgeBase, ILLMProvider, IMemoryStore, IIssueTracker
from src.domain.schema import DomainEvent, MemoryItem, MemoryScope, MemoryTier, OptimizationRequest
from src.domain.use_cases import OptimizeArtifactUseCase
from src.utils.tracing import get_trace_id


class OptimizeArtifactHandler:
    """Handle optimization requests and emit events."""

    def __init__(
        self,
        issue_tracker: IIssueTracker,
        knowledge_base: IKnowledgeBase,
        llm_provider: ILLMProvider,
        event_bus: IEventBus,
        memory_store: IMemoryStore,
        workflow_registry: WorkflowRegistry,
    ) -> None:
        self._use_case = OptimizeArtifactUseCase(
            issue_tracker=issue_tracker,
            knowledge_base=knowledge_base,
            llm_provider=llm_provider,
        )
        self._event_bus = event_bus
        self._memory_store = memory_store
        self._workflow_registry = workflow_registry

    async def handle(self, request: OptimizationRequest) -> Dict[str, object]:
        """Execute optimization and publish lifecycle events."""
        trace_id = get_trace_id()
        workflow_version = self._workflow_registry.get_version("optimization")
        await self._event_bus.publish(
            DomainEvent(
                event_type="optimization_started",
                trace_id=trace_id,
                payload={
                    "artifact_id": request.artifact_id,
                    "workflow_version": workflow_version,
                },
            )
        )

        await self._memory_store.write(
            MemoryItem(
                tier=MemoryTier.WORKING,
                scope=MemoryScope.SESSION,
                key=f"optimization:{request.artifact_id}",
                content=f"Optimization started for {request.artifact_id}",
                metadata={"workflow_version": workflow_version},
            )
        )

        result = await self._use_case.execute(request)
        await self._event_bus.publish(
            DomainEvent(
                event_type="optimization_completed",
                trace_id=trace_id,
                payload={
                    "artifact_id": request.artifact_id,
                    "workflow_version": workflow_version,
                    "success": result.get("success", False),
                },
            )
        )
        return result
