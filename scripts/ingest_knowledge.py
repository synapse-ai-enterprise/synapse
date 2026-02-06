"""Run ingestion pipeline for GitHub and Notion."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.domain.schema import UASKnowledgeUnit
from src.infrastructure.di import get_container
from src.ingestion.confluence_loader import load_confluence_pages
from src.ingestion.github_loader import load_repository
from src.ingestion.jira_loader import load_jira_issues
from src.ingestion.notion_loader import load_notion_pages
from src.utils.logger import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


async def ingest_knowledge() -> None:
    """Run ingestion pipeline for GitHub and Notion."""
    logger.info("starting_ingestion")

    # Get dependencies from DI container
    container = get_container()
    llm_provider = container.get_llm_provider()

    # Create embedding function wrapper
    async def embedding_fn(text: str) -> list[float]:
        return await llm_provider.get_embedding(text)

    # Get knowledge base with embedding function
    knowledge_base = container.get_knowledge_base(
        lambda text: asyncio.run(embedding_fn(text))
    )

    # Initialize database
    await knowledge_base.initialize_db()

    all_documents: list[UASKnowledgeUnit] = []

    # Ingest GitHub repository
    if settings.github_repo:
        try:
            logger.info("ingesting_github", repo=settings.github_repo)
            github_docs = await load_repository(settings.github_repo)
            all_documents.extend(github_docs)
            logger.info("github_ingestion_complete", count=len(github_docs))
        except Exception as e:
            logger.error("github_ingestion_error", error=str(e))

    # Ingest Notion pages
    if settings.notion_root_page_id:
        try:
            logger.info("ingesting_notion", page_id=settings.notion_root_page_id)
            notion_docs = await load_notion_pages(settings.notion_root_page_id)
            all_documents.extend(notion_docs)
            logger.info("notion_ingestion_complete", count=len(notion_docs))
        except Exception as e:
            logger.error("notion_ingestion_error", error=str(e))

    # Ingest Jira issues
    jira_keys = [key.strip() for key in settings.jira_project_keys.split(",") if key.strip()]
    if jira_keys:
        try:
            logger.info("ingesting_jira", projects=jira_keys)
            jira_docs = await load_jira_issues(jira_keys)
            all_documents.extend(jira_docs)
            logger.info("jira_ingestion_complete", count=len(jira_docs))
        except Exception as e:
            logger.error("jira_ingestion_error", error=str(e))

    # Ingest Confluence pages
    confluence_spaces = [
        key.strip() for key in settings.confluence_space_keys.split(",") if key.strip()
    ]
    if confluence_spaces:
        try:
            logger.info("ingesting_confluence", spaces=confluence_spaces)
            confluence_docs = await load_confluence_pages(confluence_spaces)
            all_documents.extend(confluence_docs)
            logger.info("confluence_ingestion_complete", count=len(confluence_docs))
        except Exception as e:
            logger.error("confluence_ingestion_error", error=str(e))

    # Add documents to knowledge base
    if all_documents:
        logger.info("adding_documents", count=len(all_documents))
        await knowledge_base.add_documents(all_documents)
        logger.info("ingestion_complete", total_documents=len(all_documents))
    else:
        logger.warning("no_documents_ingested")


if __name__ == "__main__":
    asyncio.run(ingest_knowledge())
