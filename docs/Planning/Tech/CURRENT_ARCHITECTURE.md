# Current Architecture

This document captures the observed architecture of the current workspace. It is descriptive and does not prescribe future changes.

## Architectural Style

- Hexagonal Architecture (Ports and Adapters)
- LangGraph for multi-agent orchestration
- Pydantic v2 for domain models
- Dependency Injection via `src/infrastructure/di.py`
- Async IO for external integrations

## Repository Structure

```
synapse/
├── api/                          # Vercel serverless entry
│   └── index.py
├── docs/                         # Documentation
│   ├── Planning/
│   │   ├── Tech/                 # Architecture docs
│   │   │   ├── CURRENT_ARCHITECTURE.md
│   │   │   ├── NORTH_STAR_ARCHITECTURE.md
│   │   │   ├── SYNAPSE_ARCHITECTURE_DIAGRAM.md
│   │   │   └── LANCEDB_HYBRID_RAG_ARCHITECTURE.md
│   │   ├── FIGMA_AGENT_MAPPING.md
│   │   ├── ROLES.md
│   │   ├── SYNAPSE_BACKLOG.md
│   │   ├── UI_API_CONTRACTS.md
│   │   └── USER_FLOW_STORY_DETAILING.md
│   ├── Implementation/           # Implementation tracking
│   │   ├── AGENTS_CONSOLIDATED.md
│   │   ├── IMPLEMENTATION_STATUS.md
│   │   └── MVP_STORY_DETAILING.md
│   ├── AGENTIC_ARCHITECTURE_EXPLAINER.md
│   └── DEPLOYMENT_VERCEL.md
├── scripts/                      # Utility scripts
│   ├── demo.py                   # Demo runner
│   ├── health_check.py           # Health check utility
│   ├── ingest_knowledge.py       # Knowledge ingestion
│   ├── setup_demo.sh             # Demo setup
│   ├── start_local_ui_backend.sh # Start dev servers
│   └── stop_local_ui_backend.sh  # Stop dev servers
├── src/                          # Backend source code
│   ├── adapters/                 # Hexagonal adapters
│   │   ├── egress/               # Output adapters
│   │   │   ├── jira_egress.py
│   │   │   ├── linear_egress.py
│   │   │   └── mock_issue_tracker.py
│   │   ├── ingress/              # Input adapters
│   │   │   └── linear_ingress.py
│   │   ├── llm/                  # LLM adapters
│   │   │   └── litellm_adapter.py
│   │   └── rate_limiter.py
│   ├── application/              # Application layer
│   │   ├── handlers/             # Command handlers
│   │   │   ├── optimize_artifact_handler.py
│   │   │   └── story_writing_handler.py
│   │   ├── queries/              # Query models (CQRS)
│   │   └── workflows/
│   │       └── registry.py       # Workflow versioning
│   ├── cognitive_engine/         # AI/Agent layer
│   │   ├── agents/               # Specialist agents
│   │   │   ├── developer_agent.py
│   │   │   ├── epic_analysis_agent.py
│   │   │   ├── knowledge_retrieval_agent.py
│   │   │   ├── orchestrator_agent.py
│   │   │   ├── po_agent.py
│   │   │   ├── qa_agent.py
│   │   │   ├── splitting_strategy_agent.py
│   │   │   ├── story_generation_agent.py
│   │   │   ├── story_writer_agent.py
│   │   │   ├── supervisor.py
│   │   │   ├── template_parser_agent.py
│   │   │   └── validation_gap_agent.py
│   │   ├── graph.py              # Main LangGraph workflow
│   │   ├── splitting_graph.py    # Story splitting workflow
│   │   ├── story_graph.py        # Story writing workflow
│   │   ├── nodes.py              # Graph nodes
│   │   ├── story_nodes.py        # Story workflow nodes
│   │   ├── state.py              # Cognitive state
│   │   ├── story_state.py        # Story state
│   │   └── invest.py             # INVEST validation
│   ├── domain/                   # Domain layer (core)
│   │   ├── schema.py             # Pydantic models (UAS)
│   │   ├── interfaces.py         # Port definitions
│   │   └── use_cases.py          # Business logic
│   ├── infrastructure/           # Infrastructure layer
│   │   ├── memory/
│   │   │   ├── context_graph_store.py
│   │   │   └── in_memory_store.py
│   │   ├── messaging/
│   │   │   └── event_bus.py
│   │   ├── admin_store.py        # Admin state storage
│   │   ├── di.py                 # Dependency injection
│   │   ├── prompt_library.py     # Prompt management
│   │   ├── queue.py              # Task queue
│   │   └── workers.py            # Background workers
│   ├── ingestion/                # Data ingestion
│   │   ├── chunking.py           # Text chunking
│   │   ├── confluence_loader.py  # Confluence loader
│   │   ├── github_loader.py      # GitHub loader
│   │   ├── jira_loader.py        # Jira loader
│   │   ├── notion_loader.py      # Notion loader
│   │   └── vector_db.py          # LanceDB vector store
│   ├── utils/                    # Utilities
│   │   ├── logger.py             # Structured logging
│   │   ├── prompt_monitor.py     # Prompt observability
│   │   └── tracing.py            # OpenTelemetry
│   ├── config.py                 # Configuration
│   └── main.py                   # FastAPI entry point
├── tests/                        # Test suite
│   ├── conftest.py               # Pytest fixtures
│   ├── test_adapters.py
│   ├── test_agents.py
│   ├── test_ingestion.py
│   ├── test_smoke.py
│   └── test_workflow.py
├── ui/                           # Frontend (React + Vite)
│   ├── src/
│   │   ├── app/
│   │   │   └── App.jsx           # Main app component
│   │   ├── microfrontends/       # Feature modules
│   │   │   ├── AdminApp.jsx      # Admin console
│   │   │   ├── EpicApp.jsx       # Epic management
│   │   │   ├── HistoryApp.jsx    # History view
│   │   │   ├── HomeApp.jsx       # Home dashboard
│   │   │   ├── InitiativeApp.jsx # Initiative view
│   │   │   ├── PromptManagementApp.jsx  # Prompt management
│   │   │   └── StoryApp.jsx      # Story editor
│   │   ├── shared/               # Shared utilities
│   │   │   ├── api.js            # API client
│   │   │   ├── data.js           # Static data
│   │   │   └── flows.js          # Workflow flows
│   │   ├── main.jsx              # Entry point
│   │   └── styles.css            # Global styles
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .cursorrules                  # Cursor AI rules
├── .env.example                  # Environment template
├── .gitignore
├── pyproject.toml                # Python project config
├── requirements.txt              # Python dependencies
├── vercel.json                   # Vercel deployment
└── README.md
```

### Key Directories

| Directory | Purpose |
|-----------|---------|
| `src/domain/` | Core business logic, Pydantic models, port interfaces |
| `src/adapters/` | External system integrations (LLM, issue trackers) |
| `src/cognitive_engine/` | AI agents and LangGraph workflows |
| `src/infrastructure/` | DI, messaging, storage, prompt library |
| `src/ingestion/` | Data loaders and vector DB |
| `ui/src/microfrontends/` | React feature modules |
| `docs/Planning/Tech/` | Architecture documentation |
| `scripts/` | Development and demo utilities |

## High-Level Layers

1) Domain Layer (`src/domain/`)
- `schema.py`: Unified Agile Schema (UAS) Pydantic models, including Prompt Management schemas
- `interfaces.py`: Port definitions using `typing.Protocol`, including `IPromptLibrary`
- `use_cases.py`: Use case coordination

2) Application Layer (`src/application/`)
- Command handlers: `handlers/` (orchestration boundary)
- Workflow registry: `workflows/registry.py` (version metadata)
- Query models: `queries/` (placeholders for CQRS read models)

3) Cognitive Engine (`src/cognitive_engine/`)
- LangGraph workflows: `graph.py`, `story_graph.py`, `splitting_graph.py`
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
- Prompt Library: `src/infrastructure/prompt_library.py` (centralized prompt management)

5) Entry Points
- `src/main.py` as API boundary and CLI entry
- `/webhooks/issue-tracker` for ingress
- `/api/story-writing` for story workflow
- `/api/integrations` for integration status/config
- `/api/prompts/*` for prompt library management
- `/api/observability/prompts` for prompt monitoring

6) UI Layer
- `ui/` for the frontend (Vite + React)
- UI calls the integration and story-writing APIs
- Admin Console with Audit & Governance for prompt management

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
- Prompt Monitoring (`src/utils/prompt_monitor.py`):
  - Tracks LLM call metrics (latency, tokens, cost)
  - Latency percentiles (P50, P95, P99)
  - Cost estimation per model
  - Quality score tracking
  - Configurable alerting thresholds
  - Breakdown by model, agent, and prompt template

## Prompt Management

The system includes a centralized Prompt Library for managing LLM prompts across all agents.

### Components

1) **Prompt Library** (`src/infrastructure/prompt_library.py`)
   - In-memory storage of prompt templates
   - Version control with rollback capability
   - Model-specific variants support
   - A/B testing configuration
   - Performance metrics per version
   - Default prompts for all agents (PO, QA, Dev, Supervisor, etc.)

2) **Prompt Monitor** (`src/utils/prompt_monitor.py`)
   - Real-time call tracking
   - Cost estimation by model
   - Alerting for threshold violations
   - Time-based metrics (hourly, daily)

3) **Domain Schemas** (`src/domain/schema.py`)
   - `PromptTemplate`: Template with versions and metadata
   - `PromptVersion`: Individual version with metrics
   - `PromptPerformanceMetrics`: Aggregated usage stats
   - `PromptExecutionRecord`: Individual call records
   - `ABTestConfig`: A/B testing configuration

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/prompts` | GET | List prompts with filtering |
| `/api/prompts/{id}` | GET | Get specific prompt |
| `/api/prompts` | POST | Create/update prompt |
| `/api/prompts/{id}` | DELETE | Delete prompt |
| `/api/prompts/{id}/versions` | POST | Add new version |
| `/api/prompts/{id}/rollback` | POST | Rollback to version |
| `/api/prompts/summary` | GET | Library statistics |
| `/api/prompts/metrics` | GET | Performance metrics |
| `/api/prompts/alerts` | GET | Recent alerts |
| `/api/prompts/alerts/thresholds` | PUT | Configure thresholds |

### UI Integration

The Admin Console includes an "Audit & Governance" section with:
- **Prompt Library**: Browse, search, and edit prompt templates
- **Performance Dashboard**: Metrics visualization (calls, latency, cost)
- **Alerts Configuration**: Set thresholds and view recent alerts
- **Audit Logs**: (Planned) Activity tracking and compliance

## Knowledge Management (Current)

- RAG uses LanceDB for vector retrieval with metadata.
- Evidence is rendered in the Story UI but is not modeled as a graph.
- No persistent knowledge graph or context graph is implemented yet.
- Hybrid RAG + Context Graph (GraphRAG-lite) is defined for MVP but not implemented.

## Noted Gaps and Risks

- Event bus is in-memory only (no durable transport)
- Workflow versioning is metadata-only (no parallel versions)
- CQRS is partial (queries are placeholders)
- Memory store is in-memory only (no persistence or ACLs)
- Guardrails and policy enforcement not fully implemented
- Prompt Library is in-memory only (no database persistence)
- Audit logs not yet implemented (UI placeholder exists)

## Recent Additions- **Prompt Management System**: Centralized prompt library with versioning, monitoring, and alerting
- **Admin Console Enhancements**: Audit & Governance section with prompt management UI
- **Cost Tracking**: Estimated cost calculation for LLM calls by model
- **Alerting System**: Configurable thresholds for latency, error rate, quality, and cost