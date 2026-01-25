# Agentic AI PoC: Local-First Workflow Automation

A Proof of Concept (PoC) Agentic AI system designed to orchestrate workflows between Linear, GitHub, and Notion using a local-first, self-hosted architecture.

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
agentic-poc/
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

## Quick Start (Demo)

For a quick demonstration setup:

```bash
# Run automated setup script
./scripts/setup_demo.sh

# Or manually:
poetry install
cp .env.example .env  # Edit .env and add OPENAI_API_KEY
poetry run python scripts/demo.py
```

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
LITELLM_MODEL=gpt-4-turbo-preview
OPENAI_API_KEY=your-api-key-here
DRY_RUN=true
MODE=comment_only
VECTOR_STORE_PATH=./data/lancedb
EOF
```

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

6. **Start webhook server:**
```bash
poetry run python -m src.main
# Server runs on http://localhost:8000
```

## Demo Scenarios

### Scenario 1: Basic Demo (No External APIs)

The demo script (`scripts/demo.py`) can run with just an OpenAI API key:

```bash
# Set OPENAI_API_KEY in .env
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

See `.cursorrules` for architectural standards and coding guidelines.

## License

[Your License Here]
