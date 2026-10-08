"""LLM cost estimation for the `llm_calls.cost_usd` column (OBS-002/005).

Same spirit as `app.embeddings.pipeline`'s `embedding_cost_per_1m_tokens`: a blended $/1M-token
estimate for internal cost tracking only, never surfaced as a financial figure to a user. Callers
that only track a combined token count (chat's `_synthesize`) use the blended rate; callers with
a real input/output split use it directly.
"""

from __future__ import annotations

from decimal import Decimal

from app.config import Settings, get_settings

_CENTS = Decimal("0.000001")


def _rates(model: str, settings: Settings) -> tuple[Decimal, Decimal]:
    if model == settings.llm_model_strong:
        return (
            settings.llm_cost_per_1m_input_tokens_strong,
            settings.llm_cost_per_1m_output_tokens_strong,
        )
    return (
        settings.llm_cost_per_1m_input_tokens_cheap,
        settings.llm_cost_per_1m_output_tokens_cheap,
    )


def estimate_cost(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int = 0,
    settings: Settings | None = None,
) -> Decimal:
    """Estimate cost from a real input/output token split."""
    settings = settings or get_settings()
    in_rate, out_rate = _rates(model, settings)
    million = Decimal(1_000_000)
    cost = (Decimal(input_tokens) / million * in_rate) + (
        Decimal(output_tokens) / million * out_rate
    )
    return cost.quantize(_CENTS)


def estimate_blended_cost(
    *, model: str, total_tokens: int, settings: Settings | None = None
) -> Decimal:
    """Estimate cost from a single combined token count, using the average of the in/out rates."""
    settings = settings or get_settings()
    in_rate, out_rate = _rates(model, settings)
    blended = (in_rate + out_rate) / 2
    return (Decimal(total_tokens) / Decimal(1_000_000) * blended).quantize(_CENTS)
