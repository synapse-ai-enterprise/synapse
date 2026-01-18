"""Application Entry Point (FastAPI/CLI)."""

import asyncio
import sys
from typing import Dict

import click
from fastapi import FastAPI, Header, HTTPException, Request, Response

from src.adapters.ingress.linear_ingress import LinearIngressAdapter
from src.config import settings
from src.domain.schema import OptimizationRequest
from src.infrastructure.di import get_container
from src.infrastructure.queue import enqueue_optimization_request
from src.utils.logger import get_logger, setup_logging
from src.utils.tracing import get_trace_id, setup_tracing

# Setup logging and tracing
setup_logging()
setup_tracing()

logger = get_logger(__name__)

# FastAPI app
app = FastAPI(title="Agentic AI PoC", version="0.1.0")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/webhooks/linear")
async def linear_webhook(
    request: Request,
    linear_signature: str = Header(..., alias="linear-signature"),
):
    """Handle Linear webhook events.

    Args:
        request: FastAPI request object.
        linear_signature: HMAC signature from Linear.

    Returns:
        202 Accepted response.
    """
    try:
        # Get payload
        payload = await request.json()

        # Handle webhook via ingress adapter
        ingress_adapter = LinearIngressAdapter()
        optimization_request = ingress_adapter.handle_webhook(payload, linear_signature)

        if not optimization_request:
            # Event not relevant, return 200 OK
            return Response(status_code=200)

        # Enqueue optimization request
        enqueue_optimization_request(optimization_request.model_dump())

        logger.info(
            "webhook_received",
            artifact_id=optimization_request.artifact_id,
            trigger=optimization_request.trigger,
            trace_id=get_trace_id(),
        )

        return Response(status_code=202, content="Accepted")

    except ValueError as e:
        logger.error("webhook_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("webhook_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


@click.group()
def cli():
    """Agentic AI PoC CLI."""
    pass


@cli.command()
@click.argument("issue_id")
def optimize(issue_id: str):
    """Manually optimize a Linear issue.

    Args:
        issue_id: Linear issue ID to optimize.
    """
    import asyncio

    async def run_optimization():
        """Run optimization asynchronously."""
        # Create optimization request
        request = OptimizationRequest(
            artifact_id=issue_id,
            artifact_type="issue",
            source_system="linear",
            trigger="manual",
            dry_run=settings.dry_run,
        )

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
        from src.domain.use_cases import OptimizeArtifactUseCase

        use_case = OptimizeArtifactUseCase(
            issue_tracker=issue_tracker,
            knowledge_base=knowledge_base,
            llm_provider=llm_provider,
        )

        # Execute use case
        result = await use_case.execute(request)

        if result["success"]:
            click.echo(f"Optimization completed successfully for issue {issue_id}")
        else:
            click.echo(f"Optimization failed: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(1)

    asyncio.run(run_optimization())


if __name__ == "__main__":
    # Check if running as CLI or server
    if len(sys.argv) > 1:
        # CLI mode
        cli()
    else:
        # Server mode
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=8000)
