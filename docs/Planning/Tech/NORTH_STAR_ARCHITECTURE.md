# North Star Architecture

This document defines the target production architecture for the workspace. It prioritizes reliability, security, scale, and auditability.

## Principles

1. Strict hexagonal boundaries: domain is pure and dependency-free.
2. Event-driven orchestration: agents emit and consume domain events.
3. CQRS: separate command handling from read models.
4. Repository pattern: persistence behind ports.
5. Workflow versioning: safe evolution and backward compatibility.
6. Observability-first: tracing and structured logs everywhere.

## North Star Layering

### 1) Domain Layer (`src/domain/`)

Responsibilities:
- Business rules only (no IO, no frameworks).
- Domain events for agent-to-agent communication.
- Repository interfaces (ports).

Suggested structure:
```
domain/
  entities/
  value_objects/
  events/
  repositories/
  services/
  interfaces.py
  schema.py
```

### 2) Application Layer (`src/application/`)

Responsibilities:
- Use case orchestration.
- LangGraph workflow versioning.
- Command handlers and query models (CQRS).

Suggested structure:
```
application/
  workflows/
  orchestrators/
  handlers/
  queries/
```

### 3) Cognitive Engine (`src/cognitive_engine/`)

Responsibilities:
- Agent implementations and LLM interactions.
- LangGraph nodes and state adapters.
- Agent-level events.

Suggested structure:
```
cognitive_engine/
  agents/
  nodes/
  state/
  events/
```

### 4) Infrastructure (`src/infrastructure/`)

Responsibilities:
- External adapters and persistence.
- Event bus and message transport.
- DI wiring and configuration.

Suggested structure:
```
infrastructure/
  adapters/
  repositories/
  messaging/
  persistence/
  di.py
```

## Enterprise RAG Management

### Ingestion and Parsing

Goal: clean, chunked knowledge with preserved metadata.
- Source connectors: Confluence, Jira, Notion, SharePoint, Google Drive, GitHub.
- Ad-hoc uploads: files staged, scanned, parsed, and tagged.
- Advanced parsing: tables, sections, headings, images, and metadata.
- Output: normalized `Document` and `Chunk` objects with lineage.

### Indexing and Storage

Goal: searchable knowledge with policy enforcement.
- Vector DB for semantic retrieval (kNN).
- Keyword index for exact and identifier search.
- Hybrid retrieval: vector + keyword + metadata filters.
- Optional graph store for relational knowledge (GraphRAG).

### Knowledge/Context Graph

Goal: increase context quality and explainability with explicit relationships.
- Graph nodes: Source, Document, Chunk, Entity, Story, StorySection, Decision.
- Graph edges: SOURCE_OF, PART_OF, MENTIONS, DERIVED_FROM, SUPPORTS, CONFLICTS_WITH.
- Graph queries enable multi-hop reasoning, conflict detection, and provenance.
- Every response should include traceable citations to graph nodes.
 - Start with a per-run Context Graph snapshot (GraphRAG-lite) and evolve to a persistent graph store.

### Guardrails

Goal: enterprise safety before and after generation.
- Input validation: prompt injection and policy checks.
- Output validation: PII, sensitive data leakage.
- Deny lists and redaction with audit logs.

## Memory Architecture for Agents

Memory is a first-class system with explicit tiers and governance.

### A) Conversation Memory (Short-Term)

Scope: per user session.
- Stores the dialog and decisions for multi-turn continuity.
- Retained per policy with user control to forget.

### B) Working Memory (Task-Level)

Scope: workflow run.
- Stores retrieved context, extracted entities, and reasoning artifacts.
- Optimizes agent collaboration and reduces re-retrieval.

### C) Long-Term Memory (Knowledge Base)

Scope: organization-wide.
- Stores vetted knowledge assets.
- Subject to ACL, sensitivity labels, and retention policy.

### Memory Governance

- Every memory item has source, ACL, timestamp, and sensitivity.
- Memory read/write is policy-enforced and traceable.
- Outputs should cite which memory tiers influenced responses.

## Agent Runtime Flow

1. Intent classification (business vs technical vs process).
2. Retrieve from Business KB and Tech KB (policy filtered).
3. Context assembly (ranked, deduped, token budgeted).
4. Guardrails check.
5. Prompt processing + memory injection.
6. LLM inference via Litellm adapter.
7. Validation against INVEST and acceptance criteria.
8. Optional egress to Jira/Linear with audit log.

## GraphRAG Guidance

Use GraphRAG when:
- Knowledge is relational (dependencies, ownership, process chains).
- Multi-hop reasoning and explainability are required.

Start with hybrid RAG and add GraphRAG for:
- Architecture dependencies and impact analysis.
- Cross-team ownership and change propagation.

## Observability and Auditability

- OpenTelemetry tracing for each workflow and agent decision.
- Structured logging with `artifact_id`, `agent`, `iteration`.
- Knowledge usage logs: which sources were retrieved and why.
- Immutable audit trail for compliance reviews.

## Migration Roadmap

Phase 1: Foundation
- Introduce domain events and simple event bus.
- Formalize memory tiers and access policies.

Phase 2: Application layer
- Extract `application/` and add CQRS handlers.
- Add workflow registry and versioning.

Phase 3: Retrieval quality
- Implement hybrid retrieval and guardrails.
- Add knowledge lineage and ACL enforcement.

Phase 4: Scale and reliability
- Add async processing queues and workflow history store.
- Harden observability and SLA dashboards.
