import type { AppNotification } from "../types";

/** Where a notification's evidence lives in the app, from its backend-issued source ids
 *  (FR-AL-018): a filing opens in the Filings tab, news in the News tab, anything else on the
 *  company page. Null when the notification has no single company (a cross-company digest). */
export function evidenceHref(item: Pick<AppNotification, "ticker" | "source_ids">): string | null {
  if (!item.ticker) return null;
  const base = `/company/${encodeURIComponent(item.ticker)}`;
  const ids = item.source_ids ?? [];
  const filing = ids.find((id) => id.startsWith("filing:"));
  if (filing) return `${base}/filings?filing=${encodeURIComponent(filing.slice("filing:".length))}`;
  if (ids.some((id) => id.startsWith("news:"))) return `${base}/news`;
  return base;
}
