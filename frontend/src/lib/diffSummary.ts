// The filing diff, said in one sentence (§37.4): "1 new risk factor, 16 reworded and 8 unchanged
// since the 10-K filed Feb 26, 2025."

export interface DiffCounts {
  new: number;
  removed: number;
  reworded: number;
  unchanged: number;
}

function joinList(parts: string[]): string {
  if (parts.length <= 1) return parts.join("");
  return `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}`;
}

/** `noun` is the thing being counted: "risk factor" or "passage". `since` names the baseline. */
export function summarizeDiff(counts: DiffCounts, noun: string, since: string): string {
  const total = counts.new + counts.removed + counts.reworded + counts.unchanged;
  if (total === 0) return `Nothing to compare with ${since}.`;
  const plural = (n: number) => (n === 1 ? noun : `${noun}s`);
  // The noun is attached once, to the first count: "1 new risk factor, 16 reworded and 8 unchanged".
  const parts = (
    [
      ["new", counts.new],
      ["removed", counts.removed],
      ["reworded", counts.reworded],
      ["unchanged", counts.unchanged],
    ] as const
  )
    .filter(([, n]) => n > 0)
    .map(([label, n], i) => (i === 0 ? `${n} ${label} ${plural(n)}` : `${n} ${label}`));
  return `${joinList(parts)} since ${since}.`;
}
