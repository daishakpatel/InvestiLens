import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "./apiClient";
import { getAccessToken, setAccessToken } from "./authStore";

// AUTH-002: the 15-minute access token is renewed from the rotating refresh cookie mid-session.
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const TOKEN = { access_token: "fresh", token_type: "bearer", expires_in: 900 };

/** A backend that rejects any token but "fresh", and answers refreshes with `refresh`. */
function backend(refresh: () => Response) {
  return vi.fn((url: string, init: RequestInit) => {
    if (url.endsWith("/auth/refresh")) return Promise.resolve(refresh());
    const auth = (init.headers as Record<string, string>).Authorization;
    return Promise.resolve(auth === "Bearer fresh" ? json(200, { ok: true }) : json(401, { title: "expired" }));
  });
}
const refreshCalls = (fetch: ReturnType<typeof backend>) =>
  fetch.mock.calls.filter(([url]) => url.endsWith("/auth/refresh")).length;

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
});

describe("apiRequest token renewal", () => {
  it("renews an expired token and retries the request once", async () => {
    const fetch = backend(() => json(200, TOKEN));
    vi.stubGlobal("fetch", fetch);
    setAccessToken("stale");

    await expect(apiRequest("/me")).resolves.toMatchObject({ data: { ok: true } });
    expect(getAccessToken()).toBe("fresh");
    expect(refreshCalls(fetch)).toBe(1);
  });

  it("shares one refresh between requests that expire together (regression: token reuse)", async () => {
    const fetch = backend(() => json(200, TOKEN));
    vi.stubGlobal("fetch", fetch);
    setAccessToken("stale");

    await Promise.all([apiRequest("/a"), apiRequest("/b"), apiRequest("/c")]);
    expect(refreshCalls(fetch)).toBe(1);
  });

  it("signs out when the session itself has ended", async () => {
    const fetch = backend(() => json(401, { title: "revoked" }));
    vi.stubGlobal("fetch", fetch);
    setAccessToken("stale");

    await expect(apiRequest("/me")).rejects.toMatchObject({ status: 401 });
    expect(getAccessToken()).toBeNull();
  });

  it("does not try to refresh for an anonymous request", async () => {
    const fetch = backend(() => json(200, TOKEN));
    vi.stubGlobal("fetch", fetch);

    await expect(apiRequest("/me")).rejects.toMatchObject({ status: 401 });
    expect(refreshCalls(fetch)).toBe(0);
  });
});
