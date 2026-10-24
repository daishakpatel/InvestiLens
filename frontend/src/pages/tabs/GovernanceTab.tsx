import { useState } from "react";
import { useParams } from "react-router-dom";

import { LadderChart } from "../../charts/LadderChart";
import { PayVsTsrChart } from "../../charts/PayVsTsrChart";
import { formatValue } from "../../charts/series";
import { useCitations } from "../../components/citations/CitationContext";
import { Badge } from "../../components/ui/Badge";
import { DataTable } from "../../components/ui/DataTable";
import type { Column } from "../../components/ui/DataTable";
import { Section } from "../../components/ui/Section";
import { Select } from "../../components/ui/Select";
import { AsyncContent, EmptyState } from "../../components/ui/States";
import { formatDate, toNumber } from "../../lib/format";
import { componentColumns, fieldText, pvpRows, ratioText, roleLabel } from "../../lib/governance";
import { useGovernance, useGovernanceHistory } from "../../lib/queries";
import type { CompensationRow, GovernanceResponse } from "../../types";

const SECTION_LABELS: Record<string, string> = {
  summary_compensation_table: "Summary Compensation Table",
  pay_versus_performance: "Pay Versus Performance",
  pay_ratio: "CEO pay ratio",
  cd_and_a: "Compensation Discussion and Analysis",
  say_on_pay: "Say-on-pay vote",
  beneficial_ownership: "Security ownership",
  director_independence: "Director independence",
  committees: "Board committees",
  board: "Board of directors",
};

const money = (value: string | null | undefined): string => {
  const n = toNumber(value ?? null);
  return n === null ? "—" : formatValue(n, "money");
};

/** A value that opens its source; the quote it rests on shows on hover (FR-GV-012). */
function Sourced({ sourceId, quote, children }: { sourceId: string; quote?: string | null | undefined; children: string }) {
  const { open } = useCitations();
  return (
    <button
      type="button"
      title={quote ?? undefined}
      onClick={() => open(sourceId)}
      aria-label={`${children}. Open source`}
      className="tnum text-right underline decoration-border-strong underline-offset-2 hover:decoration-text"
    >
      {children}
    </button>
  );
}

/** Tier C: AI-read facts, each with its quote, or "Not stated" (FR-GV-007, FR-GV-012). */
function Board({ data }: { data: GovernanceResponse }) {
  const facts = data.facts;
  return (
    <Section title="Board" kind="ai">
      {!facts || facts.status !== "extracted" ? (
        <p role="status" className="pt-4 text-sm text-muted">
          {facts?.status === "pending"
            ? "Not read yet. Board facts are extracted once, after the proxy is processed."
            : (facts?.reason ?? "No board information is available.")}
        </p>
      ) : (
        <>
          <dl className="divide-y divide-border/60 pt-2" data-testid="board-facts">
            {facts.fields.map((f) => (
              <div key={f.name} className="flex items-baseline justify-between gap-4 py-2 text-sm">
                <dt className="text-muted">{f.label}</dt>
                <dd className={f.value === null || f.value === undefined ? "text-subtle" : "text-text"}>
                  {f.paragraph_id ? (
                    <Sourced sourceId={f.paragraph_id} quote={f.quote}>
                      {fieldText(f)}
                    </Sourced>
                  ) : (
                    fieldText(f)
                  )}
                </dd>
              </div>
            ))}
            <div className="flex items-baseline justify-between gap-4 py-2 text-sm">
              <dt className="text-muted">Independence ratio</dt>
              <dd className={facts.independence_ratio ? "tnum text-text" : "text-subtle"}>
                {facts.independence_ratio
                  ? formatValue(Number(facts.independence_ratio), "percent")
                  : "Not stated"}
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-caption text-subtle">
            Each answer quotes the proxy word for word; hover to read the quote, select it to open the
            paragraph. The independence ratio is computed from the two counts, never read by AI.
          </p>
        </>
      )}
    </Section>
  );
}

/** Pay by component. One officer's rows are labelled by year (the name is printed once above);
 *  several officers' rows by name, so the Total column stays on screen. */
function PayTable({ rows, caption, byYear }: { rows: CompensationRow[]; caption: string; byYear: boolean }) {
  const columns: Column<CompensationRow>[] = [
    byYear
      ? { key: "year", header: "Fiscal year", render: (r) => `FY${r.fiscal_year}` }
      : { key: "who", header: "Officer", render: (r) => r.person },
    ...componentColumns(rows).map(
      ([key, label]): Column<CompensationRow> => ({
        key,
        header: label,
        numeric: true,
        render: (r) => money(r.components[key]),
      }),
    ),
    {
      key: "total",
      header: "Total",
      numeric: true,
      render: (r) => <Sourced sourceId={r.source_id}>{money(r.total)}</Sourced>,
    },
  ];
  return (
    <DataTable
      density="compact"
      label={caption}
      columns={columns}
      rows={rows}
      rowKey={(r) => `${r.person}-${r.fiscal_year}`}
    />
  );
}

/** Tier B: Summary Compensation Table rows that add up, and the validated pay ratio. */
function Pay({ data }: { data: GovernanceResponse }) {
  const comp = data.compensation;
  const ceo = comp?.rows.filter((r) => r.role === "peo") ?? [];
  const others = comp?.rows.filter((r) => r.role !== "peo" && r.fiscal_year === data.fiscal_year) ?? [];
  const ratio = data.pay_ratio;
  return (
    <Section title="CEO pay" actions={<Badge>Extracted from filing tables</Badge>}>
      <div className="space-y-5 pt-4">
        {ceo.length > 0 ? (
          <div>
            <p className="mb-2 text-sm text-text">{ceo[0]?.person}</p>
            <PayTable rows={ceo} caption="CEO pay by fiscal year" byYear />
          </div>
        ) : (
          <p role="status" className="text-sm text-muted">
            {comp?.reason ?? "Not found in this proxy."}
          </p>
        )}
        {comp && comp.rejected_rows > 0 && (
          <p role="note" className="text-caption text-warning">
            {comp.rejected_rows} row{comp.rejected_rows === 1 ? "" : "s"} of the table did not add up to
            the total and {comp.rejected_rows === 1 ? "is" : "are"} not shown.
          </p>
        )}
        <div className="flex flex-wrap items-baseline gap-x-3 text-sm" data-testid="pay-ratio">
          <span className="text-muted">CEO pay ratio</span>
          {ratio?.ratio && ratio.source_id ? (
            <>
              <Sourced sourceId={ratio.source_id}>{ratioText(ratio.ratio)}</Sourced>
              <span className="text-caption text-subtle">
                median employee {money(ratio.median_pay)} · checked against CEO total {money(ratio.ceo_total)}
              </span>
            </>
          ) : (
            <span className="text-subtle">{ratio?.reason ?? "Not found in this proxy."}</span>
          )}
        </div>
        {others.length > 0 && (
          <details>
            <summary className="cursor-pointer text-sm text-muted">
              Other named officers ({roleLabel("pfo")} and others)
            </summary>
            <div className="mt-3">
              <PayTable rows={others} caption="Other named officers' pay" byYear={false} />
            </div>
          </details>
        )}
      </div>
    </Section>
  );
}

/** Governance (§37, Phase 7g): who oversees the company and how its executives are paid, from
 *  the annual proxy statement. Exact XBRL and validated tables first; AI only for prose facts. */
export default function GovernanceTab() {
  const { ticker = "" } = useParams();
  const [year, setYear] = useState<number | null>(null);
  const governance = useGovernance(ticker, year);
  const history = useGovernanceHistory(ticker);
  return (
    <AsyncContent query={governance}>
      {(data) => {
        if (!data.filing || data.fiscal_year === null) {
          return (
            <EmptyState
              message={`${data.reason ?? "No proxy statement is available."} Proxy statements ingested for ${data.company_ticker}: ${data.proxies_ingested}.`}
            />
          );
        }
        const missing = Object.entries(data.coverage)
          .filter(([, found]) => !found)
          .map(([key]) => SECTION_LABELS[key] ?? key);
        const pvp = pvpRows(data.pay_vs_performance?.points ?? []);
        const trend = (history.data?.points ?? []).flatMap((p) => {
          const value = toNumber(p.ceo_total_pay ?? null);
          return value === null || !p.ceo_total_pay_source_id
            ? []
            : [{ window: `FY${String(p.fiscal_year).slice(2)}`, value, sourceId: p.ceo_total_pay_source_id }];
        });
        return (
          <div className="space-y-12">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="max-w-3xl text-caption text-subtle">
                From the proxy statement covering fiscal {data.fiscal_year}, filed {formatDate(data.filing.filing_date)}.
                What a proxy does not state, or what fails a check, is shown as not stated, never guessed.
              </p>
              {data.available_years.length > 1 && (
                <Select
                  aria-label="Proxy year"
                  value={String(data.fiscal_year)}
                  onChange={(e) => setYear(Number(e.target.value))}
                >
                  {data.available_years.map((y) => (
                    <option key={y} value={y}>
                      Fiscal {y} proxy
                    </option>
                  ))}
                </Select>
              )}
            </div>
            {missing.length > 0 && (
              <p role="note" className="-mt-8 text-caption text-warning">
                Not found in this proxy: {missing.join(", ")}.
              </p>
            )}

            <div className="grid gap-12 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
              <Board data={data} />
              <div className="min-w-0 space-y-12">
                <Pay data={data} />
                <Section
                  title="Pay versus performance"
                  actions={<Badge>From the proxy's XBRL</Badge>}
                >
                  <div className="pt-4">
                    {pvp.length > 0 ? (
                      <PayVsTsrChart ticker={data.company_ticker} rows={pvp} />
                    ) : (
                      <p role="status" className="text-sm text-muted">
                        {data.pay_vs_performance?.reason ?? "Not found in this proxy."}
                      </p>
                    )}
                    {data.pay_vs_performance?.company_selected_measure && (
                      <p className="mt-2 text-caption text-subtle">
                        Company-selected measure: {data.pay_vs_performance.company_selected_measure}
                      </p>
                    )}
                  </div>
                </Section>
                {trend.length > 1 && (
                  <Section title="CEO total pay over time">
                    <div className="pt-4">
                      <LadderChart
                        title="CEO total pay"
                        rows={trend}
                        period="Total"
                        slug={`${data.company_ticker}_ceo_total_pay`}
                        columnHeader="Fiscal year"
                        source="proxy statements"
                      />
                    </div>
                  </Section>
                )}
              </div>
            </div>
          </div>
        );
      }}
    </AsyncContent>
  );
}
