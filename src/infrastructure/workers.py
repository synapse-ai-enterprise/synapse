"""Worker pool for async processing."""

import asyncio
from typing import Any

from src.domain.schema import OptimizationRequest
from src.domain.use_cases import OptimizeArtifactUseCase
from src.infrastructure.di import get_container


def process_optimization(request_dict: dict) -> None:
    """Process optimization request (called by RQ worker).

    Args:
        request_dict: Serialized OptimizationRequest dictionary.
    """
    # Deserialize request
    from src.domain.schema import OptimizationRequest

    request = OptimizationRequest(**request_dict)

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
    issue_tracker = container.get_issue_tracker()

    # Create use case
    use_case = OptimizeArtifactUseCase(
        issue_tracker=issue_tracker,
        knowledge_base=knowledge_base,
        llm_provider=llm_provider,
    )

    # Execute use case
    asyncio.run(use_case.execute(request))
