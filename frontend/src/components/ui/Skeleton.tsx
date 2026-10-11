import { cn } from "./cn";

type Shape = "text" | "block" | "chart" | "row";

const SHAPE: Record<Shape, string> = {
  text: "h-3.5 w-full rounded-full",
  block: "h-24 w-full rounded-surface",
  chart: "h-64 w-full rounded-surface",
  row: "h-9 w-full rounded-control",
};

/** A placeholder shaped like the content it stands in for (UI-002). Decorative: pair it with a
 *  `role="status"` label, as `LoadingState` does. */
export function Skeleton({ shape = "text", className }: { shape?: Shape; className?: string }) {
  return <div aria-hidden className={cn("animate-shimmer bg-surface-2", SHAPE[shape], className)} />;
}

/** Small inline spinner for in-place waits (a button, a streaming answer). */
export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span
      role="status"
      aria-label={label}
      className="inline-block size-4 animate-spin rounded-full border-2 border-subtle border-t-transparent"
    />
  );
}
