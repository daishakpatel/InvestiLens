import { formatPercent } from "../../lib/format";
import {
  BASIS_LABEL,
  EMPTY_TEXT,
  RESULT_LABEL,
  deltaText,
  dotPlot,
  guidedFigure,
  guidedText,
  isCompared,
  revisionText,
} from "../../lib/guidance";
import { useGuidance, useGuidanceTrackRecord } from "../../lib/queries";
import type { GuidanceRow, GuidanceTrackRecord } from "../../types";
import { useCitations } from "../citations/CitationContext";
import { Badge } from "../ui/Badge";
import { DataTable } from "../ui/DataTable";
import type { Column } from "../ui/DataTable";
import { Section } from "../ui/Section";
import { AsyncContent } from "../ui/States";

type Open = (sourceId: string) => void;

const LINK = "rounded-control text-left transition-colors hover:text-primary";

function signed(pct: number): string {
  return `${pct >= 0 ? "+" : "−"}${formatPercent(Math.abs(pct))}`;
}

/** Revenue against its guided range, quarter by quarter, on one "% from the guided midpoint"
 *  axis: the band is the range, the dot the actual. Every row says the same in text. */
function RangeDots({ record, onOpen }: { record: GuidanceTrackRecord; onOpen: Open }) {
  const { quarters, extent } = dotPlot(record.quarters);
  if (quarters.length === 0) return null;
  return (
    <figure className="space-y-1.5" aria-label="Revenue against its guided range, by quarter">
      {quarters.map((q) => {
        const said = `${q.label}: ${RESULT_LABEL[q.result]}${q.actualPct === null ? "" : `, ${signed(q.actualPct)} vs guided midpoint`}`;
        return (
          <button
            key={q.label}
            type="button"
            onClick={() => onOpen(q.sourceId)}
            aria-label={`${said}. Show the guidance quote`}
            className="grid w-full grid-cols-[5.5rem_minmax(0,1fr)_6.5rem] items-center gap-3 rounded-control text-caption hover:bg-surface-2"
          >
            <span className="tnum text-left text-muted">{q.label}</span>
            <span aria-hidden className="relative h-5">
              <span className="absolute inset-x-0 top-1/2 h-px bg-border" />
              <span className="absolute top-0 h-5 w-px bg-border-strong" style={{ left: "50%" }} />
              <span
                className="absolute top-1.5 h-2 rounded-full bg-subtle/60"
                style={{ left: `${q.rangeStart}%`, width: `${Math.max(q.rangeEnd - q.rangeStart, 0.6)}%` }}
              />
              {q.actual !== null && (
                <span
                  className="absolute top-1 size-3 -translate-x-1/2 rounded-full border-2 border-surface bg-text"
                  style={{ left: `${q.actual}%` }}
                />
              )}
            </span>
            <span className="tnum text-right text-muted">
              {q.actualPct === null ? RESULT_LABEL[q.result] : signed(q.actualPct)}
            </span>
          </button>
        );
      })}
      <figcaption className="tnum grid grid-cols-[5.5rem_minmax(0,1fr)_6.5rem] gap-3 text-caption text-subtle">
        <span />
        <span className="flex justify-between">
          <span>{signed(-extent)}</span>
          <span>Guided midpoint</span>
          <span>{signed(extent)}</span>
        </span>
        <span className="text-right">Actual</span>
      </figcaption>
    </figure>
  );
}

function TrackRecord({ record, onOpen }: { record: GuidanceTrackRecord; onOpen: Open }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-text" data-testid="guidance-track-record">
        {record.sufficient ? `${record.label} (n=${record.n_comparable})` : record.label}
      </p>
      <RangeDots record={record} onOpen={onOpen} />
    </div>
  );
}

function columns(onOpen: Open): Column<GuidanceRow>[] {
  return [
    { key: "period", header: "Period", render: (r) => <span className="tnum">{r.period_label}</span> },
    {
      key: "metric",
      header: "Metric",
      render: (r) => (
        <span>
          {r.metric_label}
          {BASIS_LABEL[r.basis] && <span className="ml-1.5 text-caption text-subtle">{BASIS_LABEL[r.basis]}</span>}
        </span>
      ),
    },
    {
      key: "guided",
      header: "Guided",
      numeric: true,
      render: (r) => (
        <div>
          <button
            type="button"
            onClick={() => onOpen(r.source_id)}
            title={r.quote}
            aria-label={`${guidedText(r, r)}. Show the quote: ${r.quote}`}
            className={`${LINK} tnum underline decoration-dotted underline-offset-4`}
          >
            {guidedText(r, r)}
          </button>
          {r.revisions.map((rev) => (
            <button
              key={rev.id}
              type="button"
              onClick={() => onOpen(rev.source_id)}
              className={`${LINK} block text-caption text-subtle`}
            >
              {revisionText(r, rev)}
            </button>
          ))}
        </div>
      ),
    },
    {
      key: "actual",
      header: "Actual",
      numeric: true,
      render: (r) => {
        const outcome = r.outcome;
        const source = outcome?.actual_source_ids[0];
        if (outcome?.result === "not_comparable") {
          return <span className="text-caption text-subtle">{outcome.explanation}</span>;
        }
        if (!outcome || outcome.actual_value === null || !source) return <span className="text-subtle">—</span>;
        return (
          <button type="button" onClick={() => onOpen(source)} className={`${LINK} tnum`}>
            {guidedFigure(r, outcome.actual_value)}
          </button>
        );
      },
    },
    {
      key: "result",
      header: "Result",
      render: (r) =>
        r.outcome && (
          <Badge tone={isCompared(r.outcome.result) ? "data" : "neutral"}>{RESULT_LABEL[r.outcome.result]}</Badge>
        ),
    },
    {
      key: "delta",
      header: "vs midpoint",
      numeric: true,
      render: (r) => <span className="tnum text-muted">{deltaText(r, r) ?? ""}</span>,
    },
  ];
}

/** Guidance vs actual (§37.3, FR-GD-015/016): what the company guided to in its own releases, the
 *  reported result, and how revenue has landed against its range. Company guidance only. */
export function GuidanceSection({ ticker }: { ticker: string }) {
  const guidance = useGuidance(ticker);
  const record = useGuidanceTrackRecord(ticker);
  const { open } = useCitations();
  return (
    <Section title="Guidance vs actual" kind="ai">
      <AsyncContent query={guidance} isEmpty={(d) => d.items.length === 0} emptyMessage={EMPTY_TEXT}>
        {(data) => (
          <div className="space-y-8 pt-4" data-testid="guidance">
            <p className="max-w-prose text-caption text-subtle">
              {data.scope} Each figure was read from the release by AI and kept only if it matches the
              release&apos;s exact words; select one to see the quote.
            </p>
            {record.data && <TrackRecord record={record.data} onOpen={open} />}
            <DataTable
              label="Guidance by period"
              columns={columns(open)}
              rows={data.items}
              rowKey={(r) => String(r.id)}
            />
          </div>
        )}
      </AsyncContent>
    </Section>
  );
}
