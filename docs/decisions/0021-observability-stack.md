# ADR-0021: Observability stack (structlog, OpenTelemetry, Prometheus)

- **Status:** Accepted
- **Date:** 2026-10-07
- **Spec refs:** §20 (Observability stack), §28, OBS-001…005

## Problem

Phase 5c must make "life of a question" debuggable end to end (request → retrieval → LLM →
citation validator) and give real dashboards/alerts, without standing up infra this
portfolio-sized project can't run continuously (spec §31.3: "don't over-engineer"). We need a
stack that works identically offline in tests/CI and in a real deployment.

## Decision

- **Logging:** `structlog` configured for JSON output (`app/utils/logging.py` keeps its existing
  `get_logger`/`log_event`/`bind_request_id` call-site API — ~10 modules are unaffected — but now
  backs onto structlog with `contextvars` merging so `request_id` auto-attaches to every log line,
  and a redaction processor drops/masks any field key matching
  `password|secret|token|authorization|api_key` (OBS-004).
- **Tracing:** `opentelemetry-sdk` + `opentelemetry-instrumentation-fastapi`. A `ConsoleSpanExporter`
  by default (zero infra, visible in `make check`/dev logs); set `otel_exporter_otlp_endpoint` to
  point at a real collector (Jaeger/Tempo/Honeycomb) in a real deployment — no code change needed.
  Spans are added across API → retrieval (`app/rag/pipeline.py`) → LLM (`app/research/generator.py`,
  `app/chat/service.py`) → citation validator (`app/citation/pipeline.py`), carrying `company`,
  `intent`, and `prompt_version` span attributes (OBS-001).
- **Metrics:** `prometheus-client`, exposed on `GET /metrics` (no auth — standard scrape
  convention; not linked from the frontend). Histograms for API/LLM/retrieval/DB latency, counters
  for job/ingestion failures and citation rejections, gauges for ingestion lag and per-source
  freshness. Grafana dashboard JSON lives in `observability/grafana/dashboards/` and an optional
  `prometheus`+`grafana` pair is added to `docker-compose.yml` (commented, like the existing MinIO
  block) so a real deployment can `docker compose --profile observability up`.
- **Alerting:** Prometheus alerting rules in `observability/alerts.rules.yml` mirror the exact
  thresholds in `app/observability/alerts.py` — a pure, DB/metrics-driven function
  (`evaluate_alerts`) that is unit-tested without any running Prometheus/Alertmanager, satisfying
  the DoD's "alerts fire correctly in a simulated failure" without infra in CI.
- **Not adopted:** Sentry and a hosted LLM-tracing tool (Langfuse/Helicone). The spec lists them as
  optional alternatives; structured JSON logs + `llm_calls`/`retrieval_logs`/`claim_verifications`
  tables already give equivalent visibility for a project this size, and adding a third-party SaaS
  dependency with no account/budget would be unverifiable in this environment.

## Consequences

Every request is traceable via `request_id` across logs and spans with zero required
infrastructure (tests and local dev get console/JSON output); a real deployment gets real
dashboards and alerts by pointing two env vars (OTLP endpoint, Prometheus scrape target) at managed
services. The cost: metrics/traces are process-local (no cross-worker aggregation) until a real
Prometheus/OTel collector scrapes them — acceptable for a single-process deployment target (§31.3)
and revisited if the app is horizontally scaled.
