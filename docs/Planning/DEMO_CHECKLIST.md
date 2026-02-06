# Demo Preparation Checklist

Use this checklist to prepare for demonstrating the Synapse Agentic AI PoC.

## Pre-Demo Setup

### Environment Setup
- [ ] Python 3.11+ installed (`python3 --version`)
- [ ] Poetry installed (`poetry --version`)
- [ ] Node.js 18+ installed (`node --version`)
- [ ] Dependencies installed (`poetry install --extras "local-embeddings vector-store"`)
- [ ] UI dependencies installed (`cd ui && npm install`)
- [ ] `.env` file created and configured (copy from `.env.example`)

### LLM Configuration (Choose One)
**Option A: Local Ollama (Recommended for Demo)**
- [ ] Ollama installed and running (`ollama serve`)
- [ ] Model pulled (`ollama pull llama3` or `ollama pull mistral`)
- [ ] `.env` configured:
  ```
  LITELLM_MODEL=ollama/llama3
  OLLAMA_BASE_URL=http://127.0.0.1:11434
  ```

**Option B: OpenAI**
- [ ] `OPENAI_API_KEY` set in `.env`
- [ ] `LITELLM_MODEL=gpt-4o-mini` (or `gpt-4`, `gpt-4-turbo-preview`)

**Option C: Anthropic**
- [ ] `ANTHROPIC_API_KEY` set in `.env`
- [ ] `LITELLM_MODEL=claude-3-5-sonnet-20241022`

### Core Configuration
- [ ] `DRY_RUN=true` set for safe demo mode
- [ ] `MODE=comment_only` set (or `shadow` for no external writes)
- [ ] `VECTOR_STORE_PATH=./data/lancedb` configured
- [ ] `EMBEDDING_MODEL=local/all-MiniLM-L6-v2` (no API key needed)

### Verification
- [ ] Health check passes (`poetry run python scripts/health_check.py`)
- [ ] Backend starts (`poetry run python -m src.main`)
- [ ] Frontend starts (`cd ui && npm run dev`)
- [ ] Health endpoint responds (`curl http://localhost:8000/health`)
- [ ] UI loads at `http://localhost:5173`

### Optional: Integration Configuration
**Linear Integration:**
- [ ] `LINEAR_API_KEY` set
- [ ] `LINEAR_TEAM_ID` set (UUID format)
- [ ] `LINEAR_WEBHOOK_SECRET` set (for webhooks)

**Jira/Confluence Integration:**
- [ ] `JIRA_TOKEN` and `JIRA_USER_EMAIL` set
- [ ] `JIRA_BASE_URL` set (e.g., `https://your-domain.atlassian.net`)
- [ ] `CONFLUENCE_TOKEN` and `CONFLUENCE_USER_EMAIL` set
- [ ] `CONFLUENCE_BASE_URL` set

### Optional: Knowledge Base
- [ ] `GITHUB_TOKEN` set (for GitHub repo ingestion)
- [ ] `NOTION_TOKEN` set (for Notion page ingestion)
- [ ] Knowledge ingestion run (`poetry run python scripts/ingest_knowledge.py`)

---

## Quick Start Commands

```bash
# One-liner to start everything (backend + frontend)
./scripts/start_local_ui_backend.sh

# Or separately:
# Terminal 1: Backend
poetry run python -m src.main

# Terminal 2: Frontend
cd ui && npm run dev

# Stop everything
./scripts/stop_local_ui_backend.sh
```

---

## Demo Scenarios

### Scenario 1: Story Writing Workflow (Primary Demo)
**Goal:** Demonstrate end-to-end story creation with multi-agent debate

**UI Flow:**
1. Open `http://localhost:5173`
2. Navigate to **Story Writing** section
3. Enter initiative/epic context
4. Click **Generate Stories**
5. Watch the multi-agent workflow execute:
   - Knowledge retrieval from RAG
   - PO Agent drafting stories
   - QA Agent INVEST validation
   - Developer Agent technical review
   - Iterative refinement

**What to Highlight:**
- Real-time progress streaming
- Agent collaboration visible in UI
- INVEST criteria validation
- Confidence scoring
- Acceptance criteria generation

### Scenario 2: Story Splitting (Large Story Decomposition)
**Goal:** Show how large stories are split into smaller, INVEST-compliant stories

**API:**
```bash
curl -X POST http://localhost:8000/api/story-split \
  -H "Content-Type: application/json" \
  -d '{
    "story_text": "As a user, I want a complete authentication system with registration, login, password reset, OAuth, and 2FA so that I can securely access my account.",
    "title": "User Authentication System"
  }'
```

**What to Highlight:**
- Automatic story decomposition
- INVEST principle adherence
- Acceptance criteria per sub-story
- Debate rationale in response

### Scenario 3: CLI Demo Script
**Goal:** Quick command-line demonstration of the workflow

**Command:**
```bash
poetry run python scripts/demo.py
```

**What to Highlight:**
- Full workflow visualization in terminal
- Iteration-by-iteration progress
- Detailed log file generation (`logs/demo_*.log`)
- Works without external APIs (uses mock data)

### Scenario 4: Admin & Observability (Advanced)
**Goal:** Show platform configuration and monitoring capabilities

**UI Sections to Demo:**
1. **Admin** - Integration management, sync controls
2. **Prompt Management** - View/edit agent prompts, version control
3. **Templates** - Story templates, field mappings
4. **History** - Past workflow runs, audit trail

**API Endpoints:**
```bash
# Model configuration
curl http://localhost:8000/api/config/models

# Prompt metrics
curl http://localhost:8000/api/observability/prompts

# Integration status
curl http://localhost:8000/api/integrations

# Template management
curl http://localhost:8000/api/templates
```

### Scenario 5: Webhook Integration (Production-Ready)
**Goal:** Demonstrate event-driven automation

**Prerequisites:**
- Server running
- Linear webhook configured (pointing to `/webhooks/issue-tracker`)
- `LINEAR_WEBHOOK_SECRET` set for signature verification

**Flow:**
1. Create/update issue in Linear
2. Webhook triggers optimization workflow
3. AI agents process and refine the story
4. Results posted back as comments

---

## Demo Talking Points

### Architecture Highlights
- **Hexagonal Architecture**: Clean domain/application/infrastructure separation
- **Multi-Agent Debate Pattern**: PO, QA, Developer agents collaborate
- **LangGraph Orchestration**: Deterministic state machine workflows
- **INVEST Validation**: Automated quality checks (Independent, Negotiable, Valuable, Estimable, Small, Testable)
- **RAG Integration**: Context-aware using LanceDB vector store

### Multi-Provider LLM Support
- **OpenAI**: GPT-4, GPT-4 Turbo, GPT-4o, o1
- **Anthropic**: Claude 3.5 Sonnet, Claude 3 Opus
- **Google**: Gemini Pro, Gemini 1.5
- **Azure OpenAI**: Enterprise deployment
- **Ollama**: Local models (Llama 3, Mistral, Mixtral)
- Hot-swap models without code changes via `LITELLM_MODEL`

### Safety & Control
- **Dry Run Mode**: Test without external writes
- **Comment-Only Mode**: Human-in-the-loop approval
- **Shadow Mode**: Full simulation, no external effects
- **Rate Limiting**: Token bucket algorithm
- **Webhook Signature Verification**: HMAC validation

### Observability Stack
- **Structured Logging**: JSON logs with context
- **OpenTelemetry Tracing**: Distributed trace IDs
- **Prompt Monitoring**: Token usage, latency, cost tracking
- **Alert Thresholds**: Configurable quality gates

### Technical Stack
| Component | Technology |
|-----------|------------|
| Workflow | LangGraph |
| LLM Gateway | LiteLLM |
| Vector Store | LanceDB |
| Embeddings | Sentence Transformers (local) |
| API | FastAPI |
| Frontend | React + Vite |
| Validation | Pydantic V2 |

---

## Troubleshooting

### Backend Won't Start
```bash
# Check Python version
python3 --version  # Needs 3.10+

# Reinstall dependencies
poetry install --extras "local-embeddings vector-store"

# Check for port conflicts
lsof -i :8000
```

### Frontend Won't Connect to Backend
```bash
# Verify CORS is configured
# Backend logs should show CORS origins

# Check backend health
curl http://localhost:8000/health

# Restart both services
./scripts/stop_local_ui_backend.sh
./scripts/start_local_ui_backend.sh
```

### LLM Errors
```bash
# Ollama not responding
ollama serve  # Start Ollama
ollama list   # Check available models

# OpenAI rate limits
# Wait or switch to different model

# Test LLM connection
curl http://localhost:8000/api/config/current-model
```

### Vector Store Issues
```bash
# Create data directory
mkdir -p data/lancedb

# Reinitialize
rm -rf data/lancedb/*
poetry run python scripts/ingest_knowledge.py
```

### Import Errors
```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use poetry run
poetry run python -m src.main
```

---

## Post-Demo Checklist
- [ ] Document questions/feedback from audience
- [ ] Note any issues encountered
- [ ] Save demo log files (`logs/demo_*.log`)
- [ ] Reset test data if needed
- [ ] Update this checklist with improvements
