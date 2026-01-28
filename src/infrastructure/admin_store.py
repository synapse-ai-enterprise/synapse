"""In-memory admin state for integrations and configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.config import settings
from src.domain.schema import (
    IntegrationConnectRequest,
    IntegrationDetail,
    IntegrationInfo,
    IntegrationScopeUpdate,
    IntegrationTestResult,
)


def _now_label() -> str:
    return datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")


@dataclass
class IntegrationState:
    """In-memory overrides for integration status and metadata."""

    connected: Optional[bool] = None
    scopes: List[str] = field(default_factory=list)
    last_sync: Optional[str] = None
    repositories: List[str] = field(default_factory=list)
    workspace: Optional[str] = None


class AdminStore:
    """In-memory store for admin configuration."""

    def __init__(self):
        self._integrations: Dict[str, IntegrationState] = {}

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
        footer_action = "Test connection" if connected else None
        return IntegrationInfo(
            name="Jira",
            status=status,
            action=action,
            action_type=action_type,
            details=details,
            footer_action=footer_action,
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
        footer_action = "Test connection" if connected else None
        return IntegrationInfo(
            name="Linear",
            status=status,
            action=action,
            action_type=action_type,
            details=details,
            footer_action=footer_action,
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
        footer_action = "Test connection" if connected else None
        return IntegrationInfo(
            name="GitHub",
            status=status,
            action=action,
            action_type=action_type,
            details=details,
            footer_action=footer_action,
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
        footer_action = "Test connection" if connected else None
        return IntegrationInfo(
            name="Confluence",
            status=status,
            action=action,
            action_type=action_type,
            details=details,
            footer_action=footer_action,
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
        footer_action = "Test connection" if connected else None
        return IntegrationInfo(
            name="SharePoint",
            status=status,
            action=action,
            action_type=action_type,
            details=details,
            footer_action=footer_action,
        )
