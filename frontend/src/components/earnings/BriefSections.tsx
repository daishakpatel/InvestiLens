// Phase 7j: the sections of a pre-earnings preview and a post-earnings brief. Every figure opens
// its source in the citation drawer; generated text sits under the AI mark; a section without
// its input shows "Not available: {reason}" instead of being left out (FR-EB-014).
import type { ReactNode } from "react";

import {
  changeText,
  figureText,
  missingReason,
  moveText,
  reportDateText,
  volumeText,
} from "../../lib/earnings";
import { formatDate } from "../../lib/format";
import { BASIS_LABEL, RESULT_LABEL, guidedFigure, guidedText } from "../../lib/guidance";
import type {
  BriefHeader,
  BriefMissing,
  BriefReaction,
  EarningsBrief,
  EarningsPreview,
  GuidanceRow,
  MetricTable,
} from "../../types";
import { CitationChips } from "../citations/CitationChip";
import { useCitations } from "../citations/CitationContext";
import { Section } from "../ui/Section";

const LINK = "tnum rounded-control underline decoration-border-strong underline-offset-2 hover:decoration-text";
const TH = "py-2 pr-4 text-left text-caption font-medium text-muted";
const TD = "py-2 pr-4 align-top";

/** "Not available: 10-Q not yet filed." — a section whose input is missing says so. */
export function NotAvailable({ reason }: { reason: string }) {
  return (
    <p role="status" className="pt-4 text-sm text-muted">
      Not available: {reason}
    </p>
  );
}

/** A figure that opens its first source. */
function Figure({ ids, children }: { ids: readonly string[]; children: string }) {
  const { open } = useCitations();
  const [first] = ids;
  if (!first || children === "—") return <span className="tnum">{children}</span>;
  return (
    <button type="button" onClick={() => open(first)} aria-label={`${children}. Open source`} className={LINK}>
      {children}
    </button>
  );
}

function Block({
  title,
  kind = "data",
  missing,
  section,
  children,
}: {
  title: string;
  kind?: "data" | "ai";
  missing: readonly BriefMissing[];
  section: string;
  children: ReactNode;
}) {
  const reason = missingReason(missing, section);
  return (
    <div className="earnings-block">
      <Section title={title} kind={kind}>
        {reason ? <NotAvailable reason={reason} /> : children}
      </Section>
    </div>
  );
}

export function BriefTitle({ header, kind, version }: { header: BriefHeader; kind: "preview" | "brief"; version: string }) {
  return (
    <header className="space-y-1">
      <p className="text-caption text-subtle">
        {kind === "preview" ? "Pre-earnings preview: what to watch" : "Post-earnings brief: what was reported"}
      </p>
      <h2 className="text-heading font-medium">
        {header.ticker} · {header.period_label}
      </h2>
      <p className="text-sm text-muted">
        {header.company_name ? `${header.company_name} · ` : ""}
        Report date {reportDateText(header.report_date, header.date_estimated, header.report_time)} · {version}
      </p>
    </header>
  );
}

function MetricTableView({ table }: { table: MetricTable }) {
  return (
    <div className="earnings-table overflow-x-auto pt-2">
      <table className="w-full min-w-[34rem] text-sm">
        <caption className="sr-only">Reported figures for {table.period_label}</caption>
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className={TH}>Metric</th>
            <th scope="col" className={`${TH} text-right`}>{table.period_label}</th>
            <th scope="col" className={`${TH} text-right`}>vs {table.prior_quarter_label}</th>
            <th scope="col" className={`${TH} text-right`}>vs {table.prior_year_label}</th>
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row) => (
            <tr key={row.metric} className="border-b border-border/60">
              <th scope="row" className={`${TD} text-left font-normal`}>{row.label}</th>
              <td className={`${TD} text-right`}>
                {row.value === null ? (
                  <span className="text-caption text-subtle">{row.reason ?? "—"}</span>
                ) : (
                  <Figure ids={row.source_ids ?? []}>{figureText(row.value, row.unit)}</Figure>
                )}
              </td>
              <td className={`${TD} text-right`}>
                <Figure ids={row.prior_quarter_source_ids ?? []}>
                  {changeText(row.change_vs_prior_quarter, row.change_kind)}
                </Figure>
              </td>
              <td className={`${TD} text-right`}>
                <Figure ids={row.prior_year_source_ids ?? []}>
                  {changeText(row.change_vs_prior_year, row.change_kind)}
                </Figure>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GuidanceTable({ rows, withOutcome }: { rows: readonly GuidanceRow[]; withOutcome: boolean }) {
  return (
    <div className="earnings-table overflow-x-auto pt-2">
      <table className="w-full min-w-[30rem] text-sm">
        <caption className="sr-only">Company guidance</caption>
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className={TH}>Metric</th>
            <th scope="col" className={`${TH} text-right`}>Guided</th>
            {withOutcome && <th scope="col" className={`${TH} text-right`}>Actual</th>}
            {withOutcome && <th scope="col" className={TH}>Result</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-border/60">
              <th scope="row" className={`${TD} text-left font-normal`}>
                {row.metric_label}
                {BASIS_LABEL[row.basis] && <span className="ml-1.5 text-caption text-subtle">{BASIS_LABEL[row.basis]}</span>}
              </th>
              <td className={`${TD} text-right`}>
                <Figure ids={[row.source_id]}>{guidedText(row, row)}</Figure>
              </td>
              {withOutcome && (
                <td className={`${TD} text-right`}>
                  <Figure ids={row.outcome?.actual_source_ids ?? []}>
                    {guidedFigure(row, row.outcome?.actual_value ?? null)}
                  </Figure>
                </td>
              )}
              {withOutcome && (
                <td className={`${TD} text-muted`}>
                  {row.outcome ? (row.outcome.explanation ?? RESULT_LABEL[row.outcome.result]) : "—"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReactionView({ reaction }: { reaction: BriefReaction }) {
  const stats: [string, string][] = [
    ["At the next open", moveText(reaction.move_at_open)],
    ["First close", moveText(reaction.move)],
    ["Five sessions", moveText(reaction.move_5d)],
  ];
  const volume = volumeText(reaction.volume_ratio);
  return (
    <div className="space-y-3 pt-4">
      <dl className="grid grid-cols-3 gap-4">
        {stats.map(([label, value]) => (
          <div key={label}>
            <dt className="text-caption text-muted">{label}</dt>
            <dd className="text-title">
              <Figure ids={reaction.source_ids ?? []}>{value}</Figure>
            </dd>
          </div>
        ))}
      </dl>
      <p className="text-caption text-subtle">
        Share price against the last close before the earnings 8-K filed {formatDate(reaction.filing_date)}
        {volume ? `; first session ${volume}` : ""}. Adjusted closes; a description, not a reading of the move.
      </p>
    </div>
  );
}

function Flags({ flags, empty }: { flags: EarningsBrief["new_flags"]; empty: string }) {
  const { open } = useCitations();
  if (!flags || flags.length === 0) return <p className="pt-4 text-sm text-muted">{empty}</p>;
  return (
    <ul className="divide-y divide-border/60 pt-2">
      {flags.map((flag) => (
        <li key={flag.source_id} className="py-3">
          <button type="button" onClick={() => open(flag.source_id)} className="text-left hover:text-primary">
            <span className="font-medium">{flag.label}</span>
            <span className="ml-2 text-caption text-subtle">{formatDate(flag.event_date)}</span>
          </button>
          <p className="mt-1 line-clamp-2 text-sm text-muted">{flag.snippet}</p>
        </li>
      ))}
    </ul>
  );
}

function Narrative({ narrative }: { narrative: NonNullable<EarningsBrief["narrative"]> }) {
  const order: string[] = [];
  for (const s of narrative.sentences) for (const id of s.source_ids) if (!order.includes(id)) order.push(id);
  const numberOf = (id: string) => order.indexOf(id) + 1;
  return (
    <div className="space-y-2 pt-4">
      <p className="max-w-3xl text-body leading-relaxed">
        {narrative.sentences.map((s) => (
          <span key={s.text}>
            {s.text}
            <CitationChips ids={s.source_ids} numberOf={numberOf} />{" "}
          </span>
        ))}
      </p>
      {narrative.dropped > 0 && (
        <p className="text-caption text-subtle">
          {narrative.dropped} proposed sentence{narrative.dropped === 1 ? "" : "s"} failed verification and{" "}
          {narrative.dropped === 1 ? "was" : "were"} left out.
        </p>
      )}
    </div>
  );
}

export function BriefView({ brief }: { brief: EarningsBrief }) {
  const missing = brief.missing ?? [];
  const changed = brief.what_changed;
  return (
    <div className="space-y-10">
      <Block title="Summary" kind="ai" missing={missing} section="narrative">
        {brief.narrative && <Narrative narrative={brief.narrative} />}
      </Block>
      <Block title="Reported figures" missing={missing} section="headline_table">
        {brief.headline_table && <MetricTableView table={brief.headline_table} />}
      </Block>
      <Block title="Against company guidance" missing={missing} section="versus_guidance">
        <GuidanceTable rows={brief.versus_guidance ?? []} withOutcome />
      </Block>
      <Block title="Price reaction" missing={missing} section="reaction">
        {brief.reaction && <ReactionView reaction={brief.reaction} />}
      </Block>
      <Block title="What changed" missing={missing} section="what_changed">
        {changed && (
          <div className="space-y-5 pt-4">
            <p className="text-sm">
              {changed.filing_type} filed {formatDate(changed.filing_date)} against the one filed{" "}
              {formatDate(changed.against_filing_date)}: {changed.new_risks} new, {changed.removed_risks} removed and{" "}
              {changed.reworded_risks} reworded risk factors.
            </p>
            {changed.top_changes.map((c) => (
              <ChangedPassageView key={`${c.status}-${c.heading}`} change={c} />
            ))}
            {changed.topic_shifts.length > 0 && <TopicShifts shifts={changed.topic_shifts} />}
          </div>
        )}
      </Block>
      <Block title="New red flags since the last report" missing={missing} section="new_flags">
        <Flags flags={brief.new_flags} empty="No red flags reported since the previous earnings release." />
      </Block>
    </div>
  );
}

function ChangedPassageView({ change }: { change: NonNullable<EarningsBrief["what_changed"]>["top_changes"][number] }) {
  const { open } = useCitations();
  return (
    <div className="space-y-1.5">
      <p className="text-sm">
        <span className="mr-2 rounded-control bg-surface-2 px-1.5 py-0.5 text-caption capitalize text-muted">{change.status}</span>
        <button type="button" onClick={() => change.source_ids[0] && open(change.source_ids[0])} className="text-left font-medium hover:text-primary">
          {change.heading}
        </button>
      </p>
      {change.old_quote && change.status === "reworded" && (
        <blockquote className="border-l-2 border-border pl-3 text-caption text-subtle">Before: {change.old_quote}</blockquote>
      )}
      {(change.new_quote ?? change.old_quote) && (
        <blockquote className="border-l-2 border-border-strong pl-3 text-caption text-muted">
          {change.status === "removed" ? "Removed: " : change.status === "reworded" ? "Now: " : ""}
          {change.new_quote ?? change.old_quote}
        </blockquote>
      )}
    </div>
  );
}

function TopicShifts({ shifts }: { shifts: NonNullable<EarningsBrief["what_changed"]>["topic_shifts"] }) {
  return (
    <div className="earnings-table overflow-x-auto">
      <table className="w-full min-w-[24rem] text-sm">
        <caption className="pb-2 text-left text-caption text-muted">
          MD&amp;A mentions per 1,000 words (topic_taxonomy_v1 lexicon counts, not an AI judgment)
        </caption>
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className={TH}>Topic</th>
            <th scope="col" className={`${TH} text-right`}>Before</th>
            <th scope="col" className={`${TH} text-right`}>Now</th>
          </tr>
        </thead>
        <tbody>
          {shifts.map((s) => (
            <tr key={s.topic} className="border-b border-border/60">
              <th scope="row" className={`${TD} text-left font-normal`}>{s.label}</th>
              <td className={`${TD} tnum text-right`}>{s.before_per_1k.toFixed(2)}</td>
              <td className={`${TD} text-right`}>
                <Figure ids={s.source_ids}>{s.after_per_1k.toFixed(2)}</Figure>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PreviewView({ preview }: { preview: EarningsPreview }) {
  const missing = preview.missing ?? [];
  const watch = preview.watch_items ?? [];
  const record = preview.track_record;
  return (
    <div className="space-y-10">
      <Block title="What to watch" kind={watch.some((w) => w.reworded) ? "ai" : "data"} missing={missing} section="watch_items">
        {watch.length === 0 ? (
          <p className="pt-4 text-sm text-muted">
            Nothing flagged: no figure, filing or management topic met a watch rule this quarter.
          </p>
        ) : (
          <ol className="list-decimal space-y-2 pl-5 pt-4 text-body">
            {watch.map((w, i) => (
              <li key={`${w.kind}-${i}`}>
                {w.text}
                <CitationChips ids={w.source_ids} numberOf={(id) => w.source_ids.indexOf(id) + 1} />
              </li>
            ))}
          </ol>
        )}
      </Block>
      <Block title="Last quarter" missing={missing} section="last_quarter_snapshot">
        {preview.last_quarter_snapshot && <MetricTableView table={preview.last_quarter_snapshot} />}
      </Block>
      <Block title={`Company guidance for ${preview.header.period_label}`} missing={missing} section="guidance_for_period">
        <GuidanceTable rows={preview.guidance_for_period ?? []} withOutcome={false} />
      </Block>
      <Block title="Guidance track record" missing={missing} section="track_record">
        {record && <p className="pt-4 text-sm">{`${record.label} (n=${record.n_comparable})`}</p>}
      </Block>
      <Block title="Valuation" missing={missing} section="valuation_snapshot">
        {preview.valuation_snapshot && (
          <ul className="space-y-2 pt-4 text-sm">
            {preview.valuation_snapshot.lines.map((line) => (
              <li key={line.multiple}>
                <span className="text-muted">{line.label}</span>{" "}
                <Figure ids={line.source_ids}>{`${Number(line.value).toFixed(1)}×`}</Figure>
                {line.own_label && <span className="text-muted">, {line.own_label} (n={line.own_n})</span>}
                {line.peer_label && <span className="text-muted">; {line.peer_label} (n={line.peer_n})</span>}
              </li>
            ))}
          </ul>
        )}
      </Block>
      <Block title="Red flags in the last 90 days" missing={missing} section="open_flags">
        <Flags flags={preview.open_flags} empty="No red flags reported in the last 90 days." />
      </Block>
      <Block title="Reaction to the last report" missing={missing} section="last_reaction">
        {preview.last_reaction && <ReactionView reaction={preview.last_reaction} />}
      </Block>
    </div>
  );
}
