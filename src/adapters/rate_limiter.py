"""Token Bucket rate limiter implementation."""

import asyncio
import time
from typing import Optional


class TokenBucket:
    """Token Bucket rate limiter for API rate limiting.

    Implements the Token Bucket algorithm to control request rates.
    Tokens are added at a constant rate, and requests consume tokens.
    """

    def __init__(self, capacity: int, refill_rate: float):
        """Initialize token bucket.

        Args:
            capacity: Maximum number of tokens in the bucket.
            refill_rate: Tokens added per second.
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire (default: 1).

        Raises:
            ValueError: If tokens requested exceeds capacity.
        """
        if tokens > self.capacity:
            raise ValueError(f"Requested {tokens} tokens exceeds capacity {self.capacity}")

        async with self._lock:
            await self._refill()
            while self.tokens < tokens:
                # Calculate wait time
                wait_time = (tokens - self.tokens) / self.refill_rate
                await asyncio.sleep(wait_time)
                await self._refill()

            self.tokens -= tokens

    async def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    async def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire.

        Returns:
            True if tokens were acquired, False otherwise.
        """
        async with self._lock:
            await self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
