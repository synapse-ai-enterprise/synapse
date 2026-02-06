# Synapse AI: Local-First Workflow Automation

Synapse AI is an agentic AI system that orchestrates workflows between Linear, GitHub, and Notion using a local-first, self-hosted architecture.

## Architecture

This system follows **Hexagonal Architecture** (Ports and Adapters) with:
- **Domain Layer**: Pure business logic with Unified Agile Schema (UAS)
- **Application Layer**: Multi-Agent Debate (MAD) orchestration using LangGraph
- **Infrastructure Layer**: Adapters for Linear, GitHub, Notion, and LanceDB

## Key Features

- **Multi-Agent Debate Pattern**: Three specialist agents (Product Owner, QA, Developer) critique and refine artifacts iteratively
- **INVEST Criteria Validation**: Automated validation of user stories against INVEST principles
- **Read-Only Knowledge Bases**: GitHub and Notion are treated as read-only sources for RAG
- **Optimistic Locking**: Prevents data loss from concurrent edits
- **Observability**: OpenTelemetry tracing and structured logging

## Project Structure

```
synapse/
├── src/
│   ├── domain/              # Domain Layer: Pure Business Logic
│   ├── cognitive_engine/    # Application Layer: Orchestration
│   ├── ingestion/           # Infrastructure Layer: ETL
│   ├── adapters/            # Infrastructure Layer: External Adapters
│   ├── infrastructure/       # Infrastructure concerns
│   └── utils/               # Utilities
├── scripts/                 # Helper scripts
└── tests/                   # Test suite
```

## Quick Start (Local UI + API)

Use the startup scripts to run the backend API and Vite UI together.

### Option A: Standard local startup
```bash
./scripts/start_ui_backend.sh
```

### Option B: Local-only (fast iteration)
```bash
./scripts/start_local_ui_backend.sh
```

Both scripts:
- start the API on `http://localhost:8000`
- start the UI on `http://localhost:5173`
- write logs to `.backend.log` and `.frontend.log`

**If you see "Is the backend running?"**  
The UI expects the API at `http://localhost:8000`. Start the backend in a separate terminal:

```bash
# From repo root, with .env / .env.local loaded:
poetry run python -m src.main
```

Or use the script that starts both backend and frontend: `./scripts/start_local_ui_backend.sh`.

**Environment files:**
- `.env` is loaded by default
- `.env.local` is also supported (recommended for local secrets)

## Setup

### Prerequisites

- Python 3.10+
- Poetry (for dependency management)
- OpenAI API key (required for LLM functionality)
- Optional: Linear API key, GitHub token, Notion token for full integration

### Installation Steps

1. **Install dependencies:**
```bash
poetry install
```

2. **Configure environment:**
```bash
# Copy environment template (if .env.example exists)
cp .env.example .env

# Or create minimal .env file:
cat > .env << EOF
LITELLM_MODEL=ollama/llama3
OLLAMA_BASE_URL=http://127.0.0.1:11434
DRY_RUN=true
MODE=comment_only
VECTOR_STORE_PATH=./data/lancedb
EMBEDDING_MODEL=local/all-MiniLM-L6-v2
EOF
```

You can also place secrets in `.env.local` to avoid committing them.

3. **Verify installation:**
```bash
poetry run python tests/test_smoke.py
```

4. **Run demo workflow:**
```bash
poetry run python scripts/demo.py
```

5. **Optional: Ingest knowledge base:**
```bash
# Requires GITHUB_TOKEN and/or NOTION_TOKEN in .env
poetry run python scripts/ingest_knowledge.py
```

6. **Start the API + UI:**
```bash
./scripts/start_ui_backend.sh
```

## Demo Scenarios

### Scenario 1: Basic Demo (No External APIs)

The demo script (`scripts/demo.py`) can run with Ollama locally:

```bash
# Ensure Ollama is running and LITELLM_MODEL is set to an Ollama model
poetry run python scripts/demo.py
```

This demonstrates:
- Multi-agent debate workflow
- INVEST criteria validation
- Artifact optimization process

### Scenario 2: Full Integration Demo

For a complete demo with Linear integration:

1. Set `LINEAR_API_KEY` and `LINEAR_TEAM_ID` in `.env`
2. Set `DRY_RUN=false` and `MODE=comment_only` for safe testing
3. Use the CLI to optimize an issue:
```bash
poetry run python -m src.main optimize LIN-123
```

### Scenario 3: Webhook Integration

1. Start the server:
```bash
poetry run python -m src.main
```

2. Configure your issue tracker webhook to point to:
```
http://your-server:8000/webhooks/issue-tracker
```

3. Set `LINEAR_WEBHOOK_SECRET` in `.env` for signature verification

## Development

### Current MVP (Story Detailing)
- UI supports Story Detailing flow with workflow progress streaming.
- Admin Console supports Templates (User Story), Integrations (Jira + Confluence), and Models & Agents.
- Audit & Governance is marked Coming Soon.

See `docs/Implementation/MVP_STORY_DETAILING.md` and `docs/Implementation/IMPLEMENTATION_STATUS.md`.

See `.cursorrules` for architectural standards and coding guidelines.

## Deployment

Vercel deployment instructions are available in `docs/DEPLOYMENT_VERCEL.md`.

## License

[Your License Here]
