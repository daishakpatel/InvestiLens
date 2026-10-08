"""Observability: structured logging (app/utils/logging.py), tracing, and metrics (ADR-0021).

Split by concern so each can be imported independently (and mocked independently in tests):
- `tracing.py` — OpenTelemetry spans (OBS-001).
- `metrics.py` — Prometheus counters/histograms/gauges + the `/metrics` endpoint (OBS-002).
- `alerts.py` — pure, DB/metrics-driven alert evaluation, testable without Alertmanager (OBS-003).
"""
