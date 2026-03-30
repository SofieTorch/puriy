"""Standalone OpenTelemetry setup for Marimo notebooks.

Call init_tracing() once in a notebook cell to send traces to the OTel Collector.
This sets up the same exporter the API server uses, so geodata spans flow
to Tempo/Grafana when running from notebooks too.
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

_initialized = False


def init_tracing(service_name: str = "transit-lab") -> None:
    """Configure OTLP trace exporter for notebook use.

    Uses SimpleSpanProcessor (not Batch) so spans are exported immediately
    rather than buffered — important for notebooks where cells run quickly.

    Safe to call multiple times — only the first call has effect.
    """
    global _initialized
    if _initialized:
        return

    endpoint = os.environ.get("OTLP_ENDPOINT", "http://localhost:4317")

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    try:
        import grpc
        channel = grpc.insecure_channel(endpoint.replace("http://", ""))
        grpc.channel_ready_future(channel).result(timeout=1)
        channel.close()
        provider.add_span_processor(
            SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
        )
    except Exception:
        # Collector not reachable — tracing is a no-op, spans are recorded
        # but not exported.  This avoids blocking notebook cells.
        pass

    trace.set_tracer_provider(provider)
    _initialized = True
