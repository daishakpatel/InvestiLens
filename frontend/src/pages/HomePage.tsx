import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { DisambiguationPicker } from "../components/DisambiguationPicker";
import { SearchBox } from "../components/SearchBox";
import { useAuth } from "../lib/auth";
import { addRecentSearch, getRecentSearches } from "../lib/recentSearches";
import type { CompanySearchResult } from "../types";

const POPULAR: { ticker: string; name: string }[] = [
  { ticker: "NVDA", name: "NVIDIA" },
  { ticker: "AAPL", name: "Apple" },
  { ticker: "MSFT", name: "Microsoft" },
  { ticker: "JPM", name: "JPMorgan Chase" },
];

export default function HomePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [ambiguous, setAmbiguous] = useState<CompanySearchResult[] | null>(null);
  const recents = getRecentSearches();

  const go = (ticker: string, name: string) => {
    addRecentSearch({ ticker, name });
    navigate(`/company/${ticker}`);
  };

  const onSubmitQuery = (results: CompanySearchResult[]) => {
    if (results.length === 0) return;
    if (results.length === 1 && results[0]) go(results[0].ticker, results[0].name);
    else setAmbiguous(results); // never silently best-guess (§9.2)
  };

  return (
    <div className="mx-auto max-w-2xl py-10">
      <h1 className="mb-1 text-2xl font-bold">Search a company</h1>
      <p className="mb-6 text-sm text-muted">
        Evidence-grounded financials and AI research for US public companies.
      </p>

      <SearchBox
        autoFocus
        onSelect={(r) => go(r.ticker, r.name)}
        onSubmitQuery={onSubmitQuery}
      />

      {ambiguous && ambiguous.length > 1 && (
        <div className="mt-4">
          <DisambiguationPicker results={ambiguous} onSelect={(r) => go(r.ticker, r.name)} />
        </div>
      )}

      <Section title="Popular">
        <ChipRow items={POPULAR} onPick={go} />
      </Section>

      {recents.length > 0 && (
        <Section title="Recent searches">
          <ChipRow items={recents} onPick={go} />
        </Section>
      )}

      {user && (
        <Section title="Your watchlist">
          <p className="text-sm text-muted">
            Watchlist quick links appear here once you add companies (Watchlist &amp; Alerts, Phase
            4d).
          </p>
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{title}</h2>
      {children}
    </section>
  );
}

function ChipRow({
  items,
  onPick,
}: {
  items: { ticker: string; name: string }[];
  onPick: (ticker: string, name: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((c) => (
        <button
          key={c.ticker}
          type="button"
          onClick={() => onPick(c.ticker, c.name)}
          className="rounded-full border border-border bg-surface px-3 py-1 text-sm hover:bg-surface-2"
        >
          <span className="font-medium">{c.ticker}</span>{" "}
          <span className="text-muted">{c.name}</span>
        </button>
      ))}
    </div>
  );
}
