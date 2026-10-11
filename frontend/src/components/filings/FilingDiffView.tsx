import { useState } from "react";

import { CitationChip } from "../citations/CitationChip";
import { Badge } from "../ui/Badge";
import { Section } from "../ui/Section";
import { EmptyState, LoadingState } from "../ui/States";
import { formatDate, formatPercent } from "../../lib/format";
import { useFilingDiff } from "../../lib/queries";
import type { DiffOp, FilingDiffItem, FilingSummary } from "../../types";

type Status = FilingDiffItem["status"];

const STATUS: Record<Status, { label: string; tone: "warning" | "negative" | "data" | "neutral" }> = {
  new: { label: "New", tone: "warning" },
  removed: { label: "Removed", tone: "negative" },
  reworded: { label: "Reworded", tone: "data" },
  unchanged: { label: "Unchanged", tone: "neutral" },
};
const ORDER: Status[] = ["new", "removed", "reworded", "unchanged"];
const CONTEXT_WORDS = 14; // unchanged words kept on each side of an edit

export function ChangeStatusBadge({ status }: { status: string | null | undefined }) {
  const s = status ? STATUS[status as Status] : undefined;
  return s ? <Badge tone={s.tone}>{s.label} vs prior filing</Badge> : null;
}

/** Long unchanged runs are trimmed to the words around each edit, so the edits stay findable. */
function trimEqual(text: string, first: boolean, last: boolean): string {
  const words = text.split(" ");
  if (words.length <= CONTEXT_WORDS * 2) return text;
  const head = first ? [] : words.slice(0, CONTEXT_WORDS);
  const tail = last ? [] : words.slice(-CONTEXT_WORDS);
  return [...head, "…", ...tail].join(" ");
}

function WordDiff({ ops }: { ops: DiffOp[] }) {
  return (
    <p className="text-sm leading-relaxed">
      {ops.map((op, i) =>
        op.op === "insert" ? (
          <ins key={i} className="rounded bg-positive/15 px-0.5 text-positive no-underline">
            {op.text}{" "}
          </ins>
        ) : op.op === "delete" ? (
          <del key={i} className="rounded bg-negative/15 px-0.5 text-negative">
            {op.text}{" "}
          </del>
        ) : (
          <span key={i} className="text-muted">
            {trimEqual(op.text, i === 0, i === ops.length - 1)}{" "}
          </span>
        ),
      )}
    </p>
  );
}

function Sources({ label, ids, offset }: { label: string; ids: string[]; offset: number }) {
  if (ids.length === 0) return null;
  return (
    <span className="text-xs text-muted">
      {label}
      {ids.map((id, i) => (
        <CitationChip key={id} number={offset + i + 1} sourceId={id} />
      ))}
    </span>
  );
}

function DiffRow({ item }: { item: FilingDiffItem }) {
  const passage = item.new ?? item.old;
  if (!passage) return null;
  const oldIds = item.old?.source_ids ?? [];
  const body = item.new?.text ?? item.old?.text;
  return (
    <li className="flex flex-col gap-1.5 border-b border-border/60 px-4 py-3 last:border-0">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={STATUS[item.status].tone}>{STATUS[item.status].label}</Badge>
        <span className="text-xs text-muted">{item.section}</span>
        {item.status === "reworded" && item.similarity != null && (
          <span className="text-xs text-muted">{formatPercent(item.similarity, 0)} same wording</span>
        )}
        {item.decided_by === "threshold" && <Badge tone="neutral">Low-confidence match</Badge>}
        {item.decided_by === "llm" && <Badge tone="ai">AI-adjudicated match</Badge>}
      </div>
      <p className="text-sm font-medium">{passage.heading}</p>
      {item.old && item.new && item.old.heading !== item.new.heading && (
        <p className="text-xs text-muted">Previously: {item.old.heading}</p>
      )}
      <div className="flex flex-wrap gap-x-4">
        <Sources label="Prior filing" ids={oldIds} offset={0} />
        <Sources label="This filing" ids={item.new?.source_ids ?? []} offset={oldIds.length} />
      </div>
      {item.word_diff && (
        <details>
          <summary className="cursor-pointer text-xs text-primary">Show wording changes</summary>
          <div className="mt-2">
            <WordDiff ops={item.word_diff} />
          </div>
        </details>
      )}
      {body && (
        <details>
          <summary className="cursor-pointer text-xs text-primary">
            {item.status === "new" ? "Read the new passage" : "Read the removed passage"}
          </summary>
          <p className="mt-2 whitespace-pre-line text-sm leading-relaxed">{body}</p>
        </details>
      )}
    </li>
  );
}

/** Filing-to-filing change detection (§37.4): what is new, removed, or reworded vs. a baseline. */
export function FilingDiffView({
  filing,
  candidates,
}: {
  filing: FilingSummary;
  candidates: FilingSummary[]; // other filings of the same type, to pick a baseline from
}) {
  const [against, setAgainst] = useState<string | null>(null);
  const [risksOnly, setRisksOnly] = useState(true);
  const [shown, setShown] = useState<Set<Status>>(new Set(["new", "removed", "reworded"]));
  const diff = useFilingDiff(filing.filing_id, against, risksOnly ? "risk_factor" : null);

  const toggle = (status: Status) =>
    setShown((prev) => {
      const next = new Set(prev);
      if (!next.delete(status)) next.add(status);
      return next;
    });

  return (
    <Section
      title="What changed"
      actions={
        <>
          <label className="flex items-center gap-1 text-xs text-muted">
            <input
              type="checkbox"
              checked={risksOnly}
              onChange={(e) => setRisksOnly(e.target.checked)}
            />
            Risk factors only
          </label>
          <select
            aria-label="Compare against"
            value={against ?? ""}
            onChange={(e) => setAgainst(e.target.value || null)}
            className="rounded-control border border-border bg-surface px-2 py-1 text-xs"
          >
            <option value="">vs prior {filing.filing_type}</option>
            {candidates.map((c) => (
              <option key={c.filing_id} value={c.filing_id}>
                vs {c.filing_type} · {formatDate(c.filing_date)}
              </option>
            ))}
          </select>
        </>
      }
    >
      {diff.isPending ? (
        <LoadingState label="Comparing filings" />
      ) : diff.isError ? (
        <EmptyState message="No earlier parsed filing of this type to compare with." />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
            <span className="text-xs text-muted">
              Compared with {diff.data.against.filing_type} filed{" "}
              {formatDate(diff.data.against.filing_date)}:
            </span>
            {ORDER.map((status) => (
              <button
                key={status}
                type="button"
                aria-pressed={shown.has(status)}
                onClick={() => toggle(status)}
                className={`rounded-full border px-2 py-0.5 text-xs ${
                  shown.has(status) ? "border-primary text-text" : "border-border text-muted"
                }`}
              >
                {STATUS[status].label} {diff.data.counts[status]}
              </button>
            ))}
          </div>
          {diff.data.caption_detection === "heuristic" && (
            <p role="note" className="border-b border-border px-4 py-2 text-xs text-warning">
              The original filing’s formatting was unavailable, so risk-factor boundaries were
              estimated from the text. Some entries may be split or merged differently.
            </p>
          )}
          <ul className="max-h-[40rem] overflow-auto">
            {diff.data.items
              .filter((item) => shown.has(item.status))
              .sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status))
              .map((item, i) => (
                <DiffRow key={`${item.status}-${i}`} item={item} />
              ))}
          </ul>
          {diff.data.items.every((item) => !shown.has(item.status)) && (
            <EmptyState message="Nothing matches the selected change types." />
          )}
          <p className="px-4 py-3 text-xs text-muted">
            Deterministic comparison of the two filings’ text. Each entry links to the exact
            passages in both filings.
          </p>
        </>
      )}
    </Section>
  );
}
