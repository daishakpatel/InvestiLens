import { useEffect, useRef, useState } from "react";

import { useSource } from "../../lib/queries";
import { useCitations } from "./CitationContext";
import { sourceTitle, tierLabel } from "./sourceTitle";

export interface ReferenceEntry {
  number: number;
  sourceId: string;
  title?: string | null;
  tier?: number | null;
}

/** True once the element has been on screen. References resolve their titles one request each,
 *  so a long list does not ask for all of them until the reader actually reaches it. */
function useSeen<T extends Element>(): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element || seen) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) setSeen(true);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [seen]);
  return [ref, seen];
}

function ReferenceRow({ entry }: { entry: ReferenceEntry }) {
  const { open, activeSourceId } = useCitations();
  const [ref, seen] = useSeen<HTMLLIElement>();
  const needsResolve = entry.title == null || entry.tier == null;
  const source = useSource(needsResolve && seen ? entry.sourceId : null);
  const title = entry.title ?? (source.data ? sourceTitle(source.data.source) : null);
  const tier = tierLabel(entry.tier ?? source.data?.source.tier);

  return (
    <li ref={ref}>
      <button
        type="button"
        onClick={() => open(entry.sourceId)}
        aria-pressed={activeSourceId === entry.sourceId}
        className="-mx-2 flex w-[calc(100%+1rem)] items-baseline gap-3 rounded-control px-2 py-1.5 text-left text-sm transition-colors hover:bg-surface aria-pressed:bg-surface-2"
      >
        <span className="tnum w-6 shrink-0 text-right text-primary">{entry.number}</span>
        <span className="min-w-0 flex-1 truncate">{title ?? "Source"}</span>
        {tier && <span className="hidden shrink-0 text-caption text-subtle sm:inline">{tier}</span>}
      </button>
    </li>
  );
}

/** The numbered sources behind a document or an answer (§13.7): quiet, in citation order, each
 *  opening the same source view as its chip. */
export function ReferenceList({ entries }: { entries: ReferenceEntry[] }) {
  if (entries.length === 0) return null;
  return (
    <ol aria-label="References">
      {entries.map((entry) => (
        <ReferenceRow key={entry.number} entry={entry} />
      ))}
    </ol>
  );
}
