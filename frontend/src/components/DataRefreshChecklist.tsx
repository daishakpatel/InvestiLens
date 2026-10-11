import { freshnessLabel } from "../lib/format";
import type { Freshness } from "../types";
import { Check, Clock, RefreshCw, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";

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

const ICON: Record<Step, LucideIcon> = {
  done: Check,
  pending: Clock,
  running: RefreshCw,
  failed: X,
};
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
    <div>
      <h2 className="mb-2 text-label font-medium text-muted">
        {allFresh ? "Research data up to date" : "Updating research data…"}
      </h2>
      <ul className="space-y-1 text-sm">
        {sources.map((s) => {
          const step = stepFor(s.freshness_status);
          const StepIcon = ICON[step];
          return (
            <li key={s.source} className="flex items-center gap-2">
              <StepIcon aria-hidden className={`${TONE[step]} size-3.5 shrink-0`} />
              <span>{LABELS[s.source] ?? s.source}</span>
              <span className="text-caption text-subtle">
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
