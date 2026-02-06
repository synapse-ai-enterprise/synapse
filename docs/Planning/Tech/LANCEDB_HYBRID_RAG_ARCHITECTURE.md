# LanceDB, Hybrid RAG & Lite GraphRAG Architecture

This document explains how LanceDB fits into Synapse's **Hybrid RAG + Lite GraphRAG** architecture for knowledge retrieval and evidence traceability.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SYNAPSE KNOWLEDGE ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        INGESTION LAYER                               │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │   Jira   │ │Confluence│ │  GitHub  │ │  Notion  │ │ Codebase │  │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │   │
│  │       │            │            │            │            │         │   │
│  │       └────────────┴─────┬──────┴────────────┴────────────┘         │   │
│  │                          ▼                                          │   │
│  │                   ┌─────────────┐                                   │   │
│  │                   │  Chunking   │  (src/ingestion/chunking.py)      │   │
│  │                   │  + Summary  │                                   │   │
│  │                   └──────┬──────┘                                   │   │
│  └──────────────────────────┼──────────────────────────────────────────┘   │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      VECTOR STORE (LanceDB)                          │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │  ./data/lancedb/knowledge_base                                │  │   │
│  │  │                                                               │  │   │
│  │  │  Schema:                                                      │  │   │
│  │  │  ┌────────┬────────┬────────┬────────┬────────┬────────────┐ │  │   │
│  │  │  │   id   │ vector │  text  │summary │ source │  location  │ │  │   │
│  │  │  ├────────┼────────┼────────┼────────┼────────┼────────────┤ │  │   │
│  │  │  │ doc-1  │ [...]  │ ...    │ ...    │  jira  │ PROJ-123   │ │  │   │
│  │  │  │ doc-2  │ [...]  │ ...    │ ...    │conflu. │ page/xyz   │ │  │   │
│  │  │  │ doc-3  │ [...]  │ ...    │ ...    │ github │ src/api.py │ │  │   │
│  │  │  └────────┴────────┴────────┴────────┴────────┴────────────┘ │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  │                                                                      │   │
│  │  Features:                                                           │   │
│  │  • Semantic vector search (embeddings)                               │   │
│  │  • Metadata filtering (by source: jira, confluence, etc.)            │   │
│  │  • Similarity scoring (_distance → score)                            │   │
│  │  • Persistent storage (./data/lancedb/)                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    HYBRID RAG RETRIEVAL                              │   │
│  │                                                                      │   │
│  │  KnowledgeRetrievalAgent.retrieve():                                 │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │ 1. Intent Extraction (LLM)                                  │    │   │
│  │  │    └─► keywords, domain, feature, user_type                 │    │   │
│  │  │                                                             │    │   │
│  │  │ 2. Parallel Vector Search (LanceDB)                         │    │   │
│  │  │    └─► Search each source in parallel (asyncio.gather)      │    │   │
│  │  │    └─► Return similarity scores                             │    │   │
│  │  │                                                             │    │   │
│  │  │ 3. Global Ranking + Filtering                               │    │   │
│  │  │    └─► Filter by MIN_RELEVANCE_THRESHOLD (0.25)             │    │   │
│  │  │    └─► Rank globally by score                               │    │   │
│  │  │    └─► Return top MAX_TOTAL_RESULTS (15)                    │    │   │
│  │  │                                                             │    │   │
│  │  │ 4. LLM Structuring                                          │    │   │
│  │  │    └─► Organize into: decisions, constraints,               │    │   │
│  │  │        relevant_docs, code_context                          │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                                                      │   │
│  │  Why "Hybrid"?                                                       │   │
│  │  • Vector search for semantic similarity                             │   │
│  │  • Metadata filtering for source-specific retrieval                  │   │
│  │  • LLM-based structuring for context organization                    │   │
│  │  • (Future: BM25 keyword search for hybrid ranking)                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                             │                                               │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    LITE GRAPHRAG (Context Graph)                     │   │
│  │                                                                      │   │
│  │  Built per workflow run, NOT a persistent knowledge graph:           │   │
│  │                                                                      │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │  ContextGraphSnapshot (in-memory per story)                   │  │   │
│  │  │                                                               │  │   │
│  │  │  NODES:                          EDGES:                       │  │   │
│  │  │  ┌─────────────────────┐        ┌─────────────────────────┐  │  │   │
│  │  │  │ story:STORY-123     │───────►│ story → story_section   │  │  │   │
│  │  │  │ (type: story)       │        │ (type: PART_OF)         │  │  │   │
│  │  │  ├─────────────────────┤        ├─────────────────────────┤  │  │   │
│  │  │  │ story_section:desc  │        │ source → document       │  │  │   │
│  │  │  │ (type: story_section│◄──────┤ (type: SOURCE_OF)       │  │  │   │
│  │  │  ├─────────────────────┤        ├─────────────────────────┤  │  │   │
│  │  │  │ source:jira         │        │ document → chunk        │  │  │   │
│  │  │  │ (type: source)      │───────►│ (type: PART_OF)         │  │  │   │
│  │  │  ├─────────────────────┤        ├─────────────────────────┤  │  │   │
│  │  │  │ document:doc-0      │        │ chunk → story_section   │  │  │   │
│  │  │  │ (type: document)    │───────►│ (type: SUPPORTS)        │  │  │   │
│  │  │  ├─────────────────────┤        └─────────────────────────┘  │  │   │
│  │  │  │ chunk:doc-0         │                                     │  │   │
│  │  │  │ (type: chunk)       │                                     │  │   │
│  │  │  └─────────────────────┘                                     │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  │                                                                      │   │
│  │  Why "Lite" GraphRAG?                                                │   │
│  │  • NOT a full Neo4j/graph database                                   │   │
│  │  • In-memory snapshot per workflow run                               │   │
│  │  • Purpose: Evidence traceability & provenance                       │   │
│  │  • Shows: Source → Document → Chunk → Story Section                  │   │
│  │  • Enables: UI highlighting, citation tracking                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## How LanceDB Fits In

| Component | Role | LanceDB's Part |
|-----------|------|----------------|
| **Ingestion** | Chunks and indexes documents | Stores embeddings + metadata |
| **Retrieval** | Semantic search | Performs vector similarity search |
| **Filtering** | Source-specific queries | Metadata WHERE clause (`source = 'jira'`) |
| **Scoring** | Relevance ranking | Returns `_distance` → converted to similarity score |

---

## Hybrid RAG vs Pure RAG

| Feature | Pure RAG | Hybrid RAG (Synapse) |
|---------|----------|----------------------|
| Search | Vector only | Vector + metadata filtering |
| Ranking | Single score | Multi-source parallel + global ranking |
| Structure | Raw chunks | LLM-structured (decisions, constraints, docs, code) |
| Output | Flat list | Organized by semantic category |

---

## Lite GraphRAG vs Full GraphRAG

| Feature | Full GraphRAG | Lite GraphRAG (Synapse) |
|---------|---------------|-------------------------|
| Storage | Neo4j/Graph DB | In-memory per run |
| Scope | Global knowledge graph | Per-story snapshot |
| Persistence | Permanent | Transient (workflow lifetime) |
| Entities | Extracted NER entities | Evidence items only |
| Relationships | Complex ontology | Simple: SOURCE_OF, PART_OF, SUPPORTS |
| Purpose | Knowledge discovery | Evidence traceability |

---

## Data Flow Summary

```
1. INGESTION (one-time)
   Jira/Confluence/GitHub → Chunking → Embeddings → LanceDB
   
2. RETRIEVAL (per request)
   Story Text → Intent → Parallel Vector Search → Filter → Rank → Structure
   
3. CONTEXT GRAPH (per story)
   Evidence Items → Build Nodes/Edges → ContextGraphSnapshot → UI
```

---

## Key Files

| Layer | File | Purpose |
|-------|------|---------|
| Vector Store | `src/ingestion/vector_db.py` | LanceDB adapter for search/add |
| Retrieval | `src/cognitive_engine/agents/knowledge_retrieval_agent.py` | Hybrid RAG logic |
| Graph Building | `src/cognitive_engine/story_nodes.py` | `_build_context_graph()` |
| Graph Store | `src/infrastructure/memory/context_graph_store.py` | In-memory snapshot store |
| Schema | `src/domain/schema.py` | `ContextGraphNode`, `ContextGraphEdge`, `ContextGraphSnapshot` |

---

## Why This Architecture?

1. **LanceDB for simplicity**: No external database server needed, file-based
2. **Hybrid RAG for quality**: Combines vector search with metadata filtering
3. **Lite GraphRAG for traceability**: Shows exactly where evidence came from
4. **Scalable path**: Can upgrade to full GraphRAG (Neo4j) + BM25 hybrid later

---

## Configuration

### Vector Store Settings (`.env.local`)

```bash
# Vector Store
VECTOR_STORE_PATH=./data/lancedb
KNOWLEDGE_BASE_BACKEND=lancedb  # or "memory" for in-memory

# Embedding Model
EMBEDDING_MODEL=local/all-MiniLM-L6-v2  # Local, no API key needed
# Or: text-embedding-3-small (OpenAI, requires OPENAI_API_KEY)
```

### Retrieval Tuning (`knowledge_retrieval_agent.py`)

```python
MIN_RELEVANCE_THRESHOLD = 0.25  # Filter low-quality results
MAX_RESULTS_PER_SOURCE = 10     # Per-source limit
MAX_TOTAL_RESULTS = 15          # Global top-k after ranking
```

---

## Future Enhancements

| Enhancement | Effort | Impact |
|-------------|--------|--------|
| BM25 + Vector hybrid search | Medium | Better recall for keyword queries |
| Hierarchical retrieval (summary → chunk) | High | Better precision for large docs |
| Persistent graph store (Neo4j/SQLite) | High | Cross-session traceability |
| Query expansion (multiple variants) | Medium | Better recall |
| Reranking with cross-encoder | Medium | Better precision |

---

## Related Documentation

- [Current Architecture](./CURRENT_ARCHITECTURE.md)
- [North Star Architecture](./NORTH_STAR_ARCHITECTURE.md)
- [Agentic Architecture Explainer](../AGENTIC_ARCHITECTURE_EXPLAINER.md)
