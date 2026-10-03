"""API contract tests (spec §24, Phase 0c DoD). Offline — no DB or network.

Covers: the published OpenAPI matches the app (API-005 no silent contract drift), route
ordering (`/companies/search` before `/companies/{ticker}`), RFC 7807 error shape (API-001),
and the request-ID echo (API-007).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import API_V1_PREFIX, REQUEST_ID_HEADER, app

_OPENAPI_PATH = Path(__file__).resolve().parents[3] / "docs" / "openapi.json"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_published_openapi_matches_app() -> None:
    """docs/openapi.json must match the app's generated spec (run `make openapi` if this fails)."""
    published = json.loads(_OPENAPI_PATH.read_text())
    current = json.loads(json.dumps(app.openapi(), sort_keys=True))
    assert published == current, "OpenAPI drift: regenerate with `make openapi`"


def test_every_spec_endpoint_group_is_registered() -> None:
    """Every §24.2 endpoint group appears in the spec."""
    paths = app.openapi()["paths"]
    required = [
        "/health",
        "/ready",
        "/meta/data-freshness/{ticker}",
        "/companies/search",
        "/companies/{ticker}",
        "/companies/{ticker}/financials",
        "/companies/{ticker}/metrics/{metric_name}/lineage",
        "/companies/{ticker}/valuation",
        "/companies/{ticker}/prices",
        "/companies/{ticker}/filings",
        "/companies/{ticker}/news",
        "/companies/{ticker}/research/latest",
        "/filings/{filing_id}",
        "/filings/{filing_id}/sections",
        "/research",
        "/research/jobs/{job_id}",
        "/research/jobs/{job_id}/events",
        "/research/{research_id}",
        "/sources/{source_id}",
        "/chat",
        "/chat/stream",
        "/auth/register",
        "/auth/login",
        "/watchlists",
        "/alerts",
        "/admin/ingestion-runs",
    ]
    for route in required:
        assert f"{API_V1_PREFIX}{route}" in paths, f"missing endpoint: {route}"


def test_search_resolves_before_ticker(client: TestClient) -> None:
    """`/companies/search` must hit the search handler, not the `{ticker}` handler."""
    search = client.get(f"{API_V1_PREFIX}/companies/search", params={"q": "nvidia"})
    assert search.status_code == 200
    assert isinstance(search.json(), list)  # search returns a list of hits

    company = client.get(f"{API_V1_PREFIX}/companies/NVDA")
    assert company.status_code == 200
    assert "company" in company.json()  # ticker returns a single company envelope


def test_error_uses_rfc7807_shape(client: TestClient) -> None:
    resp = client.get(f"{API_V1_PREFIX}/research/1/diff", params={"against": "2"})  # 501 stub
    assert resp.status_code == 501
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["status"] == 501
    assert body["title"] == "Not Implemented"
    assert body["request_id"]  # API-007 populated in the problem body


def test_validation_error_is_problem_json(client: TestClient) -> None:
    resp = client.get(f"{API_V1_PREFIX}/companies/search")  # missing required ?q
    assert resp.status_code == 422
    assert resp.headers["content-type"] == "application/problem+json"
    assert resp.json()["errors"], "validation errors[] must be populated"


def test_request_id_is_echoed(client: TestClient) -> None:
    resp = client.get(f"{API_V1_PREFIX}/health", headers={REQUEST_ID_HEADER: "test-123"})
    assert resp.headers[REQUEST_ID_HEADER] == "test-123"  # API-007
