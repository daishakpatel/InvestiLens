import { CitationChip } from "../citations/CitationChip";
import { ReferenceList } from "../citations/ReferenceList";
import { Badge, EvidenceBadge } from "../primitives";
import { Panel } from "../Panel";
import { buildNumbering } from "../../lib/reportCitations";
import { reportToMarkdown } from "../../lib/reportExport";
import { downloadText } from "../../lib/format";
import type {
  Factor,
  ManagementTopicStatement,
  NewsItemSummary,
  ResearchClaim,
  ResearchReportEnvelope,
  Risk,
} from "../../types";

type NumberOf = (id: string) => number;

function Chips({ ids, numberOf }: { ids: string[]; numberOf: NumberOf }) {
  return (
    <>
      {ids.map((id) => (
        <CitationChip key={id} number={numberOf(id)} sourceId={id} />
      ))}
    </>
  );
}

function ClaimRow({ claim, numberOf }: { claim: ResearchClaim; numberOf: NumberOf }) {
  return (
    <li className="flex flex-col gap-1 border-b border-border/60 py-2 last:border-0">
      <p className="text-sm leading-relaxed">
        {claim.text} <Chips ids={claim.source_ids} numberOf={numberOf} />
      </p>
      <EvidenceBadge label={claim.confidence_label} />
    </li>
  );
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

export function ReportView({ envelope }: { envelope: ResearchReportEnvelope }) {
  const { report } = envelope;
  const { numberOf, order } = buildNumbering(report);

  return (
    <div className="space-y-4">
      <ReportMeta envelope={envelope} />

      {PROSE.map(({ key, title }) => {
        const claims = report[key] as ResearchClaim[];
        if (claims.length === 0) return null;
        return (
          <Panel key={key} title={title} kind="ai">
            <ul className="px-4 py-1">
              {claims.map((c) => (
                <ClaimRow key={c.claim_id} claim={c} numberOf={numberOf} />
              ))}
            </ul>
          </Panel>
        );
      })}

      {report.risks.length > 0 && <RisksCard risks={report.risks} numberOf={numberOf} />}
      {report.management_commentary.length > 0 && (
        <ManagementCard statements={report.management_commentary} numberOf={numberOf} />
      )}
      {report.bull_factors.length > 0 && (
        <FactorsCard title="Bull factors" factors={report.bull_factors} numberOf={numberOf} />
      )}
      {report.bear_factors.length > 0 && (
        <FactorsCard title="Bear factors" factors={report.bear_factors} numberOf={numberOf} />
      )}
      {report.news_summary.length > 0 && (
        <NewsSummaryCard items={report.news_summary} numberOf={numberOf} />
      )}

      {report.insufficient_evidence_sections.length > 0 && (
        <Panel title="Insufficient evidence" kind="ai">
          <p className="p-4 text-sm text-muted">
            These sections had no claims that passed citation verification, so they were left out
            rather than guessed:{" "}
            <span className="text-text">{report.insufficient_evidence_sections.join(", ")}</span>.
          </p>
        </Panel>
      )}

      <Panel title="References" kind="data">
        <div className="px-4 pb-3">
          <ReferenceList entries={order.map((id, i) => ({ number: i + 1, sourceId: id }))} />
        </div>
      </Panel>
    </div>
  );
}

function ReportMeta({ envelope }: { envelope: ResearchReportEnvelope }) {
  const onMarkdown = () =>
    downloadText(`${envelope.ticker}_research.md`, reportToMarkdown(envelope), "text/markdown");
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-surface-2 px-4 py-2 text-xs text-muted">
      <span>
        Model {envelope.model ?? "—"} · prompt {envelope.prompt_version ?? "—"} · data{" "}
        {envelope.data_version ?? "—"}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onMarkdown}
          className="rounded-md border border-border px-2 py-1 hover:bg-surface"
        >
          Export Markdown
        </button>
        <button
          type="button"
          onClick={() => window.print()}
          className="rounded-md border border-border px-2 py-1 hover:bg-surface"
        >
          Print / PDF
        </button>
      </div>
    </div>
  );
}

export function RisksCard({ risks, numberOf }: { risks: Risk[]; numberOf: NumberOf }) {
  return (
    <Panel title="Risks" kind="ai">
      <ul className="px-4 py-1">
        {risks.map((r, i) => (
          <li key={i} className="flex flex-col gap-1 border-b border-border/60 py-2 last:border-0">
            <div className="flex items-center gap-2">
              <Badge tone="warning">{r.category.replace(/_/g, " ")}</Badge>
              <EvidenceBadge label={r.evidence_label} />
            </div>
            <p className="text-sm">
              {r.description} <Chips ids={r.source_ids} numberOf={numberOf} />
            </p>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function ManagementCard({
  statements,
  numberOf,
}: {
  statements: ManagementTopicStatement[];
  numberOf: NumberOf;
}) {
  return (
    <Panel title="Management commentary" kind="ai">
      <ul className="px-4 py-1">
        {statements.map((m, i) => (
          <li key={i} className="flex flex-col gap-1 border-b border-border/60 py-2 last:border-0">
            <div className="flex items-center gap-2 text-xs text-muted">
              <Badge tone="neutral">{m.topic.replace(/_/g, " ")}</Badge>
              <span>{m.period}</span>
              {m.speaker && <span>· {m.speaker}</span>}
            </div>
            <p className="text-sm">
              {m.text} <Chips ids={m.source_ids} numberOf={numberOf} />
            </p>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function FactorsCard({
  title,
  factors,
  numberOf,
}: {
  title: string;
  factors: Factor[];
  numberOf: NumberOf;
}) {
  return (
    <Panel title={title} kind="ai">
      <div className="space-y-3 p-4">
        {factors.map((f, i) => (
          <div key={i}>
            <h3 className="text-sm font-semibold">{f.title}</h3>
            <ul>
              {f.claims.map((c) => (
                <ClaimRow key={c.claim_id} claim={c} numberOf={numberOf} />
              ))}
            </ul>
            {f.monitoring_indicator && (
              <p className="mt-1 text-xs text-muted">Watch: {f.monitoring_indicator}</p>
            )}
          </div>
        ))}
      </div>
    </Panel>
  );
}

function NewsSummaryCard({ items, numberOf }: { items: NewsItemSummary[]; numberOf: NumberOf }) {
  return (
    <Panel title="News summary" kind="ai">
      <ul className="px-4 py-1">
        {items.map((n, i) => (
          <li key={i} className="flex flex-col gap-1 border-b border-border/60 py-2 last:border-0">
            <Badge tone="neutral">{n.category}</Badge>
            <p className="text-sm">
              {n.summary} <Chips ids={n.source_ids} numberOf={numberOf} />
            </p>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
