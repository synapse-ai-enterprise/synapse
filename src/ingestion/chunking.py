"""Text chunking utilities using LangChain splitters."""

from typing import List

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def chunk_code(text: str, language: str = "python", chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """Chunk code using language-aware splitter.

    Args:
        text: Code text to chunk.
        language: Programming language (python, javascript, etc.).
        chunk_size: Maximum chunk size in characters.
        chunk_overlap: Overlap between chunks.

    Returns:
        List of chunked text strings.
    """
    splitter = RecursiveCharacterTextSplitter.from_language(
        language=language,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    documents = splitter.create_documents([text])
    return [doc.page_content for doc in documents]


def chunk_markdown_by_headers(text: str, max_tokens: int = 8000) -> List[str]:
    """Chunk Markdown by H2 headers if exceeding token limit.

    Args:
        text: Markdown text to chunk.
        max_tokens: Maximum tokens per chunk (rough estimate: 1 token ≈ 4 chars).

    Returns:
        List of chunked text strings.
    """
    max_chars = max_tokens * 4  # Rough token-to-char conversion

    if len(text) <= max_chars:
        return [text]

    # Split by H2 headers (##)
    chunks = []
    current_chunk = ""
    lines = text.split("\n")

    for line in lines:
        # Check if line is an H2 header
        if line.strip().startswith("## ") and not line.strip().startswith("###"):
            # Save current chunk if it exists
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"

            # If chunk exceeds limit, split it
            if len(current_chunk) > max_chars:
                # Try to split at paragraph boundaries
                paragraphs = current_chunk.split("\n\n")
                temp_chunk = ""
                for para in paragraphs:
                    if len(temp_chunk) + len(para) > max_chars and temp_chunk:
                        chunks.append(temp_chunk.strip())
                        temp_chunk = para + "\n\n"
                    else:
                        temp_chunk += para + "\n\n"
                current_chunk = temp_chunk

    # Add final chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]
