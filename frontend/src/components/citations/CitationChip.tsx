import { useCitations } from "./CitationContext";

/** An inline citation: a superscript number that opens its source beside the text (CIT-006).
 *  Quiet until hovered; marked while its source is the one on show. */
export function CitationChip({ number, sourceId }: { number: number; sourceId: string }) {
  const { open, activeSourceId } = useCitations();
  const active = activeSourceId === sourceId;
  return (
    <button
      type="button"
      onClick={() => open(sourceId)}
      aria-label={`Open source ${number}`}
      aria-pressed={active}
      title="View source"
      // Padding enlarges the hit area; the negative margin keeps it from shifting the line.
      className={`relative -my-1 mx-px inline-flex min-w-4 items-center justify-center rounded-[4px] px-1 py-1 align-super text-[0.72em] font-medium leading-none text-primary transition-colors hover:bg-primary/15 ${
        active ? "bg-primary/20" : ""
      }`}
    >
      {number}
    </button>
  );
}

/** The citations for one claim, in the order the backend gave them. */
export function CitationChips({
  ids,
  numberOf,
}: {
  ids: readonly string[];
  numberOf: (sourceId: string) => number;
}) {
  return (
    <>
      {ids.map((id, i) =>
        i === 0 ? (
          // A word joiner inside a no-wrap span: the first number stays on the line with the
          // sentence it supports instead of dropping to the next one alone.
          <span key={id} className="whitespace-nowrap">
            {"\u2060"}
            <CitationChip number={numberOf(id)} sourceId={id} />
          </span>
        ) : (
          <CitationChip key={id} number={numberOf(id)} sourceId={id} />
        ),
      )}
    </>
  );
}
