"""LiteLLM adapter implementing ILLMProvider."""

import asyncio
from typing import Dict, List, Optional

import litellm
from litellm import completion, embedding

from src.config import settings
from src.domain.interfaces import ILLMProvider


class LiteLLMAdapter(ILLMProvider):
    """LiteLLM adapter for LLM operations."""

    def __init__(self, model: Optional[str] = None):
        """Initialize adapter with model configuration.

        Args:
            model: Model name (defaults to config setting).
        """
        self.model = model or settings.litellm_model

        # Configure LiteLLM
        if settings.openai_api_key:
            litellm.api_key = settings.openai_api_key

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Generate a chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model name (overrides default).
            temperature: Sampling temperature.

        Returns:
            Generated text response.

        Raises:
            Exception: If completion fails after retries.
        """
        model_name = model or self.model
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                # Run blocking completion in executor
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: completion(
                        model=model_name,
                        messages=messages,
                        temperature=temperature,
                    ),
                )

                # Extract content from response
                if hasattr(response, "choices") and len(response.choices) > 0:
                    return response.choices[0].message.content or ""

                return ""

            except Exception as e:
                if attempt == max_retries - 1:
                    raise

                # Exponential backoff
                await asyncio.sleep(retry_delay * (2 ** attempt))

        return ""

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.

        Raises:
            Exception: If embedding fails after retries.
        """
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                # Run blocking embedding in executor
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: embedding(
                        model=settings.embedding_model,
                        input=[text],
                    ),
                )

                # Extract embedding from response
                if isinstance(response, list) and len(response) > 0:
                    if isinstance(response[0], dict) and "embedding" in response[0]:
                        return response[0]["embedding"]
                    elif isinstance(response[0], list):
                        return response[0]

                return []

            except Exception as e:
                if attempt == max_retries - 1:
                    raise

                # Exponential backoff
                await asyncio.sleep(retry_delay * (2 ** attempt))

        return []
