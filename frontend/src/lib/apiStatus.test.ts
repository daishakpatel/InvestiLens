import { describe, expect, it } from "vitest";

import { ApiError } from "./apiClient";
import { afterProbe, looksLikeOutage } from "./apiStatus";

// UI plan Step 2 "global states" + §28.2 (never fail silently): one banner for an outage, and an
// outage check that cannot turn a single broken endpoint into a request storm.
describe("looksLikeOutage", () => {
  it("treats network failures and 5xx responses as possible outages", () => {
    expect(looksLikeOutage(new TypeError("Failed to fetch"))).toBe(true);
    expect(looksLikeOutage(new ApiError(503, "Service Unavailable"))).toBe(true);
    expect(looksLikeOutage(new ApiError(500, "Internal Server Error"))).toBe(true);
  });

  it("does not suspect an outage for client errors or bad payloads", () => {
    expect(looksLikeOutage(new ApiError(404, "Not Found"))).toBe(false);
    expect(looksLikeOutage(new ApiError(401, "Unauthorized"))).toBe(false);
    expect(looksLikeOutage(new Error("schema mismatch"))).toBe(false);
  });
});

describe("afterProbe", () => {
  it("refetches failed queries only when the API has just recovered", () => {
    expect(afterProbe(false, true)).toEqual({ reachable: true, refetchFailed: true });
  });

  it("does not refetch when the API was reachable all along (regression: refetch loop)", () => {
    // One endpoint returning 500 forever: probe says healthy, so leave its error alone.
    expect(afterProbe(true, true)).toEqual({ reachable: true, refetchFailed: false });
  });

  it("marks the API unreachable on a failed probe and stays down until one succeeds", () => {
    expect(afterProbe(true, false)).toEqual({ reachable: false, refetchFailed: false });
    expect(afterProbe(false, false)).toEqual({ reachable: false, refetchFailed: false });
  });
});
