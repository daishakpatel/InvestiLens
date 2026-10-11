import { Command } from "cmdk";
import { ChartPie, Clock, GitCompareArrows, Search, TrendingUp } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Dialog } from "radix-ui";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { POPULAR_COMPANIES } from "../lib/config";
import { useCompanySearch } from "../lib/queries";
import { addRecentSearch, getRecentSearches } from "../lib/recentSearches";
import { useReturnFocus } from "./ui/Dialog";
import { Skeleton } from "./ui/Skeleton";

const DEBOUNCE_MS = 150;

const ACTIONS: { label: string; to: string; icon: LucideIcon }[] = [
  { label: "Compare companies", to: "/compare", icon: GitCompareArrows },
  { label: "Analyze a portfolio", to: "/portfolio", icon: ChartPie },
];

const ITEM =
  "flex h-11 cursor-default items-center gap-3 rounded-control px-3 text-sm text-text " +
  "data-[selected=true]:bg-surface-2";
const GROUP =
  "[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-3 " +
  "[&_[cmdk-group-heading]]:text-caption [&_[cmdk-group-heading]]:text-subtle";

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

function CompanyItem({
  prefix,
  ticker,
  name,
  exchange,
  icon: Icon,
  onPick,
}: {
  prefix: string;
  ticker: string;
  name: string;
  exchange?: string | null | undefined;
  icon: LucideIcon;
  onPick: (ticker: string, name: string) => void;
}) {
  return (
    <Command.Item value={`${prefix}-${ticker}`} onSelect={() => onPick(ticker, name)} className={ITEM}>
      <Icon aria-hidden className="size-4 shrink-0 text-subtle" />
      <span className="w-14 shrink-0 font-medium">{ticker}</span>
      <span className="min-w-0 flex-1 truncate text-muted">{name}</span>
      {exchange && <span className="shrink-0 text-caption text-subtle">{exchange}</span>}
    </Command.Item>
  );
}

function PaletteBody({ close }: { close: () => void }) {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const typed = text.trim();
  const query = useDebounced(typed, DEBOUNCE_MS);
  const search = useCompanySearch(query);
  // Recents are read once per opening; the palette remounts each time it opens.
  const [recents] = useState(getRecentSearches);

  // Results belong to the text on screen only once the debounce has caught up and the request for
  // exactly that text has returned. Until then nothing from an older query is selectable, so a
  // fast Enter can never open a company the user did not see highlighted (§9.2).
  const settled = typed !== "" && query === typed && search.isSuccess;
  const failed = typed !== "" && query === typed && search.isError;
  const loading = typed !== "" && !settled && !failed;
  const results = settled ? search.data : [];

  const recentTickers = new Set(recents.map((r) => r.ticker));
  const popular = POPULAR_COMPANIES.filter((c) => !recentTickers.has(c.ticker));
  const actions = ACTIONS.filter((a) => a.label.toLowerCase().includes(typed.toLowerCase()));

  const go = (to: string) => {
    close();
    navigate(to);
  };
  const openCompany = (ticker: string, name: string) => {
    addRecentSearch({ ticker, name });
    go(`/company/${ticker}`);
  };

  return (
    <Command label="Search companies" shouldFilter={false} loop>
      <div className="flex items-center gap-3 border-b border-border px-4">
        <Search aria-hidden className="size-4 shrink-0 text-subtle" />
        <Command.Input
          autoFocus
          value={text}
          onValueChange={setText}
          placeholder="Search a company or ticker"
          className="h-13 w-full bg-transparent text-body text-text outline-none placeholder:text-subtle focus-visible:outline-none"
        />
      </div>

      <Command.List className="max-h-[min(26rem,60vh)] overflow-auto p-1.5">
        {typed === "" && recents.length > 0 && (
          <Command.Group heading="Recent" className={GROUP}>
            {recents.map((c) => (
              <CompanyItem key={c.ticker} prefix="recent" icon={Clock} onPick={openCompany} {...c} />
            ))}
          </Command.Group>
        )}
        {typed === "" && popular.length > 0 && (
          <Command.Group heading="Popular" className={GROUP}>
            {popular.map((c) => (
              <CompanyItem key={c.ticker} prefix="popular" icon={TrendingUp} onPick={openCompany} {...c} />
            ))}
          </Command.Group>
        )}

        {loading && (
          <Command.Loading label="Searching">
            <div className="space-y-1.5 p-1.5">
              <Skeleton shape="row" />
              <Skeleton shape="row" />
              <Skeleton shape="row" />
            </div>
          </Command.Loading>
        )}

        {results.length > 0 && (
          <Command.Group heading="Companies" className={GROUP}>
            {results.map((r) => (
              <CompanyItem
                key={`${r.ticker}-${r.cik}`}
                prefix="company"
                icon={Search}
                ticker={r.ticker}
                name={r.name}
                exchange={r.exchange}
                onPick={openCompany}
              />
            ))}
          </Command.Group>
        )}

        {settled && results.length === 0 && (
          <p role="status" className="px-3 py-6 text-center text-sm text-muted">
            No companies match “{typed}”. Try a ticker, such as NVDA.
          </p>
        )}
        {failed && (
          <p role="alert" className="px-3 py-6 text-center text-sm text-muted">
            Search is unavailable right now. Try again in a moment.
          </p>
        )}

        {/* Actions are offered when idle, or when the text names them; never as a fallback target
            for a company search that found nothing. */}
        {actions.length > 0 && (typed === "" || results.length === 0) && !loading && (
          <Command.Group heading="Tools" className={GROUP}>
            {actions.map(({ label, to, icon: Icon }) => (
              <Command.Item key={to} value={`action-${to}`} onSelect={() => go(to)} className={ITEM}>
                <Icon aria-hidden className="size-4 shrink-0 text-subtle" />
                {label}
              </Command.Item>
            ))}
          </Command.Group>
        )}
      </Command.List>

      <div className="hidden items-center gap-4 border-t border-border px-4 py-2 text-caption text-subtle sm:flex">
        <span>↑↓ to move</span>
        <span>↵ to open</span>
        <span>esc to close</span>
      </div>
    </Command>
  );
}

/** Global company search (§9.1). The list is always shown and the user picks a row; nothing is
 *  ever opened on a best guess (§9.2). */
export default function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const returnFocus = useReturnFocus();
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <Dialog.Content
          {...returnFocus}
          aria-describedby={undefined}
          className="fixed left-1/2 top-[12vh] z-50 w-[min(40rem,calc(100vw-1.5rem))] -translate-x-1/2 overflow-hidden rounded-surface border border-border-strong bg-surface shadow-float"
        >
          <Dialog.Title className="sr-only">Search companies</Dialog.Title>
          <PaletteBody close={() => onOpenChange(false)} />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
