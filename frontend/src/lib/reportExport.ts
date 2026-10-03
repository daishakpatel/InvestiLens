// Client-side Markdown export of a report, including inline citation numbers, a reference list,
// and the disclaimer (§10.16). The backend export endpoint is Phase 4d/later; this keeps export
// working now without it.
import { DISCLAIMER } from "./config";
import { buildNumbering } from "./reportCitations";
import type { ResearchClaim, ResearchReportEnvelope } from "../types";

function claimsBlock(claims: ResearchClaim[], numberOf: (id: string) => number): string {
  return claims
    .map((c) => `- ${c.text} ${c.source_ids.map((id) => `[${numberOf(id)}]`).join("")}`)
    .join("\n");
}

const PROSE: { key: keyof ResearchReportEnvelope["report"]; title: string }[] = [
  { key: "executive_summary", title: "Executive Summary" },
  { key: "company_overview", title: "Company Overview" },
  { key: "revenue_analysis", title: "Revenue Analysis" },
  { key: "profitability_analysis", title: "Profitability Analysis" },
  { key: "balance_sheet_analysis", title: "Balance Sheet Analysis" },
  { key: "cash_flow_analysis", title: "Cash Flow Analysis" },
  { key: "valuation_analysis", title: "Valuation Analysis" },
];

export function reportToMarkdown(envelope: ResearchReportEnvelope): string {
  const { report } = envelope;
  const { numberOf, order } = buildNumbering(report);
  const out: string[] = [
    `# ${envelope.ticker} — Research Report`,
    `_Model ${envelope.model ?? "—"} · prompt ${envelope.prompt_version ?? "—"} · data ${envelope.data_version ?? "—"}_`,
    "",
  ];

  for (const { key, title } of PROSE) {
    const claims = report[key] as ResearchClaim[];
    if (claims.length) out.push(`## ${title}`, claimsBlock(claims, numberOf), "");
  }
  if (report.risks.length) {
    out.push("## Risks");
    for (const r of report.risks) {
      out.push(`- **${r.category}** — ${r.description} ${r.source_ids.map((id) => `[${numberOf(id)}]`).join("")}`);
    }
    out.push("");
  }

  if (order.length) {
    out.push("## References");
    order.forEach((id, i) => out.push(`${i + 1}. ${id}`));
    out.push("");
  }
  out.push("---", `> ${DISCLAIMER}`);
  return out.join("\n");
}
