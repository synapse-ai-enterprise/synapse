"""Notion page loader with Markdown conversion."""

import asyncio
from datetime import datetime
from typing import List
from uuid import uuid4

from notion_client import Client

from src.config import settings
from src.domain.schema import UASKnowledgeUnit
from src.ingestion.chunking import chunk_markdown_by_headers


async def load_notion_pages(root_page_id: str) -> List[UASKnowledgeUnit]:
    """Load Notion pages and convert to knowledge units.

    Args:
        root_page_id: Root page ID to start loading from.

    Returns:
        List of knowledge units from Notion pages.

    Raises:
        ValueError: If Notion token is not configured or API call fails.
    """
    if not settings.notion_token:
        raise ValueError("NOTION_TOKEN not configured")

    client = Client(auth=settings.notion_token)
    knowledge_units = []

    try:
        # Recursively load pages
        pages = await _load_pages_recursive(client, root_page_id)
        pages.append(root_page_id)  # Include root page

        for page_id in pages:
            try:
                # Get page content
                page_content = await _get_page_content(client, page_id)

                if not page_content["markdown"]:
                    continue

                # Chunk by headers if needed
                chunks = chunk_markdown_by_headers(page_content["markdown"])

                # Create knowledge units
                for idx, chunk in enumerate(chunks):
                    unit = UASKnowledgeUnit(
                        id=str(uuid4()),
                        content=chunk,
                        summary=page_content.get("title", f"Notion page chunk {idx + 1}"),
                        source="notion",
                        last_updated=page_content.get("last_updated", datetime.now().isoformat()),
                        topics=page_content.get("topics", []),
                        location=page_content.get("url", f"https://notion.so/{page_id}"),
                    )
                    knowledge_units.append(unit)

            except Exception as e:
                # Handle 404/401 errors with helpful message
                if "404" in str(e) or "401" in str(e):
                    raise ValueError(
                        f"Notion page {page_id} not accessible. "
                        "Please ensure the integration has been shared with the page in Notion."
                    ) from e
                continue  # Skip failed pages

    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Failed to load Notion pages: {str(e)}") from e

    return knowledge_units


async def _load_pages_recursive(client: Client, page_id: str) -> List[str]:
    """Recursively load all child pages.

    Args:
        client: Notion client.
        page_id: Starting page ID.

    Returns:
        List of child page IDs.
    """
    page_ids = []

    try:
        # Get child blocks
        children = client.blocks.children.list(block_id=page_id)

        for block in children.get("results", []):
            if block.get("type") == "child_page":
                child_id = block["id"]
                page_ids.append(child_id)
                # Recursively load children
                child_pages = await _load_pages_recursive(client, child_id)
                page_ids.extend(child_pages)

    except Exception:
        pass  # Skip if page doesn't have children or access denied

    return page_ids


async def _get_page_content(client: Client, page_id: str) -> dict:
    """Get page content and convert to Markdown.

    Args:
        client: Notion client.
        page_id: Page ID.

    Returns:
        Dictionary with markdown, title, url, last_updated, topics.
    """
    # Run blocking operations in executor
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_page_content_sync, client, page_id)


def _get_page_content_sync(client: Client, page_id: str) -> dict:
    """Synchronous page content retrieval.

    Args:
        client: Notion client.
        page_id: Page ID.

    Returns:
        Dictionary with page content.
    """
    # Get page properties
    page = client.pages.retrieve(page_id)

    # Extract title
    title = "Untitled"
    if "properties" in page:
        for prop_name, prop_value in page["properties"].items():
            if prop_value.get("type") == "title" and prop_value.get("title"):
                title = "".join([text.get("plain_text", "") for text in prop_value["title"]])
                break

    # Get page blocks and convert to Markdown
    blocks = client.blocks.children.list(block_id=page_id)
    markdown = _blocks_to_markdown(blocks.get("results", []))

    # Get URL
    url = page.get("url", f"https://notion.so/{page_id}")
    if not url.startswith("http"):
        url = f"https://notion.so/{url}"

    # Extract last updated time
    last_updated = ""
    if "last_edited_time" in page:
        last_updated = page["last_edited_time"]

    # Extract topics from page properties (if any)
    topics = []
    if "properties" in page:
        for prop_name, prop_value in page["properties"].items():
            if prop_value.get("type") == "multi_select":
                topics.extend([opt["name"] for opt in prop_value.get("multi_select", [])])

    return {
        "markdown": markdown,
        "title": title,
        "url": url,
        "last_updated": last_updated,
        "topics": topics,
    }


def _blocks_to_markdown(blocks: List[dict]) -> str:
    """Convert Notion blocks to Markdown.

    Args:
        blocks: List of Notion block objects.

    Returns:
        Markdown string.
    """
    markdown_lines = []

    for block in blocks:
        block_type = block.get("type", "")
        content = ""

        if block_type == "paragraph":
            rich_text = block.get("paragraph", {}).get("rich_text", [])
            content = "".join([text.get("plain_text", "") for text in rich_text])

        elif block_type == "heading_1":
            rich_text = block.get("heading_1", {}).get("rich_text", [])
            text = "".join([text.get("plain_text", "") for text in rich_text])
            content = f"# {text}"

        elif block_type == "heading_2":
            rich_text = block.get("heading_2", {}).get("rich_text", [])
            text = "".join([text.get("plain_text", "") for text in rich_text])
            content = f"## {text}"

        elif block_type == "heading_3":
            rich_text = block.get("heading_3", {}).get("rich_text", [])
            text = "".join([text.get("plain_text", "") for text in rich_text])
            content = f"### {text}"

        elif block_type == "bulleted_list_item":
            rich_text = block.get("bulleted_list_item", {}).get("rich_text", [])
            text = "".join([text.get("plain_text", "") for text in rich_text])
            content = f"- {text}"

        elif block_type == "numbered_list_item":
            rich_text = block.get("numbered_list_item", {}).get("rich_text", [])
            text = "".join([text.get("plain_text", "") for text in rich_text])
            content = f"1. {text}"

        elif block_type == "code":
            rich_text = block.get("code", {}).get("rich_text", [])
            code_text = "".join([text.get("plain_text", "") for text in rich_text])
            language = block.get("code", {}).get("language", "")
            content = f"```{language}\n{code_text}\n```"

        elif block_type == "quote":
            rich_text = block.get("quote", {}).get("rich_text", [])
            text = "".join([text.get("plain_text", "") for text in rich_text])
            content = f"> {text}"

        elif block_type == "divider":
            content = "---"

        if content:
            markdown_lines.append(content)

        # Recursively process children
        if "children" in block and block["children"]:
            child_markdown = _blocks_to_markdown(block["children"])
            if child_markdown:
                markdown_lines.append(child_markdown)

    return "\n\n".join(markdown_lines)
