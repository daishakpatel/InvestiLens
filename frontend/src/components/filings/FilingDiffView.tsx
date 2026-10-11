import { ChevronRight } from "lucide-react";
import { useState } from "react";

import { ApiError } from "../../lib/apiClient";
import { summarizeDiff } from "../../lib/diffSummary";
import { formatDate, formatPercent } from "../../lib/format";
import { useFilingDiff } from "../../lib/queries";
import type { DiffOp, FilingDiffItem, FilingSummary } from "../../types";
import { CitationChip } from "../citations/CitationChip";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Select } from "../ui/Select";
import { ErrorState, LoadingState } from "../ui/States";
import { Switch } from "../ui/Switch";
import { CHANGE_ORDER, CHANGE_STATUS } from "./changeStatus";
import type { ChangeStatus } from "./changeStatus";

const CONTEXT_WORDS = 14; // unchanged words kept on each side of an edit

/** A long unchanged run, cut down to the words around the edits on either side of it. */
function trimEqual(text: string, first: boolean, last: boolean): string {
  const words = text.split(" ");
  if (words.length <= CONTEXT_WORDS * 2) return text;
  const head = first ? [] : words.slice(0, CONTEXT_WORDS);
  const tail = last ? [] : words.slice(-CONTEXT_WORDS);
  return [...head, "…", ...tail].join(" ");
}

/** The two wordings as one passage: insertions tinted, deletions struck through. Unchanged
 *  stretches are shortened so the edits stay findable, with the full text one click away. */
function WordDiff({ ops }: { ops: DiffOp[] }) {
  const [full, setFull] = useState(false);
  const trimmed = ops.map((op, i) => (op.op === "equal" ? trimEqual(op.text, i === 0, i === ops.length - 1) : op.text));
  const shortened = trimmed.some((text, i) => text !== ops[i]?.text);
  return (
    <div className="space-y-2">
      <p className="text-sm leading-relaxed">
        {ops.map((op, i) =>
          op.op === "insert" ? (
            <ins key={i} className="rounded-[3px] bg-positive/10 px-0.5 text-positive no-underline">
              {op.text}{" "}
            </ins>
          ) : op.op === "delete" ? (
            <del key={i} className="px-0.5 text-negative">
              {op.text}{" "}
            </del>
          ) : (
            <span key={i} className="text-muted">
              {full ? op.text : trimmed[i]}{" "}
            </span>
          ),
        )}
      </p>
      {shortened && (
        <Button variant="ghost" size="sm" className="-ml-2.5" aria-expanded={full} onClick={() => setFull((v) => !v)}>
          {full ? "Show less context" : "Show more context"}
        </Button>
      )}
    </div>
  );
}

/** Links to the passage in one filing. A passage can span several stored excerpts; each number
 *  opens one of them beside the page. */
function Sources({ label, ids, offset }: { label: string; ids: string[]; offset: number }) {
  if (ids.length === 0) return null;
  return (
    <span>
      {label}
      {ids.map((id, i) => (
        <CitationChip key={id} number={offset + i + 1} sourceId={id} />
      ))}
    </span>
  );
}

function DiffRow({ item, id }: { item: FilingDiffItem; id: string }) {
  const [open, setOpen] = useState(false);
  const passage = item.new ?? item.old;
  if (!passage) return null;
  const status = CHANGE_STATUS[item.status];
  const oldIds = item.old?.source_ids ?? [];
  const body = item.status === "removed" ? item.old?.text : item.new?.text;
  return (
    <li className="py-3">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-2.5 rounded-control text-left"
      >
        <ChevronRight
          aria-hidden
          className={`mt-0.5 size-4 shrink-0 text-subtle transition-transform ${open ? "rotate-90" : ""}`}
        />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{passage.heading}</span>
          <span className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted">
            <Badge tone={status.tone}>{status.label}</Badge>
            <span>{item.section}</span>
            {item.status === "reworded" && item.similarity != null && (
              // A near-identical passage still differs: one decimal keeps it from reading "100%".
              <span>{formatPercent(item.similarity, item.similarity >= 0.995 ? 1 : 0)} same wording</span>
            )}
            {item.decided_by === "threshold" && <span className="text-warning">Low-confidence match</span>}
            {item.decided_by === "llm" && <Badge tone="ai">Matched by AI</Badge>}
          </span>
        </span>
      </button>
      {open && (
        <div id={id} className="ml-[26px] mt-3 space-y-3">
          {item.old && item.new && item.old.heading !== item.new.heading && (
            <p className="text-caption text-muted">Previously titled: {item.old.heading}</p>
          )}
          {item.word_diff ? (
            <WordDiff ops={item.word_diff} />
          ) : body ? (
            <p className="whitespace-pre-line text-sm leading-relaxed">{body}</p>
          ) : (
            item.status === "unchanged" && (
              <p className="text-sm text-muted">The wording is the same in both filings.</p>
            )
          )}
          <p className="flex flex-wrap gap-x-5 gap-y-1 text-caption text-muted">
            <Sources label="Prior filing" ids={oldIds} offset={0} />
            <Sources label="This filing" ids={item.new?.source_ids ?? []} offset={oldIds.length} />
          </p>
        </div>
      )}
    </li>
  );
}

const rowKey = (item: FilingDiffItem, i: number) => item.new?.source_ids[0] ?? item.old?.source_ids[0] ?? `row-${i}`;

/** What changed between a filing and an earlier one of the same type (§37.4): a one-sentence
 *  summary, then each new, removed, or reworded passage. The comparison is deterministic text
 *  matching, not an AI judgment, and every passage links to its place in both filings. */
export function FilingDiffView({
  filing,
  candidates,
}: {
  filing: FilingSummary;
  candidates: FilingSummary[]; // earlier filings of the same type, to pick a baseline from
}) {
  const [against, setAgainst] = useState<string | null>(null);
  const [risksOnly, setRisksOnly] = useState(true);
  const [shown, setShown] = useState<ReadonlySet<ChangeStatus>>(new Set(["new", "removed", "reworded"]));
  const diff = useFilingDiff(filing.filing_id, against, risksOnly ? "risk_factor" : null);
  const status = diff.error instanceof ApiError ? diff.error.status : null;

  const toggle = (value: ChangeStatus) =>
    setShown((prev) => {
      const next = new Set(prev);
      if (!next.delete(value)) next.add(value);
      return next;
    });

  const visible = diff.data?.items.filter((item) => shown.has(item.status)) ?? [];
  const sorted = [...visible].sort((a, b) => CHANGE_ORDER.indexOf(a.status) - CHANGE_ORDER.indexOf(b.status));
  const estimated = diff.data?.caption_detection === "heuristic";
  const lowConfidence = diff.data?.items.some((item) => item.decided_by === "threshold") ?? false;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <Select aria-label="Compare against" value={against ?? ""} onChange={(e) => setAgainst(e.target.value || null)}>
          <option value="">Compared with the prior {filing.filing_type}</option>
          {candidates.map((c) => (
            <option key={c.filing_id} value={c.filing_id}>
              Compared with {c.filing_type} filed {formatDate(c.filing_date)}
            </option>
          ))}
        </Select>
        <Switch checked={risksOnly} onCheckedChange={setRisksOnly}>
          Risk factors only
        </Switch>
      </div>

      <div className="mt-6">
        {diff.isPending ? (
          <LoadingState label="Comparing filings" />
        ) : status === 404 ? (
          <p role="status" className="py-6 text-sm text-muted">
            There is no earlier {filing.filing_type} on file to compare this one with.
          </p>
        ) : status === 422 ? (
          // One of the two filings has no readable sections (of this kind). Said as it is, with
          // the wider comparison offered rather than silently substituted.
          <div role="status" className="space-y-3 py-6 text-sm text-muted">
            <p>
              {risksOnly
                ? "The risk factors could not be read from one of these filings, so there is nothing to compare."
                : "One of these filings has not been broken into sections, so the two cannot be compared."}
            </p>
            {risksOnly && <Button onClick={() => setRisksOnly(false)}>Compare all sections</Button>}
          </div>
        ) : diff.isError ? (
          <ErrorState message="Could not compare these filings." onRetry={() => void diff.refetch()} />
        ) : (
          <>
            <p className="max-w-2xl text-body leading-relaxed" data-testid="diff-summary">
              {summarizeDiff(
                diff.data.counts,
                risksOnly ? "risk factor" : "passage",
                `the ${diff.data.against.filing_type} filed ${formatDate(diff.data.against.filing_date)}`,
              )}
            </p>
            {(estimated || lowConfidence) && (
              <p role="note" className="mt-2 max-w-2xl text-caption text-warning">
                {estimated &&
                  "The original formatting was unavailable, so where each risk factor starts and ends was estimated from the text. "}
                {lowConfidence && "Some passages were paired on a low-confidence match and are marked below."}
              </p>
            )}

            <div role="group" aria-label="Kinds of change to show" className="mt-5 flex flex-wrap gap-2">
              {CHANGE_ORDER.map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={shown.has(value)}
                  onClick={() => toggle(value)}
                  className={`inline-flex h-7 items-center gap-1.5 rounded-full border px-3 text-label font-medium transition-colors ${
                    shown.has(value)
                      ? "border-border-strong bg-surface-2 text-text"
                      : "border-border text-muted hover:text-text"
                  }`}
                >
                  {CHANGE_STATUS[value].label}
                  <span className="tnum text-subtle">{diff.data.counts[value]}</span>
                </button>
              ))}
            </div>

            {sorted.length === 0 ? (
              <p role="status" className="py-6 text-sm text-muted">
                Nothing of the selected kinds changed.
              </p>
            ) : (
              <ul className="mt-3 divide-y divide-border/60">
                {sorted.map((item, i) => (
                  <DiffRow key={rowKey(item, i)} id={`change-${rowKey(item, i)}`} item={item} />
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  );
}
