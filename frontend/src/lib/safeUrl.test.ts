import { describe, expect, it } from "vitest";

import { safeHttpUrl } from "./safeUrl";

// Security: links built from provider data (news URLs, filing links) are untrusted input.
// Only absolute http(s) addresses may reach an href (XSS via javascript:/data: URLs, SEC-).
describe("safeHttpUrl", () => {
  it("passes absolute http and https addresses", () => {
    expect(safeHttpUrl("https://www.sec.gov/Archives/edgar/data/1045810/x.htm")).toBe(
      "https://www.sec.gov/Archives/edgar/data/1045810/x.htm",
    );
    expect(safeHttpUrl("http://news.example/nvda/11")).toBe("http://news.example/nvda/11");
  });

  it("rejects script-bearing and non-web schemes, however they are disguised", () => {
    for (const url of [
      "javascript:alert(1)",
      "JaVaScRiPt:alert(1)",
      " javascript:alert(1)",
      "java\tscript:alert(1)",
      "data:text/html,<script>alert(1)</script>",
      "vbscript:msgbox(1)",
      "file:///etc/passwd",
      "blob:https://example.com/123",
    ]) {
      expect(safeHttpUrl(url), url).toBeNull();
    }
  });

  it("rejects anything that is not an absolute address", () => {
    for (const url of ["", null, undefined, "/company/NVDA", "//evil.example", "example.com", "#"]) {
      expect(safeHttpUrl(url), String(url)).toBeNull();
    }
  });
});
