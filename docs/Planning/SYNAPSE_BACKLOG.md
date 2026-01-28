# VibeKanban Backlog

## Backlog Items

### Epic → Story handoff
- Status: To Do
- Story: As a PM, I want to select generated stories and deep-link to the Story flow with the full payload so I can continue refinement seamlessly.
- Acceptance criteria:
  - User can multi-select generated stories.
  - “Open in Story Flow” deep-links with payload (ID + content).
  - Story flow pre-populates fields from payload.
  - Handles invalid/missing payload with inline error.

### Template Parser wiring
- Status: Done
- Story: As a user, I want to upload or select a template and parse required/optional fields so I can standardize story generation.
- Acceptance criteria:
  - Parsed schema shows required vs optional fields.
  - Default template is used for User Story flow.
  - Template managed in Admin Console.

### Knowledge Retrieval evidence panel
- Status: Done
- Story: As a reviewer, I want to see sources, confidence, and traceability per snippet so I can verify evidence.
- Acceptance criteria:
  - Evidence list shows retrieved items when available.
  - Empty state when no evidence.

### Story Writer full schema
- Status: Done
- Story: As a writer, I want the full story schema rendered so I can see all required details.
- Acceptance criteria:
  - UI renders description and acceptance criteria.
  - Missing fields show placeholders.

### Validation details
- Status: Done
- Story: As QA, I want INVEST results and remediation actions so I can fix issues quickly.
- Acceptance criteria:
  - INVEST criteria shown with pass/fail per item.
  - Gaps and issues listed.

### Critique loop execution
- Status: Done
- Story: As a user, I want PO/QA/Dev critiques run as separate steps with refresh + apply actions so I can iterate safely.
- Acceptance criteria:
  - Critique loop executes and displays QA/Dev notes.

### Run history model
- Status: To Do
- Story: As an operator, I want runs persisted with status, duration, agents, and outputs so I can audit workflows.
- Acceptance criteria:
  - Runs list includes status, duration, agents used.
  - Detail view shows full outputs.
  - Filters by status and date range.
  - Persistence survives reload.

### Audit log export
- Status: To Do
- Story: As a compliance user, I want to filter audit logs and export as CSV/JSON so I can report activity.
- Acceptance criteria:
  - Filters by date, actor, action type.
  - Export supports CSV and JSON.
  - Export includes filter metadata.
  - Large exports show progress.

### Technique selection UX
- Status: To Do
- Story: As a user, I want a pre-selected technique with ability to override and provide rationale so I can control generation.
- Acceptance criteria:
  - Default technique is pre-selected.
  - Manual technique entry supported.
  - Rationale field required on override.
  - Selected technique stored with run.

### Agent confidence + metadata
- Status: In Progress
- Story: As a user, I want confidence, processing time, and sources per agent so I can judge reliability.
- Acceptance criteria:
  - Confidence stored in workflow metadata.
  - Missing data shows “Not available”.

### Export workflow
- Status: To Do
- Story: As a user, I want to confirm export target and see success + ticket link so I can track results.
- Acceptance criteria:
  - Export target selection required (e.g., Linear/Jira).
  - Confirmation step before submission.
  - Success toast shows created ticket link.
  - Failure includes retry + error details.

### Initiative workflow definition
- Status: To Do
- Story: As a PM, I want the initiative flow aligned to agent architecture or marked experimental so I understand reliability.
- Acceptance criteria:
  - Initiative flow either fully mapped or labeled “Experimental”.
  - Tooltip explains limitations.
  - Experimental flow gated behind explicit acknowledgement.
  - Alignment status shown in settings.

### Workflow progress streaming
- Status: Done
- Story: As a user, I want to see live stage progression while generation is running so I can follow agent activity.
- Acceptance criteria:
  - UI updates stage status as each node starts/completes.
  - Progress persists until final state arrives.

### Admin MVP scope enforcement
- Status: In Progress
- Story: As an admin, I want non-MVP areas marked “Coming Soon” so the scope is clear.
- Acceptance criteria:
  - Admin Audit & Governance shows watermark.
  - Integrations show Jira/Confluence as active and others as coming soon.

### Knowledge base management
- Status: To Do
- Story: As an operator, I want to configure and manage knowledge sources so retrieval is controlled and auditable.
- Acceptance criteria:
  - Manage sources, sync status, and governance metadata.
  - Controls for enabling/disabling sources per workflow.

### Knowledge context references
- Status: To Do
- Story: As a user, I want to see how retrieved references are used in the story so I can validate sources.
- Acceptance criteria:
  - Define reference model (source, excerpt, confidence).
  - Link references to story fields or evidence panel.
