"""Message queue setup using Redis/RQ."""

from typing import Optional

import redis
from rq import Queue

from src.config import settings


def get_queue(name: str = "optimization") -> Queue:
    """Get Redis queue instance.

    Args:
        name: Queue name.

    Returns:
        RQ Queue instance.
    """
    redis_conn = redis.from_url(settings.redis_url)
    return Queue(name, connection=redis_conn)


def enqueue_optimization_request(request) -> None:
    """Enqueue an optimization request.

    Args:
        request: OptimizationRequest to enqueue.
    """
    queue = get_queue()
    queue.enqueue("src.infrastructure.workers.process_optimization", request)
