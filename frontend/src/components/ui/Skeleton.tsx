import { cn } from "./cn";

type Shape = "text" | "block" | "chart" | "row";

const SHAPE: Record<Shape, { height: string; radius: string }> = {
  text: { height: "h-3.5", radius: "rounded-full" },
  block: { height: "h-24", radius: "rounded-surface" },
  chart: { height: "h-64", radius: "rounded-surface" },
  row: { height: "h-9", radius: "rounded-control" },
};
const sets = (className: string | undefined, prefix: string) =>
  new RegExp(`(^|\\s)(max-)?${prefix}-`).test(className ?? "");

/** A placeholder shaped like the content it stands in for (UI-002). Decorative: pair it with a
 *  `role="status"` label, as `LoadingState` does. */
export function Skeleton({ shape = "text", className }: { shape?: Shape; className?: string }) {
  // Defaults apply only where the caller did not size it: two width utilities on one element
  // would be decided by stylesheet order, not by which was written last.
  const { height, radius } = SHAPE[shape];
  return (
    <div
      aria-hidden
      className={cn(
        "animate-shimmer bg-surface-2",
        radius,
        !sets(className, "h") && height,
        !sets(className, "w") && "w-full",
        className,
      )}
    />
  );
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
