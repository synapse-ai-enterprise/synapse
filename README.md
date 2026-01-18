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

## Setup

1. Install dependencies:
```bash
poetry install
```

2. Copy environment template:
```bash
cp .env.example .env
```

3. Configure your `.env` file with API keys and settings.

4. Run ingestion pipeline:
```bash
python scripts/ingest_knowledge.py
```

5. Start the webhook server:
```bash
python -m src.main
```

## Development

See `.cursorrules` for architectural standards and coding guidelines.

## License

[Your License Here]
