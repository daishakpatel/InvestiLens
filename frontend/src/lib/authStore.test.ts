import { afterEach, describe, expect, it, vi } from "vitest";

import { hasSessionHint, setSessionHint } from "./authStore";

// The silent refresh only runs when this browser has signed in before, so an anonymous visit
// makes no failing /auth/refresh call (NFR-ME-012: no console errors on the demo path).
describe("session hint", () => {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => store.set(k, v),
    removeItem: (k: string) => store.delete(k),
  });
  afterEach(() => store.clear());

  it("is off until a sign-in, and off again after sign-out", () => {
    expect(hasSessionHint()).toBe(false);
    setSessionHint(true);
    expect(hasSessionHint()).toBe(true);
    setSessionHint(false);
    expect(hasSessionHint()).toBe(false);
  });

  it("keeps trying the refresh when storage is blocked", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
    });
    expect(hasSessionHint()).toBe(true);
  });
});
