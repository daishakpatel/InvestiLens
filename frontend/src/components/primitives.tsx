import { useId, useState } from "react";
import type { ReactNode } from "react";

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span
      role="status"
      aria-label={label}
      className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-muted border-t-transparent"
    />
  );
}

type BadgeTone = "data" | "ai" | "neutral" | "positive" | "negative" | "warning";

const toneClass: Record<BadgeTone, string> = {
  data: "bg-primary/10 text-primary",
  ai: "bg-ai/10 text-ai",
  neutral: "bg-surface-2 text-muted",
  positive: "bg-positive/10 text-positive",
  negative: "bg-negative/10 text-negative",
  warning: "bg-warning/10 text-warning",
};

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: BadgeTone;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${toneClass[tone]}`}
    >
      {children}
    </span>
  );
}

export function LoadingState({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-6 text-sm text-muted">
      <Spinner /> <span>{label ?? "Loading…"}</span>
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="p-6 text-center text-sm text-muted" role="status">
      {message}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-start gap-2 p-6 text-sm" role="alert">
      <span className="text-negative">{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md border border-border px-3 py-1 text-xs font-medium hover:bg-surface-2"
        >
          Retry
        </button>
      )}
    </div>
  );
}

/** Accessible tooltip: works on hover and keyboard focus (UI-003). */
export function Tooltip({ label, children }: { label: ReactNode; children: ReactNode }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex">
      <span
        tabIndex={0}
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="cursor-help underline decoration-dotted underline-offset-2"
      >
        {children}
      </span>
      {open && (
        <span
          role="tooltip"
          id={id}
          className="absolute left-1/2 top-full z-20 mt-1 w-max max-w-xs -translate-x-1/2 rounded-md border border-border bg-surface p-2 text-left text-xs font-normal text-text shadow-lg"
        >
          {label}
        </span>
      )}
    </span>
  );
}
