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
                # Need to capture variables for executor
                model_name = settings.embedding_model
                text_input = text
                
                def _get_embedding():
                    from litellm import embedding as litellm_embedding
                    return litellm_embedding(
                        model=model_name,
                        input=[text_input],
                    )
                
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, _get_embedding)

                # Extract embedding from response
                # LiteLLM returns EmbeddingResponse object with data attribute
                if hasattr(response, "data") and isinstance(response.data, list) and len(response.data) > 0:
                    if isinstance(response.data[0], dict) and "embedding" in response.data[0]:
                        embedding = response.data[0]["embedding"]
                        if embedding and len(embedding) > 0:
                            return embedding
                    elif isinstance(response.data[0], list):
                        embedding = response.data[0]
                        if embedding and len(embedding) > 0:
                            return embedding
                
                # Fallback: try list format (older LiteLLM versions)
                if isinstance(response, list) and len(response) > 0:
                    if isinstance(response[0], dict) and "embedding" in response[0]:
                        embedding = response[0]["embedding"]
                        if embedding and len(embedding) > 0:
                            return embedding
                    elif isinstance(response[0], list):
                        embedding = response[0]
                        if embedding and len(embedding) > 0:
                            return embedding
                
                # If we get here, the response format is unexpected
                raise ValueError(
                    f"Unexpected embedding response format: {type(response)}. "
                    f"Response: {str(response)[:200]}"
                )

            except Exception as e:
                if attempt == max_retries - 1:
                    raise

                # Exponential backoff
                await asyncio.sleep(retry_delay * (2 ** attempt))

        return []
