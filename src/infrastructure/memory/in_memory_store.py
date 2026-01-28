"""In-memory memory store implementation."""

from typing import Dict, List, Optional

from src.domain.interfaces import IMemoryStore
from src.domain.schema import MemoryItem, MemoryScope, MemoryTier


class InMemoryStore(IMemoryStore):
    """Simple in-memory memory store."""

    def __init__(self) -> None:
        self._items: Dict[str, MemoryItem] = {}

    def _key(self, tier: MemoryTier, scope: MemoryScope, key: str) -> str:
        return f"{tier.value}:{scope.value}:{key}"

    async def write(self, item: MemoryItem) -> None:
        """Persist a memory item."""
        self._items[self._key(item.tier, item.scope, item.key)] = item

    async def read(
        self,
        tier: MemoryTier,
        scope: MemoryScope,
        key: str,
    ) -> Optional[MemoryItem]:
        """Read a memory item by key."""
        return self._items.get(self._key(tier, scope, key))

    async def search(
        self,
        query: str,
        tier: Optional[MemoryTier] = None,
        scope: Optional[MemoryScope] = None,
        limit: int = 10,
    ) -> List[MemoryItem]:
        """Search memory items by query."""
        results: List[MemoryItem] = []
        for item in self._items.values():
            if tier and item.tier != tier:
                continue
            if scope and item.scope != scope:
                continue
            if query.lower() in item.content.lower():
                results.append(item)
            if len(results) >= limit:
                break
        return results

    async def delete(self, tier: MemoryTier, scope: MemoryScope, key: str) -> bool:
        """Delete a memory item by key."""
        return self._items.pop(self._key(tier, scope, key), None) is not None
