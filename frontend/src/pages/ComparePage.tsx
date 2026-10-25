import { Plus, X } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { ComparisonBars } from "../charts/ComparisonBars";
import { formatValue } from "../charts/series";
import { CitedText } from "../components/citations/CitedText";
import { ReferenceList } from "../components/citations/ReferenceList";
import { useCommandPalette } from "../components/CommandPaletteContext";
import { PanelProvider } from "../components/panel/PanelProvider";
import { SignInHint } from "../components/SignInHint";
import { Button } from "../components/ui/Button";
import { Container } from "../components/ui/Container";
import { DataTable } from "../components/ui/DataTable";
import type { Column } from "../components/ui/DataTable";
import { Section } from "../components/ui/Section";
import { Skeleton } from "../components/ui/Skeleton";
import { AsyncContent, EmptyState } from "../components/ui/States";
import { Tooltip } from "../components/ui/Tooltip";
import { PeerSetPanel } from "../components/valuation/PeerSetPanel";
import { useAuth } from "../lib/auth";
import { MAX_COMPANIES, MIN_COMPANIES, leader, parseTickers } from "../lib/compare";
import { formatDate, toNumber } from "../lib/format";
import { metricDisplay, metricLabel, reasonText } from "../lib/metricCatalog";
import { useComparison, useComparisonCommentary, usePeers } from "../lib/queries";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import type { ComparisonCell, ComparisonMetricRow, ComparisonResponse } from "../types";

const DEFAULT_TICKERS = ["NVDA", "AMD", "INTC"];
const CHIP = "inline-flex h-8 items-center rounded-full text-sm transition-colors pointer-coarse:h-10";

function Picker({ tickers, onChange }: { tickers: string[]; onChange: (next: string[]) => void }) {
  const palette = useCommandPalette();
  const peers = usePeers(tickers[0] ?? "");
  const full = tickers.length >= MAX_COMPANIES;
  const suggestions = (peers.data?.peers ?? []).filter((peer) => !tickers.includes(peer.ticker));

  return (
    <div className="space-y-3">
      <ul aria-label="Companies compared" className="flex flex-wrap items-center gap-2">
        {tickers.map((ticker) => (
          <li key={ticker} className={`${CHIP} animate-fade-in bg-surface-2 pr-1`}>
            <Link to={`/company/${ticker}`} className="flex h-full items-center pl-3 pr-1.5 font-medium hover:underline">
              {ticker}
            </Link>
            <button
              type="button"
              aria-label={`Remove ${ticker}`}
              onClick={() => onChange(tickers.filter((t) => t !== ticker))}
              data-inline=""
              className="flex size-6 items-center justify-center rounded-full text-muted transition-colors hover:bg-surface-3 hover:text-text pointer-coarse:size-8"
            >
              <X aria-hidden className="size-3.5" />
            </button>
          </li>
        ))}
        <li>
          <button
            type="button"
            disabled={full}
            onClick={() =>
              palette.pick({
                title: "Add a company to compare",
                exclude: tickers,
                onPick: (company) => onChange([...tickers, company.ticker]),
              })
            }
            className={`${CHIP} gap-1.5 border border-border-strong px-3 font-medium hover:bg-surface-2 disabled:opacity-50`}
          >
            <Plus aria-hidden className="size-3.5" />
            Add company
          </button>
        </li>
      </ul>
      {/* This line keeps its height while the suggestions load, so the table does not jump. */}
      <div className="min-h-7 pointer-coarse:min-h-10">
        {full ? (
          <p className="text-caption text-subtle">Six companies is the most that fit side by side.</p>
        ) : (
          suggestions.length > 0 && (
            <ul aria-label={`Companies similar to ${tickers[0]}`} className="flex flex-wrap items-center gap-2">
              <li className="text-caption text-subtle">Similar to {tickers[0]}</li>
              {suggestions.map((peer) => (
                <li key={peer.ticker}>
                  <button
                    type="button"
                    title={`${peer.name} · ${peer.reason}`}
                    aria-label={`Add ${peer.ticker}, ${peer.name}`}
                    onClick={() => onChange([...tickers, peer.ticker])}
                    className={`${CHIP} h-7 gap-1 px-2.5 text-label text-muted hover:bg-surface-2 hover:text-text`}
                  >
                    <Plus aria-hidden className="size-3" />
                    {peer.ticker}
                  </button>
                </li>
              ))}
            </ul>
          )
        )}
      </div>
    </div>
  );
}

/** One figure. The strongest in its row is in full ink and the rest are quieter; never green or
 *  red, because leading a peer group is not a gain. The bar beneath is the figure's rank among
 *  the companies on screen. */
function Figure({ row, cell, leads }: { row: ComparisonMetricRow; cell: ComparisonCell; leads: boolean }) {
  const value = toNumber(cell.result.value);
  if (value === null) {
    return (
      <Tooltip label={reasonText(cell.result.warnings[0])}>
        <span className="text-subtle">N/A</span>
      </Tooltip>
    );
  }
  const rank = toNumber(cell.percentile ?? null);
  return (
    <span className="inline-block min-w-16">
      <span className={leads ? "font-semibold text-text" : "text-muted"}>
        {formatValue(value, metricDisplay(row.metric_name, row.unit))}
      </span>
      {rank !== null && (
        <span aria-hidden className="mt-1 block h-0.5 rounded-full bg-surface-3">
          <span className="block h-full rounded-full bg-subtle" style={{ width: `${Math.round(rank * 100)}%` }} />
        </span>
      )}
    </span>
  );
}

function Comparison({
  data,
  metric,
  onMetric,
}: {
  data: ComparisonResponse;
  metric: string | null;
  onMetric: (name: string) => void;
}) {
  const hasFigure = (row: ComparisonMetricRow) => row.cells.some((cell) => cell.result.value !== null);
  const rows = data.metrics.filter(hasFigure);
  const missing = data.metrics.filter((row) => !hasFigure(row));
  const selected = rows.find((row) => row.metric_name === metric) ?? rows[0];

  const columns: Column<ComparisonMetricRow>[] = [
    {
      key: "metric",
      header: "Metric",
      render: (row) => (
        <button
          type="button"
          aria-pressed={row === selected}
          onClick={() => onMetric(row.metric_name)}
          className={`-mx-2 rounded-control px-2 py-0.5 text-left transition-colors hover:text-text ${
            row === selected ? "bg-surface-2 text-text" : "text-muted"
          }`}
        >
          {metricLabel(row.metric_name)}
        </button>
      ),
    },
    ...data.companies.map((company): Column<ComparisonMetricRow> => ({
      key: company.ticker,
      header: (
        <span>
          <Link to={`/company/${company.ticker}`} className="font-medium text-text hover:underline">
            {company.ticker}
          </Link>
          <span className="block font-normal text-subtle">{company.fiscal_period ?? "No period"}</span>
        </span>
      ),
      numeric: true,
      render: (row) => {
        const cell = row.cells.find((c) => c.ticker === company.ticker);
        return cell ? <Figure row={row} cell={cell} leads={leader(row) === company.ticker} /> : null;
      },
    })),
  ];

  return (
    <div className="space-y-12">
      <div>
        <DataTable
          label="Comparison of metrics by company"
          allRows
          columns={columns}
          rows={rows}
          rowKey={(row) => row.metric_name}
        />
        <p className="mt-3 max-w-3xl text-caption text-subtle">
          Each company’s fiscal year closest to calendar {data.calendar_year ?? "year"}
          {data.companies.some((c) => c.period_end) &&
            ` (${data.companies
              .filter((c) => c.period_end)
              .map((c) => `${c.ticker} to ${formatDate(c.period_end)}`)
              .join(", ")})`}
          . The strongest figure in a row is in bold; the bar beneath a figure is its rank among
          these companies.
          {missing.length > 0 &&
            ` Not available for any of them: ${missing.map((row) => metricLabel(row.metric_name)).join(", ")}.`}
          {data.notes.length > 0 && ` ${data.notes.join(" ")}`}
        </p>
      </div>

      {selected && (
        <div className="max-w-2xl">
          <ComparisonBars row={selected} companies={data.companies} />
        </div>
      )}
    </div>
  );
}

/** A cited explanation of the differences, written on request (FR-010: marked as AI). The same
 *  verification as research reports: every sentence is cited or it is withheld. */
function Commentary({ tickers }: { tickers: string[] }) {
  const { user } = useAuth();
  const commentary = useComparisonCommentary();
  const result = commentary.data;
  // No AI text without a source (FR-020). The server withholds unsupported claims; this is the
  // same rule applied once more before the reader, so text that arrives with no citations at
  // all is treated as no answer rather than shown.
  const cited = result?.sufficient && result.rendered_text && result.citations.length > 0;

  return (
    <Section title="The differences, explained" kind="ai">
      <div className="max-w-[720px] space-y-4 pt-5">
        {result ? (
          cited ? (
            <>
              <p className="whitespace-pre-wrap text-body leading-relaxed">
                <CitedText text={result.rendered_text} citations={result.citations} />
              </p>
              <ReferenceList
                entries={result.citations.map((c) => ({ number: c.number, sourceId: c.source_id, tier: c.tier }))}
              />
            </>
          ) : (
            // Abstaining is the system working as designed: said plainly, not styled as a fault.
            <p className="text-sm text-muted">
              Not enough cited evidence to explain the differences. The figures above are unaffected.
            </p>
          )
        ) : (
          <p className="text-sm text-muted">
            A short, cited account of why these companies’ figures differ, drawn from their filings.
            It describes; it never recommends.
          </p>
        )}
        {commentary.isError && (
          <p role="alert" className="text-sm text-negative">
            The explanation could not be written. {commentary.error.message}
          </p>
        )}
        {user ? (
          <Button loading={commentary.isPending} onClick={() => commentary.mutate({ tickers })}>
            {result ? "Explain again" : "Explain the differences"}
          </Button>
        ) : (
          <SignInHint>Sign in to have the differences explained.</SignInHint>
        )}
      </div>
    </Section>
  );
}

/** Compare (§37.1): up to six companies, one table, the same calendar year. The selection and
 *  the charted metric live in the URL, so a comparison can be shared as a link. */
export default function ComparePage() {
  const [params, setParams] = useSearchParams();
  const tickers = params.has("tickers") ? parseTickers(params.get("tickers")) : DEFAULT_TICKERS;
  const comparison = useComparison(tickers, []);
  useDocumentTitle(tickers.length > 0 ? `Compare ${tickers.join(", ")}` : "Compare");

  const update = (key: string, value: string) =>
    setParams(
      (prev) => {
        prev.set(key, value);
        return prev;
      },
      { replace: true, preventScrollReset: true },
    );

  return (
    <PanelProvider>
      <Container className="space-y-10 py-10">
        <header>
          <h1 className="text-heading font-semibold">Compare</h1>
          <p className="mt-1 text-muted">Up to six companies, side by side, for the same calendar year.</p>
        </header>

        <Picker tickers={tickers} onChange={(next) => update("tickers", next.join(","))} />
        {tickers[0] && (
          <PeerSetPanel
            ticker={tickers[0]}
            onCompare={(next) => update("tickers", next.slice(0, MAX_COMPANIES).join(","))}
          />
        )}

        {tickers.length < MIN_COMPANIES ? (
          <EmptyState message="Add at least two companies to compare them." />
        ) : (
          <>
            {comparison.isPending ? (
              // The size of the table and chart to come, so the section below does not jump.
              <div role="status" aria-label="Loading the comparison" className="space-y-12">
                <Skeleton shape="block" className="h-[34rem]" />
                <Skeleton shape="chart" className="h-64 max-w-2xl" />
              </div>
            ) : (
              <AsyncContent query={comparison}>
                {(data) => (
                  <Comparison data={data} metric={params.get("metric")} onMetric={(name) => update("metric", name)} />
                )}
              </AsyncContent>
            )}
            <Commentary key={tickers.join(",")} tickers={tickers} />
          </>
        )}
      </Container>
    </PanelProvider>
  );
}
