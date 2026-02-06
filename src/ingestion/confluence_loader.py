"""Confluence page loader for knowledge ingestion."""

from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiohttp

from src.config import settings
from src.domain.schema import UASKnowledgeUnit
from src.ingestion.chunking import chunk_markdown_by_headers
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def load_confluence_pages(space_keys: List[str]) -> List[UASKnowledgeUnit]:
    """Load Confluence pages and convert them into knowledge units.

    Args:
        space_keys: Confluence space keys to ingest.

    Returns:
        List of knowledge units derived from Confluence pages.

    Raises:
        ValueError: If Confluence settings are missing or the API request fails.
    """
    normalized_keys = [key.strip() for key in space_keys if key.strip()]
    if not normalized_keys:
        return []
    if not settings.confluence_token:
        raise ValueError("CONFLUENCE_TOKEN not configured")
    if not settings.confluence_base_url:
        raise ValueError("CONFLUENCE_BASE_URL not configured")

    base_url = settings.confluence_base_url.rstrip("/")
    api_base = _confluence_api_base(base_url)
    api_url = f"{api_base}/content"

    headers = {"Accept": "application/json"}
    auth: Optional[aiohttp.BasicAuth] = None
    if settings.confluence_user_email:
        auth = aiohttp.BasicAuth(settings.confluence_user_email, settings.confluence_token)
    else:
        headers["Authorization"] = f"Bearer {settings.confluence_token}"

    knowledge_units: List[UASKnowledgeUnit] = []
    async with aiohttp.ClientSession(headers=headers, auth=auth) as session:
        for space_key in normalized_keys:
            params = {
                "spaceKey": space_key,
                "type": "page",
                "limit": 50,
                "start": 0,
                "expand": "body.storage,version,space,metadata.labels,history",
            }
            while True:
                payload = await _fetch_confluence_page(session, api_url, params)
                pages = payload.get("results", [])
                knowledge_units.extend(
                    _pages_to_units(pages, base_url, space_key)
                )
                if not payload.get("_links", {}).get("next"):
                    break
                params["start"] = params["start"] + params["limit"]

    logger.info("confluence_ingestion_complete", count=len(knowledge_units))
    return knowledge_units


async def _fetch_confluence_page(
    session: aiohttp.ClientSession,
    api_url: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    async with session.get(api_url, params=params) as response:
        if response.status != 200:
            error_text = await response.text()
            raise ValueError(
                f"Confluence API error: {response.status}. Response: {error_text[:200]}"
            )
        return await response.json()


def _pages_to_units(
    pages: List[Dict[str, Any]],
    base_url: str,
    space_key: str,
) -> List[UASKnowledgeUnit]:
    units: List[UASKnowledgeUnit] = []
    for page in pages:
        title = page.get("title", "Untitled")
        body_html = (page.get("body") or {}).get("storage", {}).get("value", "")
        updated = (page.get("version") or {}).get("when") or datetime.now().isoformat()
        labels = [
            label.get("name", "")
            for label in (page.get("metadata") or {}).get("labels", {}).get("results", [])
            if label.get("name")
        ]
        web_ui = (page.get("_links") or {}).get("webui", "")
        # Confluence Cloud webui paths don't include /wiki, but the URLs need it
        if web_ui and not web_ui.startswith("/wiki"):
            web_ui = f"/wiki{web_ui}"
        page_url = f"{base_url}{web_ui}" if web_ui else base_url

        body_text = _html_to_text(body_html).strip()
        markdown = _format_page_markdown(
            title=title,
            body=body_text,
            space_key=space_key,
            updated=updated,
        )
        chunks = chunk_markdown_by_headers(markdown)
        for idx, chunk in enumerate(chunks):
            title_suffix = f" (chunk {idx + 1})" if len(chunks) > 1 else ""
            units.append(
                UASKnowledgeUnit(
                    id=str(uuid4()),
                    content=chunk,
                    summary=f"{title}{title_suffix}".strip(),
                    source="confluence",
                    last_updated=updated,
                    topics=labels or [space_key],
                    location=page_url,
                )
            )
    return units


def _format_page_markdown(
    title: str,
    body: str,
    space_key: str,
    updated: str,
) -> str:
    body_text = body.strip() or "No content available."
    metadata = [f"- Space: {space_key}", f"- Updated: {updated}"]
    metadata_text = "\n".join(metadata)
    return (
        f"# {title}\n\n"
        f"## Content\n{body_text}\n\n"
        f"## Metadata\n{metadata_text}\n"
    )


def _confluence_api_base(base_url: str) -> str:
    if base_url.endswith("/wiki"):
        return f"{base_url}/rest/api"
    if "/wiki" in base_url:
        return f"{base_url}/rest/api"
    return f"{base_url}/wiki/rest/api"


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        if tag in {"br", "p", "li", "h1", "h2", "h3", "h4"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "li"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._chunks.append(text + " ")

    def get_text(self) -> str:
        return "".join(self._chunks)


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(html)
    text = parser.get_text()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)
