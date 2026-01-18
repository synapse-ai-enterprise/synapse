"""GitHub repository loader using recursive Git Tree API."""

import asyncio
import base64
from typing import List
from uuid import uuid4

import aiohttp
from github import Github

from src.config import settings
from src.domain.schema import UASKnowledgeUnit
from src.ingestion.chunking import chunk_code


async def load_repository(repo_name: str) -> List[UASKnowledgeUnit]:
    """Load repository content using recursive Git Tree API.

    Args:
        repo_name: Repository name in format 'owner/repo'.

    Returns:
        List of knowledge units from the repository.

    Raises:
        ValueError: If repository name is invalid or API call fails.
    """
    if not settings.github_token:
        raise ValueError("GITHUB_TOKEN not configured")

    # Initialize GitHub client
    github = Github(settings.github_token)

    try:
        # Get repository
        repo = github.get_repo(repo_name)

        # Get default branch
        default_branch = repo.default_branch
        branch_sha = repo.get_branch(default_branch).commit.sha

        # Get recursive tree
        tree = repo.get_git_tree(branch_sha, recursive=True)

        # Filter files by extension and exclude patterns
        code_extensions = {
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".java",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".cpp",
            ".c",
            ".h",
            ".hpp",
            ".cs",
            ".swift",
            ".kt",
            ".scala",
            ".clj",
            ".sh",
            ".yaml",
            ".yml",
            ".json",
            ".toml",
            ".md",
            ".txt",
            ".rst",
        }

        exclude_patterns = {
            "node_modules",
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "env",
            "dist",
            "build",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        }

        # Filter files
        file_entries = []
        for item in tree.tree:
            if item.type == "blob" and any(item.path.endswith(ext) for ext in code_extensions):
                # Check exclude patterns
                if not any(pattern in item.path for pattern in exclude_patterns):
                    file_entries.append(item)

        # Fetch file contents in batches
        knowledge_units = []
        batch_size = 10

        async with aiohttp.ClientSession() as session:
            for i in range(0, len(file_entries), batch_size):
                batch = file_entries[i : i + batch_size]
                tasks = [_fetch_file_content(session, repo, item) for item in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                for item, result in zip(batch, batch_results):
                    if isinstance(result, Exception):
                        continue  # Skip failed files

                    content, file_path = result
                    if not content:
                        continue

                    # Determine language from extension
                    language = "python"  # Default
                    if file_path.endswith((".js", ".jsx", ".ts", ".tsx")):
                        language = "javascript"
                    elif file_path.endswith((".java",)):
                        language = "java"
                    elif file_path.endswith((".go",)):
                        language = "go"
                    elif file_path.endswith((".rs",)):
                        language = "rust"
                    elif file_path.endswith((".rb",)):
                        language = "ruby"
                    elif file_path.endswith((".cpp", ".c", ".h", ".hpp")):
                        language = "cpp"
                    elif file_path.endswith((".cs",)):
                        language = "csharp"
                    elif file_path.endswith((".swift",)):
                        language = "swift"
                    elif file_path.endswith((".kt",)):
                        language = "kotlin"
                    elif file_path.endswith((".scala",)):
                        language = "scala"
                    elif file_path.endswith((".clj",)):
                        language = "clojure"
                    elif file_path.endswith((".sh",)):
                        language = "bash"

                    # Chunk code
                    chunks = chunk_code(content, language=language)

                    # Create knowledge units for each chunk
                    for idx, chunk in enumerate(chunks):
                        unit = UASKnowledgeUnit(
                            id=str(uuid4()),
                            content=chunk,
                            summary=f"Code chunk {idx + 1} from {file_path}",
                            source="github",
                            last_updated=repo.updated_at.isoformat() if repo.updated_at else "",
                            topics=[language, file_path.split("/")[-1]],
                            location=f"https://github.com/{repo_name}/blob/{default_branch}/{file_path}",
                        )
                        knowledge_units.append(unit)

                # Rate limiting: wait between batches
                if i + batch_size < len(file_entries):
                    await asyncio.sleep(0.5)  # Small delay to respect rate limits

    except Exception as e:
        raise ValueError(f"Failed to load repository {repo_name}: {str(e)}") from e

    return knowledge_units


async def _fetch_file_content(
    session: aiohttp.ClientSession, repo, item
) -> tuple[str, str]:
    """Fetch file content from GitHub.

    Args:
        session: aiohttp session.
        repo: GitHub repository object.
        item: Git tree item.

    Returns:
        Tuple of (content, file_path).
    """
    try:
        # Use GitHub API to get file content
        file = repo.get_contents(item.path)
        if file.encoding == "base64":
            content = base64.b64decode(file.content).decode("utf-8", errors="ignore")
        else:
            content = file.content

        return content, item.path
    except Exception:
        return "", item.path
