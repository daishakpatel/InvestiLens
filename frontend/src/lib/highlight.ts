/** Split a passage around its cited span. The API's offsets are sometimes positions in the whole
 *  document rather than in the excerpt it returns; a range that does not fit inside the excerpt
 *  is ignored (the excerpt is then the cited passage in full) rather than mis-highlighted. */
export function splitHighlight(
  text: string,
  start: number | null | undefined,
  end: number | null | undefined,
): { before: string; marked: string; after: string } {
  const valid =
    typeof start === "number" &&
    typeof end === "number" &&
    Number.isInteger(start) &&
    Number.isInteger(end) &&
    start >= 0 &&
    end > start &&
    end <= text.length;
  if (!valid) return { before: text, marked: "", after: "" };
  return { before: text.slice(0, start), marked: text.slice(start, end), after: text.slice(end) };
}
