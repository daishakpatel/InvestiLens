// Client-side what-if recompute (§37.2 item 10). When the user drags a weight, we recompute the
// deterministic aggregates from the per-holding data the backend already returned (`holdings_data`
// + correlation matrix) — no backend round-trip. The backend remains the source of truth for the
// initial analysis; this is a live preview using the same formulas (ADR-0026). Numbers here are a
// display convenience, never stored.
import type { HoldingData, PortfolioAnalysis, RiskStats } from "../types";

export interface RecomputedWeightedMetric {
  metricName: string;
  value: number | null;
  coverage: number;
}

export interface Recomputed {
  weights: Record<string, number>; // normalized to sum to 1
  weightedMetrics: RecomputedWeightedMetric[];
  sectorExposure: { sector: string; weight: number }[];
  hhi: number;
  effectiveHoldings: number;
  portfolioVolatility: number | null;
}

const UNKNOWN_SECTOR = "Unknown";

function num(value: string | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function normalizeWeights(raw: Record<string, number>): Record<string, number> {
  const total = Object.values(raw).reduce((a, b) => a + (b > 0 ? b : 0), 0);
  if (total <= 0) return {};
  const out: Record<string, number> = {};
  for (const [ticker, w] of Object.entries(raw)) out[ticker] = w > 0 ? w / total : 0;
  return out;
}

function metricNames(holdings: HoldingData[]): string[] {
  const names = new Set<string>();
  for (const h of holdings) for (const k of Object.keys(h.metrics ?? {})) names.add(k);
  return [...names];
}

export function recompute(
  holdings: HoldingData[],
  rawWeights: Record<string, number>,
  correlation: RiskStats["correlation"] = [],
): Recomputed {
  const weights = normalizeWeights(rawWeights);
  const byTicker = new Map(holdings.map((h) => [h.ticker, h]));

  // Weighted metrics — renormalize over holdings that actually have a value (DR-041 spirit).
  const weightedMetrics: RecomputedWeightedMetric[] = metricNames(holdings).map((name) => {
    let covered = 0;
    let acc = 0;
    for (const [ticker, w] of Object.entries(weights)) {
      const value = num(byTicker.get(ticker)?.metrics?.[name]?.value);
      if (value !== null) {
        covered += w;
        acc += w * value;
      }
    }
    return { metricName: name, value: covered > 0 ? acc / covered : null, coverage: covered };
  });

  // Sector exposure.
  const sectors: Record<string, number> = {};
  for (const [ticker, w] of Object.entries(weights)) {
    const sector = byTicker.get(ticker)?.sector ?? UNKNOWN_SECTOR;
    sectors[sector] = (sectors[sector] ?? 0) + w;
  }
  const sectorExposure = Object.entries(sectors)
    .map(([sector, weight]) => ({ sector, weight }))
    .sort((a, b) => b.weight - a.weight || a.sector.localeCompare(b.sector));

  // Concentration (HHI = Σ wᵢ²).
  const hhi = Object.values(weights).reduce((a, w) => a + w * w, 0);
  const effectiveHoldings = hhi > 0 ? 1 / hhi : 0;

  return {
    weights,
    weightedMetrics,
    sectorExposure,
    hhi,
    effectiveHoldings,
    portfolioVolatility: portfolioVolatility(holdings, weights, correlation),
  };
}

export function portfolioVolatility(
  holdings: HoldingData[],
  weights: Record<string, number>,
  correlation: RiskStats["correlation"],
): number | null {
  const vol = new Map<string, number>();
  for (const h of holdings) {
    const v = num(h.annualized_volatility);
    if (v !== null) vol.set(h.ticker, v);
  }
  const corr = new Map<string, Record<string, string>>();
  for (const row of correlation) corr.set(row.ticker, row.correlations);

  let variance = 0;
  for (const [ti, wi] of Object.entries(weights)) {
    const vi = vol.get(ti);
    if (vi === undefined) return null;
    for (const [tj, wj] of Object.entries(weights)) {
      const vj = vol.get(tj);
      if (vj === undefined) return null;
      const rho = ti === tj ? 1 : num(corr.get(ti)?.[tj]);
      if (rho === null) return null;
      variance += wi * wj * vi * vj * rho;
    }
  }
  return variance >= 0 ? Math.sqrt(variance) : null;
}

/** Convenience: pull `holdings_data` + correlation from a fresh analysis for the recompute path. */
export function recomputeFrom(
  analysis: PortfolioAnalysis,
  rawWeights: Record<string, number>,
): Recomputed {
  return recompute(analysis.holdings_data ?? [], rawWeights, analysis.risk_stats?.correlation ?? []);
}
