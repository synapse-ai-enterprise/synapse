## User Flow: Story Detailing (Module 2)

This document describes the end-user actions and system behavior in the Story Detailing workflow.

### Visuals
- **Sequence diagram:** `/Users/subhasri.vadyar/.cursor/projects/Users-subhasri-vadyar-Library-CloudStorage-OneDrive-Valtech-AI-Hackathon-synapse-valtech-repo-synapse/assets/story-detailing-generate-draft-sequence.png`
- **UI before Generate draft:** `/Users/subhasri.vadyar/.cursor/projects/Users-subhasri-vadyar-Library-CloudStorage-OneDrive-Valtech-AI-Hackathon-synapse-valtech-repo-synapse/assets/story-detailing-before-generate.png`
- **UI after Generate draft:** `/Users/subhasri.vadyar/.cursor/projects/Users-subhasri-vadyar-Library-CloudStorage-OneDrive-Valtech-AI-Hackathon-synapse-valtech-repo-synapse/assets/story-detailing-after-generate.png`

### 1) Generate draft
- **User action:** Clicks **Generate draft** after entering story text (and optional epic ID/description).
- **UI behavior:** Disables the button, shows "Running...", clears any prior error.
- **API call:** `POST /api/story-writing` with:
  - `flow`: `story_to_detail`
  - `story_text`: user draft
  - `template_text`: current template (optional)
  - `epic_id` / `epic_text`: only if start source is enabled
- **Backend workflow:** Orchestrator runs
  - Template Parser → Knowledge Retrieval → Story Writer → Validation → Critique Loop
- **UI render:** Populates timeline, template schema, evidence panel, story output, validation, and critique panels.

### 2) Start source toggle
- **User action:** Toggles **Start from EPIC**.
- **UI behavior:** Shows Epic ID + Epic description inputs.
- **Validation:** Generate draft is disabled until Epic ID is provided when toggle is on.

### 3) Epic ID input
- **User action:** Enters an Epic ID (e.g., EPIC-123).
- **UI behavior:** Enables Generate draft once story text is present.
- **Backend impact:** Sends `epic_id` for context and traceability.

### 4) Epic description input
- **User action:** Enters Epic description.
- **UI behavior:** Auto-populates story draft only if the story draft is empty.
- **Backend impact:** Sends `epic_text` as additional context.

### 5) Upload template
- **User action:** Clicks **Upload template** (placeholder).
- **Current behavior:** No action wired yet.
- **Planned:** Upload template to backend template API and refresh schema.

### 6) Preview template
- **User action:** Clicks **Preview template** (placeholder).
- **Current behavior:** No action wired yet.
- **Planned:** Show modal with current template content and schema.

### 7) Knowledge retrieval source toggles
- **User action:** Checks/unchecks Graph/Vector/Code/MCP sources.
- **UI behavior:** Updates toggle state.
- **Current behavior:** Toggles are not yet used in API calls.
- **Planned:** Send selected sources to retrieval layer as filters.

### 8) Regenerate sections
- **User action:** Clicks **Regenerate sections** (placeholder).
- **Current behavior:** No action wired yet.
- **Planned:** Re-run Story Writer node with existing context for partial regeneration.

### 9) Edit story
- **User action:** Clicks **Edit story** (placeholder).
- **Current behavior:** No action wired yet.
- **Planned:** Enable inline editing and sync back to backend for validation.

### 10) Apply fixes
- **User action:** Clicks **Apply fixes** (placeholder).
- **Current behavior:** No action wired yet.
- **Planned:** Use validation gaps to re-run Story Writer with targeted fixes.

### 11) Rerun validation
- **User action:** Clicks **Rerun validation** (placeholder).
- **Current behavior:** No action wired yet.
- **Planned:** Re-run Validation node using the current story.

### 12) Apply suggestions
- **User action:** Clicks **Apply suggestions** (placeholder).
- **Current behavior:** No action wired yet.
- **Planned:** Re-run Critique Loop and apply PO synthesis updates.

### 13) Rerun critique
- **User action:** Clicks **Rerun critique** (placeholder).
- **Current behavior:** No action wired yet.
- **Planned:** Re-run QA + Dev critique and refresh critique panel.

### 14) Export detailed story
- **User action:** Clicks **Export to Jira/Linear/Notion** (placeholder).
- **Current behavior:** No action wired yet.
- **Planned:** Send finalized story to egress adapters.
