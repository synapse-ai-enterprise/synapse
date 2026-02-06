"""Knowledge base adapters implementing IKnowledgeBase."""

import asyncio
import math
from datetime import datetime
from typing import Callable, List, Literal, Optional, TYPE_CHECKING

from src.config import settings
from src.domain.interfaces import IKnowledgeBase
from src.domain.schema import UASKnowledgeUnit
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LanceDBAdapter(IKnowledgeBase):
    """LanceDB adapter for vector storage and semantic search."""

    def __init__(self, embedding_fn: Callable[[str], List[float]]):
        """Initialize adapter with embedding function.

        Args:
            embedding_fn: Function that takes text and returns embedding vector.
        """
        self.embedding_fn = embedding_fn
        self.db = None
        self.table: Optional["Table"] = None
        self._initialized = False

    async def initialize_db(self) -> None:
        """Initialize LanceDB database and create table if needed."""
        if self._initialized:
            return

        # Run blocking LanceDB operations in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._initialize_db_sync)

    def _initialize_db_sync(self) -> None:
        """Synchronous initialization of LanceDB."""
        import lancedb
        import pyarrow as pa

        self.db = lancedb.connect(settings.vector_store_path)

        table_name = "knowledge_base"

        embedding_dim = self._get_embedding_dim()

        # Check if table exists
        if table_name in self.db.table_names():
            self.table = self.db.open_table(table_name)
            existing_dim = self._get_table_vector_dim(self.table)
            if existing_dim and embedding_dim and existing_dim != embedding_dim:
                logger.warning(
                    "vector_dimension_mismatch",
                    existing_dim=existing_dim,
                    new_dim=embedding_dim,
                    action="recreate_table",
                )
                try:
                    self.db.drop_table(table_name)
                except Exception as exc:
                    logger.warning(
                        "vector_table_drop_failed",
                        error=str(exc),
                        table=table_name,
                    )
                self.table = None
        if self.table is None:
            # Create schema for knowledge base
            schema = pa.schema(
                [
                    pa.field("id", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), embedding_dim)),
                    pa.field("text", pa.string()),
                    pa.field("summary", pa.string()),
                    pa.field("source", pa.string()),
                    pa.field("location", pa.string()),
                    pa.field("last_updated", pa.string()),
                    pa.field("topics", pa.list_(pa.string())),
                    pa.field("timestamp", pa.float64()),
                ]
            )

            self.table = self.db.create_table(table_name, schema=schema, mode="overwrite")

        self._initialized = True
        logger.info("vector_db_initialized", table=table_name, embedding_dim=embedding_dim)

    def _get_embedding_dim(self) -> int:
        try:
            test_embedding = self.embedding_fn("test")
            if test_embedding:
                return len(test_embedding)
        except Exception as exc:
            logger.warning("embedding_dim_probe_failed", error=str(exc))
        return 384

    @staticmethod
    def _get_table_vector_dim(table: "Table") -> Optional[int]:
        try:
            vector_field = table.schema.field("vector")
        except Exception:
            return None
        vector_type = vector_field.type
        list_size = getattr(vector_type, "list_size", None)
        if isinstance(list_size, int) and list_size > 0:
            return list_size
        return None

    async def search(
        self,
        query: str,
        source: Optional[str] = None,
        limit: int = 10,
    ) -> List[UASKnowledgeUnit]:
        """Search the knowledge base with optional source filter.

        Args:
            query: Search query text.
            source: Optional source filter ('github' or 'notion').
            limit: Maximum number of results.

        Returns:
            List of matching knowledge units.
        """
        if not self._initialized:
            await self.initialize_db()

        # Generate query embedding
        query_vector = await asyncio.get_event_loop().run_in_executor(
            None, self.embedding_fn, query
        )

        # Validate embedding
        if not query_vector or len(query_vector) == 0:
            raise ValueError(f"Embedding function returned empty vector for query: {query[:100]}")

        # Build search query
        search_query = self.table.search(query_vector).limit(limit)

        # Apply source filter if provided
        if source:
            search_query = search_query.where(f"source = '{source}'")

        # Execute search - convert to list of dicts instead of pandas
        loop = asyncio.get_event_loop()
        arrow_table = await loop.run_in_executor(None, search_query.to_arrow)
        
        # Convert Arrow table to list of dicts (avoid pandas dependency)
        results = []
        for i in range(arrow_table.num_rows):
            row_dict = {}
            for col_name in arrow_table.column_names:
                row_dict[col_name] = arrow_table[col_name][i].as_py()
            results.append(row_dict)

        # Convert to UASKnowledgeUnit with similarity scores
        knowledge_units = []
        for row in results:
            # LanceDB returns _distance (L2 distance); convert to similarity score
            # For cosine distance: similarity = 1 - distance
            # For L2 distance: similarity = 1 / (1 + distance)
            distance = row.get("_distance", 0.5)
            similarity_score = 1.0 / (1.0 + distance) if distance >= 0 else 0.5

            unit = UASKnowledgeUnit(
                id=row["id"],
                content=row["text"],
                summary=row.get("summary", ""),
                source=row["source"],
                last_updated=row.get("last_updated", ""),
                topics=row.get("topics", []),
                location=row["location"],
                score=round(similarity_score, 4),
            )
            knowledge_units.append(unit)

        return knowledge_units

    async def add_documents(self, documents: List[UASKnowledgeUnit]) -> None:
        """Add documents to the knowledge base.

        Args:
            documents: List of knowledge units to add.
        """
        if not self._initialized:
            await self.initialize_db()

        if not documents:
            return

        # Generate embeddings for all documents
        loop = asyncio.get_event_loop()

        # Batch process embeddings
        texts = [doc.content for doc in documents]
        embeddings = await loop.run_in_executor(
            None, lambda: [self.embedding_fn(text) for text in texts]
        )

        # Prepare data for insertion
        data = []
        current_timestamp = datetime.now().timestamp()

        for doc, embedding in zip(documents, embeddings):
            data.append(
                {
                    "id": doc.id,
                    "vector": embedding,
                    "text": doc.content,
                    "summary": doc.summary,
                    "source": doc.source,
                    "location": doc.location,
                    "last_updated": doc.last_updated,
                    "topics": doc.topics,
                    "timestamp": current_timestamp,
                }
            )

        # Upsert to table
        await loop.run_in_executor(None, self.table.add, data)


class InMemoryKnowledgeBase(IKnowledgeBase):
    """In-memory knowledge base for lightweight deployments."""

    def __init__(self, embedding_fn: Callable[[str], List[float]]):
        """Initialize adapter with embedding function."""
        self.embedding_fn = embedding_fn
        self._documents: list[dict] = []

    async def initialize_db(self) -> None:
        """No-op for in-memory backend; required by sync_integration and other callers."""
        pass

    async def search(
        self,
        query: str,
        source: Optional[Literal["github", "notion", "jira", "confluence", "direct", "codebase"]] = None,
        limit: int = 10,
    ) -> List[UASKnowledgeUnit]:
        """Search knowledge base using cosine similarity."""
        query_vector = await asyncio.get_event_loop().run_in_executor(
            None, self.embedding_fn, query
        )
        if not query_vector:
            raise ValueError(f"Embedding function returned empty vector for query: {query[:100]}")

        def cosine_similarity(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(y * y for y in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        candidates = []
        for row in self._documents:
            if source and row["source"] != source:
                continue
            score = cosine_similarity(query_vector, row["vector"])
            candidates.append((score, row))

        candidates.sort(key=lambda item: item[0], reverse=True)

        results = []
        for score, row in candidates[:limit]:
            results.append(
                UASKnowledgeUnit(
                    id=row["id"],
                    content=row["text"],
                    summary=row.get("summary", ""),
                    source=row["source"],
                    last_updated=row.get("last_updated", ""),
                    topics=row.get("topics", []),
                    location=row["location"],
                    score=round(score, 4),
                )
            )
        return results

    async def add_documents(self, documents: List[UASKnowledgeUnit]) -> None:
        """Add documents to the in-memory knowledge base."""
        if not documents:
            return

        loop = asyncio.get_event_loop()
        texts = [doc.content for doc in documents]
        embeddings = await loop.run_in_executor(
            None, lambda: [self.embedding_fn(text) for text in texts]
        )

        current_timestamp = datetime.now().timestamp()
        for doc, embedding in zip(documents, embeddings):
            self._documents.append(
                {
                    "id": doc.id,
                    "vector": embedding,
                    "text": doc.content,
                    "summary": doc.summary,
                    "source": doc.source,
                    "location": doc.location,
                    "last_updated": doc.last_updated,
                    "topics": doc.topics,
                    "timestamp": current_timestamp,
                }
            )
