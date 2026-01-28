## UI-to-backend contracts (proposed)

### Generate draft (EPIC)
- Endpoint: `POST /api/story-writing`
- Payload:
  - `flow`: `epic_to_stories`
  - `epic_text`: string (required)
  - `epic_id`: string | null
  - `selected_techniques`: string[]
  - `story_text`: null
  - `template_text`: null
  - `project_id`: string | null
  - `requester_id`: string | null
- Response: draft epic + derived stories

### Generate draft (User Story)
- Endpoint: `POST /api/story-writing`
- Payload:
  - `flow`: `story_to_detail`
  - `story_text`: string (required)
  - `template_text`: string | null
  - `epic_text`: null
  - `epic_id`: string | null
  - `selected_techniques`: string[]
  - `project_id`: string | null
  - `requester_id`: string | null
- Response: enriched story detail with acceptance criteria

### Templates (Admin)
- `GET /api/templates?artifact_type={EPIC|USER_STORY|INITIATIVE}`: list + active template metadata
- `GET /api/templates/{template_id}`: template content + version history
- `POST /api/templates`: upload new template version
- `PUT /api/templates/{template_id}`: edit template content

### Integrations (Admin)
- `GET /api/integrations`: list integrations and status
- `POST /api/integrations/{name}/connect`: connect OAuth or token
- `POST /api/integrations/{name}/test`: test connection
- `PUT /api/integrations/{name}/scopes`: update allowed projects/spaces

### Models & Agents (Admin)
- `GET /api/ai/config`: model config + enabled agents
- `PUT /api/ai/config`: update model selection, temperature, retention
- `PUT /api/ai/agents`: enable/disable agents, conflict policy

### Audit & Governance (Admin)
- `GET /api/audit/logs?from=&to=&artifact=`: audit table
- `POST /api/audit/export`: export logs (CSV/JSON)

### History
- `GET /api/history?from=&to=&status=`: workflow run history
