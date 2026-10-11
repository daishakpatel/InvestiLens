import { describe, expect, it } from "vitest";

import { isPaletteShortcut } from "./shortcuts";

const key = (key: string, mods: Partial<Record<"metaKey" | "ctrlKey" | "altKey", boolean>> = {}) => ({
  key,
  metaKey: false,
  ctrlKey: false,
  altKey: false,
  ...mods,
});

// UI plan Step 2 DoD: ⌘K, Ctrl+K, and "/" open the palette from every page.
describe("isPaletteShortcut", () => {
  it("opens on ⌘K and Ctrl+K, even while typing in a field", () => {
    expect(isPaletteShortcut(key("k", { metaKey: true }), true)).toBe(true);
    expect(isPaletteShortcut(key("K", { ctrlKey: true }), false)).toBe(true);
  });

  it('opens on a bare "/" only when the user is not typing', () => {
    expect(isPaletteShortcut(key("/"), false)).toBe(true);
    expect(isPaletteShortcut(key("/"), true)).toBe(false); // e.g. a "/" in a chat question
    expect(isPaletteShortcut(key("/", { ctrlKey: true }), false)).toBe(false);
  });

  it("ignores everything else", () => {
    expect(isPaletteShortcut(key("k"), false)).toBe(false);
    expect(isPaletteShortcut(key("k", { metaKey: true, altKey: true }), false)).toBe(false);
  });
});
