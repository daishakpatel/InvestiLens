"""LLM cost-estimation unit tests (OBS-002/005). Pure, offline — no DB, no network."""

from __future__ import annotations

from decimal import Decimal

from app.billing.cost import estimate_blended_cost, estimate_cost
from app.config import get_settings


def test_strong_model_costs_more_than_cheap_model() -> None:
    settings = get_settings()
    cheap = estimate_cost(model=settings.llm_model_cheap, input_tokens=1_000_000, output_tokens=0)
    strong = estimate_cost(model=settings.llm_model_strong, input_tokens=1_000_000, output_tokens=0)
    assert cheap == settings.llm_cost_per_1m_input_tokens_cheap
    assert strong == settings.llm_cost_per_1m_input_tokens_strong
    assert strong > cheap


def test_cost_is_decimal_never_float() -> None:
    settings = get_settings()
    cost = estimate_cost(model=settings.llm_model_strong, input_tokens=500_000, output_tokens=500)
    assert isinstance(cost, Decimal)


def test_zero_tokens_cost_zero() -> None:
    settings = get_settings()
    assert estimate_cost(model=settings.llm_model_strong, input_tokens=0, output_tokens=0) == 0
    assert estimate_blended_cost(model=settings.llm_model_strong, total_tokens=0) == 0


def test_unknown_model_falls_back_to_cheap_rate() -> None:
    settings = get_settings()
    cost = estimate_cost(model="some-other-model", input_tokens=1_000_000, output_tokens=0)
    assert cost == settings.llm_cost_per_1m_input_tokens_cheap
