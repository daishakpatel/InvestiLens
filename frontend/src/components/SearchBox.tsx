import { useEffect, useId, useRef, useState } from "react";

import { useCompanySearch } from "../lib/queries";
import type { CompanySearchResult } from "../types";
import { Spinner } from "./primitives";

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

/** Combobox search with ticker/name/exchange autocomplete (§9.1, UI-003). */
export function SearchBox({
  onSelect,
  onSubmitQuery,
  autoFocus,
}: {
  onSelect: (result: CompanySearchResult) => void;
  onSubmitQuery: (results: CompanySearchResult[]) => void;
  autoFocus?: boolean;
}) {
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const debounced = useDebounced(text, 200);
  const search = useCompanySearch(debounced);
  const results = search.data ?? [];
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  const choose = (r: CompanySearchResult | undefined) => {
    if (!r) return;
    setOpen(false);
    setText("");
    onSelect(r);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (active >= 0 && results[active]) choose(results[active]);
      else onSubmitQuery(results);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="relative">
      <div className="flex gap-2">
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={open && results.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${listId}-opt-${active}` : undefined}
          aria-label="Search a company by name, ticker, or exchange"
          autoFocus={autoFocus}
          value={text}
          placeholder="Search a company — e.g. NVIDIA or NVDA"
          onChange={(e) => {
            setText(e.target.value);
            setActive(-1);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className="w-full rounded-lg border border-border bg-surface px-4 py-3 text-base shadow-sm placeholder:text-muted focus:border-primary"
        />
        <button
          type="button"
          onClick={() => onSubmitQuery(results)}
          className="rounded-lg bg-primary px-5 py-3 font-medium text-primary-contrast hover:opacity-90"
        >
          Analyze
        </button>
      </div>

      {open && debounced.length >= 1 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-80 w-full overflow-auto rounded-lg border border-border bg-surface py-1 shadow-xl"
        >
          {search.isPending && (
            <li className="flex items-center gap-2 px-4 py-2 text-sm text-muted">
              <Spinner /> Searching…
            </li>
          )}
          {!search.isPending && results.length === 0 && (
            <li className="px-4 py-2 text-sm text-muted">No matches for “{debounced}”.</li>
          )}
          {results.map((r, i) => (
            <li
              key={`${r.ticker}-${r.cik}`}
              id={`${listId}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(r);
              }}
              onMouseEnter={() => setActive(i)}
              className={`flex cursor-pointer items-center justify-between px-4 py-2 text-sm ${
                i === active ? "bg-surface-2" : ""
              }`}
            >
              <span>
                <span className="font-medium">{r.ticker}</span>{" "}
                <span className="text-muted">{r.name}</span>
              </span>
              {r.exchange && <span className="text-xs text-muted">{r.exchange}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
