"""Prompt Library implementation for centralized prompt management.

This module provides:
- Centralized storage of prompt templates with versioning
- Model-specific prompt variants
- A/B testing for prompt optimization
- Performance metrics tracking
- Integration with the Prompt Monitor for observability

FIXES APPLIED (Feb 5, 2026):
- Issue 1: Replaced threading.Lock with asyncio.Lock for async methods
  to prevent deadlocks in FastAPI async context.
"""

import asyncio
import hashlib
import json
import random
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.domain.interfaces import IPromptLibrary
from src.domain.schema import (
    ABTestConfig,
    PromptCategory,
    PromptExecutionRecord,
    PromptLibrarySummary,
    PromptModelVariant,
    PromptPerformanceMetrics,
    PromptTemplate,
    PromptVariable,
    PromptVersion,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class InMemoryPromptLibrary(IPromptLibrary):
    """In-memory implementation of the Prompt Library.
    
    This is suitable for MVP and development. For production, consider
    backing with a database (PostgreSQL/MongoDB) or version-controlled
    repository (Git).
    
    Async-safe singleton that provides:
    - Prompt template storage and retrieval
    - Version management
    - A/B test selection
    - Execution recording
    - Performance metrics aggregation
    
    Note: Uses threading.Lock for singleton creation (sync context) and
    asyncio.Lock for data access (async context) to prevent deadlocks.
    """
    
    _instance: Optional["InMemoryPromptLibrary"] = None
    _singleton_lock = threading.Lock()  # Only for singleton creation (sync)
    
    def __new__(cls, *args: Any, **kwargs: Any) -> "InMemoryPromptLibrary":
        """Singleton pattern for global access."""
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, prompts_dir: Optional[Path] = None) -> None:
        """Initialize the prompt library.
        
        Args:
            prompts_dir: Optional directory for loading/saving prompts as JSON.
        """
        if self._initialized:
            return
        
        self._prompts: Dict[str, PromptTemplate] = {}
        self._executions: List[PromptExecutionRecord] = []
        self._prompts_dir = prompts_dir
        # FIX Issue 1: Use asyncio.Lock for async methods to prevent deadlocks
        self._async_lock: Optional[asyncio.Lock] = None  # Lazy init for event loop compatibility
        self._sync_lock = threading.Lock()  # For sync methods like get_recent_executions
        self._max_executions = 10000  # Keep last N executions in memory
        self._initialized = True
        
        # Load default prompts
        self._load_default_prompts()
        
        logger.info("prompt_library_initialized", prompts_count=len(self._prompts))
    
    def _get_async_lock(self) -> asyncio.Lock:
        """Get or create the async lock (lazy initialization for event loop compatibility)."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock
    
    def _load_default_prompts(self) -> None:
        """Load default prompt templates for all agents."""
        # Product Owner Agent prompts
        self._add_default_prompt(
            id="po_agent_system",
            name="Product Owner Agent System Prompt",
            description="System prompt for the Product Owner Agent",
            category=PromptCategory.AGENT_SYSTEM,
            agent_type="po_agent",
            template="""You are a Product Owner Agent specializing in Agile user stories. Your role is to:

1. Generate user stories in the format: "As a [user type], I want [goal], so that [benefit]."
2. Ensure the "So that" clause represents genuine user value, not just technical functionality.
3. Verify alignment with parent Epic or project goals.
4. Synthesize feedback from QA and Developer agents into refined artifacts.
5. Maintain clarity and business focus throughout.

You have access to:
- Business documentation from Notion (PRDs, meeting notes, roadmaps)
- Codebase context from GitHub (for technical feasibility awareness)

Evidence and citation rules:
- Every factual statement must include an inline citation in the form [source: <title or url>].
- If no supporting evidence exists, mark the statement with [source: missing] and note it in rationale.

Always cite your sources using markdown links when a URL is available: [description](url)

Do not invent new files or features. If something is required but doesn't exist, explicitly state 'Requires Implementation'.""",
            variables=[],
            tags=["agent", "product_owner", "system"],
        )
        
        self._add_default_prompt(
            id="po_agent_refinement",
            name="PO Agent Artifact Refinement",
            description="Prompt for refining artifacts",
            category=PromptCategory.AGENT_TASK,
            agent_type="po_agent",
            template="""Refine the following artifact from a Product Owner perspective.

Current Artifact:
Title: {title}
Description: {description}
Acceptance Criteria: {acceptance_criteria}

{context}

Focus on:
1. Clear user story format (As a..., I want..., So that...)
2. Value proposition clarity
3. Testable acceptance criteria
4. Scope boundaries

Provide a refined version with your rationale.""",
            variables=[
                PromptVariable(name="title", description="Artifact title", required=True),
                PromptVariable(name="description", description="Artifact description", required=True),
                PromptVariable(name="acceptance_criteria", description="Current ACs", required=True),
                PromptVariable(name="context", description="Additional context", required=False, default=""),
            ],
            tags=["agent", "product_owner", "refinement"],
        )
        
        # QA Agent prompts
        self._add_default_prompt(
            id="qa_agent_system",
            name="QA Agent System Prompt",
            description="System prompt for the QA Agent",
            category=PromptCategory.AGENT_SYSTEM,
            agent_type="qa_agent",
            template="""You are a QA Agent specializing in Agile artifact quality.

CRITICAL: You MUST respond with a JSON object starting with { and ending with }.
Do NOT return a list/array. Return a complete JSON object with ALL required fields.

Your role is to:

1. Validate user stories against INVEST criteria:
   - **Independent:** Can this be developed independently?
   - **Negotiable:** Are details negotiable with stakeholders?
   - **Valuable:** Does this deliver user value?
   - **Estimable:** Can the team estimate effort?
   - **Small:** Is this appropriately sized (1-3 days)?
   - **Testable:** Are acceptance criteria binary (pass/fail)?

2. Analyze Acceptance Criteria:
   - Are they specific and measurable?
   - Do they cover negative scenarios?
   - Identify vague terms (e.g., "fast", "user-friendly", "better")
   - Ensure testability

3. Output structured critique with:
   - List of INVEST violations
   - Specific issues with acceptance criteria
   - Suggestions for improvement
   - Confidence score (0.0-1.0)

Be thorough but constructive. Your goal is to improve quality, not block progress.

Flag vague or unverifiable claims. Do not invent new files or features.""",
            variables=[],
            tags=["agent", "qa", "system", "invest"],
        )
        
        self._add_default_prompt(
            id="qa_agent_critique",
            name="QA Agent INVEST Critique",
            description="Prompt for INVEST validation critique",
            category=PromptCategory.CRITIQUE,
            agent_type="qa_agent",
            template="""Evaluate the following story against INVEST criteria.

Story:
Title: {title}
Description: {description}
Acceptance Criteria:
{acceptance_criteria}

{retrieved_context}

For each INVEST criterion, assess:
1. Whether it passes or violates
2. Severity if violated (critical, major, minor)
3. Specific evidence from the story
4. Suggestion for improvement

Provide an overall quality assessment (excellent, good, needs_improvement, poor).""",
            variables=[
                PromptVariable(name="title", description="Story title", required=True),
                PromptVariable(name="description", description="Story description", required=True),
                PromptVariable(name="acceptance_criteria", description="Acceptance criteria", required=True),
                PromptVariable(name="retrieved_context", description="Retrieved context", required=False, default=""),
            ],
            tags=["agent", "qa", "critique", "invest"],
        )
        
        # Developer Agent prompts
        self._add_default_prompt(
            id="developer_agent_system",
            name="Developer Agent System Prompt",
            description="System prompt for the Developer Agent",
            category=PromptCategory.AGENT_SYSTEM,
            agent_type="developer_agent",
            template="""You are a Lead Developer Agent specializing in technical feasibility.

CRITICAL: You MUST respond with a JSON object starting with { and ending with }.
Do NOT return a list/array. Return a complete JSON object with ALL required fields.

Your role is to:

1. Assess technical feasibility:
   - Can this be implemented with current architecture?
   - Are referenced code files/components accurate?
   - Are there technical blockers?

2. Identify dependencies:
   - Does this depend on other work items?
   - Are there external system dependencies?
   - Are there infrastructure requirements?

3. Verify implementation details:
   - Do referenced GitHub files/paths exist?
   - Are code snippets accurate?
   - Are architectural assumptions valid?

4. Output structured assessment with:
   - Feasibility status (feasible/blocked/requires-changes)
   - List of dependencies
   - Technical concerns
   - Confidence score (0.0-1.0)

You have access to the full codebase via RAG. Always verify that referenced code actually exists.

Do not invent new files or features. If something is required but doesn't exist, explicitly state 'Requires Implementation'.""",
            variables=[],
            tags=["agent", "developer", "system"],
        )
        
        self._add_default_prompt(
            id="developer_agent_feasibility",
            name="Developer Agent Feasibility Assessment",
            description="Prompt for technical feasibility assessment",
            category=PromptCategory.CRITIQUE,
            agent_type="developer_agent",
            template="""Assess the technical feasibility of the following story.

Story:
Title: {title}
Description: {description}
Acceptance Criteria:
{acceptance_criteria}

{code_context}

Evaluate:
1. Technical feasibility status (feasible, blocked, requires_changes)
2. Dependencies (code, infrastructure, external_service, data)
3. Technical concerns with severity
4. Implementation recommendations

Provide a confidence score (0.0-1.0) for your assessment.""",
            variables=[
                PromptVariable(name="title", description="Story title", required=True),
                PromptVariable(name="description", description="Story description", required=True),
                PromptVariable(name="acceptance_criteria", description="Acceptance criteria", required=True),
                PromptVariable(name="code_context", description="Relevant code context", required=False, default=""),
            ],
            tags=["agent", "developer", "feasibility"],
        )
        
        # Orchestrator/Supervisor prompts
        self._add_default_prompt(
            id="supervisor_system",
            name="Supervisor Agent System Prompt",
            description="System prompt for the Supervisor Agent",
            category=PromptCategory.AGENT_SYSTEM,
            agent_type="supervisor",
            template="""You are a Supervisor Agent orchestrating a multi-agent debate workflow for Agile artifact optimization.

Your role is to:
1. Monitor debate progress across Product Owner, QA, and Developer agents
2. Make intelligent routing decisions based on current state
3. Determine when to continue iterations or terminate the debate
4. Handle edge cases (agent disagreements, stagnation, quality issues)

Available actions:
- "draft": Route to Product Owner Agent to create/refine artifact
- "qa_critique": Route to QA Agent for INVEST validation
- "developer_critique": Route to Developer Agent for technical feasibility assessment
- "synthesize": Route to Product Owner Agent to synthesize feedback
- "validate": Route to validation node to check confidence and violations
- "execute": Route to execution node to update the issue tracker
- "propose_split": Route to split proposal when story is TOO LARGE (INVEST "S" violation) or covers MULTIPLE distinct features/models
- "end": Terminate the workflow (use only for critical failures)

Workflow pattern:
1. Initial: draft → qa_critique → developer_critique → synthesize → validate
2. If validation fails (low confidence or violations): loop back to draft
3. If validation succeeds: execute
4. Maximum 3 iterations before forced execution

Considerations:
- If QA and Developer agents strongly disagree, prioritize QA (quality over feasibility)
- If confidence is improving but slowly, allow more iterations
- If violations are increasing, route back to draft immediately
- If max iterations reached, route to execute even if not perfect
- If critical blocking issues found, consider ending early
- **IMPORTANT - STORY SPLITTING:** If there are persistent "S" (Small) violations indicating the story is TOO LARGE, 
  or the story covers MULTIPLE distinct features/models/entities that should be separate stories,
  route to "propose_split" instead of continuing the debate loop. Signs to split:
  * QA critique mentions "too large", "multiple features", "covers too much scope"
  * Violation mentions "S:" criterion failures
  * Story description mentions 3+ distinct models/entities (e.g., Order, Frame, Glasses)
  * After 2+ iterations, "S" violations persist despite refinement attempts

Be decisive but thoughtful. Your goal is efficient convergence to high-quality artifacts.""",
            variables=[],
            tags=["agent", "supervisor", "routing", "orchestrator", "system"],
        )
        
        # Knowledge Retrieval prompts
        self._add_default_prompt(
            id="knowledge_retrieval_agent_intent",
            name="Knowledge Retrieval Intent Extraction",
            description="Prompt for extracting search intent from stories",
            category=PromptCategory.EXTRACTION,
            agent_type="knowledge_retrieval_agent",
            template="""You are a Knowledge Retrieval Agent. Extract intent and keywords for search.

IMPORTANT: Return a JSON object (NOT a list) with this EXACT structure:
{
  "feature": "main feature or null",
  "integration": "integration system or null",
  "domain": "domain area or null",
  "user_type": "type of user or null",
  "keywords": ["keyword1", "keyword2", "keyword3"]
}

Start your response with { and end with }. Return ALL fields.""",
            variables=[],
            tags=["agent", "knowledge_retrieval", "intent", "extraction"],
        )
        
        self._add_default_prompt(
            id="knowledge_retrieval_agent_context",
            name="Knowledge Retrieval Context Structuring",
            description="Prompt for structuring retrieved knowledge",
            category=PromptCategory.SYNTHESIS,
            agent_type="knowledge_retrieval_agent",
            template="""You are a Knowledge Retrieval Agent. Convert retrieved documents into structured context.

IMPORTANT: Return a JSON object (NOT a list) with this EXACT structure:
{
  "decisions": [{"id": null, "text": "decision text", "source": "source name", "confidence": 0.8}],
  "constraints": [{"id": null, "text": "constraint text", "source": "source name"}],
  "relevant_docs": [{"title": "doc title", "excerpt": "relevant text", "source": "source", "url": "url if available", "relevance": 0.8}],
  "code_context": []
}

Use empty arrays [] if no items exist. Start with { and end with }.
Do not invent sources; only use provided documents.""",
            variables=[],
            tags=["agent", "knowledge_retrieval", "context", "synthesis"],
        )
        
        # Story Writer prompts
        self._add_default_prompt(
            id="story_writer_agent_system",
            name="Story Writer Agent System Prompt",
            description="System prompt for populating story templates with context",
            category=PromptCategory.AGENT_SYSTEM,
            agent_type="story_writer_agent",
            template="""You are a Story Writer Agent. You MUST respond with a valid JSON object.

Your role is to populate a story template with all required fields.

CRITICAL: Your response must be a JSON object starting with { and ending with }.
Do NOT return a list/array. Do NOT return just one field. Return ALL fields together.

You must return a JSON object with this EXACT structure:
{
  "title": "Story title here",
  "description": "Full story description here",
  "acceptance_criteria": [
    {"type": "gherkin", "scenario": "...", "given": "...", "when": "...", "then": "..."}
  ],
  "dependencies": ["dependency 1", "dependency 2"],
  "nfrs": ["non-functional requirement 1"],
  "out_of_scope": ["item not in scope"],
  "assumptions": ["assumption 1"],
  "open_questions": ["question 1"]
}

Rules:
- Include ALL fields in your response, even if empty (use empty arrays [])
- Use Gherkin format for acceptance_criteria
- Cite sources with [source: <title>] in the description""",
            variables=[],
            tags=["agent", "story_writer", "generation", "system"],
        )
        
        # Validation prompts
        self._add_default_prompt(
            id="validation_gap_agent_system",
            name="Validation Gap Agent System Prompt",
            description="System prompt for the Validation & Gap Detection Agent",
            category=PromptCategory.AGENT_SYSTEM,
            agent_type="validation_gap_agent",
            template="""You are a Validation & Gap Detection Agent.

IMPORTANT: Return a JSON object (NOT a list) with this EXACT structure:
{
  "invest_score": {
    "independent": true,
    "negotiable": true,
    "valuable": true,
    "estimable": true,
    "small": true,
    "testable": true,
    "overall": "pass"
  },
  "issues": [{"severity": "warning", "type": "general", "message": "issue description"}],
  "gaps": [{"field": "field_name", "gap": "gap description"}],
  "ungrounded_claims": ["claim without evidence"],
  "technical_risks": [{"risk": "risk description", "mitigation": "how to address"}]
}

Use empty arrays [] if no items exist. Start with { and end with }.""",
            variables=[],
            tags=["agent", "validation", "system", "gap_detection"],
        )
        
        # Template Parser Agent prompts
        self._add_default_prompt(
            id="template_parser_agent_system",
            name="Template Parser Agent System Prompt",
            description="System prompt for the Template Parser Agent",
            category=PromptCategory.AGENT_SYSTEM,
            agent_type="template_parser_agent",
            template="""You are a Template Parser Agent that parses story templates.

IMPORTANT: Return a JSON object (NOT a list) with this EXACT structure:
{
  "required_fields": ["title", "description", "acceptance_criteria"],
  "optional_fields": ["dependencies", "nfrs", "out_of_scope"],
  "format_style": "gherkin",
  "sections": [{"name": "acceptance_criteria", "format": "gherkin", "min_items": 3}]
}

Start your response with { and end with }. Return ALL fields.""",
            variables=[],
            tags=["agent", "template_parser", "system"],
        )
        
        # Story Generation Agent prompts
        self._add_default_prompt(
            id="story_generation_agent_system",
            name="Story Generation Agent System Prompt",
            description="System prompt for the Story Generation Agent",
            category=PromptCategory.AGENT_SYSTEM,
            agent_type="story_generation_agent",
            template="""You are a Story Generation Agent. Your role is to:
1. Apply the selected splitting techniques to the epic.
2. Generate INVEST-friendly user stories that are small and independent.
3. Use clear titles and descriptions in user story format.
4. Suggest story points using Fibonacci (1,2,3,5,8) when reasonable.
5. Provide initial acceptance criteria that are specific and testable.
6. Maintain traceability to the parent epic.

Quality constraints:
- Focus on user value; avoid implementation details unless required by the epic.
- Each story should represent one coherent outcome or workflow step.
- Avoid duplicates; keep scope tight and explicit.
- If information is missing, keep description concise and add an acceptance criterion that clarifies the needed behavior.

Evidence and citation rules:
- Every factual statement must include an inline citation in the form [source: epic] or [source: <explicit text from epic>].
- If no supporting evidence exists in the epic text, mark the statement with [source: missing].

Return a JSON object matching the requested schema exactly. Do not add extra fields.""",
            variables=[],
            tags=["agent", "story_generation", "system"],
        )
        
        # Splitting Strategy Agent prompts
        self._add_default_prompt(
            id="splitting_strategy_agent_system",
            name="Splitting Strategy Agent System Prompt",
            description="System prompt for the Splitting Strategy Agent",
            category=PromptCategory.AGENT_SYSTEM,
            agent_type="splitting_strategy_agent",
            template="""You are a Splitting Strategy Agent. Your role is to:
1. Analyze epic characteristics and recommend splitting techniques.
2. Apply SPIDR framework (Spike, Path, Interface, Data, Rules).
3. Apply Humanizing Work patterns (Simple/Complex, Defer Performance, Break Out Spike, Workflow Steps, Operations, Breaking Conjunctions).
4. Rank techniques by relevance and explain why.

Return a JSON object matching the requested schema exactly.""",
            variables=[],
            tags=["agent", "splitting_strategy", "system"],
        )
        
        # Epic Analysis Agent prompts
        self._add_default_prompt(
            id="epic_analysis_agent_system",
            name="Epic Analysis Agent System Prompt",
            description="System prompt for the Epic Analysis Agent",
            category=PromptCategory.AGENT_SYSTEM,
            agent_type="epic_analysis_agent",
            template="""You are an Epic Analysis Agent. Your role is to:
1. Parse the epic description and extract key entities (user, capability, benefit, constraints).
2. Classify the epic type (feature, technical, architectural).
3. Assess complexity (0.0-1.0).
4. Flag ambiguities and missing information.
5. Identify the most likely domain.

Return a JSON object matching the requested schema exactly.""",
            variables=[],
            tags=["agent", "epic_analysis", "system"],
        )
    
    def _add_default_prompt(
        self,
        id: str,
        name: str,
        description: str,
        category: PromptCategory,
        agent_type: str,
        template: str,
        variables: List[PromptVariable],
        tags: List[str],
    ) -> None:
        """Add a default prompt template."""
        version = PromptVersion(
            version="1.0.0",
            template=template,
            changelog="Initial version",
            is_active=True,
            metrics=PromptPerformanceMetrics(),
        )
        
        prompt = PromptTemplate(
            id=id,
            name=name,
            description=description,
            category=category,
            agent_type=agent_type,
            tags=tags,
            variables=variables,
            current_version="1.0.0",
            versions=[version],
        )
        
        self._prompts[id] = prompt
    
    async def get_prompt(
        self,
        prompt_id: str,
        version: Optional[str] = None,
    ) -> Optional[PromptTemplate]:
        """Get a prompt template by ID."""
        async with self._get_async_lock():
            prompt = self._prompts.get(prompt_id)
            if prompt is None:
                return None
            
            # Return a copy to prevent mutation
            return prompt.model_copy(deep=True)
    
    async def get_prompt_for_agent(
        self,
        agent_type: str,
        task: str,
        model: Optional[str] = None,
    ) -> Optional[PromptTemplate]:
        """Get the best prompt for an agent and task."""
        async with self._get_async_lock():
            # Try exact match first
            exact_id = f"{agent_type}_{task}"
            if exact_id in self._prompts:
                return self._prompts[exact_id].model_copy(deep=True)
            
            # Search by agent_type and tags
            candidates: List[PromptTemplate] = []
            for prompt in self._prompts.values():
                if prompt.agent_type == agent_type:
                    if task in prompt.tags or task in prompt.id:
                        candidates.append(prompt)
            
            if not candidates:
                return None
            
            # If multiple candidates, prefer one with best performance metrics
            if len(candidates) > 1:
                candidates.sort(
                    key=lambda p: self._get_version_metrics(p).success_rate,
                    reverse=True
                )
            
            return candidates[0].model_copy(deep=True)
    
    def _get_version_metrics(self, prompt: PromptTemplate) -> PromptPerformanceMetrics:
        """Get metrics for current version of a prompt."""
        for v in prompt.versions:
            if v.version == prompt.current_version:
                return v.metrics
        return PromptPerformanceMetrics()
    
    async def render_prompt(
        self,
        prompt_id: str,
        model: str,
        variables: Dict[str, Any],
        version: Optional[str] = None,
    ) -> str:
        """Render a prompt with variable substitution."""
        prompt = await self.get_prompt(prompt_id, version)
        if prompt is None:
            raise ValueError(f"Prompt not found: {prompt_id}")
        
        return prompt.render(model, **variables)
    
    async def list_prompts(
        self,
        category: Optional[PromptCategory] = None,
        agent_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[PromptTemplate]:
        """List prompts with optional filtering."""
        async with self._get_async_lock():
            results: List[PromptTemplate] = []
            
            for prompt in self._prompts.values():
                # Apply filters
                if category is not None and prompt.category != category:
                    continue
                if agent_type is not None and prompt.agent_type != agent_type:
                    continue
                if tags is not None:
                    if not any(tag in prompt.tags for tag in tags):
                        continue
                
                results.append(prompt.model_copy(deep=True))
            
            return results
    
    async def save_prompt(self, prompt: PromptTemplate) -> None:
        """Save or update a prompt template."""
        async with self._get_async_lock():
            prompt.updated_at = datetime.utcnow()
            self._prompts[prompt.id] = prompt.model_copy(deep=True)
        
        logger.info("prompt_saved", prompt_id=prompt.id, version=prompt.current_version)
    
    async def delete_prompt(self, prompt_id: str) -> bool:
        """Delete a prompt template."""
        async with self._get_async_lock():
            if prompt_id in self._prompts:
                del self._prompts[prompt_id]
                logger.info("prompt_deleted", prompt_id=prompt_id)
                return True
            return False
    
    async def add_version(
        self,
        prompt_id: str,
        version: str,
        template: str,
        changelog: Optional[str] = None,
        set_active: bool = True,
    ) -> bool:
        """Add a new version to a prompt template."""
        async with self._get_async_lock():
            if prompt_id not in self._prompts:
                return False
            
            prompt = self._prompts[prompt_id]
            
            # Check if version already exists
            for v in prompt.versions:
                if v.version == version:
                    logger.warning("version_exists", prompt_id=prompt_id, version=version)
                    return False
            
            new_version = PromptVersion(
                version=version,
                template=template,
                changelog=changelog,
                is_active=set_active,
                metrics=PromptPerformanceMetrics(),
            )
            
            prompt.versions.append(new_version)
            
            if set_active:
                # Deactivate previous versions
                for v in prompt.versions:
                    if v.version != version:
                        v.is_active = False
                prompt.current_version = version
            
            prompt.updated_at = datetime.utcnow()
            
            logger.info(
                "version_added",
                prompt_id=prompt_id,
                version=version,
                set_active=set_active,
            )
            return True
    
    async def rollback_version(self, prompt_id: str, version: str) -> bool:
        """Rollback to a previous prompt version."""
        async with self._get_async_lock():
            if prompt_id not in self._prompts:
                return False
            
            prompt = self._prompts[prompt_id]
            
            # Find the target version
            target_version = None
            for v in prompt.versions:
                if v.version == version:
                    target_version = v
                    break
            
            if target_version is None:
                return False
            
            # Update active status
            for v in prompt.versions:
                v.is_active = (v.version == version)
            
            prompt.current_version = version
            prompt.updated_at = datetime.utcnow()
            
            logger.info("version_rollback", prompt_id=prompt_id, version=version)
            return True
    
    async def record_execution(self, record: PromptExecutionRecord) -> None:
        """Record a prompt execution for monitoring."""
        async with self._get_async_lock():
            # Add to execution history
            self._executions.append(record)
            
            # Trim if too many
            if len(self._executions) > self._max_executions:
                self._executions = self._executions[-self._max_executions:]
            
            # Update prompt metrics
            if record.prompt_id in self._prompts:
                prompt = self._prompts[record.prompt_id]
                for v in prompt.versions:
                    if v.version == record.version:
                        self._update_version_metrics(v.metrics, record)
                        break
        
        logger.debug(
            "execution_recorded",
            prompt_id=record.prompt_id,
            version=record.version,
            success=record.success,
            latency_ms=record.latency_ms,
        )
    
    def _update_version_metrics(
        self,
        metrics: PromptPerformanceMetrics,
        record: PromptExecutionRecord,
    ) -> None:
        """Update version metrics with new execution record."""
        n = metrics.total_uses
        
        # Update counts
        metrics.total_uses += 1
        
        # Update success rate (running average)
        success_value = 1.0 if record.success else 0.0
        metrics.success_rate = (metrics.success_rate * n + success_value) / (n + 1)
        
        # Update error rate
        error_value = 0.0 if record.success else 1.0
        metrics.error_rate = (metrics.error_rate * n + error_value) / (n + 1)
        
        # Update latency (running average)
        metrics.avg_latency_ms = (metrics.avg_latency_ms * n + record.latency_ms) / (n + 1)
        
        # Update tokens (running average)
        metrics.avg_input_tokens = (metrics.avg_input_tokens * n + record.input_tokens) / (n + 1)
        metrics.avg_output_tokens = (metrics.avg_output_tokens * n + record.output_tokens) / (n + 1)
        
        # Update quality score if provided
        if record.quality_score is not None:
            if metrics.quality_score is None:
                metrics.quality_score = record.quality_score
            else:
                metrics.quality_score = (metrics.quality_score * n + record.quality_score) / (n + 1)
        
        # Update last used
        metrics.last_used = record.timestamp
    
    async def get_summary(self) -> PromptLibrarySummary:
        """Get summary statistics for the prompt library."""
        async with self._get_async_lock():
            summary = PromptLibrarySummary(
                total_prompts=len(self._prompts),
                prompts_by_category={},
                prompts_by_agent={},
                total_executions=len(self._executions),
                avg_success_rate=1.0,
                avg_latency_ms=0.0,
                active_ab_tests=0,
                top_performing_prompts=[],
            )
            
            # Count by category and agent
            for prompt in self._prompts.values():
                cat = prompt.category.value
                summary.prompts_by_category[cat] = summary.prompts_by_category.get(cat, 0) + 1
                
                if prompt.agent_type:
                    summary.prompts_by_agent[prompt.agent_type] = (
                        summary.prompts_by_agent.get(prompt.agent_type, 0) + 1
                    )
                
                if prompt.enable_ab_testing and prompt.ab_test_config and prompt.ab_test_config.is_active:
                    summary.active_ab_tests += 1
            
            # Calculate aggregate metrics
            if self._executions:
                total_success = sum(1 for e in self._executions if e.success)
                summary.avg_success_rate = total_success / len(self._executions)
                summary.avg_latency_ms = sum(e.latency_ms for e in self._executions) / len(self._executions)
            
            # Find top performing prompts
            prompt_scores: List[tuple[str, float]] = []
            for prompt in self._prompts.values():
                metrics = self._get_version_metrics(prompt)
                if metrics.total_uses > 0:
                    score = metrics.success_rate * 0.5 + (1 - min(metrics.avg_latency_ms / 5000, 1)) * 0.3
                    if metrics.quality_score is not None:
                        score += metrics.quality_score * 0.2
                    prompt_scores.append((prompt.id, score))
            
            prompt_scores.sort(key=lambda x: x[1], reverse=True)
            summary.top_performing_prompts = [p[0] for p in prompt_scores[:5]]
            
            return summary
    
    async def select_ab_variant(
        self,
        prompt_id: str,
        session_id: Optional[str] = None,
    ) -> str:
        """Select a version based on A/B test configuration."""
        async with self._get_async_lock():
            if prompt_id not in self._prompts:
                raise ValueError(f"Prompt not found: {prompt_id}")
            
            prompt = self._prompts[prompt_id]
            
            # If no A/B testing, return current version
            if not prompt.enable_ab_testing or prompt.ab_test_config is None:
                return prompt.current_version
            
            config = prompt.ab_test_config
            
            # If test not active, return control
            if not config.is_active:
                return config.control_version
            
            # Use session_id for consistent selection if provided
            if session_id:
                # Hash session to get consistent bucket
                hash_value = int(hashlib.md5(session_id.encode()).hexdigest(), 16)
                rand_value = (hash_value % 10000) / 10000.0
            else:
                rand_value = random.random()
            
            # Select version based on traffic split
            cumulative = 0.0
            for version, split in config.traffic_split.items():
                cumulative += split
                if rand_value < cumulative:
                    return version
            
            # Fallback to control
            return config.control_version
    
    def get_recent_executions(
        self,
        prompt_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[PromptExecutionRecord]:
        """Get recent execution records (sync method for non-async contexts)."""
        with self._sync_lock:
            if prompt_id:
                records = [e for e in self._executions if e.prompt_id == prompt_id]
            else:
                records = list(self._executions)
            
            return records[-limit:]
    
    async def get_prompt_template(
        self,
        prompt_id: str,
        version: Optional[str] = None,
    ) -> Optional[str]:
        """Get just the template string for a prompt.
        
        This is a convenience method for agents to fetch the template text
        without dealing with the full PromptTemplate object.
        
        Args:
            prompt_id: The prompt ID to fetch.
            version: Optional specific version. If None, uses current active version.
            
        Returns:
            The template string, or None if prompt not found.
        """
        prompt = await self.get_prompt(prompt_id, version)
        if prompt is None:
            return None
        
        # Find the requested version or current version
        target_version = version or prompt.current_version
        for v in prompt.versions:
            if v.version == target_version:
                return v.template
        
        # Fallback to first version if specified version not found
        if prompt.versions:
            return prompt.versions[0].template
        
        return None
    
    def get_prompt_template_sync(
        self,
        prompt_id: str,
        version: Optional[str] = None,
    ) -> Optional[str]:
        """Synchronous version of get_prompt_template.
        
        For use in contexts where async is not available (e.g., class initialization).
        
        Args:
            prompt_id: The prompt ID to fetch.
            version: Optional specific version.
            
        Returns:
            The template string, or None if prompt not found.
        """
        with self._sync_lock:
            prompt = self._prompts.get(prompt_id)
            if prompt is None:
                return None
            
            target_version = version or prompt.current_version
            for v in prompt.versions:
                if v.version == target_version:
                    return v.template
            
            if prompt.versions:
                return prompt.versions[0].template
            
            return None
    
    def get_all_prompt_ids(self) -> List[str]:
        """Get list of all prompt IDs in the library.
        
        Returns:
            List of prompt IDs.
        """
        with self._sync_lock:
            return list(self._prompts.keys())


# Global singleton instance
_prompt_library: Optional[InMemoryPromptLibrary] = None


def get_prompt_library() -> InMemoryPromptLibrary:
    """Get the global prompt library instance."""
    global _prompt_library
    if _prompt_library is None:
        _prompt_library = InMemoryPromptLibrary()
    return _prompt_library
