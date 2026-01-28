## Implementation Status: Story Detailing MVP

Based on `docs/Implementation/MVP_STORY_DETAILING.md`.

### Scope Summary
- MVP flow: Start from story text → Template parsing → Knowledge retrieval → Story writer → Validation → Critique loop
- Admin MVP: Templates (User Story), Integrations (Jira + Confluence), Models & Agents enabled
- Out of MVP: Audit & Governance

### Current Status (High-Level)
- **UI flow:** Implemented end-to-end Story Detailing flow with draft input, workflow visualization, and results rendering.
- **Template Parser (UI):** Template management moved to Admin Console; preview previously shown in Story screen is currently hidden.
- **Knowledge Retrieval (UI):** Source listing moved/hidden from Story screen; integration sources defined in Admin.
- **Story Writer:** Outputs rendered in Story screen with acceptance criteria and summary.
- **Validation:** INVEST and gap details rendered in Story screen.
- **Critique Loop:** QA/Dev notes rendered in Story screen.
- **Workflow progress:** Streaming updates for node status implemented; UI shows stage progress in the flow diagram.
- **Admin Console:** Templates and Models & Agents are active; Integrations limited to Jira + Confluence; Audit marked as Coming Soon.

### MVP Checklist
- [x] Start from story text (manual input)
- [x] Parse template and show schema (via admin-managed template; UI shows schema in output)
- [x] Retrieve evidence from configured sources (backend; UI renders evidence list in output)
- [x] Populate story schema (description, ACs, dependencies, NFRs, assumptions, questions)
- [x] Validate INVEST + gaps and apply fixes (validation results visible)
- [x] Run critique loop (PO/QA/Dev) and apply updates
- [x] Start source epic input (manual epic ID + description)

### TODOs / Pending Work
- [ ] **Knowledge Base Management:** define UX + backend for managing knowledge sources, ingestion, and governance.
- [ ] **Admin Console → Integrations:** finish integration management UX beyond Jira/Confluence, including status, scopes, and testing.
- [ ] **Knowledge Base Context References:** define how retrieved references are stored, surfaced, and applied in the Story workflow (see notes below).

### Notes: Knowledge Context Strategy (to define)
- Define reference model: source type, title, excerpt, URL, confidence, and linkage to story sections.
- Decide retrieval policy: which sources, ranking thresholds, and how to merge duplicates.
- Determine how references are displayed: inline citations in story fields vs. evidence panel.
- Decide storage strategy: whether to store references in working memory, long-term memory, or both.
