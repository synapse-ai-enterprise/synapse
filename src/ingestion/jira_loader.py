"""Jira issue loader for knowledge ingestion."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiohttp

from src.config import settings
from src.domain.schema import UASKnowledgeUnit
from src.ingestion.chunking import chunk_markdown_by_headers
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def load_jira_issues(project_keys: List[str]) -> List[UASKnowledgeUnit]:
    """Load Jira issues and convert them into knowledge units.

    Args:
        project_keys: Jira project keys to ingest.

    Returns:
        List of knowledge units derived from Jira issues.

    Raises:
        ValueError: If Jira settings are missing or the API request fails.
    """
    normalized_keys = [key.strip() for key in project_keys if key.strip()]
    if not normalized_keys:
        return []
    if not settings.jira_token:
        raise ValueError("JIRA_TOKEN not configured")
    if not settings.jira_base_url:
        raise ValueError("JIRA_BASE_URL not configured")

    base_url = settings.jira_base_url.rstrip("/")
    api_url = f"{base_url}/rest/api/3/search/jql"

    jql = "project in ({keys}) order by updated desc".format(
        keys=",".join(normalized_keys)
    )
    params = {
        "jql": jql,
        "fields": "summary,description,updated,created,issuetype,project",
        "maxResults": 50,
        "startAt": 0,
    }

    headers = {"Accept": "application/json"}
    auth: Optional[aiohttp.BasicAuth] = None
    if settings.jira_user_email:
        auth = aiohttp.BasicAuth(settings.jira_user_email, settings.jira_token)
    else:
        headers["Authorization"] = f"Bearer {settings.jira_token}"

    issues: List[Dict[str, Any]] = []
    async with aiohttp.ClientSession(headers=headers, auth=auth) as session:
        while True:
            payload = await _fetch_jira_page(session, api_url, params)
            issues.extend(payload.get("issues", []))
            total = payload.get("total", len(issues))
            start_at = params["startAt"]
            max_results = params["maxResults"]
            if start_at + max_results >= total:
                break
            params["startAt"] = start_at + max_results

    knowledge_units: List[UASKnowledgeUnit] = []
    for issue in issues:
        key = issue.get("key", "UNKNOWN")
        fields = issue.get("fields", {}) or {}
        summary = fields.get("summary", "")
        description = _adf_to_text(fields.get("description"))
        updated = fields.get("updated") or datetime.now().isoformat()
        project_key = (fields.get("project") or {}).get("key", "")
        issue_type = (fields.get("issuetype") or {}).get("name", "")
        issue_url = f"{base_url}/browse/{key}"

        markdown = _format_issue_markdown(
            key=key,
            summary=summary,
            description=description,
            project_key=project_key,
            issue_type=issue_type,
            updated=updated,
        )
        chunks = chunk_markdown_by_headers(markdown)
        for idx, chunk in enumerate(chunks):
            title_suffix = f" (chunk {idx + 1})" if len(chunks) > 1 else ""
            knowledge_units.append(
                UASKnowledgeUnit(
                    id=str(uuid4()),
                    content=chunk,
                    summary=f"{key}: {summary}{title_suffix}".strip(),
                    source="jira",
                    last_updated=updated,
                    topics=[project_key] if project_key else [],
                    location=issue_url,
                )
            )

    logger.info("jira_ingestion_complete", count=len(knowledge_units))
    return knowledge_units


async def _fetch_jira_page(
    session: aiohttp.ClientSession,
    api_url: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Fetch a page of Jira issues."""
    async with session.get(api_url, params=params) as response:
        if response.status != 200:
            error_text = await response.text()
            raise ValueError(
                f"Jira API error: {response.status}. Response: {error_text[:200]}"
            )
        return await response.json()


def _format_issue_markdown(
    key: str,
    summary: str,
    description: str,
    project_key: str,
    issue_type: str,
    updated: str,
) -> str:
    """Format Jira issue fields into markdown for chunking."""
    description_text = description.strip() or "No description provided."
    metadata = []
    if project_key:
        metadata.append(f"- Project: {project_key}")
    if issue_type:
        metadata.append(f"- Type: {issue_type}")
    if updated:
        metadata.append(f"- Updated: {updated}")
    metadata_text = "\n".join(metadata) if metadata else "No metadata available."
    return (
        f"# {key}: {summary}\n\n"
        f"## Description\n{description_text}\n\n"
        f"## Metadata\n{metadata_text}\n"
    )


def _adf_to_text(adf: Any) -> str:
    """Convert Jira Atlassian Document Format to plain text."""
    if not adf:
        return ""
    if isinstance(adf, str):
        return adf
    if isinstance(adf, list):
        return "\n".join(filter(None, (_adf_to_text(item) for item in adf))).strip()
    if not isinstance(adf, dict):
        return str(adf)

    node_type = adf.get("type", "")
    content = adf.get("content", [])

    if node_type == "text":
        return adf.get("text", "")

    fragments: List[str] = []
    for child in content:
        child_text = _adf_to_text(child)
        if child_text:
            fragments.append(child_text)

    text = "\n".join(fragments).strip()
    if node_type in {"paragraph", "heading"}:
        return text + "\n"
    return text
