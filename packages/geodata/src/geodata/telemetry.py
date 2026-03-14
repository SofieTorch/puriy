"""Library-level tracer for geodata.

This module only creates a tracer — it does NOT configure exporters.
The application (API server, notebook, CLI) is responsible for setting up
the exporter via OpenTelemetry SDK. If no exporter is configured, spans
are silently discarded (no-op).
"""

from opentelemetry import trace

tracer = trace.get_tracer("geodata")
