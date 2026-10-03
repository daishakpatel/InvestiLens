import { useCitations } from "./CitationContext";

/** A numbered, keyboard-focusable inline citation chip (CIT-006, §13.7). */
export function CitationChip({ number, sourceId }: { number: number; sourceId: string }) {
  const { open } = useCitations();
  return (
    <button
      type="button"
      onClick={() => open(sourceId)}
      aria-label={`Open source ${number}`}
      title="View source"
      className="mx-0.5 inline-flex min-w-5 items-center justify-center rounded bg-primary/10 px-1 align-super text-[0.7em] font-semibold text-primary hover:bg-primary/20"
    >
      [{number}]
    </button>
  );
}
