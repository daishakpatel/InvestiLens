import { CitationChip } from "./CitationChip";
import type { Evidence } from "./CitationContext";

/** The sentences behind one count (§37.5): every mention that was tallied, each a click away
 *  from the filing passage it came from. */
export function StatementsView({ view }: { view: Extract<Evidence, { kind: "statements" }> }) {
  return (
    <div className="space-y-4 overflow-y-auto p-5">
      <header>
        <h3 className="text-title font-medium">{view.title}</h3>
        <p className="mt-1 text-caption text-muted">{view.subtitle}</p>
      </header>
      <ol className="space-y-4 text-sm leading-relaxed">
        {view.statements.map((statement, i) => (
          <li key={`${statement.source_id}-${i}`} className="border-b border-border/60 pb-4 last:border-0">
            {statement.text} <CitationChip number={i + 1} sourceId={statement.source_id} />
          </li>
        ))}
      </ol>
    </div>
  );
}
