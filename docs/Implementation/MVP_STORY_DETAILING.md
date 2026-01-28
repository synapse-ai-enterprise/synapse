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
- Integrations: Jira + Confluence only
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
