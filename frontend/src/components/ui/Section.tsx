import type { ReactNode } from "react";

import type { Freshness } from "../../types";
import { AiMark } from "./AiMark";
import { FreshnessBadge } from "./Badge";

/** The default container: a heading row and content, with no border and no background.
 *  `kind="ai"` adds the AI mark that distinguishes generated content from data (FR-010). */
export function Section({
  title,
  id,
  kind = "data",
  freshness,
  actions,
  children,
}: {
  title: string;
  id?: string; // anchor target for in-page links (old tab URLs redirect to these)
  kind?: "data" | "ai";
  freshness?: Freshness | null | undefined;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-label={title}>
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-border pb-3">
        <div className="flex items-baseline gap-2.5">
          <h2 className="text-title font-medium">{title}</h2>
          {kind === "ai" && <AiMark />}
        </div>
        <div className="flex items-center gap-3">
          {actions}
          <FreshnessBadge freshness={freshness} />
        </div>
      </header>
      <div>{children}</div>
    </section>
  );
}

/** The one bordered, raised container, for content that genuinely needs separating. */
export function Surface({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <div className={`rounded-surface border border-border bg-surface ${className}`}>{children}</div>
  );
}
