// Which companies the signed-in user is watching.
//
// The API can create and delete a watchlist, but has no operation that adds a company to one
// (UI plan Step 5 hand-off; ADR-0031). Until it does, each watched company is stored as its own
// watchlist, named by its ticker. That convention lives in this file and nowhere else: a list
// that carries real `items` is read as well, so when the API gains the missing operation only
// `watchEntry` and the Watch button's two calls need to change.
import type { Watchlist } from "../types";

const TICKER = /^[A-Z][A-Z0-9.-]{0,9}$/;

/** Watched tickers, oldest first, without repeats. */
export function watchedTickers(lists: readonly Watchlist[]): string[] {
  const tickers = lists.flatMap((list) =>
    list.items.length > 0
      ? list.items.map((item) => item.ticker.toUpperCase())
      : TICKER.test(list.name)
        ? [list.name]
        : [],
  );
  return [...new Set(tickers)];
}

/** The list that stands for watching `ticker`: what "unwatch" deletes. */
export function watchEntry(lists: readonly Watchlist[], ticker: string): Watchlist | undefined {
  const wanted = ticker.toUpperCase();
  return lists.find((list) => list.items.length === 0 && list.name === wanted);
}
