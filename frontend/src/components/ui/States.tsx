import type { UseQueryResult } from "@tanstack/react-query";
import { CircleAlert, Inbox } from "lucide-react";
import type { ReactNode } from "react";

import { useApiStatus } from "../../lib/apiStatus";
import { Button } from "./Button";
import { Skeleton } from "./Skeleton";

/** Loading placeholder: skeleton lines, announced once to assistive tech (UI-002). */
export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-3 py-6">
      <Skeleton className="w-2/5" />
      <Skeleton />
      <Skeleton className="w-4/5" />
    </div>
  );
}

export function EmptyState({
  message,
  icon,
  action,
}: {
  message: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div role="status" className="flex flex-col items-center gap-3 px-4 py-10 text-center">
      <span aria-hidden className="text-subtle">
        {icon ?? <Inbox className="size-5" />}
      </span>
      <p className="max-w-sm text-sm text-muted">{message}</p>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-4 py-10 text-center">
      <CircleAlert aria-hidden className="size-5 text-negative" />
      <p className="max-w-sm text-sm text-text">{message}</p>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
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
  const { online, reachable } = useApiStatus();
  if (query.isPending) return <LoadingState />;
  if (query.isError) {
    // An outage is announced once, by the shell's banner; each panel waits instead of repeating
    // the error, and reloads on its own when the API is back.
    if (!online || !reachable) return <LoadingState label="Waiting for connection" />;
    const message = query.error instanceof Error ? query.error.message : "Something went wrong.";
    return <ErrorState message={message} onRetry={() => void query.refetch()} />;
  }
  if (isEmpty?.(query.data)) return <EmptyState message={emptyMessage} />;
  return <>{children(query.data)}</>;
}
