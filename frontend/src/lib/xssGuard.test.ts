import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// XSS defense (scope #6): filing/news text is untrusted. React escapes interpolated strings by
// default, so our only real XSS risk is `dangerouslySetInnerHTML`. This guard fails the build if
// anyone introduces it, keeping the "untrusted text renders as text" guarantee a hard invariant.
const SRC = join(fileURLToPath(new URL(".", import.meta.url)), "..");

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else if (/\.(ts|tsx)$/.test(entry.name) && !entry.name.endsWith(".test.ts")) out.push(full);
  }
  return out;
}

describe("XSS source guard", () => {
  it("never uses dangerouslySetInnerHTML anywhere in the frontend source", () => {
    const offenders = walk(SRC).filter((f) =>
      readFileSync(f, "utf8").includes("dangerouslySetInnerHTML"),
    );
    expect(offenders).toEqual([]);
  });
});
