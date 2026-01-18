"""LanceDB Adapter implementing IKnowledgeBase."""

import asyncio
from datetime import datetime
from typing import Callable, List, Literal, Optional

import lancedb
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lancedb.table import Table

from src.config import settings
from src.domain.interfaces import IKnowledgeBase
from src.domain.schema import UASKnowledgeUnit


class LanceDBAdapter(IKnowledgeBase):
    """LanceDB adapter for vector storage and semantic search."""

    def __init__(self, embedding_fn: Callable[[str], List[float]]):
        """Initialize adapter with embedding function.

        Args:
            embedding_fn: Function that takes text and returns embedding vector.
        """
        self.embedding_fn = embedding_fn
        self.db: Optional[lancedb.DBConnection] = None
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
        import pyarrow as pa

        self.db = lancedb.connect(settings.vector_store_path)

        table_name = "knowledge_base"

        # Check if table exists
        if table_name in self.db.table_names():
            self.table = self.db.open_table(table_name)
        else:
            # Create schema for knowledge base
            schema = pa.schema(
                [
                    pa.field("id", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), 1536)),  # OpenAI embedding dimension
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

    async def search(
        self,
        query: str,
        source: Optional[Literal["github", "notion"]] = None,
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

        # Convert to UASKnowledgeUnit
        knowledge_units = []
        for row in results:
            unit = UASKnowledgeUnit(
                id=row["id"],
                content=row["text"],
                summary=row.get("summary", ""),
                source=row["source"],
                last_updated=row.get("last_updated", ""),
                topics=row.get("topics", []),
                location=row["location"],
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
        import pandas as pd

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

        df = pd.DataFrame(data)

        # Upsert to table
        await loop.run_in_executor(None, self.table.add, df)
