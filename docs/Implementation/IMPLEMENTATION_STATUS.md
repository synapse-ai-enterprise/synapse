## Implementation Status: Story Detailing MVP

Based on `docs/Implementation/MVP_STORY_DETAILING.md`.

### Scope Summary
- MVP flow: Start from story text → Template parsing → Knowledge retrieval → Story writer → Validation → Critique loop
- Admin MVP: Templates (User Story), Integrations (Jira + Confluence), Models & Agents enabled
- Out of MVP: Audit & Governance

### Current Status (High-Level)
- **UI flow:** Implemented end-to-end Story Detailing flow with draft input, workflow visualization, and results rendering.
- **Template Parser (UI):** Template managed in Admin Console; formatted template preview shown in Story screen.
- **Knowledge Retrieval (UI):** Evidence list rendered in Story screen; integrations defined in Admin.
- **Knowledge Retrieval (Backend):** Jira + Confluence ingestion loaders added; ingestion script now supports both sources.
- **Story Writer:** Outputs rendered in Story screen with acceptance criteria and summary.
- **Validation:** INVEST and gap details rendered in Story screen (no auto-apply yet).
- **Critique Loop:** QA/Dev notes rendered in Story screen; critique loop executes once per run.
- **Workflow progress:** Streaming updates for node status implemented; UI shows stage progress in the flow diagram.
- **Admin Console:** Templates and Models & Agents are active; Integrations limited to Jira + Confluence; Audit marked as Coming Soon.
- **Agent configuration:** Orchestrator / Business / Technical groupings reflected in Admin UI.
- **Supervisor:** Not used for Story Detailing; Orchestrator remains coordinator for MVP.
- **Knowledge Context Strategy:** Hybrid RAG + Context Graph (GraphRAG-lite) defined in `docs/Implementation/MVP_STORY_DETAILING.md`.

### MVP Checklist
- [x] Start from story text (manual input)
- [x] Parse template and show schema (via admin-managed template; UI shows schema in output)
- [x] Retrieve evidence from configured sources (backend; UI renders evidence list in output)
- [x] Populate story schema (description, ACs, dependencies, NFRs, assumptions, questions)
- [x] Validate INVEST + gaps (validation results visible)
- [x] Run critique loop (PO/QA/Dev)
- [x] Start source epic input (manual epic ID + description)
- [ ] Lightweight role selector (client-side only) for MVP roles

### TODOs / Pending Work
- [ ] **Knowledge Base Management:** implement UX + backend for managing knowledge sources, ingestion, and governance.
- [ ] **Admin Console → Integrations:** finish integration management UX beyond Jira/Confluence, including status, scopes, and testing.
- [ ] **Jira + Confluence ingestion wiring:** add scheduled ingestion and admin-triggered sync flow.
- [ ] **Context Graph Model:** implement node/edge schema and snapshot in domain layer.
- [ ] **Context Graph Store:** add MVP in-memory graph store adapter and port.
- [ ] **Context Graph Wiring:** emit graph snapshot from retrieval and attach to story artifacts.
- [ ] **Context References UI:** surface graph-linked citations in story fields and evidence panel.
- [ ] **Role-based access (lightweight):** client-side gating for MVP roles.

### Notes: Knowledge Context Strategy (defined)
- Reference model: source type, title, excerpt, URL, confidence, and linkage to story sections.
- Retrieval policy: source list, ranking thresholds, and duplicate merge logic.
- Display: inline citations in story fields plus evidence panel.
- Storage: working-memory snapshot per run; long-term persistence out of MVP.
- MVP Context Graph: nodes/edges and snapshot attached to story artifacts.
- Mapping: graph IDs map to UI evidence items and story sections.
