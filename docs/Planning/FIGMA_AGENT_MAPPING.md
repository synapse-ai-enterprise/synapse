## Screen-to-agent mapping (Updated)

### Product creation
- Create an EPIC (Module 1)
  - Orchestrator: `orchestrator_agent`
  - Business: `epic_analysis_agent`, `splitting_strategy_agent`, `story_generation_agent`
  - Critique loop (optional): `po_agent`, `qa_agent`, `developer_agent`

- Create a User Story (Story Detailing / Module 2)
  - Orchestrator: `orchestrator_agent`
  - Specialist pipeline: `template_parser_agent` → `knowledge_retrieval_agent` → `story_writer_agent` → `validation_gap_agent`
  - Critique loop: `po_agent`, `qa_agent`, `developer_agent`

### Admin Console
- Templates (preview/edit)
  - Agents: `template_parser_agent` (structure/field mapping)
  - Optional: `knowledge_retrieval_agent` if templates reference ingested knowledge

- Models & Agents
  - User-facing categories: Orchestrator / Business / Technical
  - Maps to: `orchestrator_agent`, `po_agent`, `qa_agent`, `developer_agent`
  - Infrastructure: `litellm_adapter` for model selection

- Integrations
  - Ingress/egress: `linear_ingress`, `linear_egress`, `github_loader`, `notion_loader`
  - Indirectly impacts: `knowledge_retrieval_agent` and story generation context

- Audit & Governance
  - Orchestrator output + tracing/logging from `utils/tracing.py`, `utils/logger.py`

### Navigation-level
- History
  - Aggregated run history from orchestrator and queue/workers

- Initiative (Coming soon)
  - No direct agent yet; likely requires an initiative synthesis workflow

## Gaps and questions
- Initiative workflow: missing domain schema and agent pipeline.
- History source: no defined storage/retention model for run history.
- Templates: storage/versioning and upload pipeline are not defined in backend.
- Integrations: UI shows Jira/Confluence; backend currently supports Linear/Notion/GitHub (MVP uses Jira + Confluence).
- Audit export: UI shows export logs; backend export endpoint not specified.
