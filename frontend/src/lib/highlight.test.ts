import { describe, expect, it } from "vitest";

import { splitHighlight } from "./highlight";

// CIT-002/CIT-006: the source view highlights the cited span inside the quoted passage.
describe("splitHighlight", () => {
  it("splits a passage around a span that lies inside it", () => {
    expect(splitHighlight("Revenue grew strongly this year.", 8, 21)).toEqual({
      before: "Revenue ",
      marked: "grew strongly",
      after: " this year.",
    });
  });

  it("ignores offsets that do not fit the excerpt (document offsets on a chunk)", () => {
    // Regression: char offsets 7803-9645 on a 1,842-character excerpt once produced an empty mark.
    const text = "x".repeat(1842);
    expect(splitHighlight(text, 7803, 9645)).toEqual({ before: text, marked: "", after: "" });
  });

  it("ignores missing, reversed, or fractional ranges", () => {
    for (const [start, end] of [
      [null, null],
      [5, 5],
      [9, 3],
      [-1, 4],
      [1.5, 4],
    ] as [number | null, number | null][]) {
      expect(splitHighlight("some text", start, end).marked).toBe("");
    }
  });
});
