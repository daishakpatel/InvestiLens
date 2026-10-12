import { describe, expect, it } from "vitest";

import type { Watchlist } from "../types";
import { watchEntry, watchedTickers } from "./watchlist";

const list = (id: string, name: string, items: string[] = []): Watchlist => ({
  id,
  name,
  items: items.map((ticker) => ({ ticker })),
});

// FR-007 (watchlist): the stand-in for a missing "add to watchlist" API operation.
describe("watchedTickers", () => {
  it("reads one-company lists named by ticker, oldest first, without repeats", () => {
    const lists = [list("1", "NVDA"), list("2", "BRK.B"), list("3", "NVDA")];
    expect(watchedTickers(lists)).toEqual(["NVDA", "BRK.B"]);
  });

  it("ignores a list whose name is not a ticker, and reads real items when a list has them", () => {
    const lists = [list("1", "My favourites"), list("2", "Chips", ["amd", "INTC"]), list("3", "nvda")];
    expect(watchedTickers(lists)).toEqual(["AMD", "INTC"]);
  });
});

describe("watchEntry", () => {
  it("finds the list to delete, case-insensitively, and never a list with real items", () => {
    const lists = [list("1", "Chips", ["NVDA"]), list("2", "NVDA")];
    expect(watchEntry(lists, "nvda")?.id).toBe("2");
    expect(watchEntry(lists, "AMD")).toBeUndefined();
  });
});
