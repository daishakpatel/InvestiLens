import { ExternalLink } from "lucide-react";
import { useState } from "react";

import { formatDate } from "../../lib/format";
import { detailText, emptyText, severityLabel, severityTone } from "../../lib/redFlags";
import { safeHttpUrl } from "../../lib/safeUrl";
import { useRedFlags } from "../../lib/queries";
import type { RedFlagItem, RedFlagsResponse } from "../../types";
import { useCitations } from "../citations/CitationContext";
import { Badge } from "../ui/Badge";
import { Section } from "../ui/Section";
import { Skeleton } from "../ui/Skeleton";
import { ErrorState } from "../ui/States";
import { Tooltip } from "../ui/Tooltip";

const SHOWN = 3; // the Overview is a summary: the rest are one click away

/** One reported event: what, when, the filing's own words, and the filing itself. */
function FlagRow({ item, onOpen }: { item: RedFlagItem; onOpen: (sourceId: string) => void }) {
  const url = safeHttpUrl(item.filing.url);
  const detail = detailText(item);
  return (
    <li className="border-b border-border py-3 last:border-b-0" data-testid={`red-flag-${item.rule_key}`}>
      <Tooltip label={<span className="block max-w-72">{item.explanation}</span>}>
        <span className="text-sm font-medium text-text">{item.label}</span>
      </Tooltip>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-subtle">
        <Badge tone={severityTone(item.severity)}>{severityLabel(item.severity)}</Badge>
        <span>
          {item.filing.filing_type} · filed {formatDate(item.event_date)}
        </span>
        {detail && <span className="text-muted">{detail}</span>}
      </div>
      <button
        type="button"
        onClick={() => onOpen(item.source_id)}
        aria-label={`Show the source of: ${item.label}`}
        className="mt-2 block w-full rounded-control text-left text-sm text-muted transition-colors hover:text-text"
      >
        <q className="line-clamp-2">{item.snippet}</q>
      </button>
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="mt-1 inline-flex items-center gap-1 text-caption font-medium text-primary hover:underline"
        >
          Open filing <ExternalLink aria-hidden className="size-3" />
        </a>
      )}
    </li>
  );
}

/** The panel body for each state: loading, error, empty (with the scanned-through date), or the
 *  list. Pure, so every state can be rendered in a test. */
export function RedFlagList({
  state,
  data,
  onOpen,
  onRetry,
}: {
  state: "loading" | "error" | "ready";
  data?: RedFlagsResponse | undefined;
  onOpen: (sourceId: string) => void;
  onRetry?: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  if (state === "loading") {
    return (
      <div role="status" aria-label="Loading red flags" className="space-y-3 pt-4">
        <Skeleton className="w-4/5" />
        <Skeleton className="w-3/5" />
      </div>
    );
  }
  if (state === "error" || !data) {
    return <ErrorState message="Red flags could not be loaded." {...(onRetry ? { onRetry } : {})} />;
  }
  if (data.items.length === 0) {
    return <p className="pt-4 text-sm text-muted">{emptyText(data.last_scanned_at)}</p>;
  }
  const shown = expanded ? data.items : data.items.slice(0, SHOWN);
  return (
    <div className="pt-1">
      <ul>
        {shown.map((item) => (
          <FlagRow key={item.source_id} item={item} onOpen={onOpen} />
        ))}
      </ul>
      {data.items.length > SHOWN && (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="mt-2 text-sm font-medium text-primary hover:underline"
        >
          {expanded ? "Show fewer" : `Show all ${data.items.length}`}
        </button>
      )}
      {data.last_scanned_at && (
        <p className="mt-3 text-caption text-subtle">Scanned through {formatDate(data.last_scanned_at)}.</p>
      )}
    </div>
  );
}

/** "How to read this": flags are reported events, found by fixed rules, not conclusions. */
function HowToRead() {
  return (
    <details className="pt-3 text-caption text-muted">
      <summary className="cursor-pointer text-subtle marker:text-subtle">How to read this</summary>
      <p className="mt-2 max-w-prose">
        Each flag means an event was reported in an SEC filing, such as an 8-K item, a late-filing
        notice or going-concern wording, found by fixed rules with no AI judgement. It is not a
        conclusion about the company: many are routine, like planned retirements. The label says how
        closely an analyst would usually read it. Select a quote to see where it came from.
      </p>
    </details>
  );
}

/** Red flags on the Overview (FR-RF-012..014). */
export function RedFlagsSection({ ticker }: { ticker: string }) {
  const flags = useRedFlags(ticker);
  const { open } = useCitations();
  return (
    <Section title="Red flags">
      <RedFlagList
        state={flags.isPending ? "loading" : flags.isError ? "error" : "ready"}
        data={flags.data}
        onOpen={open}
        onRetry={() => void flags.refetch()}
      />
      <HowToRead />
    </Section>
  );
}
