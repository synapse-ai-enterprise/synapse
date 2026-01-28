"""In-memory event bus implementation."""

import asyncio
from typing import Awaitable, Callable, Dict, List

from src.domain.interfaces import IEventBus
from src.domain.schema import DomainEvent


class InMemoryEventBus(IEventBus):
    """Simple in-memory async event bus."""

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable[[DomainEvent], Awaitable[None]]]] = {}

    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event."""
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            return
        await asyncio.gather(*(handler(event) for handler in handlers))

    async def publish_many(self, events: List[DomainEvent]) -> None:
        """Publish multiple domain events."""
        for event in events:
            await self.publish(event)

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None:
        """Subscribe a handler to an event type."""
        self._handlers.setdefault(event_type, []).append(handler)
