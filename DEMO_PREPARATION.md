# Demo Preparation Summary

This document summarizes what has been prepared for demonstrating the Agentic AI PoC.

## What Has Been Done

### ✅ 1. Fixed Missing Dependencies
- Added `click` dependency to `pyproject.toml` (required for CLI functionality)

### ✅ 2. Created Demo Scripts
- **`scripts/demo.py`**: Standalone demo script that showcases the workflow
  - Can run with minimal configuration (just OpenAI API key)
  - Shows multi-agent debate pattern
  - Demonstrates INVEST validation
  - Handles missing API keys gracefully

- **`scripts/setup_demo.sh`**: Automated setup script
  - Installs dependencies
  - Creates `.env` file if missing
  - Creates data directories
  - Runs smoke tests

### ✅ 3. Documentation Updates
- **`README.md`**: Enhanced with:
  - Quick start section
  - Multiple demo scenarios
  - Step-by-step setup instructions
  - Troubleshooting tips

- **`DEMO_CHECKLIST.md`**: Comprehensive checklist for:
  - Pre-demo setup
  - Demo scenarios
  - Talking points
  - Troubleshooting

### ✅ 4. Configuration Template
- Created `.env.example` template (attempted, may be blocked by gitignore)
- Documented all required environment variables in README

## What You Need to Do

### Before the Demo

1. **Install Dependencies:**
   ```bash
   poetry install
   ```

2. **Create `.env` File:**
   ```bash
   # Minimum required for demo:
   LITELLM_MODEL=gpt-4-turbo-preview
   OPENAI_API_KEY=your-key-here
   DRY_RUN=true
   MODE=comment_only
   VECTOR_STORE_PATH=./data/lancedb
   ```

3. **Verify Setup:**
   ```bash
   poetry run python tests/test_smoke.py
   ```

4. **Test Demo Script:**
   ```bash
   poetry run python scripts/demo.py
   ```

### Optional: Full Integration Demo

If you want to show Linear integration:

1. Add to `.env`:
   ```
   LINEAR_API_KEY=your-linear-key
   LINEAR_TEAM_ID=your-team-uuid
   ```

2. Test CLI optimization:
   ```bash
   poetry run python -m src.main optimize LIN-XXX
   ```

3. Or start webhook server:
   ```bash
   poetry run python -m src.main
   ```

## Demo Scenarios

### Scenario 1: Basic Workflow (Recommended for First Demo)
- **Requires:** OpenAI API key only
- **Command:** `poetry run python scripts/demo.py`
- **Shows:** Multi-agent debate, INVEST validation, workflow structure
- **Duration:** ~2-3 minutes

### Scenario 2: CLI Optimization
- **Requires:** OpenAI API key + Linear API key
- **Command:** `poetry run python -m src.main optimize LIN-XXX`
- **Shows:** Real Linear integration, end-to-end workflow
- **Duration:** ~5 minutes

### Scenario 3: Webhook Integration
- **Requires:** Full setup + webhook configuration
- **Command:** `poetry run python -m src.main` (server mode)
- **Shows:** Event-driven automation
- **Duration:** ~10 minutes (includes setup)

## Key Files for Demo

- `scripts/demo.py` - Main demo script
- `scripts/setup_demo.sh` - Quick setup
- `DEMO_CHECKLIST.md` - Detailed checklist
- `README.md` - Updated with demo instructions
- `tests/test_smoke.py` - Verification tests

## Architecture Highlights to Mention

1. **Hexagonal Architecture**: Clean separation of domain, application, and infrastructure
2. **Multi-Agent Debate**: Three specialized agents (PO, QA, Developer) collaborate
3. **LangGraph Orchestration**: State machine for workflow management
4. **INVEST Validation**: Automated quality checks for user stories
5. **RAG Integration**: Context-aware optimization using knowledge base
6. **Observability**: Structured logging and OpenTelemetry tracing

## Troubleshooting

If something doesn't work:

1. **Check dependencies:** `poetry install`
2. **Verify `.env`:** Ensure API keys are set (no quotes)
3. **Run smoke tests:** `poetry run python tests/test_smoke.py`
4. **Check logs:** Demo script provides detailed error messages
5. **Review DEMO_CHECKLIST.md:** Common issues documented there

## Next Steps

1. Run the setup script: `./scripts/setup_demo.sh`
2. Add your OpenAI API key to `.env`
3. Test the demo: `poetry run python scripts/demo.py`
4. Review `DEMO_CHECKLIST.md` for talking points
5. Practice the demo scenarios

Good luck with your demonstration! 🚀
