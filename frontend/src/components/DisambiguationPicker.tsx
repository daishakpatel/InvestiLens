import type { CompanySearchResult } from "../types";

/** Shown when a query matches several companies — explicit pick, never a silent best-guess (§9.2). */
export function DisambiguationPicker({
  results,
  onSelect,
}: {
  results: CompanySearchResult[];
  onSelect: (result: CompanySearchResult) => void;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h2 className="mb-3 text-sm font-semibold">Did you mean…</h2>
      <ul className="divide-y divide-border">
        {results.map((r) => (
          <li key={`${r.ticker}-${r.cik}`}>
            <button
              type="button"
              onClick={() => onSelect(r)}
              className="flex w-full items-center justify-between gap-4 py-3 text-left hover:bg-surface-2"
            >
              <span>
                <span className="font-medium">{r.name}</span>
                <span className="ml-2 text-sm text-muted">
                  {r.ticker}
                  {r.exchange ? ` · ${r.exchange}` : ""}
                </span>
              </span>
              <span aria-hidden className="text-muted">
                →
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
