import { describe, expect, it } from "vitest";

import { summarizeDiff } from "./diffSummary";

// §37.4: the Changes view opens with a plain-language summary of the diff.
describe("summarizeDiff", () => {
  const since = "the 10-K filed Feb 26, 2025";

  it("names each non-zero count once, in order of importance", () => {
    expect(summarizeDiff({ new: 1, removed: 0, reworded: 16, unchanged: 8 }, "risk factor", since)).toBe(
      "1 new risk factor, 16 reworded and 8 unchanged since the 10-K filed Feb 26, 2025.",
    );
  });

  it("pluralises by the first count shown", () => {
    expect(summarizeDiff({ new: 2, removed: 1, reworded: 0, unchanged: 0 }, "risk factor", since)).toBe(
      "2 new risk factors and 1 removed since the 10-K filed Feb 26, 2025.",
    );
    expect(summarizeDiff({ new: 0, removed: 0, reworded: 0, unchanged: 3 }, "passage", since)).toBe(
      "3 unchanged passages since the 10-K filed Feb 26, 2025.",
    );
  });

  it("says so when there is nothing to compare", () => {
    expect(summarizeDiff({ new: 0, removed: 0, reworded: 0, unchanged: 0 }, "passage", since)).toBe(
      "Nothing to compare with the 10-K filed Feb 26, 2025.",
    );
  });
});
