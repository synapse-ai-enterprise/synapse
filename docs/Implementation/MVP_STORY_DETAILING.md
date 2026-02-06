## MVP: Story Detailing (Kanban Scope)

### Goal
Deliver the end-to-end **Story Detailing** flow (Module 2):
Template Parser → Knowledge Retrieval → Story Writer → Validation → Critique.

### MVP Flow Steps (UI)
1) Start from story text (manual input or pasted epic/story)
2) Parse template and show required/optional fields
3) Retrieve evidence from configured sources
4) Populate story schema (description, ACs, dependencies, NFRs, assumptions, questions)
5) Validate INVEST + gaps and apply fixes
6) Run critique loop (PO/QA/Dev) and apply updates

### Admin MVP Scope
- Templates: User Story only
- Integrations: Jira + Confluence only (ingestion loaders implemented)
- Models & Agents: enabled
- Audit & Governance: future release

### Agent Configuration (User-facing)
- **Orchestrator** — `Story Detailing`, `Epic → Stories`
- **Business (PO)** — `Epic → Stories`, `Story Detailing (critique)`
- **Technical (QA + Dev)** — `Story Detailing`, `Story Detailing (critique)`

### Supervisor Agent (MVP Guidance)
- The **SupervisorAgent** is implemented for the **Optimization/MAD workflow** only.
- For **Story Detailing**, keep **OrchestratorAgent** as the coordinator in MVP.
- If we need supervisor-driven routing later, gate it behind a feature flag and reuse
  the supervisor flow described in `SUPERVISOR_IMPLEMENTATION.md`.

### MVP Stories to Track in Kanban
1) Template Parser wiring  
2) Knowledge Retrieval evidence panel  
3) Story Writer full schema  
4) Validation details  
5) Critique loop execution  
6) Agent confidence + metadata (recommended)

### Additional MVP Story Required
7) Start source epic input (manual epic ID + description) to avoid `epic_id: null`  

### MVP Role-Based Access (Lightweight)
Include a **lightweight role selector** (client-side only) to gate features:
- **Product Manager / Product Owner**: Story Detailing flow + exports
- **QA Lead**: Validation + critique panels, read-only story edits
- **Engineering Lead / Developer**: Feasibility sections, dependencies, read-only edits
- **Admin**: Templates, Integrations, Models & Agents, Audit
- **Business Analyst / Delivery Manager**: History + export logs

Out of MVP:
- Real authentication (SSO/OAuth), server-side RBAC, audit-grade access control

### Hybrid RAG + Context Graph (MVP)
Goal: increase context quality and traceability using a lightweight Context Graph
that complements existing vector retrieval (GraphRAG-lite).

#### MVP Knowledge/Context Graph
- **Node types:** Source, Document, Chunk, Entity, Story, StorySection, Decision.
- **Edge types:** SOURCE_OF, PART_OF, MENTIONS, DERIVED_FROM, SUPPORTS, CONFLICTS_WITH.
- **Storage:** lightweight graph stored in memory store for MVP (persist later).
- **Linking:** every retrieved chunk is linked to a Story and StorySection (AC, NFR, dependency, etc.).
- **Citations:** story fields store reference IDs so evidence can be surfaced inline or in the evidence panel.

#### MVP Retrieval + Graph Build Flow
1) Ingest documents into LanceDB with metadata (source, author, timestamp, sensitivity).
   - Jira issues and Confluence pages are now supported by ingestion loaders.
2) On retrieval, capture top-N chunks and create graph nodes/edges for the workflow run.
3) Deduplicate by URL/hash and keep best-ranked chunk per source.
4) Emit `ContextGraphSnapshot` in workflow output and attach to story artifact metadata.

#### MVP Governance (Lightweight)
- Respect existing metadata fields (source, timestamp) and basic sensitivity tags.
- No mutation to external systems; graph is internal only.
- Provide an evidence panel and optional inline citations for transparency.

#### Out of MVP
- Persistent graph store, ACL enforcement, and policy checks.
- Cross-run graph analytics (change impact, ownership, and dependency reasoning).
