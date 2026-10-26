import { Fragment, createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { renderMarkdown, safeHref } from "./markdown";

const html = (source: string) => renderToStaticMarkup(createElement(Fragment, null, ...renderMarkdown(source)));

describe("thesis markdown is safe by construction (FR-TH-018)", () => {
  it("shows raw HTML and script as text, never as markup", () => {
    const out = html('<script>alert(1)</script> <img src=x onerror="alert(2)"> <b>bold</b>');
    expect(out).not.toContain("<script");
    expect(out).not.toContain("<img");
    expect(out).not.toContain("<b>");
    expect(out).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
  });

  it("keeps only http(s) links, opened without a referrer or opener", () => {
    const out = html("[docs](https://sec.gov/x) [bad](javascript:alert(1)) [data](data:text/html,x)");
    expect(out).toContain('href="https://sec.gov/x"');
    expect(out).toContain('rel="noopener noreferrer nofollow"');
    expect(out).not.toContain("javascript:");
    expect(out).not.toContain('href="data:');
    expect(safeHref("HTTP://EXAMPLE.COM")).toBe("HTTP://EXAMPLE.COM");
    expect(safeHref('https://x" onmouseover="y')).toBeNull();
  });

  it("never loads a remote image", () => {
    const out = html("![chart](https://tracker.example/pixel.png) ![](x)");
    expect(out).not.toContain("<img");
    expect(out).toContain("[image: chart]");
    expect(out).toContain("[image]");
  });

  it("renders headings, lists, quotes, emphasis and code", () => {
    const out = html("# Thesis\n\n- one **two**\n- *three*\n\n1. first\n2. `code`\n\n> quoted\n> more\n\nPlain\ntext.");
    expect(out).toContain("<h3");
    expect(out).toMatch(/<ul[^>]*><li>one <strong>two<\/strong><\/li><li><em>three<\/em><\/li><\/ul>/);
    expect(out).toMatch(/<ol[^>]*><li>first<\/li><li><code[^>]*>code<\/code><\/li><\/ol>/);
    expect(out).toContain("quoted more");
    expect(out).toContain("<p>Plain text.</p>");
  });
});
