# Demo Preparation Checklist

Use this checklist to prepare for demonstrating the Agentic AI PoC.

## Pre-Demo Setup

### ✅ Environment Setup
- [ ] Poetry installed (`poetry --version`)
- [ ] Python 3.10+ available (`python3 --version`)
- [ ] Dependencies installed (`poetry install`)
- [ ] `.env` file created and configured
- [ ] `OPENAI_API_KEY` set in `.env` (required for LLM)
- [ ] `LINEAR_API_KEY` set (optional, for Linear integration)
- [ ] `DRY_RUN=true` set for safe testing

### ✅ Verification
- [ ] Smoke tests pass (`poetry run python tests/test_smoke.py`)
- [ ] Demo script runs (`poetry run python scripts/demo.py`)
- [ ] No import errors
- [ ] Data directory exists (`./data/lancedb`)

### ✅ Knowledge Base (Optional)
- [ ] `GITHUB_TOKEN` set (if ingesting GitHub repos)
- [ ] `NOTION_TOKEN` set (if ingesting Notion pages)
- [ ] Knowledge ingestion run (`poetry run python scripts/ingest_knowledge.py`)
- [ ] Vector store populated

## Demo Scenarios

### Scenario 1: Basic Workflow Demo
**Goal:** Show multi-agent debate pattern without external APIs

**Steps:**
1. Run: `poetry run python scripts/demo.py`
2. Explain the workflow steps as they execute
3. Show how agents critique and refine artifacts
4. Highlight INVEST validation

**What to Show:**
- Multi-agent orchestration
- Iterative refinement process
- INVEST criteria checking
- Confidence scoring

### Scenario 2: CLI Optimization
**Goal:** Demonstrate manual optimization of a Linear issue

**Prerequisites:**
- `LINEAR_API_KEY` set
- `LINEAR_TEAM_ID` set
- A test Linear issue ID

**Steps:**
1. Show issue in Linear
2. Run: `poetry run python -m src.main optimize LIN-XXX`
3. Show the optimization process
4. Check Linear for comments/changes

**What to Show:**
- Issue loading from Linear
- Context retrieval from knowledge base
- Agent collaboration
- Results written back to Linear

### Scenario 3: Webhook Integration
**Goal:** Show automated workflow triggered by Linear events

**Prerequisites:**
- Server running
- Linear webhook configured
- `LINEAR_WEBHOOK_SECRET` set

**Steps:**
1. Start server: `poetry run python -m src.main`
2. Show webhook endpoint: `http://localhost:8000/webhooks/issue-tracker`
3. Trigger event in Linear (e.g., create/update issue)
4. Show logs of processing
5. Show results in Linear

**What to Show:**
- Webhook reception
- Asynchronous processing
- Event-driven workflow
- Results in Linear

## Demo Talking Points

### Architecture Highlights
- **Hexagonal Architecture**: Clean separation of concerns
- **Multi-Agent Debate**: Three specialized agents (PO, QA, Developer)
- **LangGraph Orchestration**: State machine for workflow
- **INVEST Validation**: Automated quality checks
- **RAG Integration**: Context-aware optimization

### Key Features
- **Dry Run Mode**: Safe testing without side effects
- **Comment-Only Mode**: Human-in-the-loop approval
- **Observability**: Structured logging and tracing
- **Rate Limiting**: Token bucket algorithm
- **Optimistic Locking**: Prevents concurrent edit conflicts

### Technical Stack
- **LangGraph**: Workflow orchestration
- **LiteLLM**: Unified LLM interface
- **LanceDB**: Local vector store
- **Pydantic V2**: Type-safe schemas
- **FastAPI**: Webhook server

## Troubleshooting

### Common Issues

**Import Errors:**
```bash
# Reinstall dependencies
poetry install
```

**Missing API Keys:**
- Check `.env` file exists
- Verify keys are set (no quotes needed)
- Restart terminal/shell after setting

**Vector Store Errors:**
- Ensure `./data/lancedb` directory exists
- Run ingestion script to initialize

**Linear API Errors:**
- Verify `LINEAR_API_KEY` is valid
- Check `LINEAR_TEAM_ID` is correct UUID
- Ensure API key has necessary permissions

**LLM Errors:**
- Verify `OPENAI_API_KEY` is valid
- Check API quota/limits
- Try different model if needed

## Post-Demo

- [ ] Document any issues encountered
- [ ] Note questions from audience
- [ ] Update demo script if needed
- [ ] Clean up test data if necessary
