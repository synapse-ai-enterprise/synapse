# Demo Preparation Summary

This document summarizes the Synapse Agentic AI PoC capabilities and how to demonstrate them.

## Platform Overview

Synapse is an AI-powered product story writing and optimization platform that uses multi-agent collaboration to create high-quality, INVEST-compliant user stories.

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Story Writing** | Generate user stories from initiatives/epics with multi-agent debate |
| **Story Splitting** | Decompose large stories into smaller, INVEST-compliant pieces |
| **Story Optimization** | Refine existing stories using RAG-enhanced context |
| **INVEST Validation** | Automated quality checks against INVEST criteria |
| **Knowledge Base** | RAG integration with GitHub, Notion, Jira, Confluence |
| **Multi-Provider LLM** | Switch between OpenAI, Anthropic, Google, Azure, Ollama |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Poetry (`pip install poetry`)

### One-Command Setup
```bash
./scripts/start_local_ui_backend.sh
```

This will:
1. Install Python dependencies via Poetry
2. Start the FastAPI backend on port 8000
3. Install npm packages for the UI
4. Start the Vite dev server on port 5173

### Manual Setup
```bash
# 1. Install dependencies
poetry install --extras "local-embeddings vector-store"
cd ui && npm install && cd ..

# 2. Configure environment
cp .env.example .env
# Edit .env with your LLM configuration

# 3. Start backend
poetry run python -m src.main

# 4. Start frontend (new terminal)
cd ui && npm run dev
```

### Verify Setup
```bash
# Health check
poetry run python scripts/health_check.py

# API health
curl http://localhost:8000/health

# Open UI
open http://localhost:5173
```

---

## Environment Configuration

### Minimal Configuration (Local Ollama)
```env
# .env file
LITELLM_MODEL=ollama/llama3
OLLAMA_BASE_URL=http://127.0.0.1:11434
DRY_RUN=true
MODE=comment_only
VECTOR_STORE_PATH=./data/lancedb
EMBEDDING_MODEL=local/all-MiniLM-L6-v2
```

### Cloud LLM Configuration (OpenAI)
```env
LITELLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-your-key-here
DRY_RUN=true
MODE=comment_only
VECTOR_STORE_PATH=./data/lancedb
EMBEDDING_MODEL=local/all-MiniLM-L6-v2
```

### Full Integration Configuration
```env
# LLM
LITELLM_MODEL=ollama/llama3
OLLAMA_BASE_URL=http://127.0.0.1:11434

# Safety
DRY_RUN=true
MODE=comment_only

# Vector Store
VECTOR_STORE_PATH=./data/lancedb
EMBEDDING_MODEL=local/all-MiniLM-L6-v2

# Linear (Optional)
LINEAR_API_KEY=lin_api_xxx
LINEAR_TEAM_ID=uuid-here
LINEAR_WEBHOOK_SECRET=secret-here

# Jira (Optional)
JIRA_TOKEN=your-atlassian-api-token
JIRA_USER_EMAIL=your-email@company.com
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_PROJECT_KEYS=PROJ1,PROJ2

# Confluence (Optional)
CONFLUENCE_TOKEN=your-atlassian-api-token
CONFLUENCE_USER_EMAIL=your-email@company.com
CONFLUENCE_BASE_URL=https://your-domain.atlassian.net/wiki
CONFLUENCE_SPACE_KEYS=SPACE1,SPACE2

# Knowledge Sources (Optional)
GITHUB_TOKEN=ghp_xxx
GITHUB_REPO=owner/repo
NOTION_TOKEN=secret_xxx
NOTION_ROOT_PAGE_ID=page-id
```

---

## Demo Scenarios

### 1. Story Writing Workflow (Recommended First Demo)

**Goal:** Show end-to-end AI-powered story creation

**Steps:**
1. Open `http://localhost:5173`
2. Click on **Story Writing** / **Epic** section
3. Enter context:
   - Initiative: "Build a customer portal for self-service account management"
   - Epic: "User authentication and profile management"
4. Click **Generate Stories**
5. Watch the workflow execute with real-time updates

**What Happens:**
```
1. Knowledge Retrieval → Fetches relevant context from RAG
2. PO Agent Draft    → Creates initial story with ACs
3. QA Agent Critique → Validates against INVEST criteria
4. Dev Agent Review  → Assesses technical feasibility
5. PO Agent Synthesis→ Incorporates feedback
6. Validation        → Checks confidence threshold
7. (Repeat if needed)→ Up to 3 debate iterations
```

**Key Points to Highlight:**
- Multi-agent collaboration visible in UI
- INVEST validation with specific feedback
- Confidence scoring (aim for >0.8)
- Generated acceptance criteria

### 2. Story Splitting Demo

**Goal:** Demonstrate large story decomposition

**Via API:**
```bash
curl -X POST http://localhost:8000/api/story-split \
  -H "Content-Type: application/json" \
  -d '{
    "story_text": "As a user, I want a complete e-commerce checkout flow including cart management, payment processing with multiple providers, shipping calculation, tax handling, order confirmation, and email notifications so that I can purchase products.",
    "title": "E-commerce Checkout"
  }' | jq
```

**Expected Output:**
- 4-6 smaller stories
- Each with focused scope
- Individual acceptance criteria
- INVEST-compliant sizing

### 3. CLI Demo Script

**Goal:** Quick terminal-based demonstration

```bash
poetry run python scripts/demo.py
```

**Output Includes:**
- Step-by-step workflow visualization
- Agent critiques displayed in full
- INVEST violation tracking
- Confidence score progression
- Complete log file: `logs/demo_*.log`

### 4. Model Switching Demo

**Goal:** Show multi-provider flexibility

```bash
# Check current model
curl http://localhost:8000/api/config/current-model | jq

# List all available models
curl http://localhost:8000/api/config/models | jq

# View Ollama models (if running)
curl http://localhost:8000/api/config/models | jq '.ollama_models'
```

**Key Point:** Change `LITELLM_MODEL` in `.env` and restart to switch providers.

### 5. Admin & Observability Demo

**Goal:** Show platform management capabilities

**Admin UI:**
1. Navigate to Admin section
2. Show integration status (Linear, Jira, Confluence)
3. Demonstrate test connection
4. Show sync capabilities

**Prompt Management:**
1. Navigate to Prompt Management
2. Show agent prompts (PO, QA, Developer)
3. Demonstrate version history
4. Show performance metrics

**API Endpoints:**
```bash
# Prompt metrics
curl http://localhost:8000/api/observability/prompts | jq

# Prompt history
curl http://localhost:8000/api/observability/prompts/history?limit=10 | jq

# All prompts
curl http://localhost:8000/api/prompts | jq

# Templates
curl http://localhost:8000/api/templates | jq
```

---

## Architecture Highlights

### Multi-Agent Debate Pattern
```
┌─────────────────────────────────────────────────────────────┐
│                      Supervisor                              │
│  (Orchestrates workflow, decides continue/stop)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   PO Agent   │ │   QA Agent   │ │ Dev Agent    │
│  (Drafting,  │ │   (INVEST    │ │ (Technical   │
│  Synthesis)  │ │  Validation) │ │  Feasibility)│
└──────────────┘ └──────────────┘ └──────────────┘
```

### INVEST Criteria
| Criterion | What It Means |
|-----------|---------------|
| **I**ndependent | Can be developed in any order |
| **N**egotiable | Details can be discussed |
| **V**aluable | Delivers user/business value |
| **E**stimable | Team can estimate effort |
| **S**mall | Fits in one sprint |
| **T**estable | Clear pass/fail criteria |

### Key Technologies
- **LangGraph**: State machine workflow orchestration
- **LiteLLM**: Unified interface to 100+ LLM providers
- **LanceDB**: Local vector database for RAG
- **Sentence Transformers**: Local embeddings (no API needed)
- **FastAPI**: High-performance async API
- **React + Vite**: Modern frontend stack

---

## API Reference

### Story Writing
```bash
POST /api/story-writing
{
  "flow": "epic",
  "epic_id": "optional-epic-id",
  "project_id": "project-context",
  "initiative_context": "Business context",
  "epic_context": "Epic details"
}
```

### Story Splitting
```bash
POST /api/story-split
{
  "story_text": "Large story description",
  "title": "Optional title"
}
```

### Model Configuration
```bash
GET /api/config/models
GET /api/config/current-model
```

### Observability
```bash
GET /api/observability/prompts
GET /api/observability/prompts/history
POST /api/observability/prompts/reset
```

### Integrations
```bash
GET /api/integrations
POST /api/integrations/{name}/connect
POST /api/integrations/{name}/test
POST /api/integrations/{name}/sync
```

### Templates
```bash
GET /api/templates
POST /api/templates
GET /api/templates/{id}
PUT /api/templates/{id}
DELETE /api/templates/{id}
```

### Prompts
```bash
GET /api/prompts
POST /api/prompts
GET /api/prompts/{id}
DELETE /api/prompts/{id}
POST /api/prompts/{id}/versions
POST /api/prompts/{id}/rollback
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Backend won't start | Check Python 3.11+, run `poetry install` |
| Ollama errors | Run `ollama serve`, then `ollama pull llama3` |
| CORS errors | Check `CORS_ORIGINS` in `.env` |
| Import errors | Use `poetry run python -m src.main` |
| Vector store errors | Create `data/lancedb` directory |
| UI won't connect | Verify backend at `http://localhost:8000/health` |

### Logs and Debugging
```bash
# Backend logs
cat .backend.log

# Frontend logs
cat .frontend.log

# Demo execution logs
ls -la logs/

# Real-time backend logs
poetry run python -m src.main 2>&1 | tee debug.log
```

---

## Demo Tips

1. **Start with CLI demo** (`scripts/demo.py`) for quick validation
2. **Use Ollama** for reliable, offline-capable demos
3. **Enable DRY_RUN=true** to prevent accidental external writes
4. **Pre-pull Ollama models** before the demo (`ollama pull llama3`)
5. **Have backup models** configured (e.g., OpenAI key as fallback)
6. **Check health endpoint** before starting UI demo
7. **Keep log files** for post-demo analysis

---

## Files Reference

| File | Purpose |
|------|---------|
| `scripts/demo.py` | CLI demonstration script |
| `scripts/start_local_ui_backend.sh` | Start backend + frontend |
| `scripts/stop_local_ui_backend.sh` | Stop all services |
| `scripts/health_check.py` | Verify environment setup |
| `scripts/ingest_knowledge.py` | Populate knowledge base |
| `.env.example` | Configuration template |
| `DEMO_CHECKLIST.md` | Pre-demo verification |

---

## Support

- Review `DEMO_CHECKLIST.md` for detailed setup verification
- Check architecture docs in `docs/Planning/Tech/`
- See `LLM_PROVIDER_SWITCHING.md` for model configuration
- See `OLLAMA_CONFIGURATION.md` for local LLM setup
