"""In-memory admin state for integrations and configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from src.config import settings
from src.domain.schema import (
    IntegrationAction,
    IntegrationConnectRequest,
    IntegrationDetail,
    IntegrationInfo,
    IntegrationScopeUpdate,
    IntegrationTestResult,
)


# ============================================
# Runtime Model Configuration
# ============================================

class RuntimeModelConfig(BaseModel):
    """Runtime configuration for LLM models (can be changed without restart)."""
    model: Optional[str] = Field(None, description="Currently selected model (None = use env default)")
    temperature: float = Field(default=0.7, description="Default temperature for completions")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    updated_by: Optional[str] = Field(None, description="Who made the change")


# Global runtime model configuration (singleton)
_runtime_model_config: RuntimeModelConfig = RuntimeModelConfig()


def get_runtime_model_config() -> RuntimeModelConfig:
    """Get the current runtime model configuration."""
    return _runtime_model_config


def set_runtime_model(
    model: str,
    temperature: Optional[float] = None,
    updated_by: Optional[str] = None,
) -> RuntimeModelConfig:
    """Set the runtime model configuration.
    
    Args:
        model: Model identifier (e.g., 'ollama/llama3', 'gpt-4')
        temperature: Optional temperature override
        updated_by: Optional user identifier
        
    Returns:
        Updated RuntimeModelConfig
    """
    global _runtime_model_config
    _runtime_model_config.model = model
    if temperature is not None:
        _runtime_model_config.temperature = temperature
    _runtime_model_config.updated_at = datetime.now(timezone.utc).isoformat()
    _runtime_model_config.updated_by = updated_by
    return _runtime_model_config


def get_effective_model() -> str:
    """Get the effective model to use (runtime override or env default)."""
    if _runtime_model_config.model:
        return _runtime_model_config.model
    return settings.litellm_model


def get_effective_temperature() -> float:
    """Get the effective temperature to use."""
    return _runtime_model_config.temperature


def reset_runtime_model_config() -> RuntimeModelConfig:
    """Reset runtime config to use environment defaults."""
    global _runtime_model_config
    _runtime_model_config = RuntimeModelConfig()
    return _runtime_model_config


def _now_label() -> str:
    return datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================
# Template Management Models
# ============================================

class FieldMapping(BaseModel):
    """Mapping from template field to target system field."""
    source_field: str = Field(description="Field name in template")
    target_field: str = Field(description="Field name in target system")
    required: bool = Field(default=False, description="Whether field is required")
    description: Optional[str] = Field(None, description="Field description")


class TemplateVersion(BaseModel):
    """Version of a template with content and metadata."""
    version: str = Field(description="Version string (e.g., '2.1')")
    content: str = Field(description="Template content (markdown/text)")
    field_mappings: List[FieldMapping] = Field(default_factory=list)
    output_structure: Optional[str] = Field(None, description="Example output structure")
    changelog: Optional[str] = Field(None, description="Version changelog")
    created_at: str = Field(default_factory=_now_iso)
    created_by: Optional[str] = Field(None, description="User who created version")
    is_active: bool = Field(default=False, description="Whether this is active version")


class Template(BaseModel):
    """Template for artifact generation."""
    id: str = Field(description="Unique template ID")
    name: str = Field(description="Template display name")
    artifact_type: str = Field(description="Artifact type: user_story, epic, initiative")
    description: Optional[str] = Field(None, description="Template description")
    versions: List[TemplateVersion] = Field(default_factory=list)
    current_version: str = Field(description="Currently active version")
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class TemplateCreateRequest(BaseModel):
    """Request to create a new template."""
    name: str
    artifact_type: str = "user_story"
    description: Optional[str] = None
    content: str
    field_mappings: List[FieldMapping] = Field(default_factory=list)
    output_structure: Optional[str] = None


class TemplateUpdateRequest(BaseModel):
    """Request to update template content (creates new version)."""
    content: str
    field_mappings: Optional[List[FieldMapping]] = None
    output_structure: Optional[str] = None
    changelog: Optional[str] = None
    created_by: Optional[str] = None


@dataclass
class IntegrationState:
    """In-memory overrides for integration status and metadata."""

    connected: Optional[bool] = None
    scopes: List[str] = field(default_factory=list)
    last_sync: Optional[str] = None
    repositories: List[str] = field(default_factory=list)
    workspace: Optional[str] = None


# Default User Story template content
DEFAULT_USER_STORY_TEMPLATE = """# User Story Template Specification

## 1. Field Mappings

- **Title** → title (required)
- **Description** → description (required)
- **Acceptance Criteria** → acceptance_criteria (required)
- **Dependencies** → linked_issues (optional)
- **NFRs** → custom_field_10042 (optional)
- **Story Points** → story_points (optional)
- **Priority** → priority (optional)

## 2. Output Structure

```yaml
title: "As a [persona], I want [capability] so that [benefit]"
description: |
  ### Business Value
  [Describe the business value and user benefit]
  
  ### Context
  [Provide relevant context and background]
  
  ### Technical Notes
  [Include any technical considerations]
acceptance_criteria:
  - Given [context], When [action], Then [outcome]
  - Given [context], When [action], Then [outcome]
linked_issues: ["EPIC-123", "STORY-456"]
story_points: 5
priority: "High"
```

## 3. Guidelines

### Title Format
Use the format: "As a [persona], I want [capability] so that [benefit]"

### Acceptance Criteria
- Use Gherkin format (Given/When/Then) for testability
- Include positive and negative scenarios
- Make criteria measurable and specific

### INVEST Principles
- **I**ndependent: Story can be developed independently
- **N**egotiable: Details can be negotiated
- **V**aluable: Delivers value to the user
- **E**stimable: Can be estimated by the team
- **S**mall: Can be completed in one sprint
- **T**estable: Has clear acceptance criteria
"""

DEFAULT_EPIC_TEMPLATE = """# Epic Template Specification

## 1. Field Mappings

- **Title** → title (required)
- **Description** → description (required)
- **Business Objective** → business_objective (required)
- **Success Metrics** → success_metrics (optional)
- **Target Users** → target_users (optional)
- **Dependencies** → dependencies (optional)

## 2. Output Structure

```yaml
title: "[Epic Name]"
description: |
  ### Overview
  [High-level description of the epic]
  
  ### Business Objective
  [What business goal does this achieve?]
  
  ### Target Users
  [Who will benefit from this epic?]
  
  ### Success Metrics
  [How will we measure success?]
  
  ### Scope
  [What's in scope and out of scope]
dependencies: []
target_release: "Q2 2026"
```

## 3. Guidelines

### Epic Sizing
- Should be completable within 1-2 quarters
- Contains 5-15 user stories
- Has clear business value

### Decomposition Strategy
- Break down by user journey phases
- Split by persona types
- Separate by feature domains
"""


class AdminStore:
    """In-memory store for admin configuration."""

    def __init__(self):
        self._integrations: Dict[str, IntegrationState] = {}
        self._templates: Dict[str, Template] = {}
        self._initialize_default_templates()

    def _initialize_default_templates(self) -> None:
        """Initialize default templates if not already present."""
        # Default User Story template
        if "user_story_default" not in self._templates:
            self._templates["user_story_default"] = Template(
                id="user_story_default",
                name="User Story Template Specification",
                artifact_type="user_story",
                description="Standard template for user story generation with INVEST principles",
                current_version="2.1",
                versions=[
                    TemplateVersion(
                        version="2.1",
                        content=DEFAULT_USER_STORY_TEMPLATE,
                        field_mappings=[
                            FieldMapping(source_field="Title", target_field="title", required=True),
                            FieldMapping(source_field="Description", target_field="description", required=True),
                            FieldMapping(source_field="Acceptance criteria", target_field="acceptance_criteria", required=True),
                            FieldMapping(source_field="Dependencies", target_field="linked_issues", required=False),
                            FieldMapping(source_field="NFRs", target_field="custom_field_10042", required=False),
                        ],
                        output_structure='title: "As a shopper, I can retry payment"\ndescription: "### Business value\\n..."\nacceptance_criteria:\n  - [x] When a retriable payment error occurs...\n  - [ ] Retry attempts are logged...\nlinked_issues: ["SYN-INIT-1423"]',
                        changelog="Updated field mappings and added NFR support",
                        created_at="2026-01-21T10:00:00Z",
                        is_active=True,
                    ),
                    TemplateVersion(
                        version="2.0",
                        content="# User Story Template v2.0\n\n## Fields\n- Title\n- Description\n- Acceptance Criteria",
                        field_mappings=[
                            FieldMapping(source_field="Title", target_field="title", required=True),
                            FieldMapping(source_field="Description", target_field="description", required=True),
                            FieldMapping(source_field="Acceptance criteria", target_field="acceptance_criteria", required=True),
                        ],
                        changelog="Major update with new structure",
                        created_at="2025-12-18T10:00:00Z",
                        is_active=False,
                    ),
                    TemplateVersion(
                        version="1.8",
                        content="# User Story Template v1.8\n\n## Basic Fields\n- Title\n- Description",
                        field_mappings=[
                            FieldMapping(source_field="Title", target_field="title", required=True),
                            FieldMapping(source_field="Description", target_field="description", required=True),
                        ],
                        changelog="Initial stable version",
                        created_at="2025-10-02T10:00:00Z",
                        is_active=False,
                    ),
                ],
                created_at="2025-10-02T10:00:00Z",
                updated_at="2026-01-21T10:00:00Z",
            )

        # Default Epic template
        if "epic_default" not in self._templates:
            self._templates["epic_default"] = Template(
                id="epic_default",
                name="Epic Template Specification",
                artifact_type="epic",
                description="Standard template for epic generation and breakdown",
                current_version="1.0",
                versions=[
                    TemplateVersion(
                        version="1.0",
                        content=DEFAULT_EPIC_TEMPLATE,
                        field_mappings=[
                            FieldMapping(source_field="Title", target_field="title", required=True),
                            FieldMapping(source_field="Description", target_field="description", required=True),
                            FieldMapping(source_field="Business Objective", target_field="business_objective", required=True),
                        ],
                        changelog="Initial epic template",
                        created_at="2026-01-15T10:00:00Z",
                        is_active=True,
                    ),
                ],
                created_at="2026-01-15T10:00:00Z",
                updated_at="2026-01-15T10:00:00Z",
            )

    # ============================================
    # Template Management Methods
    # ============================================

    def list_templates(self, artifact_type: Optional[str] = None) -> List[Template]:
        """List all templates, optionally filtered by artifact type."""
        templates = list(self._templates.values())
        if artifact_type:
            templates = [t for t in templates if t.artifact_type == artifact_type]
        return templates

    def get_template(self, template_id: str) -> Optional[Template]:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def get_active_template(self, artifact_type: str) -> Optional[Template]:
        """Get the active template for an artifact type."""
        for template in self._templates.values():
            if template.artifact_type == artifact_type:
                # Return first template with an active version
                for version in template.versions:
                    if version.is_active:
                        return template
        return None

    def get_active_template_content(self, artifact_type: str) -> Optional[str]:
        """Get the active template content for an artifact type."""
        template = self.get_active_template(artifact_type)
        if template:
            for version in template.versions:
                if version.is_active:
                    return version.content
        return None

    def create_template(self, request: TemplateCreateRequest) -> Template:
        """Create a new template."""
        template_id = f"{request.artifact_type}_{uuid4().hex[:8]}"
        
        version = TemplateVersion(
            version="1.0",
            content=request.content,
            field_mappings=request.field_mappings,
            output_structure=request.output_structure,
            changelog="Initial version",
            is_active=True,
        )
        
        template = Template(
            id=template_id,
            name=request.name,
            artifact_type=request.artifact_type,
            description=request.description,
            versions=[version],
            current_version="1.0",
        )
        
        self._templates[template_id] = template
        return template

    def update_template(self, template_id: str, request: TemplateUpdateRequest) -> Optional[Template]:
        """Update a template by creating a new version."""
        template = self._templates.get(template_id)
        if not template:
            return None
        
        # Determine new version number
        current_major, current_minor = template.current_version.split(".")
        new_version = f"{current_major}.{int(current_minor) + 1}"
        
        # Deactivate all existing versions
        for version in template.versions:
            version.is_active = False
        
        # Get field mappings from request or previous active version
        field_mappings = request.field_mappings
        if field_mappings is None:
            # Copy from previous active version
            for version in template.versions:
                if version.version == template.current_version:
                    field_mappings = version.field_mappings
                    break
            field_mappings = field_mappings or []
        
        # Create new version
        new_version_obj = TemplateVersion(
            version=new_version,
            content=request.content,
            field_mappings=field_mappings,
            output_structure=request.output_structure,
            changelog=request.changelog or f"Updated to version {new_version}",
            created_by=request.created_by,
            is_active=True,
        )
        
        template.versions.insert(0, new_version_obj)
        template.current_version = new_version
        template.updated_at = _now_iso()
        
        return template

    def rollback_template_version(self, template_id: str, target_version: str) -> Optional[Template]:
        """Rollback a template to a previous version."""
        template = self._templates.get(template_id)
        if not template:
            return None
        
        # Find target version
        target_found = False
        for version in template.versions:
            if version.version == target_version:
                target_found = True
                version.is_active = True
            else:
                version.is_active = False
        
        if not target_found:
            return None
        
        template.current_version = target_version
        template.updated_at = _now_iso()
        return template

    def delete_template(self, template_id: str) -> bool:
        """Delete a template."""
        if template_id in self._templates:
            del self._templates[template_id]
            return True
        return False

    def list_integrations(self) -> List[IntegrationInfo]:
        """Return the current integration list."""
        return [
            self._build_jira(),
            self._build_linear(),
            self._build_github(),
            self._build_notion(),
            self._build_confluence(),
            self._build_sharepoint(),
        ]

    def connect_integration(self, name: str, payload: IntegrationConnectRequest) -> IntegrationInfo:
        """Connect an integration using a token (simulated)."""
        state = self._get_state(name)
        state.connected = bool(payload.token)
        state.last_sync = _now_label()
        return self._build_by_name(name)

    def update_scopes(self, name: str, payload: IntegrationScopeUpdate) -> IntegrationInfo:
        """Update scopes for an integration."""
        state = self._get_state(name)
        state.scopes = payload.scopes
        state.last_sync = _now_label()
        return self._build_by_name(name)

    def test_integration(self, name: str) -> IntegrationTestResult:
        """Test the integration connection (simulated)."""
        info = self._build_by_name(name)
        success = info.status == "connected"
        message = "Connection successful." if success else "Integration is not connected."
        return IntegrationTestResult(success=success, message=message)

    def record_sync(self, name: str) -> IntegrationInfo:
        """Record a sync event for an integration."""
        state = self._get_state(name)
        state.last_sync = _now_label()
        return self._build_by_name(name)

    def _get_state(self, name: str) -> IntegrationState:
        normalized = name.strip().lower()
        if normalized not in self._integrations:
            self._integrations[normalized] = IntegrationState()
        return self._integrations[normalized]

    def _build_by_name(self, name: str) -> IntegrationInfo:
        normalized = name.strip().lower()
        if normalized == "jira":
            return self._build_jira()
        if normalized == "linear":
            return self._build_linear()
        if normalized == "github":
            return self._build_github()
        if normalized == "notion":
            return self._build_notion()
        if normalized == "confluence":
            return self._build_confluence()
        if normalized == "sharepoint":
            return self._build_sharepoint()
        raise ValueError(f"Unsupported integration: {name}")

    def _build_jira(self) -> IntegrationInfo:
        state = self._get_state("jira")
        connected = state.connected
        if connected is None:
            connected = bool(settings.jira_token)
        status = "connected" if connected else "not_connected"
        scopes = state.scopes or (
            [item.strip() for item in settings.jira_project_keys.split(",") if item.strip()]
        )
        project_label = ", ".join(scopes) if scopes else "Not configured"
        last_sync = state.last_sync or "Not synced"
        details = [
            IntegrationDetail(label="Allowed projects", value=project_label),
            IntegrationDetail(label="Last sync", value=last_sync),
        ]
        action = "Manage scopes" if connected else "Connect"
        action_type = "scopes" if connected else "connect"
        footer_actions = []
        if connected:
            footer_actions = [
                IntegrationAction(label="Sync now", action_type="sync"),
                IntegrationAction(label="Test connection", action_type="test"),
            ]
        footer_action = footer_actions[0].label if footer_actions else None
        return IntegrationInfo(
            name="Jira",
            status=status,
            action=action,
            action_type=action_type,
            details=details,
            footer_action=footer_action,
            footer_actions=footer_actions,
        )

    def _build_linear(self) -> IntegrationInfo:
        state = self._get_state("linear")
        connected = state.connected
        if connected is None:
            connected = bool(settings.linear_api_key)
        status = "connected" if connected else "not_connected"
        scopes = state.scopes or ["All projects"]
        last_sync = state.last_sync or "Not synced"
        details = [
            IntegrationDetail(label="Allowed projects", value=", ".join(scopes)),
            IntegrationDetail(label="Last sync", value=last_sync),
        ]
        action = "Manage scopes" if connected else "Connect"
        action_type = "scopes" if connected else "connect"
        footer_actions = []
        if connected:
            footer_actions = [IntegrationAction(label="Test connection", action_type="test")]
        footer_action = footer_actions[0].label if footer_actions else None
        return IntegrationInfo(
            name="Linear",
            status=status,
            action=action,
            action_type=action_type,
            details=details,
            footer_action=footer_action,
            footer_actions=footer_actions,
        )

    def _build_github(self) -> IntegrationInfo:
        state = self._get_state("github")
        connected = state.connected
        if connected is None:
            connected = bool(settings.github_token)
        status = "connected" if connected else "not_connected"
        repositories = state.repositories or ([settings.github_repo] if settings.github_repo else [])
        repo_label = ", ".join(repositories) if repositories else "Not configured"
        last_sync = state.last_sync or "Not synced"
        details = [
            IntegrationDetail(label="Repositories", value=repo_label),
            IntegrationDetail(label="Last scan", value=last_sync),
        ]
        action = "Manage repositories" if connected else "Connect"
        action_type = "repos" if connected else "connect"
        footer_actions = []
        if connected:
            footer_actions = [IntegrationAction(label="Test connection", action_type="test")]
        footer_action = footer_actions[0].label if footer_actions else None
        return IntegrationInfo(
            name="GitHub",
            status=status,
            action=action,
            action_type=action_type,
            details=details,
            footer_action=footer_action,
            footer_actions=footer_actions,
        )

    def _build_notion(self) -> IntegrationInfo:
        state = self._get_state("notion")
        connected = state.connected
        if connected is None:
            connected = bool(settings.notion_token)
        status = "connected" if connected else "not_connected"
        workspace = state.workspace or ("Configured" if settings.notion_root_page_id else "Not configured")
        details = [IntegrationDetail(label="Workspace", value=workspace)]
        action = "Manage workspace" if connected else "Connect"
        action_type = "workspace" if connected else "connect"
        return IntegrationInfo(
            name="Notion",
            status=status,
            action=action,
            action_type=action_type,
            details=details,
            footer_action=None,
            footer_actions=[],
        )

    def _build_confluence(self) -> IntegrationInfo:
        state = self._get_state("confluence")
        connected = state.connected
        if connected is None:
            connected = bool(settings.confluence_token)
        status = "connected" if connected else "not_connected"
        spaces = state.scopes or (
            [item.strip() for item in settings.confluence_space_keys.split(",") if item.strip()]
        )
        space_label = ", ".join(spaces) if spaces else "Not configured"
        last_sync = state.last_sync or "Not synced"
        details = [
            IntegrationDetail(label="Allowed spaces", value=space_label),
            IntegrationDetail(label="Last sync", value=last_sync),
        ]
        action = "Manage spaces" if connected else "Connect"
        action_type = "scopes" if connected else "connect"
        footer_actions = []
        if connected:
            footer_actions = [
                IntegrationAction(label="Sync now", action_type="sync"),
                IntegrationAction(label="Test connection", action_type="test"),
            ]
        footer_action = footer_actions[0].label if footer_actions else None
        return IntegrationInfo(
            name="Confluence",
            status=status,
            action=action,
            action_type=action_type,
            details=details,
            footer_action=footer_action,
            footer_actions=footer_actions,
        )

    def _build_sharepoint(self) -> IntegrationInfo:
        state = self._get_state("sharepoint")
        connected = state.connected
        if connected is None:
            connected = bool(settings.sharepoint_token)
        status = "connected" if connected else "not_connected"
        site = state.workspace or (settings.sharepoint_site_name or "Not configured")
        details = [IntegrationDetail(label="Site", value=site)]
        action = "Manage workspace" if connected else "Connect"
        action_type = "workspace" if connected else "connect"
        footer_actions = []
        if connected:
            footer_actions = [IntegrationAction(label="Test connection", action_type="test")]
        footer_action = footer_actions[0].label if footer_actions else None
        return IntegrationInfo(
            name="SharePoint",
            status=status,
            action=action,
            action_type=action_type,
            details=details,
            footer_action=footer_action,
            footer_actions=footer_actions,
        )
