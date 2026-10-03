import { useSource } from "../../lib/queries";
import { Badge } from "../primitives";
import { useCitations } from "./CitationContext";
import { sourceTitle } from "./sourceTitle";

export interface ReferenceEntry {
  number: number;
  sourceId: string;
  title?: string | null;
  tier?: number | null;
}

/** Numbered reference list with tier badges (§13.7). Entries missing a title/tier resolve lazily. */
export function ReferenceList({ entries }: { entries: ReferenceEntry[] }) {
  if (entries.length === 0) return null;
  return (
    <section aria-label="References" className="mt-4 border-t border-border pt-3">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">References</h3>
      <ol className="space-y-1 text-sm">
        {entries.map((e) => (
          <ReferenceRow key={e.number} entry={e} />
        ))}
      </ol>
    </section>
  );
}

function ReferenceRow({ entry }: { entry: ReferenceEntry }) {
  const { open } = useCitations();
  const needsResolve = entry.title == null || entry.tier == null;
  const source = useSource(needsResolve ? entry.sourceId : null);
  const title = entry.title ?? (source.data ? sourceTitle(source.data.source) : entry.sourceId);
  const tier = entry.tier ?? source.data?.source.tier ?? null;

  return (
    <li className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => open(entry.sourceId)}
        className="font-medium text-primary hover:underline"
      >
        [{entry.number}]
      </button>
      <span className="truncate">{title}</span>
      {tier != null && <Badge tone="neutral">Tier {tier}</Badge>}
    </li>
  );
}
