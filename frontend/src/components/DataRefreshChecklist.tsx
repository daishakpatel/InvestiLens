import { freshnessLabel } from "../lib/format";
import type { Freshness } from "../types";

// §9.3 refresh checklist. States: done | pending | running | failed. We derive them from each
// source's freshness; a live SSE refresh job (per-source `running` transitions) lands with the
// Phase 5d worker, and this component already renders that state union.
type Step = "done" | "pending" | "running" | "failed";

const LABELS: Record<string, string> = {
  sec: "SEC filings & financial statements",
  price: "Market data",
  news: "News",
};

function stepFor(status: Freshness["freshness_status"]): Step {
  if (status === "fresh") return "done";
  if (status === "failed") return "failed";
  return "pending";
}

const ICON: Record<Step, string> = { done: "✓", pending: "…", running: "⟳", failed: "✗" };
const TONE: Record<Step, string> = {
  done: "text-positive",
  pending: "text-muted",
  running: "text-primary",
  failed: "text-negative",
};

export function DataRefreshChecklist({ sources }: { sources: Freshness[] }) {
  if (sources.length === 0) return null;
  const allFresh = sources.every((s) => s.freshness_status === "fresh");
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h2 className="mb-2 text-sm font-semibold">
        {allFresh ? "Research data up to date" : "Updating research data…"}
      </h2>
      <ul className="space-y-1 text-sm">
        {sources.map((s) => {
          const step = stepFor(s.freshness_status);
          return (
            <li key={s.source} className="flex items-center gap-2">
              <span className={`${TONE[step]} w-4 text-center`} aria-hidden>
                {ICON[step]}
              </span>
              <span>{LABELS[s.source] ?? s.source}</span>
              <span className="text-xs text-muted">
                {step === "failed"
                  ? `failed — using cached (${freshnessLabel(s.as_of).replace("Updated ", "")})`
                  : freshnessLabel(s.as_of)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
