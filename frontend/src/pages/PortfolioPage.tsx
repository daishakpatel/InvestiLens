import { Plus, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { formatValue } from "../charts/series";
import { CitationChip } from "../components/citations/CitationChip";
import { useCommandPalette } from "../components/CommandPaletteContext";
import { PanelProvider } from "../components/panel/PanelProvider";
import { Button, IconButton } from "../components/ui/Button";
import { Container } from "../components/ui/Container";
import { Input } from "../components/ui/Input";
import { Section } from "../components/ui/Section";
import { Skeleton } from "../components/ui/Skeleton";
import { Stat } from "../components/ui/Stat";
import { EmptyState, ErrorState } from "../components/ui/States";
import { formatDate, formatPercent, toNumber } from "../lib/format";
import { metricDisplay, metricLabel } from "../lib/metricCatalog";
import { recomputeFrom, toPercentages } from "../lib/portfolioRecompute";
import type { Recomputed } from "../lib/portfolioRecompute";
import { usePortfolioAnalysis } from "../lib/queries";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import type { PortfolioAnalysis } from "../types";

interface Holding {
  ticker: string;
  weight: string; // as typed, in percent; parsed when used so the field can be cleared
}

const DEFAULT: Holding[] = [
  { ticker: "NVDA", weight: "40" },
  { ticker: "AAPL", weight: "30" },
  { ticker: "JPM", weight: "30" },
];
// The weighted figures shown as headline stats, in reading order.
const HEADLINE = ["yoy_growth", "gross_margin", "net_margin", "fcf_margin"];
// Categorical hues, used only where colour is the one way to tell parts of a whole apart.
const HUES = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)", "var(--chart-6)"];

const weightOf = (holding: Holding) => Math.max(toNumber(holding.weight) ?? 0, 0);
const list = (items: string[]) =>
  items.length <= 1 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;

function HoldingsEditor({ holdings, onChange }: { holdings: Holding[]; onChange: (next: Holding[]) => void }) {
  const palette = useCommandPalette();
  const total = Math.round(holdings.reduce((sum, h) => sum + weightOf(h), 0) * 10) / 10;
  const off = holdings.length > 0 && total !== 100;

  return (
    <section aria-label="Holdings">
      <h2 className="border-b border-border pb-2 text-label text-muted">Holdings</h2>
      <table className="w-full text-sm">
        <caption className="sr-only">Hypothetical holdings and their weights</caption>
        <tbody>
          {holdings.map((holding, i) => (
            <tr key={holding.ticker} className="animate-fade-in border-b border-border/60">
              <th scope="row" className="py-2 text-left font-medium">
                <Link to={`/company/${holding.ticker}`} className="hover:underline">
                  {holding.ticker}
                </Link>
              </th>
              <td className="py-2">
                <span className="flex items-center justify-end gap-1.5">
                  <span className="w-20">
                    <Input
                    type="number"
                    inputMode="decimal"
                    min={0}
                    max={100}
                    step="any"
                    value={holding.weight}
                    onChange={(event) =>
                      onChange(holdings.map((h, j) => (j === i ? { ...h, weight: event.target.value } : h)))
                    }
                    aria-label={`${holding.ticker} weight, percent`}
                    className="tnum text-right"
                  />
                  </span>
                  <span aria-hidden className="text-subtle">
                    %
                  </span>
                </span>
              </td>
              <td className="w-9 py-2 text-right">
                <IconButton
                  size="sm"
                  label={`Remove ${holding.ticker}`}
                  onClick={() => onChange(holdings.filter((_, j) => j !== i))}
                >
                  <X aria-hidden className="size-3.5" />
                </IconButton>
              </td>
            </tr>
          ))}
        </tbody>
        {holdings.length > 0 && (
          <tfoot>
            <tr>
              <th scope="row" className="py-2.5 text-left font-normal text-muted">
                Total
              </th>
              <td className={`tnum py-2.5 pr-5 text-right font-medium ${off ? "text-warning" : ""}`}>{total}%</td>
              <td />
            </tr>
          </tfoot>
        )}
      </table>
      {off && (
        <p role="status" className="mt-1 text-caption text-warning">
          Weights do not add up to 100%. The results use them in proportion.
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          size="sm"
          onClick={() =>
            palette.pick({
              title: "Add a holding",
              exclude: holdings.map((h) => h.ticker),
              onPick: (company) => onChange([...holdings, { ticker: company.ticker, weight: "10" }]),
            })
          }
        >
          <Plus aria-hidden className="size-3.5" />
          Add holding
        </Button>
        {off && total > 0 && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              const scaled = toPercentages(holdings.map(weightOf));
              onChange(holdings.map((h, i) => ({ ...h, weight: String(scaled[i] ?? 0) })));
            }}
          >
            Normalize to 100%
          </Button>
        )}
      </div>
    </section>
  );
}

/** Parts of a whole as one bar. Sectors sit in name order and take the palette's hues in that
 *  order, so a sector keeps its place and colour while the weights move, and only neighbouring
 *  palette slots ever touch (which is what the palette is validated for). Past six sectors the
 *  smallest are folded into "Other". */
function SectorBar({ sectors }: { sectors: Recomputed["sectorExposure"] }) {
  const held = sectors.filter((s) => s.weight > 0); // largest first
  const shown = held.length > HUES.length ? held.slice(0, HUES.length - 1) : held;
  const other = held.slice(shown.length).reduce((sum, s) => sum + s.weight, 0);
  const parts = [
    ...[...shown]
      .sort((x, y) => x.sector.localeCompare(y.sector))
      .map((s, i) => ({ ...s, color: HUES[i] ?? "var(--text-subtle)" })),
    ...(other > 0 ? [{ sector: "Other", weight: other, color: "var(--text-subtle)" }] : []),
  ];
  return (
    <div>
      <div
        role="img"
        aria-label={`Sector exposure: ${parts.map((p) => `${p.sector} ${formatPercent(p.weight, 0)}`).join(", ")}`}
        className="flex h-3 w-full gap-0.5"
      >
        {parts.map((part) => (
          <span
            key={part.sector}
            className="h-full min-w-1 rounded-[3px] transition-[flex-grow] duration-(--duration-slow)"
            style={{ flexGrow: part.weight, flexBasis: 0, backgroundColor: part.color }}
          />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-1.5 text-sm">
        {parts.map((part) => (
          <li key={part.sector} className="flex items-center gap-2">
            <span aria-hidden className="size-2.5 rounded-[2px]" style={{ backgroundColor: part.color }} />
            {part.sector}
            <span className="tnum text-muted">{formatPercent(part.weight, 0)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** How the holdings' daily returns move together. Blue for together, orange for opposite, shade
 *  for strength; the figure is always printed, so colour is never the only cue. */
function Correlations({ analysis }: { analysis: PortfolioAnalysis }) {
  const risk = analysis.risk_stats;
  const rows = (risk?.correlation ?? []).filter((row) => Object.keys(row.correlations).length > 1);
  if (!risk || rows.length < 2) return null;
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-0.5 text-sm">
          <caption className="sr-only">Correlation of daily returns between holdings</caption>
          <thead>
            <tr>
              <td />
              {rows.map((row) => (
                <th key={row.ticker} scope="col" className="px-2 pb-1 text-center text-label font-normal text-muted">
                  {row.ticker}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.ticker}>
                <th scope="row" className="pr-3 text-left text-label font-normal text-muted">
                  {row.ticker}
                </th>
                {rows.map((column) => {
                  const rho = toNumber(row.correlations[column.ticker] ?? null);
                  const self = row.ticker === column.ticker;
                  const shade = rho === null || self ? 0 : Math.round(Math.min(Math.abs(rho), 1) * 55);
                  const hue = (rho ?? 0) >= 0 ? "var(--chart-1)" : "var(--chart-2)";
                  return (
                    <td
                      key={column.ticker}
                      style={{ backgroundColor: `color-mix(in srgb, ${hue} ${shade}%, var(--surface))` }}
                      className={`tnum h-9 min-w-16 text-center ${self ? "text-subtle" : ""}`}
                    >
                      {rho === null ? "N/A" : self ? "1" : rho.toFixed(2).replace("-", "−")}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-caption text-subtle">
        Correlation of daily returns, {formatDate(risk.window_start)} to {formatDate(risk.window_end)}. 1 moves
        together, 0 is unrelated, −1 moves opposite.
      </p>
    </div>
  );
}

/** What is missing, one sentence each, naming the holdings concerned (never a silent gap). */
function gaps(analysis: PortfolioAnalysis, recomputed: Recomputed): string[] {
  const data = analysis.holdings_data ?? [];
  const sentences: string[] = [];
  for (const name of HEADLINE) {
    const metric = recomputed.weightedMetrics.find((m) => m.metricName === name);
    if (!metric || metric.coverage >= 0.9995) continue;
    const without = data.filter((h) => h.metrics?.[name]?.value == null).map((h) => h.ticker);
    if (without.length === 0) continue;
    sentences.push(
      metric.value === null
        ? `${metricLabel(name)} is not reported by any holding.`
        : `${metricLabel(name)} is not reported by ${list(without)}; the figure covers the other ${formatPercent(metric.coverage, 0)} of the portfolio.`,
    );
  }
  const noPrices = (analysis.risk_stats?.holding_volatility ?? [])
    .filter((h) => h.annualized_volatility == null)
    .map((h) => h.ticker);
  if (noPrices.length > 0) {
    sentences.push(`There is no price history for ${list(noPrices)}, so volatility and correlation leave ${noPrices.length === 1 ? "it" : "them"} out.`);
  }
  return sentences;
}

function Results({ analysis, weights }: { analysis: PortfolioAnalysis; weights: Record<string, number> }) {
  const recomputed = useMemo(() => recomputeFrom(analysis, weights), [analysis, weights]);
  if (Object.keys(recomputed.weights).length === 0) {
    return <EmptyState message="Give at least one holding a weight above zero to see results." />;
  }
  const unit = (name: string) => analysis.weighted_metrics.find((m) => m.metric_name === name)?.unit ?? "ratio";
  const stats = HEADLINE.flatMap((name) => {
    const metric = recomputed.weightedMetrics.find((m) => m.metricName === name);
    return metric && metric.value !== null ? [{ name, value: metric.value }] : [];
  });
  const missing = gaps(analysis, recomputed);

  // Citation numbers for the risk themes, in reading order.
  const numbers = new Map<string, number>();
  for (const theme of analysis.risk_themes) {
    for (const c of theme.contributions) for (const id of c.source_ids) if (!numbers.has(id)) numbers.set(id, numbers.size + 1);
  }

  return (
    <div className="space-y-12">
      <div>
        <div className="flex flex-wrap gap-x-10 gap-y-6">
          {stats.map(({ name, value }) => (
            <Stat
              key={name}
              label={metricLabel(name)}
              value={formatValue(value, metricDisplay(name, unit(name)))}
              meta={{ formula: "Average of the holdings, by weight" }}
            />
          ))}
          <Stat
            label="Effective holdings"
            value={recomputed.effectiveHoldings.toFixed(1)}
            meta={{ formula: `1 ÷ the sum of squared weights (HHI ${recomputed.hhi.toFixed(2)})` }}
          />
          {recomputed.portfolioVolatility !== null && (
            <Stat
              label="Volatility, annualized"
              value={formatPercent(recomputed.portfolioVolatility)}
              meta={{ formula: "From daily returns and the correlations below" }}
            />
          )}
        </div>
        {missing.length > 0 && (
          <ul className="mt-4 max-w-2xl space-y-1 text-caption text-subtle">
            {missing.map((sentence) => (
              <li key={sentence}>{sentence}</li>
            ))}
          </ul>
        )}
      </div>

      <Section title="Sector exposure">
        <div className="pt-5">
          <SectorBar sectors={recomputed.sectorExposure} />
        </div>
      </Section>

      {analysis.risk_stats && (
        <Section title="How the holdings move together">
          <div className="pt-5">
            <Correlations analysis={analysis} />
            {(analysis.risk_stats.correlation ?? []).filter((r) => Object.keys(r.correlations).length > 1).length < 2 && (
              <p className="text-sm text-muted">At least two holdings with a price history are needed.</p>
            )}
          </div>
        </Section>
      )}

      {/* The themes come from each holding's AI research report, so the section carries the AI mark. */}
      <Section title="Risk themes" kind="ai">
        <div className="max-w-[720px] pt-5">
          {analysis.risk_themes.length === 0 ? (
            <p className="text-sm text-muted">
              No risk themes yet. They are gathered from each holding’s research report, and none of these
              holdings has one.
            </p>
          ) : (
            <ul className="divide-y divide-border/60">
              {analysis.risk_themes.map((theme) => {
                const held = [...new Set(theme.contributions.map((c) => c.ticker))];
                const weight = held.reduce((sum, ticker) => sum + (recomputed.weights[ticker] ?? 0), 0);
                return (
                  <li key={theme.category} className="space-y-1.5 py-4 first:pt-0">
                    <p className="text-label text-muted">
                      {theme.category.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())} · {list(held)} ·{" "}
                      {formatPercent(weight, 0)} of the portfolio
                    </p>
                    {theme.contributions
                      .filter((c) => c.source_ids.length > 0)
                      .map((c, i) => (
                        <p key={`${c.ticker}-${i}`} className="text-body leading-relaxed">
                          <span className="font-medium">{c.ticker}:</span> {c.description}
                          {c.source_ids.map((id) => (
                            <CitationChip key={id} number={numbers.get(id) ?? 0} sourceId={id} />
                          ))}
                        </p>
                      ))}
                  </li>
                );
              })}
            </ul>
          )}
          {analysis.notes.map((note) => (
            <p key={note} className="mt-3 text-caption text-subtle">
              {note}
            </p>
          ))}
        </div>
      </Section>
    </div>
  );
}

function ResultsSkeleton() {
  return (
    <div role="status" aria-label="Analyzing the portfolio" className="space-y-10">
      <div className="flex gap-10">
        <Skeleton className="h-10 w-24" />
        <Skeleton className="h-10 w-24" />
        <Skeleton className="h-10 w-24" />
      </div>
      <Skeleton shape="block" className="h-24" />
      <Skeleton shape="block" className="h-40" />
    </div>
  );
}

/** Portfolio (§37.2): hypothetical holdings on the left, what they add up to on the right. A new
 *  set of companies is analysed by the server once; after that every change of weight is
 *  recomputed here from what the server returned, with no further request. */
export default function PortfolioPage() {
  const [holdings, setHoldings] = useState<Holding[]>(DEFAULT);
  const { mutate, data, isError, error } = usePortfolioAnalysis();
  useDocumentTitle("Portfolio");

  const tickers = holdings.map((h) => h.ticker);
  const tickerKey = tickers.join(",");
  useEffect(() => {
    // Equal weights: the server needs a positive weight for each, and the weights that matter
    // are applied here, live.
    if (tickerKey) mutate(tickerKey.split(",").map((ticker) => ({ ticker, weight: 1 })));
  }, [tickerKey, mutate]);

  // Results belong to the companies they were computed for; a stale analysis is not shown.
  const analysis = data && data.holdings.map((h) => h.ticker).sort().join() === [...tickers].sort().join() ? data : null;
  const weights = useMemo(
    () => Object.fromEntries(holdings.map((h) => [h.ticker, weightOf(h)])),
    [holdings],
  );

  return (
    <PanelProvider>
      <Container className="space-y-10 py-10">
        <header>
          <h1 className="text-heading font-semibold">Portfolio</h1>
          <p className="mt-1 text-muted">Hypothetical portfolio. Not investment advice.</p>
        </header>

        <div className="grid gap-x-16 gap-y-12 lg:grid-cols-[320px_minmax(0,1fr)]">
          <div className="lg:sticky lg:top-20 lg:self-start">
            <HoldingsEditor holdings={holdings} onChange={setHoldings} />
          </div>
          <div className="min-w-0" aria-live="off">
            {holdings.length === 0 ? (
              <EmptyState message="Add a holding to see what the portfolio adds up to." />
            ) : analysis ? (
              <Results analysis={analysis} weights={weights} />
            ) : isError ? (
              <ErrorState
                message={error.message}
                onRetry={() => mutate(tickers.map((ticker) => ({ ticker, weight: 1 })))}
              />
            ) : (
              <ResultsSkeleton />
            )}
          </div>
        </div>
      </Container>
    </PanelProvider>
  );
}
