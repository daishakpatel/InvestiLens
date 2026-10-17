import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { TickerRow } from "../components/home/TickerRow";
import { Watchlist } from "../components/home/Watchlist";
import { SearchTrigger } from "../components/SearchTrigger";
import { Container } from "../components/ui/Container";
import { useAuth } from "../lib/auth";
import { POPULAR_COMPANIES } from "../lib/config";
import { getRecentSearches } from "../lib/recentSearches";

const EXAMPLE = POPULAR_COMPANIES[0] ?? { ticker: "NVDA", name: "NVIDIA" };

const FEATURES: { title: string; body: string; cta: string; to: string }[] = [
  {
    title: "Financials with lineage",
    body: "Revenue, margins and cash flow taken straight from SEC filings. Every figure can show the filing and the formula behind it.",
    cta: `See ${EXAMPLE.name}’s financials`,
    to: `/company/${EXAMPLE.ticker}/financials`,
  },
  {
    title: "AI research with citations",
    body: "A full research report in which each claim links to the passage it came from. Where the evidence is thin, the report says so.",
    cta: `Read ${EXAMPLE.name}’s research`,
    to: `/company/${EXAMPLE.ticker}/research`,
  },
  {
    title: "Filing change detection",
    body: "What changed between one annual report and the next: new risk factors, removed ones, and reworded passages, word by word.",
    cta: `See what changed at ${EXAMPLE.name}`,
    to: `/company/${EXAMPLE.ticker}/filings`,
  },
];

function TickerList({ title, items }: { title: string; items: { ticker: string; name: string }[] }) {
  return (
    <section aria-label={title}>
      <h2 className="border-b border-border pb-2 text-label text-muted">{title}</h2>
      <ul className="divide-y divide-border/60">
        {items.map((item) => (
          <TickerRow key={item.ticker} {...item} />
        ))}
      </ul>
    </section>
  );
}

export default function HomePage() {
  const { user } = useAuth();
  const [recents] = useState(getRecentSearches);
  const recentTickers = new Set(recents.map((r) => r.ticker));
  const popular = POPULAR_COMPANIES.filter((c) => !recentTickers.has(c.ticker));
  const lists = [
    { title: "Recent", items: recents },
    { title: "Popular", items: popular },
  ].filter((list) => list.items.length > 0);
  // One column width for the lists and the watchlist beneath them, so their edges line up.
  const column = lists.length > 1 ? "max-w-4xl" : "max-w-xl";

  return (
    <Container>
      {/* The hero fills the first screen on a laptop; only the next heading shows at the fold. */}
      <section className="flex min-h-[calc(100svh-11rem)] flex-col items-center justify-center py-16 text-center">
        <h1 className="text-display-s font-semibold md:text-display-l">Research you can verify.</h1>
        <p className="mt-4 max-w-xl text-body text-muted md:text-title">
          Financials, filings, and AI analysis for US public companies, with every number traced
          and every claim cited.
        </p>
        <div className="mt-10 w-full max-w-xl">
          <SearchTrigger variant="hero" />
        </div>
      </section>

      <div className="space-y-20">
        {/* A signed-in reader's own companies come before the general lists. */}
        {user && (
          <div className={`mx-auto ${column}`}>
            <Watchlist userId={user.id} />
          </div>
        )}

        <div
          className={`mx-auto grid grid-cols-1 gap-x-16 gap-y-10 ${column} ${
            lists.length > 1 ? "md:grid-cols-2" : ""
          }`}
        >
          {lists.map((list) => (
            <TickerList key={list.title} {...list} />
          ))}
        </div>

        <section aria-label="What you get" className="grid gap-x-12 gap-y-10 md:grid-cols-3">
          {FEATURES.map((feature) => (
            <div key={feature.title} className="border-t border-border pt-5">
              <h2 className="text-title font-medium">{feature.title}</h2>
              <p className="mt-2 text-muted">{feature.body}</p>
              <Link
                to={feature.to}
                className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
              >
                {feature.cta}
                <ArrowRight aria-hidden className="size-4" />
              </Link>
            </div>
          ))}
        </section>
      </div>
    </Container>
  );
}
