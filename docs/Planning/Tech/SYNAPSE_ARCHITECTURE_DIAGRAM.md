# Synapse Architecture Diagram

## Mermaid Diagram (Renderable)

Copy this into any Mermaid renderer (GitHub, Notion, mermaid.live, etc.):

```mermaid
flowchart TB
    subgraph FRONTEND["🖥️ Frontend (React + Vite)"]
        direction LR
        subgraph MICROFRONTENDS["Microfrontends"]
            direction TB
            HOME["🏠 HomeApp"]
            STORY["📝 StoryApp"]
            EPIC["📋 EpicApp"]
            INIT["🚀 InitiativeApp"]
            ADMIN["⚙️ AdminApp"]
            HIST["📜 HistoryApp"]
        end
        subgraph SHARED["Shared"]
            direction TB
            API_CLIENT["API Client<br/>(SSE Stream)"]
            FLOWS["Flows"]
            DATA["Data"]
        end
    end

    subgraph INTEGRATIONS["🔌 Integration Sources"]
        direction LR
        JIRA["🎫 Jira<br/>Integration"]
        CONF["📄 Confluence<br/>Integration"]
        GH["💻 GitHub<br/>Integration"]
        NOT["📝 Notion<br/>Integration"]
    end

    subgraph REGISTRY["Integration Registry"]
        REG["Webhook Handlers + Loaders"]
    end

    subgraph OBSERVABILITY["📊 Observability"]
        direction TB
        PMON["Prompt<br/>Monitoring"]
        TRACE["Trace<br/>Logging"]
        OTEL["OpenTelemetry"]
        ALERTS["Alert<br/>Manager"]
    end

    subgraph PROMPT_MGMT["📋 Prompt Management"]
        direction TB
        PLIB["Prompt<br/>Library"]
        PVER["Version<br/>Control"]
        ABTEST["A/B<br/>Testing"]
        PMET["Performance<br/>Metrics"]
    end

    subgraph AGENT_COMPONENT["🤖 Agent Component"]
        direction TB
        LLM_GW["LLM Gateway<br/>(LiteLLM)"]
        LANG["LangGraph<br/>Orchestrator"]
        CTRL["Agent<br/>Controller"]
        API["FastAPI<br/>Server"]
    end

    subgraph HYBRID_RAG["🔍 Hybrid RAG Component"]
        direction TB
        KR["Knowledge<br/>Retrieval Agent"]
        LANCE[("LanceDB<br/>Vector Store")]
        CGB["Context Graph<br/>Builder"]
        ET["Evidence<br/>Tracker"]
    end

    subgraph MULTI_AGENT["👥 Multi-Agent Debate"]
        direction LR
        PO["Product<br/>Owner"]
        QA["QA<br/>Agent"]
        DEV["Developer<br/>Agent"]
        SUP["Supervisor<br/>Agent"]
    end

    subgraph LLM_PROVIDERS["🧠 LLM Providers"]
        direction LR
        OLLAMA["Ollama"]
        OPENAI["OpenAI"]
        GEMINI["Gemini"]
        CLAUDE["Claude"]
    end

    subgraph DATA_SOURCES["📚 Data Sources"]
        direction TB
        DS_JIRA[("Jira<br/>Issues")]
        DS_CONF[("Confluence<br/>Pages")]
        DS_GH[("GitHub<br/>Repos")]
    end

    %% Frontend to Backend
    HOME --> API_CLIENT
    STORY --> API_CLIENT
    EPIC --> API_CLIENT
    INIT --> API_CLIENT
    ADMIN --> API_CLIENT
    HIST --> API_CLIENT
    API_CLIENT -->|"REST + SSE"| API

    %% Integrations
    JIRA --> REG
    CONF --> REG
    GH --> REG
    NOT --> REG

    REG --> API
    API --> CTRL
    CTRL --> LANG

    %% Prompt Management Flow (NEW)
    LANG --> PLIB
    PLIB --> PVER
    PLIB --> ABTEST
    PLIB --> LLM_GW
    ABTEST --> PMET

    LLM_GW --> OLLAMA
    LLM_GW --> OPENAI
    LLM_GW --> GEMINI
    LLM_GW --> CLAUDE

    CTRL --> KR
    KR --> LANCE
    KR --> CGB
    CGB --> ET

    LANCE --> DS_JIRA
    LANCE --> DS_CONF
    LANCE --> DS_GH

    LANG --> PO
    LANG --> QA
    LANG --> DEV
    SUP --> LANG

    %% Observability connections
    LLM_GW --> PMON
    PMON --> PMET
    PMON --> ALERTS
    API --> PMON
    LANG --> TRACE
    TRACE --> OTEL
    PMON --> OTEL

    %% Styling
    classDef frontend fill:#ec4899,stroke:#db2777,color:#fff
    classDef microfrontend fill:#f472b6,stroke:#ec4899,color:#fff
    classDef shared fill:#fda4af,stroke:#fb7185,color:#000
    classDef integration fill:#f97316,stroke:#ea580c,color:#fff
    classDef registry fill:#eab308,stroke:#ca8a04,color:#000
    classDef agent fill:#3b82f6,stroke:#2563eb,color:#fff
    classDef rag fill:#06b6d4,stroke:#0891b2,color:#fff
    classDef multiagent fill:#8b5cf6,stroke:#7c3aed,color:#fff
    classDef llm fill:#6b7280,stroke:#4b5563,color:#fff
    classDef data fill:#10b981,stroke:#059669,color:#fff
    classDef obs fill:#f3f4f6,stroke:#9ca3af,color:#000
    classDef prompt fill:#fef3c7,stroke:#f59e0b,color:#000

    class HOME,STORY,EPIC,INIT,ADMIN,HIST microfrontend
    class API_CLIENT,FLOWS,DATA shared
    class JIRA,CONF,GH,NOT integration
    class REG registry
    class LLM_GW,LANG,CTRL,API agent
    class KR,LANCE,CGB,ET rag
    class PO,QA,DEV,SUP multiagent
    class OLLAMA,OPENAI,GEMINI,CLAUDE llm
    class DS_JIRA,DS_CONF,DS_GH data
    class PMON,TRACE,OTEL,ALERTS obs
    class PLIB,PVER,ABTEST,PMET prompt
```

---

## Component Breakdown

### Layer 0: Frontend (Pink)
| Component | Purpose |
|-----------|---------|
| HomeApp | Landing page, navigation |
| StoryApp | Story detailing workflow UI |
| EpicApp | Epic splitting workflow UI |
| InitiativeApp | Initiative breakdown workflow UI |
| AdminApp | Integration settings, templates |
| HistoryApp | View past workflow runs |
| API Client | REST + SSE streaming to backend |

### Layer 1: Integration Sources (Orange)
| Component | Purpose |
|-----------|---------|
| Jira Integration | Load issues, sync stories |
| Confluence Integration | Load documentation pages |
| GitHub Integration | Load code, PRs, issues |
| Notion Integration | Load knowledge pages |

### Layer 2: Agent Component (Blue)
| Component | Purpose |
|-----------|---------|
| FastAPI Server | REST API endpoints |
| Agent Controller | Request routing |
| LangGraph Orchestrator | Workflow state machine |
| LLM Gateway (LiteLLM) | Multi-provider LLM access |

### Layer 3: Prompt Management (Amber) - NEW
| Component | Purpose |
|-----------|---------|
| Prompt Library | Centralized prompt template storage |
| Version Control | Prompt versioning and rollback |
| A/B Testing | Prompt variant testing |
| Performance Metrics | Track prompt effectiveness |

### Layer 4: Hybrid RAG Component (Cyan)
| Component | Purpose |
|-----------|---------|
| Knowledge Retrieval Agent | Intent extraction + search |
| LanceDB Vector Store | Embeddings + metadata |
| Context Graph Builder | Build evidence graph |
| Evidence Tracker | Track citations |

### Layer 5: Multi-Agent Debate (Purple)
| Component | Purpose |
|-----------|---------|
| Product Owner Agent | Business value, clarity |
| QA Agent | INVEST validation |
| Developer Agent | Technical feasibility |
| Supervisor Agent | Routing decisions |

### Layer 6: Observability (Gray)
| Component | Purpose |
|-----------|---------|
| Prompt Monitoring | Track LLM calls, tokens, cost |
| Alert Manager | Threshold-based alerting |
| Trace Logging | Structured logs |
| OpenTelemetry | Distributed tracing export |

---

## Draw.io / Excalidraw Template

To create a visual diagram like the reference image:

### Color Palette
```
Frontend:            #ec4899 (Pink)
Microfrontends:      #f472b6 (Light Pink)
Shared:              #fda4af (Rose)
Integration Sources: #f97316 (Orange)
Registry:            #eab308 (Yellow)
Agent Component:     #3b82f6 (Blue)
Prompt Management:   #fef3c7 (Amber) - NEW
Hybrid RAG:          #06b6d4 (Cyan)
Multi-Agent:         #8b5cf6 (Purple)
LLM Providers:       #6b7280 (Gray)
Data Sources:        #10b981 (Green)
Observability:       #f3f4f6 (Light Gray)
```

### Box Layout (Top to Bottom, Left to Right)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SYNAPSE: AGENTIC STORY WRITER                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ FRONTEND - React + Vite (Pink)                                       │   │
│  │  ┌─────────────────────────────────────────┐ ┌───────────────────┐  │   │
│  │  │ Microfrontends                          │ │ Shared            │  │   │
│  │  │  ┌───────┐┌───────┐┌───────┐┌────────┐ │ │ ┌───────────────┐ │  │   │
│  │  │  │ Home  ││ Story ││ Epic  ││Initiat.│ │ │ │ API Client    │ │  │   │
│  │  │  │ App   ││ App   ││ App   ││  App   │ │ │ │ (SSE Stream)  │ │  │   │
│  │  │  └───────┘└───────┘└───────┘└────────┘ │ │ ├───────────────┤ │  │   │
│  │  │  ┌─────────┐ ┌─────────┐               │ │ │ Flows + Data  │ │  │   │
│  │  │  │ Admin   │ │ History │               │ │ └───────┬───────┘ │  │   │
│  │  │  │ App     │ │ App     │               │ │         │         │  │   │
│  │  │  └─────────┘ └─────────┘               │ └─────────┼─────────┘  │   │
│  │  └────────────────────────────────────────┘           │            │   │
│  └───────────────────────────────────────────────────────┼────────────┘   │
│                                                          │                 │
│                                             REST + SSE   │                 │
│                                                          ▼                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ INTEGRATION SOURCES (Orange)                                         │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                    │   │
│  │  │  Jira   │ │Confluenc│ │ GitHub  │ │ Notion  │                    │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘                    │   │
│  └───────┼──────────┼──────────┼──────────┼────────────────────────────┘   │
│          └──────────┴─────┬────┴──────────┘                                 │
│                           ▼                                                 │
│  ┌─────────────────────────────────────────┐   ┌───────────────────────┐   │
│  │ INTEGRATION REGISTRY (Yellow)           │   │ OBSERVABILITY (Gray)  │   │
│  │  Webhook Handlers + Loaders             │   │  ┌─────────────────┐  │   │
│  └─────────────────────┬───────────────────┘   │  │ Prompt Monitor  │  │   │
│                        ▼                        │  ├─────────────────┤  │   │
│  ┌─────────────────────────────────────────┐   │  │ Alert Manager   │  │   │
│  │ AGENT COMPONENT (Blue)                  │   │  ├─────────────────┤  │   │
│  │  ┌───────────┐  ┌───────────────────┐   │   │  │ Trace Logging   │  │   │
│  │  │LLM Gateway│  │Agent Controller   │   │   │  ├─────────────────┤  │   │
│  │  │ (LiteLLM) │  └─────────┬─────────┘   │   │  │ OpenTelemetry   │  │   │
│  │  └─────┬─────┘            │             │   │  └─────────────────┘  │   │
│  │        │      ┌───────────▼─────────┐   │   └───────────────────────┘   │
│  │        │      │LangGraph Orchestrator│   │                               │
│  │        │      └───────────┬─────────┘   │   ┌───────────────────────┐   │
│  │        │                  │             │   │ PROMPT MGMT (Amber)   │   │
│  │  ┌─────▼─────┐  ┌─────────▼─────────┐   │   │  ┌─────────────────┐  │   │
│  │  │FastAPI    │◄─┤  Handlers         │   │   │  │ Prompt Library  │  │   │
│  │  │Server     │  │  (Story/Optimize) │   │   │  ├─────────────────┤  │   │
│  │  └───────────┘  └───────────────────┘   │   │  │ Version Control │  │   │
│  └─────────────────────┬───────────────────┘   │  ├─────────────────┤  │   │
│                        │                        │  │ A/B Testing     │  │   │
│     ┌──────────────────┼──────────────────┐    │  ├─────────────────┤  │   │
│     ▼                  ▼                  ▼    │  │ Perf Metrics    │  │   │
│  ┌─────────────────────────────────────────┐   │  └─────────────────┘  │   │
│  │ MULTI-AGENT DEBATE (Purple)             │   └───────────────────────┘   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐   │   ┌───────────────────────┐   │
│  │  │Product  │ │  QA     │ │Developer│   │   │ HYBRID RAG (Cyan)     │   │
│  │  │Owner    │ │ Agent   │ │ Agent   │   │   │  ┌─────────────────┐  │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘   │   │  │Knowledge        │  │   │
│  │       └───────────┼───────────┘        │   │  │Retrieval Agent  │  │   │
│  │                   ▼                    │   │  └────────┬────────┘  │   │
│  │            ┌─────────────┐             │   │           │           │   │
│  │            │ Supervisor  │             │   │  ┌────────▼────────┐  │   │
│  │            │   Agent     │             │   │  │    LanceDB      │  │   │
│  │            └─────────────┘             │   │  │  Vector Store   │  │   │
│  └─────────────────────────────────────────┘   │  └────────┬────────┘  │   │
│                                                │           │           │   │
│  ┌─────────────────────────────────────────┐   │  ┌────────▼────────┐  │   │
│  │ LLM PROVIDERS (Gray)                    │   │  │ Context Graph   │  │   │
│  │  ┌───────┐ ┌───────┐ ┌───────┐ ┌─────┐ │   │  │   Builder       │  │   │
│  │  │Ollama │ │OpenAI │ │Gemini │ │Claude│ │   │  └────────┬────────┘  │   │
│  │  └───────┘ └───────┘ └───────┘ └─────┘ │   │           │           │   │
│  └─────────────────────────────────────────┘   │  ┌────────▼────────┐  │   │
│                                                │  │Evidence Tracker │  │   │
│                                                │  └─────────────────┘  │   │
│                                                └───────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ DATA SOURCES (Green)                                                 │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                    │   │
│  │  │ Jira Issues │ │ Confluence  │ │ GitHub Repos│                    │   │
│  │  │     DB      │ │   Pages     │ │   + Code    │                    │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Render Options

1. **Mermaid Live Editor**: https://mermaid.live - Paste the mermaid code above
2. **GitHub**: Just include the mermaid block in a `.md` file
3. **Notion**: Use `/mermaid` block
4. **Excalidraw**: Create boxes manually with the color palette
5. **draw.io**: Import as template and customize

---

## Export to Image

To export the Mermaid diagram as PNG/SVG:
1. Go to https://mermaid.live
2. Paste the code
3. Click "Download PNG" or "Download SVG"
