import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";

import { freshnessLabel } from "../lib/format";
import type { Freshness } from "../types";
import { Badge, EmptyState, ErrorState, LoadingState } from "./primitives";

export function FreshnessBadge({ freshness }: { freshness: Freshness | null | undefined }) {
  if (!freshness) return null;
  const tone =
    freshness.freshness_status === "fresh"
      ? "neutral"
      : freshness.freshness_status === "stale"
        ? "warning"
        : "negative";
  const text =
    freshness.freshness_status === "failed"
      ? `Refresh failed · cached ${freshnessLabel(freshness.as_of).replace("Updated ", "")}`
      : freshnessLabel(freshness.as_of);
  return (
    <Badge tone={tone}>
      <span aria-hidden>{freshness.freshness_status === "fresh" ? "●" : "▲"}</span> {text}
    </Badge>
  );
}

export function Panel({
  title,
  kind = "data",
  freshness,
  actions,
  children,
}: {
  title: string;
  kind?: "data" | "ai";
  freshness?: Freshness | null | undefined;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      aria-label={title}
      className="rounded-xl border border-border bg-surface shadow-sm"
    >
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">{title}</h2>
          <Badge tone={kind === "ai" ? "ai" : "data"}>
            {kind === "ai" ? "AI interpretation" : "Data"}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          {actions}
          <FreshnessBadge freshness={freshness} />
        </div>
      </header>
      <div>{children}</div>
    </section>
  );
}

/** Renders the right state for a query: loading, error (retryable), empty, or the happy path. */
export function AsyncContent<T>({
  query,
  isEmpty,
  emptyMessage = "No data available.",
  children,
}: {
  query: UseQueryResult<T>;
  isEmpty?: (data: T) => boolean;
  emptyMessage?: string;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) return <LoadingState />;
  if (query.isError) {
    const message = query.error instanceof Error ? query.error.message : "Something went wrong.";
    return <ErrorState message={message} onRetry={() => void query.refetch()} />;
  }
  if (isEmpty?.(query.data)) return <EmptyState message={emptyMessage} />;
  return <>{children(query.data)}</>;
}
