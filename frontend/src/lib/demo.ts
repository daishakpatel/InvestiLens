// The public demo's banner and guided path (Phase 7l Part B, NFR-ME-007, NFR-ME-010).
import { formatDate } from "./format";

export const RISK_QUESTION = "What changed in risk factors vs last year?";

/** The banner every demo page carries. Without a date it still says the data is fixture data. */
export function demoBannerText(asOf: string | null | undefined): string {
  const when = asOf ? ` as of ${formatDate(asOf)}` : "";
  return `Demo: fixture data${when}. Not investment advice.`;
}

export interface DemoScenario {
  title: string;
  description: string;
  to: string;
}

/** Three one-click paths, each served from recorded data with no network calls. */
export const SCENARIOS: DemoScenario[] = [
  {
    title: "NVIDIA at a glance",
    description:
      "Quarterly and trailing figures, reported red flags and earnings-quality scores, each with its source.",
    to: "/company/NVDA",
  },
  {
    title: "Ask a cited question",
    description: `“${RISK_QUESTION}” Every sentence of the answer links to the passage it rests on.`,
    to: `/company/NVDA/chat?ask=${encodeURIComponent(RISK_QUESTION)}`,
  },
  {
    title: "See what changed in a filing",
    description: "The latest annual report against the one before: new, removed and reworded risk factors.",
    to: "/company/NVDA/filings?view=changes",
  },
];
