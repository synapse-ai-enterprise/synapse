## Consolidated Agents (User-Facing vs Implementation)

This document defines which agents are user-facing in the Admin Console, how they map to backend implementation agents, and which flows they apply to.

### User-facing agent categories (Admin Console)

| Category | Purpose | Relevant flows (labels) | Backend implementation agents |
| --- | --- | --- | --- |
| Orchestrator | Routes steps and controls workflow | `Story Detailing`, `Epic → Stories` | `OrchestratorAgent` (`src/cognitive_engine/agents/orchestrator_agent.py`) |
| Business | Business intent, value, and narrative | `Epic → Stories`, `Story Detailing (critique)` | `ProductOwnerAgent` (`src/cognitive_engine/agents/po_agent.py`), `EpicAnalysisAgent`, `SplittingStrategyAgent`, `StoryGenerationAgent` |
| Technical | Feasibility, quality, and constraints | `Story Detailing`, `Story Detailing (critique)` | `DeveloperAgent` (`src/cognitive_engine/agents/developer_agent.py`), `QAAgent` (`src/cognitive_engine/agents/qa_agent.py`) |

**Note:** These categories are intended for Admin configuration only. The UI should not expose internal specialist agent toggles (template parser, knowledge retrieval, story writer) unless needed for troubleshooting.

### Specialist agents (implementation-only)

These agents are used in workflows but are not intended as separate user-facing config toggles:

- `TemplateParserAgent` — parses template schema
- `KnowledgeRetrievalAgent` — retrieves evidence/context
- `StoryWriterAgent` — populates story schema
- `ValidationGapDetectionAgent` — INVEST + gap detection
- `EpicAnalysisAgent` / `SplittingStrategyAgent` / `StoryGenerationAgent`
- `SupervisorAgent` — **used only in Optimization/MAD workflow**

### Flow mapping

**Epic → Stories (Module 1)**
- Orchestrator: `OrchestratorAgent`
- Business: `EpicAnalysisAgent`, `SplittingStrategyAgent`, `StoryGenerationAgent`
- Critique loop: `ProductOwnerAgent`, `QAAgent`, `DeveloperAgent` (optional)

**Story Detailing (Module 2)**
- Orchestrator: `OrchestratorAgent`
- Specialist pipeline: `TemplateParserAgent` → `KnowledgeRetrievalAgent` → `StoryWriterAgent` → `ValidationGapDetectionAgent`
- Critique loop: `ProductOwnerAgent`, `QAAgent`, `DeveloperAgent`

**Optimization / MAD workflow**
- Orchestrator: `SupervisorAgent` (not user-facing in Admin Console)
- Critique loop: `ProductOwnerAgent`, `QAAgent`, `DeveloperAgent`

### Alignment with FIGMA_AGENT_MAPPING.md

**Aligned**
- Admin → Models & Agents should map to **Orchestrator**, **Business**, **Technical** categories.
- Templates and Integrations are admin-managed; specialist agents use them indirectly.

**Deviations / Updates Needed**
- Figma mapping lists `story_generation_agent` for “Create a User Story”; the current implementation uses **Story Detailing** agents (`TemplateParser`, `KnowledgeRetrieval`, `StoryWriter`, `ValidationGapDetection`).
- `SupervisorAgent` is not part of Story Detailing; it is for **Optimization** only.
- Integrations list in Figma (Jira/Confluence/SharePoint) differs from backend (Linear/Notion/GitHub); MVP scope is Jira + Confluence.

### Recommended Admin Console structure

**Agent Configuration (User-facing)**
- Orchestrator (Story workflows) — `Story Detailing`, `Epic → Stories`
- Business (PO) — `Epic → Stories`, `Story Detailing (critique)`
- Technical (QA + Dev) — `Story Detailing`, `Story Detailing (critique)`
- Critique loop toggles grouped under Business/Technical (no separate section)

**Hidden (implementation-only)**
- Template Parser
- Knowledge Retrieval
- Story Writer
- Validation & Gap Detection
- Supervisor (Optimization only)
