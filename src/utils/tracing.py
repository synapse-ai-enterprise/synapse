"""OpenTelemetry tracing setup."""

from opentelemetry import trace
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.config import settings


def setup_tracing() -> None:
    """Setup OpenTelemetry tracing with console exporter."""
    if not settings.enable_tracing:
        return

    # Create tracer provider
    provider = TracerProvider()
    trace.set_tracer_provider(provider)

    # Add console exporter
    console_exporter = ConsoleSpanExporter()
    span_processor = BatchSpanProcessor(console_exporter)
    provider.add_span_processor(span_processor)


def get_tracer(name: str):
    """Get tracer instance.

    Args:
        name: Tracer name.

    Returns:
        Tracer instance.
    """
    return trace.get_tracer(name)


def get_trace_id() -> str:
    """Get current trace ID.

    Returns:
        Trace ID as string.
    """
    span = trace.get_current_span()
    if span:
        context = span.get_span_context()
        return format(context.trace_id, "032x")
    return ""
