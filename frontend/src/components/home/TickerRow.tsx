import { Link } from "react-router-dom";

import { Sparkline } from "../../charts/Sparkline";
import { formatUsd, toNumber } from "../../lib/format";
import { useRecentPrices } from "../../lib/queries";
import { latestQuote } from "../../lib/quote";
import { addRecentSearch } from "../../lib/recentSearches";
import { Delta } from "../ui/Delta";
import { Skeleton } from "../ui/Skeleton";

const SPARK_SESSIONS = 30;

/** One company: ticker, name, last close, day change, and optionally the last 30 sessions as a
 *  sparkline. The whole row is the link. */
export function TickerRow({
  ticker,
  name,
  sparkline = false,
}: {
  ticker: string;
  name: string | undefined; // undefined while it is still being looked up
  sparkline?: boolean;
}) {
  const prices = useRecentPrices(ticker);
  const quote = latestQuote(prices.data?.points);
  const closes = (prices.data?.points ?? [])
    .slice(-SPARK_SESSIONS)
    .map((point) => toNumber(point.adj_close ?? point.close ?? null))
    .filter((value): value is number => value !== null);
  return (
    <li className="animate-fade-in">
      <Link
        to={`/company/${ticker}`}
        onClick={() => name && addRecentSearch({ ticker, name })}
        className="-mx-3 flex h-12 items-center gap-3 rounded-control px-3 transition-colors hover:bg-surface"
      >
        <span className="w-14 shrink-0 font-medium">{ticker}</span>
        <span className="min-w-0 flex-1 truncate text-muted">{name ?? <Skeleton className="w-32" />}</span>
        {sparkline && (
          <span className="hidden w-24 shrink-0 sm:block">
            <Sparkline values={closes} className="w-full" />
          </span>
        )}
        {/* The price cells keep their width while loading and stay empty (not dashed) when a
            company has no price data. */}
        <span className="tnum w-20 shrink-0 text-right">
          {prices.isPending ? <Skeleton className="ml-auto w-14" /> : quote && formatUsd(quote.close)}
        </span>
        <span className="w-20 shrink-0 text-right text-sm">
          {quote && <Delta value={quote.changePct} />}
        </span>
      </Link>
    </li>
  );
}
