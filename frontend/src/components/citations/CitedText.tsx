import { CitationChip } from "./CitationChip";

/** Render verified text, turning its inline [n] markers into citation chips. A marker with no
 *  matching citation is left as text rather than made into a chip that opens nothing. */
export function CitedText({
  text,
  citations,
}: {
  text: string;
  citations: readonly { number: number; source_id: string }[];
}) {
  const byNumber = new Map(citations.map((c) => [c.number, c.source_id]));
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const match = /^\[(\d+)\]$/.exec(part);
        if (match) {
          const n = Number(match[1]);
          const sourceId = byNumber.get(n);
          if (sourceId) return <CitationChip key={i} number={n} sourceId={sourceId} />;
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}
