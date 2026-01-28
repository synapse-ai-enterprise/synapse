# Product Story Writing AI - Agents Architecture

## System Overview

A multi-agent system for intelligent product story writing that transforms epics into delivery-ready user stories by leveraging organizational knowledge from Docs, Emails, Codebase, Jira, and Confluence.

**Core Capabilities:**
- Module 1: Epic-to-Story Breakdown with industry-standard techniques
- Module 2: Story Detailing with context-aware knowledge retrieval

---

## Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Agent                        │
│          (Coordinates workflow, manages context)             │
└──────────────┬──────────────────────────────┬────────────────┘
               │                              │
    ┌──────────▼──────────┐      ┌───────────▼────────────┐
    │  Module 1 Agents    │      │   Module 2 Agents      │
    └─────────────────────┘      └────────────────────────┘
```

---

## Agent Definitions

### 1. Orchestrator Agent

**Role:** Central coordinator and conversation manager

**Responsibilities:**
- Route user requests to appropriate specialized agents
- Maintain conversation state and context
- Aggregate results from multiple agents
- Handle user interactions and clarifications
- Manage handoffs between Module 1 and Module 2

**Capabilities:**
- Natural language understanding
- Context window management
- Agent coordination
- User preference tracking

**Memory Access:**
- Working memory (conversation history)
- Canonical product knowledge
- User preferences

---

## Module 1: Epic Breakdown Agents

### 2. Epic Analysis Agent

**Role:** Understand and analyze epic content

**Responsibilities:**
- Parse epic descriptions (free text or Jira-sourced)
- Extract key entities: users, capabilities, benefits, constraints
- Identify complexity indicators
- Classify epic type (feature, technical, architectural)
- Flag ambiguities and missing information

**Capabilities:**
- Entity extraction
- Intent classification
- Complexity assessment
- Domain understanding

**Memory Access:**
- Vector DB: Similar past epics
- Graph DB: Related features, products, decisions
- Canonical knowledge: Product vision, domain model

**Outputs:**
```json
{
  "epic_id": "EPIC-123",
  "entities": {
    "user_persona": "customer",
    "capability": "manage recurring subscriptions",
    "benefit": "automate renewals"
  },
  "complexity_score": 0.75,
  "ambiguities": ["What payment methods?", "Support existing subscriptions?"],
  "domain": "billing"
}
```

---

### 3. Splitting Strategy Agent

**Role:** Recommend breakdown techniques

**Responsibilities:**
- Analyze epic characteristics against splitting patterns
- Apply SPIDR framework (Spike, Path, Interface, Data, Rules)
- Apply Humanizing Work patterns (Simple/Complex, Defer Performance, Break Out Spike)
- Rank techniques by relevance
- Explain why each technique is suitable

**Knowledge Base:**

**SPIDR Techniques:**
| Technique | When to Use | Example |
|-----------|------------|---------|
| Spike | High uncertainty, needs investigation | "Investigate subscription pricing models" |
| Path | Multiple user flows | "Credit card path vs PayPal path" |
| Interface | Multiple channels/surfaces | "Web interface vs Mobile app" |
| Data | Complex data scope | "Basic subscriptions vs tiered plans" |
| Rules | Complex business rules | "Simple renewal rules first" |

**Humanizing Work Patterns:**
- Simple/Complex: Extract simplest vertical slice
- Defer Performance: Split functional vs optimized
- Break Out Spike: Time-box uncertainty
- Workflow Steps: One story per step
- Operations: CRUD variations
- Breaking Conjunctions: Split "and" statements

**Capabilities:**
- Pattern matching
- Technique ranking
- Explanation generation
- Interactive recommendation

**Memory Access:**
- Vector DB: Past successful breakdowns
- Graph DB: Feature dependencies, constraints
- Historical: What splitting techniques worked for similar epics

**Outputs:**
```json
{
  "recommendations": [
    {
      "technique": "Path",
      "confidence": 0.9,
      "rationale": "Epic involves multiple payment methods",
      "example_splits": ["Credit card renewal", "PayPal renewal"]
    },
    {
      "technique": "Data",
      "confidence": 0.85,
      "rationale": "Subscription types vary in complexity",
      "example_splits": ["Basic monthly", "Advanced tiered"]
    }
  ]
}
```

---

### 4. Story Generation Agent

**Role:** Create user stories from selected techniques

**Responsibilities:**
- Apply chosen splitting techniques
- Generate story titles in standard format
- Create initial descriptions
- Suggest story points / sizing
- Maintain traceability to parent epic

**Prompt Templates:**

**SPIDR Path Split:**
```
Given epic: {epic_text}
Apply Path technique to split by alternate user flows.

For each distinct user path:
1. Identify the flow variation
2. Create story: "As a {user}, I can {action} via {path_variant}"
3. Ensure each story delivers value independently

Output format:
- Story title
- Brief description
- Path being addressed
```

**Humanizing Work Simple/Complex:**
```
Given epic: {epic_text}
Extract the simplest vertical slice that delivers core value.

1. Identify minimal functionality that cuts through all layers
2. Create simple core story
3. Identify complexity variations as separate stories
4. Ensure each story is testable

Output format:
- Core story (simplest)
- Variation stories (complexities)
- Value delivered by each
```

**Capabilities:**
- Template-based generation
- Value validation
- Story format standardization
- Acceptance criteria scaffolding

**Memory Access:**
- Vector DB: Story writing style examples
- Graph DB: Feature decomposition patterns
- Canonical: Story format standards

**Outputs:**
```json
{
  "stories": [
    {
      "story_id": "STORY-456",
      "title": "As a customer, I can renew subscriptions via credit card",
      "description": "Enable subscription renewal using credit card payment",
      "technique_applied": "Path",
      "parent_epic": "EPIC-123",
      "story_points": 5,
      "initial_acceptance_criteria": [
        "Customer can select credit card payment",
        "Renewal processes successfully",
        "Confirmation email sent"
      ]
    }
  ]
}
```

---

## Module 2: Story Detailing Agents

### 5. Template Parser Agent

**Role:** Understand and validate story templates

**Responsibilities:**
- Parse uploaded story templates
- Extract required vs optional fields
- Detect formatting expectations (Gherkin, free-form, etc.)
- Validate template structure
- Create filling strategy

**Supported Template Formats:**
- Standard user story format
- Gherkin (Given/When/Then)
- Custom organizational templates
- Multiple section types

**Capabilities:**
- Template structure detection
- Field requirement extraction
- Format validation
- Schema generation

**Memory Access:**
- Canonical: Approved template standards

**Outputs:**
```json
{
  "template_schema": {
    "required_fields": ["title", "description", "acceptance_criteria"],
    "optional_fields": ["dependencies", "nfrs", "out_of_scope"],
    "format_style": "gherkin",
    "sections": [
      {
        "name": "acceptance_criteria",
        "format": "given_when_then",
        "min_items": 3
      }
    ]
  }
}
```

---

### 6. Knowledge Retrieval Agent

**Role:** Gather relevant context from all sources

**Responsibilities:**
- Extract story intent and domain keywords
- Query Graph DB for related decisions, constraints, features
- Query Vector DB for relevant documents, emails, discussions
- Access codebase via Git MCP for technical context
- Prioritize and rank retrieved information
- Filter noise and irrelevant content

**Retrieval Strategy:**

**Phase 1 - Intent Extraction:**
```
Story: "As a customer, I can renew subscriptions via PayPal"

Extracted:
- Feature: subscription_renewal
- Integration: paypal
- Domain: billing, payments
- User_type: customer
```

**Phase 2 - Graph Traversal:**
```cypher
// Find related decisions
MATCH (story:Feature {name: "subscription_renewal"})-[:SOLVES]->(problem:UserProblem)
MATCH (decision:Decision)-[:IMPACTS]->(story)
MATCH (constraint:Constraint)-[:LIMITS]->(story)
RETURN decision, constraint, problem

// Find dependencies
MATCH (story)-[:DEPENDS_ON]->(dependency)
RETURN dependency
```

**Phase 3 - Vector Retrieval:**
```
Query: "PayPal integration billing subscription"
Filters:
- project: current_project
- recency: last_6_months
- source: [prd, confluence, email, jira]
- min_relevance: 0.7
```

**Phase 4 - Code Context (Git MCP):**
```
Search:
- Files containing "paypal", "subscription", "billing"
- Recent commits related to payment integrations
- Feature flags affecting billing
- API endpoints and configurations
```

**Capabilities:**
- Multi-source retrieval
- Relevance ranking
- Deduplication
- Source attribution

**Memory Access:**
- Vector DB: All episodic memory
- Graph DB: All semantic/relational memory
- MCP connections: Live data sources

**Outputs:**
```json
{
  "context": {
    "decisions": [
      {
        "id": "DEC-89",
        "text": "Use PayPal API v2 for all new integrations",
        "source": "confluence://payments-arch-decision",
        "confidence": 0.95
      }
    ],
    "constraints": [
      {
        "id": "CONS-12",
        "text": "All payment flows must support 3D Secure",
        "source": "email://security-requirements-2024"
      }
    ],
    "relevant_docs": [
      {
        "title": "Payment Integration Guide",
        "excerpt": "PayPal integration requires...",
        "source": "confluence://dev-docs/payments",
        "relevance": 0.89
      }
    ],
    "code_context": [
      {
        "file": "src/billing/payment_processor.py",
        "snippet": "class PayPalProcessor...",
        "note": "Existing PayPal infrastructure available"
      }
    ]
  }
}
```

---

### 7. Story Writer Agent

**Role:** Populate story template with retrieved knowledge

**Responsibilities:**
- Fill each template section using retrieved context
- Write clear, actionable descriptions
- Generate comprehensive acceptance criteria
- Document dependencies and constraints
- Add non-functional requirements where applicable
- Define explicit scope boundaries
- Flag gaps and assumptions

**Section-Specific Logic:**

**Description:**
```
Inputs: 
- Story title
- Retrieved decisions (why this exists)
- Product goals from canonical memory
- Similar past stories

Output:
Clear explanation connecting user need → solution → business value
Anchored to actual organizational context, not generic
```

**Acceptance Criteria:**
```
Inputs:
- Retrieved Jira tickets with existing ACs
- Email clarifications
- Code constraints
- Template format (Gherkin vs free-form)

Output:
Testable, specific criteria
Edge cases from historical issues
Technical constraints from codebase
```

**Dependencies:**
```
Inputs:
- Graph traversal results (depends_on relationships)
- Code analysis (external services, feature flags)
- Jira links

Output:
Other stories, teams, services, infrastructure
```

**Non-Functional Requirements:**
```
Inputs:
- Architecture docs
- Performance requirements from similar features
- Security/compliance constraints

Output:
Performance targets, security requirements, compliance needs
```

**Capabilities:**
- Context synthesis
- Technical writing
- Assumption detection
- Gap identification

**Memory Access:**
- All retrieved context from Knowledge Retrieval Agent
- Canonical: Writing style, product principles

**Outputs:**
```json
{
  "populated_story": {
    "title": "As a customer, I can renew subscriptions via PayPal",
    "description": "This story enables customers to renew active subscriptions using PayPal, improving payment flexibility and reducing churn for users without credit cards. This aligns with the Q2 payments expansion initiative documented in PRD-2024-Q2.",
    "acceptance_criteria": [
      {
        "type": "gherkin",
        "scenario": "Successful PayPal renewal",
        "given": "An active subscription nearing renewal date",
        "when": "Customer selects PayPal as payment method",
        "then": "Renewal processes via PayPal API v2 and confirmation email sent"
      }
    ],
    "dependencies": [
      "STORY-442: PayPal API v2 integration",
      "Service: billing-service-v2 deployed"
    ],
    "nfrs": [
      "Renewal confirmation within 3 seconds (per architecture standards)",
      "All transactions logged to audit system",
      "Support 3D Secure authentication"
    ],
    "out_of_scope": [
      "Refund processing (deferred to STORY-460)",
      "Subscription plan upgrades",
      "Historical payment method migration"
    ],
    "assumptions": [
      "PayPal sandbox environment available for testing",
      "Existing billing service v2 supports PayPal processor"
    ],
    "open_questions": [
      "Should we support PayPal Credit in this story?",
      "What's the fallback if PayPal API is down?"
    ]
  }
}
```

---

### 8. Validation & Gap Detection Agent

**Role:** Ensure story quality and completeness

**Responsibilities:**
- Validate story against INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable)
- Check for missing information
- Identify ungrounded assumptions
- Flag potential conflicts with existing features
- Ensure technical feasibility
- Verify acceptance criteria are testable

**Validation Checks:**

**INVEST Criteria:**
```
✓ Independent: Can be delivered without other incomplete stories?
✓ Negotiable: Room for discussion on implementation?
✓ Valuable: Clear user/business value?
✓ Estimable: Enough information to size?
✓ Small: Deliverable in a sprint?
✓ Testable: Clear acceptance criteria?
```

**Completeness:**
- All template required fields populated
- Acceptance criteria specific and measurable
- Dependencies identified and valid
- No invented information (all claims sourced)

**Technical Feasibility:**
- No conflicts with code constraints
- Dependencies actually exist
- APIs/services available

**Capabilities:**
- Quality assessment
- Conflict detection
- Feasibility checking
- Gap analysis

**Memory Access:**
- Graph DB: Feature conflicts, dependencies
- Code context: Technical constraints

**Outputs:**
```json
{
  "validation_results": {
    "invest_score": {
      "independent": true,
      "negotiable": true,
      "valuable": true,
      "estimable": true,
      "small": false,
      "testable": true,
      "overall": "warning"
    },
    "issues": [
      {
        "severity": "warning",
        "type": "size",
        "message": "Story may be too large (estimated 13 points). Consider splitting.",
        "suggestion": "Split into basic PayPal flow + error handling stories"
      }
    ],
    "gaps": [
      {
        "field": "acceptance_criteria",
        "gap": "No error handling scenarios specified",
        "suggestion": "Add AC for PayPal API timeout, declined payment"
      }
    ],
    "ungrounded_claims": [],
    "technical_risks": [
      {
        "risk": "PayPal API v2 not yet deployed to production",
        "mitigation": "Add dependency on infrastructure story INFRA-88"
      }
    ]
  }
}
```

---

## Agent Interaction Flows

### Flow 1: Epic → Stories (Module 1)

```
User: "Break down this epic: [epic description]"
     ↓
Orchestrator → Epic Analysis Agent
     ↓
Epic Analysis Agent: Analyzes epic, extracts entities
     ↓
Orchestrator → Splitting Strategy Agent
     ↓
Splitting Strategy Agent: Recommends techniques
     ↓
Orchestrator: "Here are recommended splitting options: Path, Data, Interface"
     ↓
User: "Use Path + Data"
     ↓
Orchestrator → Story Generation Agent (with selected techniques)
     ↓
Story Generation Agent: Creates candidate stories
     ↓
Orchestrator: Presents stories to user
     ↓
User: "Detail story 1"
     ↓
[Transition to Module 2 Flow]
```

### Flow 2: Story → Detailed Story (Module 2)

```
User: "Detail this story" + [uploads template]
     ↓
Orchestrator → Template Parser Agent
     ↓
Template Parser Agent: Parses template structure
     ↓
Orchestrator → Knowledge Retrieval Agent
     ↓
Knowledge Retrieval Agent: Gathers context (Graph + Vector + Code + MCPs)
     ↓
Orchestrator → Story Writer Agent
     ↓
Story Writer Agent: Populates template with retrieved knowledge
     ↓
Orchestrator → Validation Agent
     ↓
Validation Agent: Checks quality, identifies gaps
     ↓
Orchestrator: Presents detailed story + validation results
     ↓
User: "Make ACs more detailed"
     ↓
Orchestrator → Story Writer Agent (re-runs AC section only)
     ↓
Story Writer Agent: Enhances acceptance criteria
     ↓
Orchestrator: Presents updated story
     ↓
User: "Approve"
     ↓
Orchestrator: Writes to memory (Vector + Graph), exports to Jira
```

---

## Memory Integration

### How Agents Use Memory

**Vector DB (Episodic Memory):**
- Epic Analysis Agent: Find similar epics
- Splitting Strategy Agent: Recall successful patterns
- Story Writer Agent: Match writing style
- Knowledge Retrieval Agent: Semantic search

**Graph DB (Semantic Memory):**
- Epic Analysis Agent: Understand feature relationships
- Knowledge Retrieval Agent: Traverse decisions, constraints
- Validation Agent: Check dependencies, conflicts
- Story Writer Agent: Access decision rationale

**Canonical Knowledge:**
- All agents: Product vision, principles, standards
- Template Parser Agent: Approved templates
- Story Writer Agent: Brand voice, non-negotiables

### Memory Writes

**After Epic Breakdown (Module 1):**
```
Vector DB:
- Store epic text + embedding
- Store generated stories + embeddings

Graph DB:
- Create Epic node
- Create Story nodes
- Link: Epic → BREAKS_INTO → Story
- Link stories if dependencies exist
```

**After Story Detailing (Module 2):**
```
Vector DB:
- Store final story + embedding
- Store all retrieved context snippets

Graph DB:
- Update Story node with full details
- Add Decision nodes (if new decisions made)
- Add Constraint nodes (if new constraints found)
- Create relationships: Story → DEPENDS_ON, IMPLEMENTS, CONSTRAINED_BY
```

---

## Agent Communication Protocol

### Inter-Agent Messages

```json
{
  "from_agent": "orchestrator",
  "to_agent": "epic_analysis",
  "message_type": "request",
  "payload": {
    "epic_text": "As a customer...",
    "context": {
      "project": "billing-system",
      "requester": "user_123"
    }
  },
  "callback": "orchestrator_receive"
}
```

### Agent Response Format

```json
{
  "from_agent": "epic_analysis",
  "to_agent": "orchestrator",
  "message_type": "response",
  "status": "success",
  "payload": {
    "analysis": {...},
    "confidence": 0.89
  },
  "metadata": {
    "processing_time_ms": 1234,
    "sources_accessed": ["vector_db", "graph_db"]
  }
}
```

---

## Configuration & Customization

### Agent Behavior Configuration

Each agent can be tuned via configuration:

```yaml
epic_analysis_agent:
  complexity_threshold: 0.7
  min_confidence: 0.6
  flag_ambiguity_threshold: 0.8

splitting_strategy_agent:
  max_recommendations: 5
  technique_preference_order: ["path", "data", "spike", "interface", "rules"]
  explain_all_techniques: true

story_writer_agent:
  default_ac_format: "gherkin"
  include_nfrs_by_default: true
  max_assumptions: 3
  min_ac_count: 3

knowledge_retrieval_agent:
  vector_search_limit: 10
  graph_traversal_depth: 3
  recency_weight: 0.3
  relevance_threshold: 0.7
```

### User Preferences (Learned Over Time)

```json
{
  "user_id": "pm_alice",
  "preferences": {
    "story_detail_level": "high",
    "preferred_splitting_techniques": ["path", "data"],
    "ac_format": "gherkin",
    "include_technical_details": true,
    "story_point_estimation": "enabled"
  },
  "patterns": {
    "typical_story_complexity": "medium",
    "frequently_deferred_items": ["performance_optimization", "edge_cases"],
    "common_feedback": "wants more security considerations"
  }
}
```

---

## Implementation Recommendations

### Tech Stack (Per Agent)

**Orchestrator:**
- LangGraph for workflow orchestration
- State management: Redis or in-memory

**Analysis Agents:**
- LLM: GPT-4.1 or Claude Sonnet 4.5
- Structured output parsing

**Knowledge Retrieval:**
- Vector DB: Weaviate / Pinecone
- Graph DB: Neo4j
- MCP clients: Jira, Confluence, Git, Email

**Writer Agents:**
- LLM: GPT-4.1 or Claude Opus 4.5
- Template engine: Jinja2 for prompts

### Deployment Pattern

```
┌─────────────────────────────────────────┐
│         API Gateway / UI Layer          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│       Orchestrator Agent Service        │
└──┬────┬────┬────┬────┬────┬────┬───────┘
   │    │    │    │    │    │    │
   │    │    │    │    │    │    │
┌──▼┐ ┌─▼┐ ┌─▼┐ ┌─▼┐ ┌─▼┐ ┌─▼┐ ┌▼──┐
│EA│ │SS│ │SG│ │TP│ │KR│ │SW│ │VG │
└──┘ └──┘ └──┘ └──┘ └──┘ └──┘ └───┘
     (All specialized agents as microservices or functions)
```

**EA** = Epic Analysis
**SS** = Splitting Strategy  
**SG** = Story Generation
**TP** = Template Parser
**KR** = Knowledge Retrieval
**SW** = Story Writer
**VG** = Validation & Gap Detection

---

## Success Metrics

### Agent Performance

**Epic Analysis Agent:**
- Entity extraction accuracy > 90%
- Ambiguity detection precision > 85%

**Splitting Strategy Agent:**
- Recommendation acceptance rate > 70%
- Time to decision < 2 minutes

**Knowledge Retrieval Agent:**
- Retrieval relevance score > 0.8
- Source coverage (all MCPs queried) = 100%

**Story Writer Agent:**
- Template compliance = 100%
- Ungrounded claim rate < 5%
- User edit rate < 30%

**Validation Agent:**
- INVEST violation detection accuracy > 90%
- False positive rate < 10%

### System Performance

- Epic → Stories: < 30 seconds
- Story → Detailed Story: < 60 seconds
- User satisfaction score: > 4.0/5.0
- Stories requiring major revision: < 20%

---

## Future Enhancements

### Advanced Agent Capabilities

**Learning Agents:**
- Continuously improve from user feedback
- Adapt splitting strategies based on success metrics
- Personalize to team/project patterns

**Collaborative Agents:**
- Multi-stakeholder story review agent
- Conflict resolution agent for competing requirements
- Estimation calibration agent

**Quality Agents:**
- Technical debt analyzer
- Story dependency optimizer
- Release planning assistant

### Extended Knowledge

- Product analytics integration
- Customer feedback incorporation
- Competitive analysis integration
- Regulatory compliance checking

---

## Conclusion

This agent architecture provides:

✅ **Modular design** - Each agent has clear responsibilities  
✅ **Scalable** - Agents can be deployed independently  
✅ **Extensible** - New agents can be added without disrupting existing flow  
✅ **Intelligent** - Leverages both vector and graph memory appropriately  
✅ **User-centric** - Supports interactive refinement and learning  
✅ **Production-ready** - Includes validation, error handling, and quality checks

The system transforms product backlog management from manual writing to intelligent reconstruction from organizational knowledge.