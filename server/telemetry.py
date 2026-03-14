"""Application-level OpenTelemetry setup for the API server.

Configures the OTLP exporter and auto-instruments FastAPI + SQLAlchemy.
Library code (geodata) only creates child spans — this module wires them
to an actual exporter so they flow to the OTel Collector.
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def init_tracing(app, engine) -> None:
    """Initialize OpenTelemetry tracing for the FastAPI server."""
    endpoint = os.environ.get("OTLP_ENDPOINT", "http://localhost:4317")

    resource = Resource.create({"service.name": "open-transit-api"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
