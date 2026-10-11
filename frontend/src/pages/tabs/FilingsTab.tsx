import { ArrowLeft, ArrowUpRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { FilingDiffView } from "../../components/filings/FilingDiffView";
import { DataTable } from "../../components/ui/DataTable";
import type { Column } from "../../components/ui/DataTable";
import { Delta } from "../../components/ui/Delta";
import { Input } from "../../components/ui/Input";
import { Section } from "../../components/ui/Section";
import { SegmentedControl } from "../../components/ui/SegmentedControl";
import { AsyncContent } from "../../components/ui/States";
import { PillTabPanel, PillTabs } from "../../components/ui/Tabs";
import { formatDate, formatUsd } from "../../lib/format";
import { useEarningsReactions, useFilingSections, useFilings } from "../../lib/queries";
import { EXTERNAL_LINK, safeHttpUrl } from "../../lib/safeUrl";
import { useMediaQuery } from "../../lib/useMediaQuery";
import type { EarningsResponse, FilingSummary } from "../../types";

type EarningsEvent = EarningsResponse["events"][number];
type View = "changes" | "outline";

/** From this width the list and the open filing sit side by side; below it they take turns. */
const TWO_COLUMN = "(min-width: 1024px)";
const DIFFABLE = new Set(["10-K", "10-Q"]);
const TYPE_ORDER = ["10-K", "10-Q", "8-K"];
const LINK_BUTTON =
  "inline-flex h-9 shrink-0 items-center gap-2 rounded-control border border-border-strong px-3.5 text-sm " +
  "font-medium transition-colors hover:bg-surface-2 active:bg-surface-3";

function FilingList({
  filings,
  selectedId,
  replace,
}: {
  filings: FilingSummary[];
  selectedId: string | null;
  replace: boolean;
}) {
  const [type, setType] = useState("all");
  const [query, setQuery] = useState("");
  const present = new Set(filings.map((f) => f.filing_type));
  const types = [...TYPE_ORDER.filter((t) => present.has(t)), ...[...present].filter((t) => !TYPE_ORDER.includes(t)).sort()];
  const term = query.trim().toLowerCase();
  const shown = filings.filter(
    (f) =>
      (type === "all" || f.filing_type === type) &&
      (!term ||
        `${f.filing_type} ${formatDate(f.filing_date)} ${f.filing_date ?? ""} ${f.period_end ?? ""} ${f.accession_number}`
          .toLowerCase()
          .includes(term)),
  );

  return (
    <nav
      aria-label="Filings"
      className="lg:sticky lg:top-[7.5rem] lg:flex lg:max-h-[calc(100dvh-8.5rem)] lg:flex-col"
    >
      <div className="space-y-3 pb-3">
        <SegmentedControl
          label="Filing type"
          value={type}
          onValueChange={setType}
          options={[{ value: "all", label: "All" }, ...types.map((t) => ({ value: t, label: t }))]}
        />
        <Input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Filter filings"
          placeholder="Filter by date or accession number"
        />
      </div>
      {shown.length === 0 ? (
        <p role="status" className="px-3 py-6 text-sm text-muted">
          No filings match.
        </p>
      ) : (
        <ul className="-mx-3 lg:mx-0 lg:min-h-0 lg:overflow-y-auto">
          {shown.map((f) => (
            <li key={f.filing_id}>
              <Link
                to={{ search: `?filing=${encodeURIComponent(f.filing_id)}` }}
                replace={replace}
                preventScrollReset
                aria-current={f.filing_id === selectedId ? "true" : undefined}
                className={`flex items-baseline gap-3 rounded-control px-3 py-2.5 transition-colors hover:bg-surface-2 ${
                  f.filing_id === selectedId ? "bg-surface-2" : ""
                }`}
              >
                <span className="w-11 shrink-0 text-sm font-medium">{f.filing_type}</span>
                <span className="min-w-0">
                  <span className="block text-sm">Filed {formatDate(f.filing_date)}</span>
                  {f.period_end && (
                    <span className="block text-caption text-muted">Period ending {formatDate(f.period_end)}</span>
                  )}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}

/** The sections found in a filing. The text itself is read at the SEC: only cited excerpts are
 *  shown in the app, beside the claim that cites them. */
function Outline({ filing }: { filing: FilingSummary }) {
  const sections = useFilingSections(filing.filing_id);
  const [query, setQuery] = useState("");
  const term = query.trim().toLowerCase();
  return (
    <AsyncContent
      query={sections}
      isEmpty={(data) => data.sections.length === 0}
      emptyMessage="No section outline is available for this filing."
    >
      {(data) => {
        const shown = data.sections.filter(
          (s) => !term || `${s.title} ${s.section_path.join(" ")}`.toLowerCase().includes(term),
        );
        return (
          <div>
            <Input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              aria-label="Filter sections"
              placeholder="Filter sections (Item 1A, risk, revenue…)"
              className="max-w-sm"
            />
            {shown.length === 0 ? (
              <p role="status" className="py-6 text-sm text-muted">
                No sections match “{query.trim()}”.
              </p>
            ) : (
              <ol aria-label="Filing sections" className="mt-3 divide-y divide-border/60">
                {shown.map((s, i) => (
                  <li key={i} className="flex flex-wrap items-baseline justify-between gap-x-4 py-2.5 text-sm">
                    <span>{s.title || s.section_path.join(" › ")}</span>
                    {s.section_path.length > 1 && (
                      <span className="text-caption text-muted">{s.section_path.join(" › ")}</span>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </div>
        );
      }}
    </AsyncContent>
  );
}

function FilingDetail({
  filing,
  candidates,
  view,
  onView,
  headingRef,
}: {
  filing: FilingSummary;
  candidates: FilingSummary[];
  view: View;
  onView: (view: View) => void;
  headingRef: RefObject<HTMLHeadingElement | null>;
}) {
  // The URL comes from the filing index, a third party: only a plain web address is linked.
  const original = safeHttpUrl(filing.primary_document_url);
  return (
    <article aria-labelledby="filing-heading" className="min-w-0">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b border-border pb-4">
        <div className="min-w-0">
          <h2
            id="filing-heading"
            ref={headingRef}
            tabIndex={-1}
            className="scroll-mt-4 text-title font-medium outline-none"
          >
            {filing.filing_type} filed {formatDate(filing.filing_date)}
          </h2>
          <p className="mt-1 text-caption text-muted">
            {[filing.period_end && `Period ending ${formatDate(filing.period_end)}`, `Accession ${filing.accession_number}`]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        {original ? (
          <a href={original} {...EXTERNAL_LINK} className={LINK_BUTTON}>
            Open original
            <ArrowUpRight aria-hidden className="size-4" />
          </a>
        ) : (
          <p className="text-caption text-muted">Original document not available</p>
        )}
      </header>

      <div className="pt-5">
        {DIFFABLE.has(filing.filing_type) ? (
          <PillTabs
            label="Filing views"
            value={view}
            onValueChange={onView}
            tabs={[
              { value: "changes", label: "Changes" },
              { value: "outline", label: "Outline" },
            ]}
          >
            <PillTabPanel value="changes" className="pt-6">
              <FilingDiffView key={filing.filing_id} filing={filing} candidates={candidates} />
            </PillTabPanel>
            <PillTabPanel value="outline" className="pt-6">
              <Outline key={filing.filing_id} filing={filing} />
            </PillTabPanel>
          </PillTabs>
        ) : (
          <Outline key={filing.filing_id} filing={filing} />
        )}
      </div>
    </article>
  );
}

const EARNINGS_COLUMNS: Column<EarningsEvent>[] = [
  { key: "filed", header: "Earnings 8-K filed", render: (e) => formatDate(e.filing.filing_date) },
  {
    key: "before",
    header: "Close before",
    numeric: true,
    render: (e) => (e.pre_close ? formatUsd(e.pre_close) : null),
  },
  {
    key: "after",
    header: "Close after",
    numeric: true,
    render: (e) => (e.post_close ? formatUsd(e.post_close) : null),
  },
  {
    key: "move",
    header: "Move",
    numeric: true,
    render: (e) =>
      e.move == null ? (
        <span className="text-subtle">N/A (no price data)</span>
      ) : (
        <Delta value={e.move} digits={1} />
      ),
  },
];

/** Deterministic price move around each earnings 8-K (§37.3). No expectations data is shown. */
function EarningsReactions({ ticker }: { ticker: string }) {
  const earnings = useEarningsReactions(ticker);
  return (
    <Section title="Earnings-day price reaction">
      <AsyncContent
        query={earnings}
        isEmpty={(d) => d.events.length === 0}
        emptyMessage="No earnings releases (8-K Item 2.02) have been ingested."
      >
        {(data) => (
          <div className="pt-4">
            <DataTable
              label="Earnings-day price reaction"
              caption="Change in adjusted close from the last session before each earnings 8-K to the first session after it."
              columns={EARNINGS_COLUMNS}
              rows={data.events}
              rowKey={(event) => event.filing.filing_id}
            />
          </div>
        )}
      </AsyncContent>
    </Section>
  );
}

/** Filings: the list, and beside it the open filing as what changed since the last one (the
 *  reason to open a 10-K) or as its outline. Which filing and view are open lives in the URL,
 *  so a comparison can be linked to and the browser's Back works on a phone. */
export default function FilingsTab() {
  const { ticker = "" } = useParams();
  const filings = useFilings(ticker, 200);
  const [params, setParams] = useSearchParams();
  const twoColumn = useMediaQuery(TWO_COLUMN);
  const headingRef = useRef<HTMLHeadingElement>(null);

  // Newest first by filing date; the API pages by id, which is not chronological.
  const all = useMemo(
    () => [...(filings.data ?? [])].sort((a, b) => (b.filing_date ?? "").localeCompare(a.filing_date ?? "")),
    [filings.data],
  );
  const requested = all.find((f) => f.filing_id === params.get("filing")) ?? null;
  // Side by side there is always a filing open: the latest annual report unless one was chosen.
  const selected = requested ?? (twoColumn ? (all.find((f) => f.filing_type === "10-K") ?? all[0] ?? null) : null);
  const requestedId = requested?.filing_id ?? null;

  const wanted = params.get("view");
  const view: View = wanted === "outline" || wanted === "changes" ? wanted : "changes";
  const setView = (next: View) =>
    setParams(
      (prev) => {
        prev.set("view", next);
        return prev;
      },
      { replace: true, preventScrollReset: true },
    );

  // On a phone, opening a filing replaces the list: bring its heading into view and focus, so
  // the reader (and a screen reader) starts at the top of what they opened.
  useEffect(() => {
    if (!twoColumn && requestedId) headingRef.current?.focus();
  }, [twoColumn, requestedId]);

  return (
    <AsyncContent
      query={filings}
      isEmpty={(data) => data.length === 0}
      emptyMessage={`No filings have been ingested for ${ticker.toUpperCase()}.`}
    >
      {() => (
        <div className="space-y-16">
          <div className="lg:grid lg:grid-cols-[300px_minmax(0,1fr)] lg:gap-x-12">
            {(twoColumn || !selected) && (
              <FilingList filings={all} selectedId={selected?.filing_id ?? null} replace={twoColumn} />
            )}
            {selected && (
              <div className="min-w-0">
                {!twoColumn && (
                  <Link
                    to={{ search: "" }}
                    preventScrollReset
                    className="-ml-2 mb-4 inline-flex h-10 items-center gap-1.5 rounded-control px-2 text-sm text-muted hover:text-text"
                  >
                    <ArrowLeft aria-hidden className="size-4" />
                    All filings
                  </Link>
                )}
                <FilingDetail
                  filing={selected}
                  candidates={all.filter(
                    (f) =>
                      f.filing_type === selected.filing_type &&
                      (f.filing_date ?? "") < (selected.filing_date ?? ""),
                  )}
                  view={view}
                  onView={setView}
                  headingRef={headingRef}
                />
              </div>
            )}
          </div>
          {(twoColumn || !selected) && <EarningsReactions ticker={ticker} />}
        </div>
      )}
    </AsyncContent>
  );
}
