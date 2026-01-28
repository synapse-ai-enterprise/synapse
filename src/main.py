"""Application Entry Point (FastAPI/CLI)."""

import asyncio
import json
import sys

import click
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from src.config import settings
from src.domain.schema import (
    IntegrationConnectRequest,
    IntegrationScopeUpdate,
    IntegrationTestResult,
    OptimizationRequest,
    StoryWritingRequest,
)
from src.infrastructure.di import get_container
from src.infrastructure.queue import enqueue_optimization_request
from src.application.handlers.optimize_artifact_handler import OptimizeArtifactHandler
from src.application.handlers.story_writing_handler import StoryWritingHandler
from src.utils.logger import get_logger, setup_logging
from src.utils.tracing import get_trace_id, setup_tracing

# Setup logging and tracing
setup_logging()
setup_tracing()

logger = get_logger(__name__)

# FastAPI app
app = FastAPI(title="Agentic AI PoC", version="0.1.0")
default_cors_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]
cors_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or default_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Log startup configuration for monitoring."""
    logger.info(
        "api_startup",
        issue_tracker_provider=settings.issue_tracker_provider,
        webhook_provider=settings.webhook_provider,
        embedding_model=settings.embedding_model,
        vector_store_path=settings.vector_store_path,
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/webhooks/issue-tracker")
async def issue_tracker_webhook(request: Request):
    """Handle issue tracker webhook events.

    Args:
        request: FastAPI request object.

    Returns:
        202 Accepted response.
    """
    try:
        # Get payload
        payload = await request.json()

        # Handle webhook via ingress adapter
        container = get_container()
        ingress_adapter = container.get_webhook_ingress()
        optimization_request = ingress_adapter.handle_webhook(payload, request.headers)

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


@app.post("/api/story-writing")
async def run_story_writing(request: StoryWritingRequest):
    """Run the product story writing workflow."""
    try:
        logger.info(
            "story_writing_request",
            flow=request.flow,
            epic_id=request.epic_id,
            project_id=request.project_id,
            trace_id=get_trace_id(),
        )
        container = get_container()
        llm_provider = container.get_llm_provider()
        event_bus = container.get_event_bus()
        memory_store = container.get_memory_store()
        workflow_registry = container.get_workflow_registry()

        async def embedding_fn(text: str) -> list[float]:
            return await llm_provider.get_embedding(text)

        knowledge_base = container.get_knowledge_base(
            lambda text: asyncio.run(embedding_fn(text))
        )

        handler = StoryWritingHandler(
            knowledge_base=knowledge_base,
            llm_provider=llm_provider,
            event_bus=event_bus,
            memory_store=memory_store,
            workflow_registry=workflow_registry,
        )

        result = await handler.handle(request)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        logger.info(
            "story_writing_success",
            flow=request.flow,
            trace_id=get_trace_id(),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("story_writing_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/story-writing/stream")
async def stream_story_writing(request: StoryWritingRequest):
    """Stream story writing workflow progress via SSE."""
    queue: asyncio.Queue = asyncio.Queue()

    class StreamProgressCallback:
        async def on_node_start(self, node_name: str, state: dict) -> None:
            await queue.put({"event": "node_start", "node": node_name})

        async def on_node_complete(self, node_name: str, state: dict) -> None:
            await queue.put({"event": "node_complete", "node": node_name})

        async def on_iteration_update(self, iteration: int, state: dict) -> None:
            await queue.put({"event": "iteration", "iteration": iteration})

    async def run_workflow():
        try:
            container = get_container()
            llm_provider = container.get_llm_provider()
            event_bus = container.get_event_bus()
            memory_store = container.get_memory_store()
            workflow_registry = container.get_workflow_registry()

            async def embedding_fn(text: str) -> list[float]:
                return await llm_provider.get_embedding(text)

            knowledge_base = container.get_knowledge_base(
                lambda text: asyncio.run(embedding_fn(text))
            )

            handler = StoryWritingHandler(
                knowledge_base=knowledge_base,
                llm_provider=llm_provider,
                event_bus=event_bus,
                memory_store=memory_store,
                workflow_registry=workflow_registry,
                progress_callback=StreamProgressCallback(),
            )

            result = await handler.handle(request)
            await queue.put({"event": "done", "result": result})
        except Exception as exc:
            logger.error("story_writing_stream_error", error=str(exc), trace_id=get_trace_id())
            await queue.put({"event": "error", "message": str(exc)})
        finally:
            await queue.put(None)

    async def event_stream():
        task = asyncio.create_task(run_workflow())
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"
        await task

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/integrations")
async def list_integrations():
    """List integration status and configuration."""
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        integrations = admin_store.list_integrations()
        return {"integrations": [integration.model_dump() for integration in integrations]}
    except Exception as e:
        logger.error("integrations_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/integrations/{name}/connect")
async def connect_integration(name: str, payload: IntegrationConnectRequest):
    """Connect an integration using a token (simulated)."""
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        integration = admin_store.connect_integration(name, payload)
        return integration.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("integrations_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/integrations/{name}/test", response_model=IntegrationTestResult)
async def test_integration(name: str):
    """Test an integration connection (simulated)."""
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        return admin_store.test_integration(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("integrations_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/api/integrations/{name}/scopes")
async def update_integration_scopes(name: str, payload: IntegrationScopeUpdate):
    """Update integration scopes (simulated)."""
    try:
        container = get_container()
        admin_store = container.get_admin_store()
        integration = admin_store.update_scopes(name, payload)
        return integration.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("integrations_error", error=str(e), trace_id=get_trace_id())
        raise HTTPException(status_code=500, detail="Internal server error")


@click.group()
def cli():
    """Agentic AI PoC CLI."""
    pass


@cli.command()
@click.argument("issue_id")
def optimize(issue_id: str):
    """Manually optimize an issue.

    Args:
        issue_id: Issue ID to optimize.
    """
    import asyncio

    async def run_optimization():
        """Run optimization asynchronously."""
        # Create optimization request
        request = OptimizationRequest(
            artifact_id=issue_id,
            artifact_type="issue",
            source_system=settings.issue_tracker_provider.strip().lower(),
            trigger="manual",
            dry_run=settings.dry_run,
        )

        # Get dependencies from DI container
        container = get_container()
        llm_provider = container.get_llm_provider()
        event_bus = container.get_event_bus()
        memory_store = container.get_memory_store()
        workflow_registry = container.get_workflow_registry()

        # Create embedding function wrapper
        async def embedding_fn(text: str) -> list[float]:
            return await llm_provider.get_embedding(text)

        # Get knowledge base with embedding function
        knowledge_base = container.get_knowledge_base(
            lambda text: asyncio.run(embedding_fn(text))
        )
        issue_tracker = container.get_issue_tracker()

        handler = OptimizeArtifactHandler(
            issue_tracker=issue_tracker,
            knowledge_base=knowledge_base,
            llm_provider=llm_provider,
            event_bus=event_bus,
            memory_store=memory_store,
            workflow_registry=workflow_registry,
        )

        # Execute handler
        result = await handler.handle(request)

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
