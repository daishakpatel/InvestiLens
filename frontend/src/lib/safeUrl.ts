// URLs that arrive in API data (a news link, a filing's "open original", a source's deep link)
// originate with third parties and are untrusted (SEC-, conventions: "untrusted data"). React
// does not stop `javascript:` or `data:` URLs in an href, so every such link goes through here.

/** The URL if it is an absolute http(s) address, otherwise null. Callers render no link at all
 *  for null, rather than a dead or dangerous one. */
export function safeHttpUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
  } catch {
    return null; // relative, malformed, or scheme-only
  }
}

/** Attributes for a link that leaves the app: a new tab that cannot reach back into this one. */
export const EXTERNAL_LINK = { target: "_blank", rel: "noreferrer noopener" } as const;
