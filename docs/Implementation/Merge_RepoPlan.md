# Synapse Merge Plan: Best of Both Repositories

> **Source Repos:**
> - `migush-repo`: `/Users/subhasri.vadyar/Library/CloudStorage/OneDrive-Valtech/AI/Hackathon/synapse-valtech/migush-repo`
> - `workspace`: `/Users/subhasri.vadyar/Library/CloudStorage/OneDrive-Valtech/AI/Hackathon/synapse-valtech/repo/synapse`

---

## Executive Summary

This document outlines the merge strategy to combine the best features from both repositories:

| From migush-repo (Adding) | From Workspace (Keeping) |
|---------------------------|--------------------------|
| Artifact Splitting | Story Writing Pipeline (8 agents) |
| Debate Round Enforcement | React UI (6 microfrontends) |
| Feedback-Driven Re-drafts | Jira/Confluence Integration |
| Chain-of-thought Prompts | Memory/Event Systems |
| | Vercel Deployment |

---

## Architecture Overview (Post-Merge)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SYNAPSE UI (React)                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  HomeApp    │  │  StoryApp   │  │  AdminApp   │  │  HistoryApp │            │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │
│                         │                                                        │
│                         ▼                                                        │
│              🆕 Split Proposal Panel                                            │
│              (When stories are too large)                                        │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FastAPI Backend                                     │
│  /api/story-writing  │  /api/optimize  │  /api/integrations  │  /webhooks      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           ▼                           ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   Story Writing     │    │   Artifact          │    │   Artifact          │
│   Pipeline          │    │   Optimization      │    │   SPLITTING         │
│   (8 agents)        │    │   Pipeline          │    │   🆕 (from migush)  │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
                                       │
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         COGNITIVE ENGINE (LangGraph)                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │  Core Agents: PO, QA, Developer, Supervisor                                 ││
│  │  + Story Agents: Epic Analysis, Knowledge Retrieval, Orchestrator,          ││
│  │                  Splitting Strategy, Story Generation, Story Writer,        ││
│  │                  Template Parser, Validation Gap Detection                   ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │  🆕 NEW FROM MIGUSH:                                                        ││
│  │  • propose_artifact_split() - Break large stories into smaller ones         ││
│  │  • split_proposal_node - LangGraph node for splitting                       ││
│  │  • Debate round enforcement with _last_node tracking                        ││
│  │  • feedback_summary in re-drafts for iterative improvement                  ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INFRASTRUCTURE                                         │
│  Memory Store │ Event Bus │ Context Graph │ Admin Store │ Workflow Registry     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INTEGRATIONS                                           │
│  Jira │ Confluence │ Linear │ GitHub │ Notion │ LanceDB (Vector)                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Schema Updates

**File:** `src/domain/schema.py`

### 1.1 Add Artifact Splitting Models

```python
class SplitArtifactItem(BaseModel):
    """One artifact in a split proposal (multiple smaller stories from one large one)."""

    title: str = Field(description="User story title for this artifact")
    description: str = Field(description="Description for this artifact")
    acceptance_criteria: List[str] = Field(description="Acceptance criteria for this artifact")
    suggested_ref_suffix: Optional[str] = Field(
        None,
        description="Optional short label for traceability, e.g. Order, Frame, Glasses",
    )


class ArtifactSplitProposal(BaseModel):
    """PO Agent output when proposing to split one large artifact into multiple smaller ones."""

    artifacts: List[SplitArtifactItem] = Field(
        description="List of smaller artifacts that together preserve original scope"
    )
    rationale: Optional[str] = Field(None, description="Why the split was proposed")
```

### 1.2 Update SupervisorDecision

Add `"propose_split"` to the `next_action` literal:

```python
class SupervisorDecision(BaseModel):
    """Supervisor routing decision for multi-agent debate."""

    next_action: Literal[
        "draft",
        "qa_critique",
        "developer_critique",
        "synthesize",
        "validate",
        "execute",
        "propose_split",  # <-- ADD THIS
        "end"
    ] = Field(description="Next action to take in the workflow")
    reasoning: str = Field(description="Explanation for the routing decision")
    should_continue: bool = Field(description="Whether to continue the debate loop")
    priority_focus: Optional[Literal["quality", "feasibility", "business_value", "none"]] = Field(
        None, description="Primary focus area for next iteration"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the routing decision")
```

---

## Phase 2: State Updates

**File:** `src/cognitive_engine/state.py`

### 2.1 Add proposed_artifacts Field

```python
from src.domain.schema import CoreArtifact

class CognitiveState(BaseModel):
    """State object for the cognitive engine workflow."""
    
    # ... existing fields ...
    
    # NEW: For artifact splitting
    proposed_artifacts: List[CoreArtifact] = Field(
        default_factory=list,
        description="Proposed split artifacts when story is too large"
    )
```

---

## Phase 3: PO Agent Enhancement

**File:** `src/cognitive_engine/agents/po_agent.py`

### 3.1 Add Imports

```python
from src.domain.schema import (
    ArtifactRefinement,
    ArtifactSplitProposal,  # <-- ADD
    CoreArtifact,
    UASKnowledgeUnit,
)
```

### 3.2 Update draft_artifact Method

Add `feedback_summary` parameter:

```python
async def draft_artifact(
    self,
    artifact: CoreArtifact,
    context: List[UASKnowledgeUnit],
    feedback_summary: Optional[str] = None,  # <-- ADD THIS
) -> CoreArtifact:
    """Generate initial or re-draft artifact.

    Args:
        artifact: Raw or refined artifact to improve.
        context: Retrieved knowledge units for context.
        feedback_summary: Optional summary of QA/Developer feedback to address (for re-drafts).

    Returns:
        Draft artifact with improved title, description, and acceptance criteria.
    """
    # Format context
    context_text = self._format_context(context)
    
    # NEW: Add feedback section for re-drafts
    feedback_section = ""
    if feedback_summary:
        feedback_section = f"""
**Feedback from previous round (address these):**
{feedback_summary}

"""
    
    messages = [
        {"role": "system", "content": self.SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Generate a refined user story based on the following artifact and context.{feedback_section}

**Current Artifact:**
Title: {artifact.title}
...
```

### 3.3 Add propose_artifact_split Method

```python
async def propose_artifact_split(
    self,
    artifact: CoreArtifact,
    qa_critique: Optional[str] = None,
    violations_summary: Optional[List[str]] = None,
) -> List[CoreArtifact]:
    """Propose splitting one large artifact into multiple smaller ones.

    Use when the story is too large (INVEST S) or covers multiple distinct
    features/models; the result preserves original scope as multiple artifacts.

    Args:
        artifact: Current (large) artifact to split.
        qa_critique: Optional QA critique text.
        violations_summary: Optional list of violation descriptions (e.g. "S: Story too large").

    Returns:
        List of CoreArtifact proposals (2 or more) that together cover the original scope.
    """
    critique_section = ""
    if qa_critique:
        critique_section = f"\n**QA Critique:**\n{qa_critique[:600]}{'...' if len(qa_critique) > 600 else ''}\n"
    violations_section = ""
    if violations_summary:
        violations_section = "\n**INVEST violations (e.g. Story too large):**\n" + "\n".join(
            f"- {v}" for v in violations_summary[:15]
        ) + "\n"

    ac_block = chr(10).join(f"- {ac}" for ac in artifact.acceptance_criteria) if artifact.acceptance_criteria else "None"
    messages = [
        {"role": "system", "content": self.SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""The following artifact has been assessed as too large or covering multiple distinct features. Your task is to propose splitting it into MULTIPLE smaller artifacts that TOGETHER preserve the FULL original scope. You MUST NOT drop any model or entity that appears in the original.

**Current artifact:**
Title: {artifact.title}
Description: {artifact.description}
Acceptance Criteria:
{ac_block}
{critique_section}{violations_section}

**CRITICAL RULES (follow strictly):**
1. **One artifact per model/entity when the original names multiple.** If the original mentions Order, Frame, and Glasses (or any other distinct models/entities), you MUST output one artifact for EACH of them (e.g. suggested_ref_suffix: "Order", "Frame", "Glasses"). Do NOT merge them into fewer artifacts.
2. **Preserve every acceptance criterion.** Each original AC must appear in exactly one of the proposed artifacts.
3. Output at least 2 artifacts. Use suggested_ref_suffix for each for traceability.
4. Each proposed artifact must be a valid user story (title, description, acceptance criteria) and pass INVEST (Small, Independent, Testable).

Output your split proposal as JSON. Put your final JSON after FINAL_JSON:

FINAL_JSON:
{{
  "artifacts": [
    {{ "title": "...", "description": "...", "acceptance_criteria": ["..."], "suggested_ref_suffix": "Order" }},
    {{ "title": "...", "description": "...", "acceptance_criteria": ["..."], "suggested_ref_suffix": "Frame" }},
    ...
  ],
  "rationale": "Brief explanation of the split"
}}""",
        },
    ]

    proposal = await self.llm_provider.structured_completion(
        messages=messages,
        response_model=ArtifactSplitProposal,
        temperature=0.5,
    )

    # Build full CoreArtifact list from template artifact + each split item
    result: List[CoreArtifact] = []
    for i, item in enumerate(proposal.artifacts):
        ref_suffix = item.suggested_ref_suffix or str(i + 1)
        human_ref = f"{artifact.human_ref}-{ref_suffix}" if artifact.human_ref else f"split-{i + 1}"
        url = f"{artifact.url.rstrip('/')}-{ref_suffix}" if artifact.url else ""
        proposed = artifact.model_copy()
        proposed.title = item.title
        proposed.description = item.description
        proposed.acceptance_criteria = item.acceptance_criteria
        proposed.human_ref = human_ref
        proposed.url = url or proposed.url
        result.append(proposed)

    return result
```

---

## Phase 4: Nodes Update

**File:** `src/cognitive_engine/nodes.py`

### 4.1 Update drafting_node with Feedback

```python
async def drafting_node(
    state_dict: Dict[str, Any],
    po_agent: ProductOwnerAgent,
) -> Dict[str, Any]:
    """Drafting node: PO Agent generates draft artifact."""
    state = _state_from_dict(state_dict)
    
    # Use refined_artifact if available (from previous iteration), otherwise current_artifact
    artifact_to_draft = state.refined_artifact if state.refined_artifact else state.current_artifact
    
    if not artifact_to_draft:
        return state_dict

    # NEW: Build feedback summary for re-drafts
    feedback_summary = None
    if state.refined_artifact and (state.qa_critique or state.developer_critique):
        parts = []
        if state.qa_critique:
            parts.append(f"QA: {state.qa_critique[:800]}{'...' if len(state.qa_critique) > 800 else ''}")
        if state.developer_critique:
            parts.append(f"Developer: {state.developer_critique[:600]}{'...' if len(state.developer_critique) > 600 else ''}")
        if state.invest_violations:
            parts.append("INVEST violations to fix: " + "; ".join(str(v) for v in state.invest_violations[:10]))
        feedback_summary = "\n".join(parts)

    draft = await po_agent.draft_artifact(
        artifact_to_draft,
        state.retrieved_context,
        feedback_summary=feedback_summary,  # <-- NEW PARAMETER
    )

    state.draft_artifact = draft
    return _state_to_dict(state)
```

### 4.2 Add split_proposal_node

```python
async def split_proposal_node(
    state_dict: Dict[str, Any],
    po_agent: ProductOwnerAgent,
) -> Dict[str, Any]:
    """Propose splitting the current artifact into multiple smaller artifacts.

    Used when the debate concludes the story is too large (INVEST S) or covers
    multiple distinct features; the result is a proposal for N artifacts that
    together preserve original scope. Uses the ORIGINAL artifact (from ingress)
    so the split preserves full scope.
    """
    state = _state_from_dict(state_dict)
    # Use original artifact so split preserves full scope
    artifact = state.current_artifact or state.refined_artifact or state.draft_artifact
    if not artifact:
        return state_dict

    violations_summary: List[str] = []
    for v in state.structured_qa_violations:
        if hasattr(v, "criterion") and hasattr(v, "description"):
            violations_summary.append(f"{v.criterion}: {v.description}")
        elif isinstance(v, dict):
            violations_summary.append(
                f"{v.get('criterion', '?')}: {v.get('description', '')}"
            )
    if not violations_summary and state.invest_violations:
        violations_summary = list(state.invest_violations)

    proposed = await po_agent.propose_artifact_split(
        artifact,
        qa_critique=state.qa_critique,
        violations_summary=violations_summary or None,
    )
    state.proposed_artifacts = proposed
    return _state_to_dict(state)
```

---

## Phase 5: Graph Update

**File:** `src/cognitive_engine/graph.py`

### 5.1 Add Debate Round Enforcement

Update `supervisor_route()` function:

```python
def supervisor_route(state: Dict) -> Literal[
    "drafting", "qa_critique", "developer_critique", "synthesize", 
    "validate", "execution", "split_proposal"
]:
    """Route based on supervisor decision and full-round enforcement."""
    next_action = state.get("_next_action")
    last_node = state.get("_last_node", "unknown")
    draft_present = bool(state.get("draft_artifact"))
    qa_present = bool(state.get("qa_critique"))
    developer_present = bool(state.get("developer_critique"))
    refined_present = bool(state.get("refined_artifact"))

    # NEW: Enforce full debate round: qa → developer → synthesize → validate
    # before allowing re-draft, so quality improves via full multi-agent input
    if last_node == "qa_critique" and qa_present and not developer_present:
        return "developer_critique"
    if last_node == "developer_critique" and developer_present and not refined_present:
        return "synthesize"
    if last_node == "synthesize" and refined_present:
        return "validate"

    # Safety cap: if supervisor chose "draft" but we just finished drafting,
    # route to qa_critique to start the round
    if next_action == "draft" and draft_present and last_node == "drafting":
        return "qa_critique"

    # Map supervisor actions to node names
    action_map = {
        "draft": "drafting",
        "qa_critique": "qa_critique",
        "developer_critique": "developer_critique",
        "synthesize": "synthesize",
        "validate": "validate",
        "execute": "execution",
        "propose_split": "split_proposal",  # <-- ADD THIS
    }

    # Default routing logic if supervisor hasn't decided yet
    if not next_action:
        if not draft_present:
            return "drafting"
        elif not qa_present:
            return "qa_critique"
        elif not developer_present:
            return "developer_critique"
        elif not refined_present:
            return "synthesize"
        else:
            return "validate"

    if next_action == "end":
        return "execution"

    return action_map.get(next_action, "validate")
```

### 5.2 Add split_proposal Node and Edges

```python
# Add wrapper function
async def split_proposal_wrapper(state):
    state["_current_node"] = "split_proposal"
    result = await split_proposal_node(state, po_agent)
    result["_current_node"] = "split_proposal"
    return result

# Add node to graph
graph.add_node("split_proposal", split_proposal_wrapper)

# Update conditional edges
graph.add_conditional_edges(
    "supervisor",
    supervisor_route,
    {
        "drafting": "drafting",
        "qa_critique": "qa_critique",
        "developer_critique": "developer_critique",
        "synthesize": "synthesize",
        "validate": "validation",
        "execution": "execution",
        "split_proposal": "split_proposal",  # <-- ADD THIS
    },
)

# Add terminal edge for split_proposal
graph.add_edge("split_proposal", END)
```

### 5.3 Update execution_node to Handle Split Proposals

```python
async def execution_node(
    state_dict: Dict[str, Any],
    issue_tracker: IIssueTracker,
) -> Dict[str, Any]:
    """Execution node: Update Linear via adapter (single artifact path).

    When state has proposed_artifacts, the outcome is a multi-artifact proposal
    and we do not update the original issue; the proposal is consumed by the caller.
    """
    state = _state_from_dict(state_dict)
    
    # NEW: If split proposal exists, don't update original
    if state.proposed_artifacts:
        return _state_to_dict(state)

    artifact_to_update = state.refined_artifact or state.draft_artifact
    if not artifact_to_update:
        return state_dict

    success = await issue_tracker.update_issue(
        state.request.artifact_id,
        artifact_to_update,
    )

    return {"execution_success": success, **_state_to_dict(state)}
```

---

## Phase 6: UI Integration (StoryApp.jsx)

**File:** `ui/src/microfrontends/StoryApp.jsx`

### 6.1 Component Location

The Split Proposal Panel goes **inside StoryApp.jsx**, between the Critique Loop and Export sections:

```
┌─────────────────────────────────────────────────────────────────┐
│  StoryApp.jsx Structure                                         │
├─────────────────────────────────────────────────────────────────┤
│  Story Input Form                                               │
│  Workflow Progress Bar                                          │
│  Story Writer Output Panel                                      │
│  Evidence List & Traceability Panels                            │
│  Critique Loop (QA Notes, Developer Notes)                      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 🆕 SPLIT PROPOSAL PANEL (Insert around line 651)        │   │
│  │ ─────────────────────────────────────────────────────── │   │
│  │ ⚠️ Story Too Large - Split Recommended                  │   │
│  │                                                         │   │
│  │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │   │
│  │ │ Story 1:    │ │ Story 2:    │ │ Story 3:    │        │   │
│  │ │ Order Model │ │ Frame Model │ │ Glasses     │        │   │
│  │ │ ...ACs...   │ │ ...ACs...   │ │ ...ACs...   │        │   │
│  │ └─────────────┘ └─────────────┘ └─────────────┘        │   │
│  │                                                         │   │
│  │ [Export All to Jira] [Edit Splits] [Reject & Refine]   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Export Section                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 JSX Code (Insert around line 651)

```jsx
{/* Split Proposal Panel - Shows when story is too large */}
{storyRun?.proposed_artifacts && storyRun.proposed_artifacts.length > 0 && (
  <div className="card">
    <div className="section">
      <div className="split-proposal-header">
        <span className="status-pill warn">Story Split Recommended</span>
        <h3>This story covers multiple features</h3>
        <p className="muted">
          Based on INVEST analysis, we recommend splitting this into{" "}
          {storyRun.proposed_artifacts.length} smaller stories:
        </p>
      </div>
      
      <div className="split-cards-grid">
        {storyRun.proposed_artifacts.map((artifact, idx) => (
          <div key={idx} className="split-card">
            <div className="split-card-header">
              <span className="split-badge">
                {artifact.suggested_ref_suffix || artifact.human_ref || `Part ${idx + 1}`}
              </span>
              <h4>{artifact.title}</h4>
            </div>
            <p className="muted">{artifact.description}</p>
            {artifact.acceptance_criteria && artifact.acceptance_criteria.length > 0 && (
              <div className="split-card-ac">
                <strong>Acceptance Criteria:</strong>
                <ul>
                  {artifact.acceptance_criteria.map((ac, i) => (
                    <li key={i}>{ac}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
      
      <div className="actions align-left">
        <button type="button" className="primary">
          Export All to Jira
        </button>
        <button type="button" className="ghost">
          Edit Splits
        </button>
        <button type="button" className="ghost">
          Reject &amp; Refine as Single Story
        </button>
      </div>
    </div>
  </div>
)}
```

### 6.3 CSS Additions

**File:** `ui/src/styles.css`

```css
/* ============================
   Split Proposal Styles
   ============================ */

.split-proposal-header {
  margin-bottom: 20px;
}

.split-proposal-header h3 {
  margin: 8px 0 4px 0;
}

.split-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.split-card {
  background: var(--bg-secondary, #f8f9fa);
  border: 1px solid var(--border-color, #e1e4e8);
  border-radius: 8px;
  padding: 16px;
  transition: border-color 0.2s ease;
}

.split-card:hover {
  border-color: var(--accent-color, #0066cc);
}

.split-card-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.split-badge {
  display: inline-block;
  background: var(--accent-color, #0066cc);
  color: white;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  width: fit-content;
}

.split-card h4 {
  margin: 0;
  font-size: 14px;
  line-height: 1.4;
}

.split-card > p.muted {
  font-size: 13px;
  margin-bottom: 12px;
}

.split-card-ac {
  border-top: 1px solid var(--border-color, #e1e4e8);
  padding-top: 12px;
  margin-top: 12px;
}

.split-card-ac strong {
  font-size: 12px;
  color: var(--text-secondary, #586069);
}

.split-card-ac ul {
  margin: 8px 0 0 0;
  padding-left: 20px;
}

.split-card-ac li {
  font-size: 13px;
  color: var(--text-muted, #6a737d);
  margin-bottom: 4px;
  line-height: 1.4;
}
```

---

## Execution Order & Checklist

| Step | File | Action | Status |
|------|------|--------|--------|
| 1 | `src/domain/schema.py` | Add `SplitArtifactItem`, `ArtifactSplitProposal`, update `SupervisorDecision` | ⬜ |
| 2 | `src/cognitive_engine/state.py` | Add `proposed_artifacts` field | ⬜ |
| 3 | `src/cognitive_engine/agents/po_agent.py` | Add `feedback_summary` param, add `propose_artifact_split()` | ⬜ |
| 4 | `src/cognitive_engine/nodes.py` | Update `drafting_node`, add `split_proposal_node` | ⬜ |
| 5 | `src/cognitive_engine/graph.py` | Add debate enforcement, add `split_proposal` routing | ⬜ |
| 6a | `ui/src/microfrontends/StoryApp.jsx` | Add Split Proposal Panel | ⬜ |
| 6b | `ui/src/styles.css` | Add split card styles | ⬜ |
| 7 | Tests | Run existing tests + new split tests | ⬜ |

---

## Files Modified Summary

| File | Lines Changed | Type |
|------|--------------|------|
| `src/domain/schema.py` | +30 | Schema models |
| `src/cognitive_engine/state.py` | +5 | State field |
| `src/cognitive_engine/agents/po_agent.py` | +100 | Agent method |
| `src/cognitive_engine/nodes.py` | +50 | New node |
| `src/cognitive_engine/graph.py` | +30 | Routing logic |
| `ui/src/microfrontends/StoryApp.jsx` | +50 | UI component |
| `ui/src/styles.css` | +70 | CSS styles |

**Total: ~335 lines of changes**

---

## Testing Plan

### Unit Tests
- [ ] Test `propose_artifact_split()` with large stories containing multiple models
- [ ] Test debate round enforcement (qa → developer → synthesize flow)
- [ ] Test `feedback_summary` is passed correctly in re-drafts
- [ ] Test `split_proposal_node` returns valid artifacts

### Integration Tests
- [ ] Full workflow where supervisor decides to split
- [ ] Verify UI displays split proposals correctly
- [ ] Test export functionality for split stories

### Regression Tests
- [ ] Ensure existing story writing pipeline works unchanged
- [ ] Ensure existing artifact optimization works unchanged
- [ ] Verify all existing tests pass

---

## Rollback Plan

All changes are additive and backwards-compatible. If issues arise:

1. **Quick fix**: Remove `split_proposal` from routing map in `graph.py`
2. **Full rollback**: Revert commits in reverse order (6 → 1)
3. **Partial rollback**: Keep schema models, disable routing only

---

## Post-Merge Capabilities

| Feature | Before | After |
|---------|--------|-------|
| Story Writing Pipeline | ✅ | ✅ |
| React UI | ✅ | ✅ |
| Jira/Confluence Integration | ✅ | ✅ |
| Memory/Event Systems | ✅ | ✅ |
| **Artifact Splitting** | ❌ | ✅ |
| **Debate Round Enforcement** | Partial | ✅ Full |
| **Feedback-Driven Re-drafts** | ❌ | ✅ |
| **Split Proposal UI** | ❌ | ✅ |

---

## Estimated Effort

| Phase | Time |
|-------|------|
| Schema + State | 30 min |
| PO Agent | 1 hour |
| Nodes | 1 hour |
| Graph | 45 min |
| UI (StoryApp + CSS) | 45 min |
| Testing | 1-2 hours |
| **Total** | **4-6 hours** |
