# Synapse Agentic AI Architecture (1-page)

![RAG vs AI Agents vs Agentic RAG](/Users/subhasri.vadyar/.cursor/projects/Users-subhasri-vadyar-Library-CloudStorage-OneDrive-Valtech-AI-Hackathon-synapse-valtech-repo-synapse/assets/image-eb9a11b4-6a89-406b-8476-2eb11e49b387.png)

![Synapse Agentic Workflow (Domain + Task Agents)](/Users/subhasri.vadyar/.cursor/projects/Users-subhasri-vadyar-Library-CloudStorage-OneDrive-Valtech-AI-Hackathon-synapse-valtech-repo-synapse/assets/synapse-agentic-workflow-n8n.png)

## What this system is
Synapse is an agentic AI system that orchestrates multiple specialist agents to generate, critique, and refine Agile artifacts. It is not just RAG or a single-agent chatbot; it uses a supervisor-driven, multi-agent loop with stateful memory and iterative feedback until quality criteria are met.

## How it maps to the attached diagram
- **Agentic RAG**: The workflow combines retrieval with multi-agent planning and critique.
- **Aggregator/Orchestrator Agent**: `SupervisorAgent` and `OrchestratorAgent` decide next actions and route work.
- **Specialist Agents**: Product Owner, QA, and Developer agents collaborate with critique and synthesis.
- **Memory**: Structured state + critique history + vector store for long-term knowledge.
- **Tools/Data sources**: Issue tracker and knowledge base adapters act as tool-like integrations.

## End-to-end flow (simplified)
1. **Ingress**: Input request enters the cognitive graph.
2. **Context Assembly**: Retrieve relevant knowledge from the vector store.
3. **Drafting**: Product Owner agent drafts an artifact.
4. **Critique Loop**:
   - QA agent checks INVEST quality.
   - Developer agent checks feasibility/risks.
   - PO agent synthesizes and refines.
5. **Validation**: Confidence scoring and violation checks.
6. **Execution**: Update downstream systems (e.g., issue tracker).

## Diagram: Cognitive agentic workflow (as implemented)
```mermaid
flowchart TD
    A[Ingress] --> B[Context Assembly]
    B --> C[Supervisor Decision]
    C --> D["Drafting<br/><span style='color:#6b7280'>PO</span>"]
    C --> E["QA Critique<br/><span style='color:#6b7280'>INVEST</span>"]
    C --> F["Dev Critique<br/><span style='color:#6b7280'>Feasibility</span>"]
    C --> G["Synthesis<br/><span style='color:#6b7280'>PO</span>"]
    C --> H[Validation]
    H --> C
    D --> C
    E --> C
    F --> C
    G --> C
    H --> I[Execution]
    I --> J[End]
```

## Diagram: Story generation workflow and mapping
This maps the story-writing flow to the agentic loop (orchestrator = supervisor role).

```mermaid
flowchart TD
    O[Orchestrator] --> EA[Epic Analysis]
    O --> SS[Splitting Strategy]
    O --> SG[Story Generation]
    O --> TP[Template Parser]
    O --> KR[Knowledge Retrieval]
    O --> SW[Story Writer]
    O --> VL[Validation]
    O --> CL["Critique Loop<br/><span style='color:#6b7280'>QA+Dev+PO</span>"]
    EA --> O
    SS --> O
    SG --> O
    TP --> O
    KR --> O
    SW --> O
    VL --> O
    CL --> O
```

**Mapping to the agentic loop**
- **Supervisor/Planner**: `OrchestratorAgent` decides next step.
- **Drafting**: `StoryWriterAgent` produces the populated story.
- **Critique Loop**: `QAAgent` + `DeveloperAgent` + `ProductOwnerAgent` refine.
- **Validation**: `ValidationGapDetectionAgent` checks gaps.
- **Retrieval/Context**: `KnowledgeRetrievalAgent` pulls evidence for grounding.

## Domain-based vs task-based agent mapping
The system uses both domain-based agents (user-facing roles) and task-based specialists:

- **User-facing categories remain domain-based**: Business/Technical/Orchestrator with PO/QA/Dev critique.
- **Story detailing is task-based**: template parsing, retrieval, writing, and validation are handled by specialist agents.
- **Result**: This is not a full shift to task-based agents; both models are present and coordinated.

**How the two models map in practice**
```mermaid
flowchart LR
    subgraph Domain_Agents["Domain-based: User-facing"]
        PO["Product Owner<br/><span style='color:#6b7280'>Business</span>"]
        QA["QA<br/><span style='color:#6b7280'>Quality/INVEST</span>"]
        DEV["Developer<br/><span style='color:#6b7280'>Technical</span>"]
        ORC[Supervisor/Orchestrator]
    end

    subgraph Task_Agents["Task-based: Story Detailing"]
        TP[Template Parser]
        KR[Knowledge Retrieval]
        SW[Story Writer]
        VL[Validation]
    end

    ORC --> TP
    ORC --> KR
    ORC --> SW
    ORC --> VL

    TP --> ORC
    KR --> ORC
    SW --> ORC
    VL --> ORC

    QA --> ORC
    DEV --> ORC
    PO --> ORC
```

## Unified diagram (single view)
This single diagram shows the agentic workflow, story generation flow, and how domain-based and task-based agents map together.
All agent interactions are mediated by the Orchestrator via shared state; agents do not call each other directly. The orchestrator chooses the next step based on state, so the sequence is conditional. The numbered arrows below show a typical happy-path sequence.

```mermaid
flowchart LR
    subgraph INPUT["Input"]
        direction TB
        U[User Request] --> IN[Ingress] --> CA[Context Assembly]
    end

    ORC["Orchestrator Hub<br/>Routes steps based on state"]
    CA --> ORC

    subgraph TASK["Task-based: Story Detailing"]
        direction TB
        subgraph TASK_ROW1[" "]
            direction LR
            EA["Epic Analysis<br/>Summarizes epic intent"] --> SS["Splitting Strategy<br/>Recommends story splits"] --> SG["Story Generation<br/>Generates story candidates"]
        end
        subgraph TASK_ROW2[" "]
            direction LR
            KR["Knowledge Retrieval<br/>Pulls relevant context"] --> SW["Story Writer<br/>Populates story from template"] --> VL["Validation<br/>Checks gaps and coverage"]
        end
        subgraph TASK_ROW3[" "]
            direction LR
            TP["Template Parser<br/>Parses story template"]
        end
    end

    subgraph DOMAIN["Domain-based: User-facing"]
        direction LR
        PO["Product Owner<br/>Refines value and clarity"]
        QA["QA<br/>Flags INVEST violations"]
        DEV["Developer<br/>Assesses feasibility"]
    end

    ART["Draft/Story Artifact<br/>Shared working output"]

    ORC --> EA --> ORC
    ORC --> SS --> ORC
    ORC --> SG --> ORC
    ORC --> KR --> ORC
    ORC --> SW --> ORC
    ORC --> VL --> ORC
    ORC --> TP --> ORC

    SW --> ART
    VL --> ART
    ART --> PO
    ART --> QA
    ART --> DEV

    ORC --> PO --> ORC
    ORC --> QA --> ORC
    ORC --> DEV --> ORC

    subgraph OUTPUT["Output"]
        direction TB
        EXE[Execution / Output] --> END[End]
    end
    ORC --> EXE

    classDef orchestrator fill:#dbeafe,stroke:#2563eb,stroke-width:1px,color:#0f172a;
    classDef task fill:#dcfce7,stroke:#16a34a,stroke-width:1px,color:#14532d;
    classDef domain fill:#f3e8ff,stroke:#7c3aed,stroke-width:1px,color:#3b0764;
    classDef infra fill:#f3f4f6,stroke:#6b7280,stroke-width:1px,color:#111827;
    classDef artifact fill:#fef9c3,stroke:#ca8a04,stroke-width:1px,color:#713f12;

    class ORC orchestrator;
    class EA,SS,SG,TP,KR,SW,VL task;
    class PO,QA,DEV domain;
    class U,IN,CA,EXE,END infra;
    class ART artifact;
```

Yes, an n8n-style diagram can help for presentations. If you want it, I can generate a visual flowchart (PNG/SVG) using this unified layout.

## Core components and responsibilities
- **Supervisor + LangGraph routing**: Dynamic decision-making across steps.
- **Multi-agent debate pattern**: QA + Dev critique, PO synthesizes.
- **Stateful memory**: Debate history and confidence tracking per iteration.
- **Retrieval**: LanceDB-backed retrieval provides evidence and context.
- **Adapters**: Clean integration points for LLMs, issue trackers, and knowledge stores.

## Hybrid RAG + Context Graph (GraphRAG-lite)
This is the recommended MVP approach: keep vector retrieval as the primary signal and
build a lightweight Context Graph per workflow run for provenance and multi-hop links.

### How to start implementation
1) **Define the context graph schema** in the domain layer (nodes, edges, snapshot).
2) **Add a graph store port** (Protocol) and in-memory adapter for MVP.
3) **Extend retrieval** to emit graph nodes/edges alongside retrieved chunks.
4) **Attach a snapshot** to the story artifact so UI can render citations/evidence.

### Where to start in this repo
- **Domain models**: `src/domain/schema.py` (add ContextGraphNode/Edge/Snapshot).
- **Ports**: `src/domain/interfaces.py` (graph store + graph builder protocols).
- **Retrieval**: `src/ingestion/vector_db.py` (return chunk metadata + IDs).
- **Workflow state**: `src/cognitive_engine/story_state.py` (store graph snapshot).
- **Story output**: `src/cognitive_engine/story_nodes.py` (attach citations).
- **Memory store**: `src/infrastructure/memory/in_memory_store.py` (MVP graph cache).

### Jira + Confluence integration difficulty
Moderate. The API surfaces are well-documented, but the complexity is in:
- OAuth/Token handling, scopes, and tenant configuration (especially Atlassian Cloud).
- Rate limits and pagination for large spaces/projects.
- Content parsing for Confluence (rich text + attachments).
You can model both as ingestion adapters using the same patterns as existing ingress/egress
adapters, but plan for 1–2 sprints if you need robust coverage and governance.

## Why this qualifies as Agentic AI (vs RAG)
- **Planning and routing**: Supervisor selects the next action based on state.
- **Multiple agents**: Distinct roles with separate critiques.
- **Feedback loops**: Iterative refinement with convergence criteria.
- **Memory + retrieval**: Persistent context across iterations.

## Key files for reference
- Orchestration graph: `src/cognitive_engine/graph.py`
- Supervisor routing: `src/cognitive_engine/agents/supervisor.py`
- Critique loop: `src/cognitive_engine/story_nodes.py`
- State + memory: `src/cognitive_engine/story_state.py`, `src/infrastructure/memory/`
- Retrieval: `src/ingestion/vector_db.py`

---
Note: The attached image is referenced via a local absolute path. If you plan to share or commit this document, move the image into the repo (e.g., `docs/assets/`) and update the link.
