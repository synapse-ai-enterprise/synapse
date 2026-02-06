"""In-memory context graph store implementation."""

from typing import Dict, Optional

from src.domain.interfaces import IContextGraphStore
from src.domain.schema import ContextGraphSnapshot


class InMemoryContextGraphStore(IContextGraphStore):
    """Simple in-memory store for context graph snapshots."""

    def __init__(self) -> None:
        self._snapshots: Dict[str, ContextGraphSnapshot] = {}

    async def write(self, snapshot: ContextGraphSnapshot) -> None:
        """Persist a context graph snapshot."""
        if not snapshot.story_id:
            return
        self._snapshots[snapshot.story_id] = snapshot

    async def read(self, story_id: str) -> Optional[ContextGraphSnapshot]:
        """Read a context graph snapshot by story id."""
        return self._snapshots.get(story_id)
