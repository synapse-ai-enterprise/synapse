# Current Architecture

This document captures the observed architecture of the current workspace. It is descriptive and does not prescribe future changes.

## Architectural Style

- Hexagonal Architecture (Ports and Adapters)
- LangGraph for multi-agent orchestration
- Pydantic v2 for domain models
- Dependency Injection via `src/infrastructure/di.py`
- Async IO for external integrations

## High-Level Layers

1) Domain Layer (`src/domain/`)
- `schema.py`: Unified Agile Schema (UAS) Pydantic models
- `interfaces.py`: Port definitions using `typing.Protocol`
- `use_cases.py`: Use case coordination

2) Application Layer (`src/application/`)
- Command handlers: `handlers/` (orchestration boundary)
- Workflow registry: `workflows/registry.py` (version metadata)
- Query models: `queries/` (placeholders for CQRS read models)

3) Cognitive Engine (`src/cognitive_engine/`)
- LangGraph workflows: `graph.py`, `story_graph.py`
- Agents: `agents/` (PO, QA, Dev, Supervisor, and story pipeline agents)
- State: `state.py`, `story_state.py`
- Nodes: `nodes.py`, `story_nodes.py`

4) Infrastructure / Adapters
- Ingress adapters: `src/adapters/ingress/`
- Egress adapters: `src/adapters/egress/`
- LLM adapter: `src/adapters/llm/litellm_adapter.py`
- Ingestion: `src/ingestion/` (LanceDB-backed vector storage)
- Infrastructure services: `src/infrastructure/` (DI, queue, workers)
- Event bus: `src/infrastructure/messaging/event_bus.py`
- Memory store: `src/infrastructure/memory/in_memory_store.py`

5) Entry Points
- `src/main.py` as API boundary and CLI entry
- `/webhooks/issue-tracker` for ingress
- `/api/story-writing` for story workflow
- `/api/integrations` for integration status/config

6) UI Layer
- `ui/` for the frontend (Vite + React)
- UI calls the integration and story-writing APIs

## Current Agent Workflows

### Optimization Workflow

Flow (simplified):
1. Ingress request
2. Context assembly
3. Supervisor agent
4. Draft + critique loop (PO, QA, Dev)
5. Synthesis + validation
6. Egress / downstream output

### Story Writing Workflow

Flow (simplified):
1. Orchestrator
2. Epic analysis
3. Splitting strategy
4. Story generation
5. Validation gap
6. Story writer

## Data Flow (Current)

1. External systems or UI trigger API in `src/main.py`
2. Application handlers in `src/application/handlers/` are invoked
3. Use cases in `src/domain/use_cases.py` run via LangGraph workflows
4. Agents call LLM adapter and retrieval services
5. Optional async queue/worker executes optimization requests
6. Event bus emits workflow lifecycle events
7. Egress adapter updates downstream systems (e.g., Linear)

## Observability

- Structured logging (structlog)
- OpenTelemetry traces with `trace_id` on artifacts

## Noted Gaps and Risks

- Event bus is in-memory only (no durable transport)
- Workflow versioning is metadata-only (no parallel versions)
- CQRS is partial (queries are placeholders)
- Memory store is in-memory only (no persistence or ACLs)
- Guardrails and policy enforcement not fully implemented
