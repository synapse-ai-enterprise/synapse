## Commit History Notes (Feature vs Main)

These notes describe changes enabled on `feature/synapse-functional-mvp` compared to `main`.

Date: 2026-01-28

### Introducing Agents Documentation

- Added `docs/agents_v1.0.md` and supporting guidance for the multi-agent setup.
- Added supervisor and workflow documentation (`SUPERVISOR_IMPLEMENTATION.md`, `docs/Implementation/IMPLEMENTATION_STATUS.md`).

### 1. Creating UI (React)

- Added a Vite + React UI under `ui/`.
- Added microfrontend views for Admin, Epic, Initiative, Story, and History.
- Added shared API helpers and flow/data helpers for the UI.
- Implemented Story Detailing MVP experience with streaming workflow status, loading states, and critique panels.
- Added Home landing page layout and CTA navigation to Story + Admin.

### 2. Docs

- Added planning and implementation docs (backlog, contracts, MVP story detailing).
- Added demo preparation/checklist/analysis docs.
- Added LLM provider switching guidance.
- Added implementation status tracking, consolidated agents, and documentation guide.

### 3. Vercel Deployment Configuration

- Added `vercel.json` for Vercel builds (API + UI).
- Added `api/index.py` as the FastAPI serverless entrypoint.
- Added `requirements.txt` for Vercel Python runtime.
- Added `docs/DEPLOYMENT_VERCEL.md` and linked it in `README.md`.
- Updated CORS and Vercel deployment defaults in `src/main.py` / `src/config.py`.
- Updated UI API base URL to be environment-aware in `ui/src/shared/api.js`.
- Added local UI + API startup scripts (`scripts/start_local_ui_backend.sh`, `scripts/stop_local_ui_backend.sh`).

### 4. BE Changes and Introductions

- Added application layer handlers and workflow registry (`src/application/`).
- Added agent orchestration modules and story workflow graph/state (`src/cognitive_engine/`).
- Added infra components for admin store, messaging/event bus, queue workers.
- Added ingestion updates for vector DB handling.
- Expanded domain interfaces, schema, and use cases for new workflows.
- Added SSE endpoint for story writing progress and streaming UI updates.
- Added critique loop execution (PO/QA/Dev) and safeguards to avoid repeat loops.
- Enabled `.env.local` support for local secrets and startup scripts.
