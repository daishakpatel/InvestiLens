// Phase 7k (FR-TH-010, FR-TH-017): "Draft from my notes". The model only suggests a title and
// registry metrics with starting thresholds; the user reviews each suggestion, edits it, and
// nothing is saved until they accept. No stance is ever suggested.
import { useState } from "react";

import { COMPARATOR_SYMBOL, valueText } from "../../lib/thesis";
import { useDraftThesis } from "../../lib/thesisQueries";
import type { DraftKpi, KpiCreate } from "../../types";
import { AiMark } from "../ui/AiMark";
import { Button } from "../ui/Button";
import { TEXTAREA } from "./styles";

export function DraftAssist({
  ticker,
  onAccept,
}: {
  ticker: string;
  onAccept: (title: string | null, kpis: KpiCreate[]) => void;
}) {
  const [notes, setNotes] = useState("");
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [useTitle, setUseTitle] = useState(true);
  const draft = useDraftThesis();
  const result = draft.data;

  const toggle = (i: number) =>
    setPicked((old) => {
      const next = new Set(old);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  const accept = () => {
    if (!result) return;
    const kpis = result.kpis
      .filter((_, i) => picked.has(i))
      .map(({ metric, period_type, comparator, threshold, label, rationale }: DraftKpi) => ({
        metric,
        period_type,
        comparator,
        threshold,
        label,
        rationale,
      }));
    onAccept(useTitle ? result.title : null, kpis);
    draft.reset();
    setPicked(new Set());
  };

  return (
    <section aria-label="Draft from my notes" className="space-y-3 rounded-surface border border-border p-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-medium">Draft from my notes</h3>
        <AiMark label="AI suggestions" />
      </div>
      <p className="text-caption text-subtle">
        Paste your own notes. The model only suggests a title and metrics from the list with starting thresholds;
        you choose what to keep and edit every threshold. It never suggests a stance, and nothing is saved until you
        accept.
      </p>
      <textarea
        className={TEXTAREA}
        rows={4}
        maxLength={5000}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        aria-label="Your notes"
        placeholder="e.g. Data-center demand should keep revenue growing; margins depend on pricing."
      />
      <Button
        size="sm"
        loading={draft.isPending}
        disabled={!notes.trim()}
        onClick={() => draft.mutate({ ticker, notes })}
      >
        Suggest a structure
      </Button>
      {draft.isError && (
        <p role="alert" className="text-sm text-negative">
          {draft.error.message}
        </p>
      )}
      {result && (
        <div className="space-y-2" aria-label="Suggestions to review">
          {result.title && (
            <label className="flex items-start gap-2 rounded-control bg-surface-2 p-2 text-sm">
              <input type="checkbox" checked={useTitle} onChange={(e) => setUseTitle(e.target.checked)} className="mt-1" />
              <span>
                <span className="mr-1.5 font-mono text-primary">+</span>Title: {result.title}
              </span>
            </label>
          )}
          {result.kpis.length === 0 && <p className="text-sm text-muted">No suggestion fit the metric list.</p>}
          {result.kpis.map((kpi, i) => (
            <label key={`${kpi.metric}-${i}`} className="flex items-start gap-2 rounded-control bg-surface-2 p-2 text-sm">
              <input type="checkbox" checked={picked.has(i)} onChange={() => toggle(i)} className="mt-1" aria-label={`Keep ${kpi.label}`} />
              <span>
                <span className="mr-1.5 font-mono text-primary">+</span>
                {kpi.label}: {kpi.metric_label} ({kpi.period_type}) {COMPARATOR_SYMBOL[kpi.comparator]}{" "}
                {valueText(kpi.threshold, kpi.unit)}
                <span className="ml-1.5 text-caption text-subtle">starting threshold, edit it</span>
                {kpi.rationale && <span className="block text-caption text-muted">{kpi.rationale}</span>}
              </span>
            </label>
          ))}
          {result.dropped > 0 && (
            <p className="text-caption text-subtle">
              {result.dropped} suggestion{result.dropped === 1 ? " was" : "s were"} left out (not a trackable metric, period or
              unit).
            </p>
          )}
          <div className="flex gap-2">
            <Button size="sm" variant="primary" onClick={accept} disabled={!useTitle && picked.size === 0}>
              Accept selected
            </Button>
            <Button size="sm" variant="ghost" onClick={() => draft.reset()}>
              Discard
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
