import type { ReactNode } from "react";

import { freshnessLabel } from "../../lib/format";
import type { Freshness } from "../../types";

export type BadgeTone = "data" | "ai" | "neutral" | "positive" | "negative" | "warning";

const DOT: Record<BadgeTone, string> = {
  data: "bg-primary",
  ai: "bg-ai",
  neutral: "bg-subtle",
  positive: "bg-positive",
  negative: "bg-negative",
  warning: "bg-warning",
};

/** A quiet label: a 6 px tone dot plus text. Reach for it only when the tone carries meaning. */
export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-caption font-medium text-muted">
      <span aria-hidden className={`size-1.5 shrink-0 rounded-full ${DOT[tone]}`} />
      {children}
    </span>
  );
}

/** Data freshness (FR-011): plain text when fresh, toned only when something is wrong. */
export function FreshnessBadge({ freshness }: { freshness: Freshness | null | undefined }) {
  if (!freshness) return null;
  const status = freshness.freshness_status;
  if (status === "fresh") {
    return <span className="text-caption text-subtle">{freshnessLabel(freshness.as_of)}</span>;
  }
  const cached = freshnessLabel(freshness.as_of).replace("Updated ", "");
  return (
    <Badge tone={status === "stale" ? "warning" : "negative"}>
      {status === "stale" ? `Stale · updated ${cached}` : `Refresh failed · cached ${cached}`}
    </Badge>
  );
}
