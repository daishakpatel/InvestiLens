"""Deterministic price-based portfolio risk: volatility and correlation (§37.2).

Computed from `price_history` daily returns in backend `Decimal` math — never by the LLM. Volatility
is annualized sample standard deviation of daily simple returns; correlation is Pearson over the
pair's common trading days; portfolio volatility is sqrt(wᵀ Σ w) with Σᵢⱼ = σᵢ σⱼ ρᵢⱼ. These are
statistical risk signals, not reported financial figures, but we keep them in Decimal for
determinism. Holdings without price history are surfaced as unavailable, never silently dropped.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from itertools import pairwise

from app.portfolio.weights import NormalizedWeight
from app.schemas.portfolio import CorrelationRow, HoldingVolatility, RiskStats

_TRADING_DAYS = Decimal(252)
_RESULT_PRECISION = Decimal("0.00000001")


def daily_returns(series: list[tuple[date, Decimal]]) -> dict[date, Decimal]:
    """Simple daily returns keyed by the later date. `series` must be oldest-first, price > 0."""
    returns: dict[date, Decimal] = {}
    for (_, prev), (day, cur) in pairwise(series):
        if prev > 0:
            returns[day] = (cur - prev) / prev
    return returns


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / Decimal(len(values))


def _stdev(values: list[Decimal]) -> Decimal | None:
    """Sample standard deviation (n-1). None when there are fewer than two observations."""
    if len(values) < 2:
        return None
    mean = _mean(values)
    variance = sum(((v - mean) ** 2 for v in values), Decimal(0)) / Decimal(len(values) - 1)
    return variance.sqrt()


def annualized_volatility(returns: dict[date, Decimal]) -> Decimal | None:
    std = _stdev(list(returns.values()))
    return None if std is None else (std * _TRADING_DAYS.sqrt())


def correlation(a: dict[date, Decimal], b: dict[date, Decimal]) -> Decimal | None:
    """Pearson correlation of two return series over their common dates (≥2 needed)."""
    common = sorted(set(a) & set(b))
    if len(common) < 2:
        return None
    xs = [a[d] for d in common]
    ys = [b[d] for d in common]
    mx, my = _mean(xs), _mean(ys)
    cov = sum(((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)), Decimal(0))
    var_x = sum(((x - mx) ** 2 for x in xs), Decimal(0))
    var_y = sum(((y - my) ** 2 for y in ys), Decimal(0))
    denom = (var_x * var_y).sqrt()
    if denom == 0:
        return None
    return cov / denom


def build_risk_stats(
    prices: dict[str, list[tuple[date, Decimal]]],
    weights: list[NormalizedWeight],
    *,
    window_start: date | None = None,
    window_end: date | None = None,
) -> RiskStats:
    """Assemble per-holding volatility, the correlation matrix, and portfolio volatility."""
    returns = {ticker: daily_returns(series) for ticker, series in prices.items()}
    vols: dict[str, Decimal | None] = {
        w.ticker: annualized_volatility(returns.get(w.ticker, {})) for w in weights
    }

    holding_vol: list[HoldingVolatility] = []
    for w in weights:
        vol = vols[w.ticker]
        holding_vol.append(
            HoldingVolatility(
                ticker=w.ticker,
                annualized_volatility=(
                    vol.quantize(_RESULT_PRECISION) if vol is not None else None
                ),
                observations=len(returns.get(w.ticker, {})),
            )
        )

    corr_rows: list[CorrelationRow] = []
    corr_matrix: dict[tuple[str, str], Decimal] = {}
    for wi in weights:
        row: dict[str, Decimal] = {}
        for wj in weights:
            if wi.ticker == wj.ticker:
                value = Decimal(1)
            else:
                value = correlation(returns.get(wi.ticker, {}), returns.get(wj.ticker, {}))  # type: ignore[assignment]
            if value is not None:
                row[wj.ticker] = value.quantize(_RESULT_PRECISION)
                corr_matrix[(wi.ticker, wj.ticker)] = value
        corr_rows.append(CorrelationRow(ticker=wi.ticker, correlations=row))

    notes: list[str] = []
    missing = [w.ticker for w in weights if vols[w.ticker] is None]
    if missing:
        notes.append(f"Price history unavailable for: {', '.join(missing)}.")

    port_vol = _portfolio_volatility(weights, vols, corr_matrix)
    return RiskStats(
        window_start=window_start.isoformat() if window_start else None,
        window_end=window_end.isoformat() if window_end else None,
        holding_volatility=holding_vol,
        correlation=corr_rows,
        portfolio_volatility=(
            port_vol.quantize(_RESULT_PRECISION) if port_vol is not None else None
        ),
        notes=notes,
    )


def _portfolio_volatility(
    weights: list[NormalizedWeight],
    vols: dict[str, Decimal | None],
    corr: dict[tuple[str, str], Decimal],
) -> Decimal | None:
    """Portfolio stdev sqrt(wT.Cov.w); None unless every holding has a vol and the matrix is OK."""
    if any(vols[w.ticker] is None for w in weights):
        return None
    variance = Decimal(0)
    for wi in weights:
        for wj in weights:
            rho = corr.get((wi.ticker, wj.ticker))
            if rho is None:
                return None
            variance += wi.weight * wj.weight * vols[wi.ticker] * vols[wj.ticker] * rho  # type: ignore[operator]
    if variance < 0:
        return None
    return variance.sqrt()
