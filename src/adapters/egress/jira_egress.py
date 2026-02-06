"""Jira API egress adapter implementing IIssueTracker."""

from __future__ import annotations

from typing import Dict, Optional

import aiohttp

from src.adapters.rate_limiter import TokenBucket
from src.config import settings
from src.domain.interfaces import IIssueTracker
from src.domain.schema import CoreArtifact, NormalizedPriority, WorkItemStatus


class JiraEgressAdapter(IIssueTracker):
    """Jira egress adapter with REST API, optimistic locking, and rate limiting."""

    def __init__(self):
        """Initialize adapter with rate limiter."""
        self.api_token = settings.jira_token
        self.user_email = settings.jira_user_email
        self.base_url = settings.jira_base_url.rstrip("/")
        self.dry_run = settings.dry_run
        self.mode = settings.mode
        self.require_approval_label = settings.require_approval_label
        self.source_system = settings.issue_tracker_provider.strip().lower()

        # Conservative token bucket: 60 requests/minute
        self.rate_limiter = TokenBucket(capacity=60, refill_rate=1.0)

        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        self.auth: Optional[aiohttp.BasicAuth] = None
        if self.user_email:
            self.auth = aiohttp.BasicAuth(self.user_email, self.api_token)
        elif self.api_token:
            self.headers["Authorization"] = f"Bearer {self.api_token}"

    async def get_issue(self, issue_id: str) -> CoreArtifact:
        """Fetch an issue by ID or key."""
        self._ensure_configured()
        await self.rate_limiter.acquire()
        url = f"{self.base_url}/rest/api/3/issue/{issue_id}"
        params = {
            "fields": "summary,description,priority,status,issuetype,project,updated,created,parent",
        }
        async with aiohttp.ClientSession(headers=self.headers, auth=self.auth) as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(
                        f"Jira API error: {response.status}. Response: {error_text[:200]}"
                    )
                data = await response.json()
                return self._map_to_artifact(data)

    async def update_issue(self, issue_id: str, artifact: CoreArtifact) -> bool:
        """Update an issue with optimistic locking."""
        if self.dry_run:
            return True
        if self.mode == "comment_only":
            comment = self._format_optimization_comment(artifact)
            return await self.post_comment(issue_id, comment)

        current = await self.get_issue(issue_id)
        original_updated_at = current.raw_metadata.get("updatedAt")
        current_after = await self.get_issue(issue_id)
        if current_after.raw_metadata.get("updatedAt") != original_updated_at:
            comment = (
                "🤖 AI Optimization Prepared\n\n"
                "I prepared an optimization, but the ticket was edited while I was working. "
                "Please review my suggestions:\n\n"
                f"{self._format_optimization_comment(artifact)}"
            )
            return await self.post_comment(issue_id, comment)

        return await self._execute_update(issue_id, artifact)

    async def create_issue(self, artifact: CoreArtifact) -> str:
        """Create a new issue. Returns the issue URL."""
        self._ensure_configured()
        if self.dry_run:
            return "dry-run://issue"

        project_key = self._get_default_project_key()
        await self.rate_limiter.acquire()
        url = f"{self.base_url}/rest/api/3/issue"

        fields = {
            "project": {"key": project_key},
            "summary": artifact.title,
            "description": self._to_adf(self._format_description(artifact)),
            "issuetype": {"name": artifact.type or "Task"},
        }
        payload = {"fields": fields}

        async with aiohttp.ClientSession(headers=self.headers, auth=self.auth) as session:
            async with session.post(url, json=payload) as response:
                if response.status != 201:
                    error_text = await response.text()
                    raise ValueError(
                        f"Jira API error: {response.status}. Response: {error_text[:200]}"
                    )
                data = await response.json()
                issue_key = data.get("key", "")
                return f"{self.base_url}/browse/{issue_key}" if issue_key else ""

    async def post_comment(self, issue_id: str, comment: str) -> bool:
        """Post a comment to an issue."""
        self._ensure_configured()
        if self.dry_run:
            return True
        await self.rate_limiter.acquire()
        url = f"{self.base_url}/rest/api/3/issue/{issue_id}/comment"
        payload = {"body": self._to_adf(comment)}
        async with aiohttp.ClientSession(headers=self.headers, auth=self.auth) as session:
            async with session.post(url, json=payload) as response:
                return response.status in {200, 201}

    async def _execute_update(self, issue_id: str, artifact: CoreArtifact) -> bool:
        await self.rate_limiter.acquire()
        url = f"{self.base_url}/rest/api/3/issue/{issue_id}"
        fields = {
            "summary": artifact.title,
            "description": self._to_adf(self._format_description(artifact)),
        }
        payload = {"fields": fields}
        async with aiohttp.ClientSession(headers=self.headers, auth=self.auth) as session:
            async with session.put(url, json=payload) as response:
                if response.status not in {200, 204}:
                    return False
                if self.require_approval_label and self.mode == "autonomous":
                    await self._add_label(issue_id, self.require_approval_label)
                return True

    async def _add_label(self, issue_id: str, label_name: str) -> None:
        await self.rate_limiter.acquire()
        url = f"{self.base_url}/rest/api/3/issue/{issue_id}"
        payload = {"update": {"labels": [{"add": label_name}]}}
        async with aiohttp.ClientSession(headers=self.headers, auth=self.auth) as session:
            await session.put(url, json=payload)

    def _map_to_artifact(self, issue_data: Dict) -> CoreArtifact:
        fields = issue_data.get("fields", {}) or {}
        priority_name = (fields.get("priority") or {}).get("name", "").lower()
        priority_map = {
            "highest": NormalizedPriority.CRITICAL,
            "high": NormalizedPriority.HIGH,
            "medium": NormalizedPriority.MEDIUM,
            "low": NormalizedPriority.LOW,
            "lowest": NormalizedPriority.LOW,
        }
        status_category = (fields.get("status") or {}).get("statusCategory", {}) or {}
        status_key = status_category.get("key", "").lower()
        status_map = {
            "new": WorkItemStatus.TODO,
            "to do": WorkItemStatus.TODO,
            "indeterminate": WorkItemStatus.IN_PROGRESS,
            "done": WorkItemStatus.DONE,
        }

        parent_ref = None
        if fields.get("parent"):
            parent_ref = fields["parent"].get("key")

        issue_key = issue_data.get("key", "")
        return CoreArtifact(
            source_system=self.source_system,
            source_id=issue_data.get("id", issue_key),
            human_ref=issue_key,
            url=f"{self.base_url}/browse/{issue_key}" if issue_key else "",
            title=fields.get("summary", ""),
            description=self._adf_to_text(fields.get("description")),
            acceptance_criteria=[],
            type=(fields.get("issuetype") or {}).get("name", "Story"),
            status=status_map.get(status_key, WorkItemStatus.TODO),
            priority=priority_map.get(priority_name, NormalizedPriority.NONE),
            parent_ref=parent_ref,
            raw_metadata={
                "updatedAt": fields.get("updated"),
                "createdAt": fields.get("created"),
            },
        )

    def _format_optimization_comment(self, artifact: CoreArtifact) -> str:
        ac_text = (
            "\n".join(f"- {ac}" for ac in artifact.acceptance_criteria)
            if artifact.acceptance_criteria
            else "None specified"
        )
        return (
            "🤖 AI Optimization Suggestion\n\n"
            f"**Proposed Title:** {artifact.title}\n\n"
            "**Proposed Description:**\n"
            f"{artifact.description}\n\n"
            "**Acceptance Criteria:**\n"
            f"{ac_text}\n\n"
            "---\n"
            "*Review and apply manually if approved.*"
        )

    def _format_description(self, artifact: CoreArtifact) -> str:
        description = artifact.description or ""
        if artifact.acceptance_criteria:
            ac_text = "\n".join(f"- {ac}" for ac in artifact.acceptance_criteria)
            return f"{description}\n\nAcceptance Criteria:\n{ac_text}".strip()
        return description

    def _ensure_configured(self) -> None:
        if not self.api_token:
            raise ValueError("JIRA_TOKEN not configured.")
        if not self.base_url:
            raise ValueError("JIRA_BASE_URL not configured.")

    def _get_default_project_key(self) -> str:
        keys = [key.strip() for key in settings.jira_project_keys.split(",") if key.strip()]
        if not keys:
            raise ValueError("JIRA_PROJECT_KEYS not configured.")
        return keys[0]

    @staticmethod
    def _to_adf(text: str) -> Dict:
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
        if not paragraphs:
            paragraphs = [""]
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": paragraph}]}
                for paragraph in paragraphs
            ],
        }

    @staticmethod
    def _adf_to_text(adf: object) -> str:
        if not adf:
            return ""
        if isinstance(adf, str):
            return adf
        if isinstance(adf, list):
            return "\n".join(
                filter(None, (JiraEgressAdapter._adf_to_text(item) for item in adf))
            ).strip()
        if not isinstance(adf, dict):
            return str(adf)

        node_type = adf.get("type", "")
        content = adf.get("content", [])

        if node_type == "text":
            return adf.get("text", "")

        fragments = []
        for child in content:
            child_text = JiraEgressAdapter._adf_to_text(child)
            if child_text:
                fragments.append(child_text)

        text = "\n".join(fragments).strip()
        if node_type in {"paragraph", "heading"}:
            return text + "\n"
        return text
