import { Star } from "lucide-react";

import { useCompany, useWatchlists } from "../../lib/queries";
import { watchedTickers } from "../../lib/watchlist";
import { useCommandPalette } from "../CommandPaletteContext";
import { Button } from "../ui/Button";
import { Section } from "../ui/Section";
import { AsyncContent, EmptyState } from "../ui/States";
import { TickerRow } from "./TickerRow";

function WatchedRow({ ticker }: { ticker: string }) {
  const company = useCompany(ticker);
  // A ticker that no longer resolves still shows, by its symbol, so it can be opened and removed.
  const name = company.data?.company.name ?? (company.isError ? "" : undefined);
  return <TickerRow ticker={ticker} name={name} sparkline />;
}

/** The signed-in reader's watched companies on Home: price, day change, and a month's trend. */
export function Watchlist({ userId }: { userId: string }) {
  const lists = useWatchlists(userId);
  const palette = useCommandPalette();
  return (
    <Section title="Watchlist">
      <AsyncContent query={lists}>
        {(data) => {
          const tickers = watchedTickers(data);
          return tickers.length === 0 ? (
            <EmptyState
              icon={<Star className="size-5" />}
              message="Nothing watched yet. Open a company and choose Watch to keep it here, with its price and trend."
              action={<Button onClick={palette.open}>Find a company</Button>}
            />
          ) : (
            <ul className="divide-y divide-border/60">
              {tickers.map((ticker) => (
                <WatchedRow key={ticker} ticker={ticker} />
              ))}
            </ul>
          );
        }}
      </AsyncContent>
    </Section>
  );
}
