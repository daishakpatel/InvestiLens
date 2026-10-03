import { useParams } from "react-router-dom";

import { RisksCard } from "../../components/research/ReportView";
import { Panel } from "../../components/Panel";
import { LoadingState } from "../../components/primitives";
import { buildNumbering } from "../../lib/reportCitations";
import { useLatestResearch } from "../../lib/queries";

export default function RisksTab() {
  const { ticker = "" } = useParams();
  const latest = useLatestResearch(ticker);

  if (latest.isPending) return <LoadingState />;
  if (latest.isSuccess && latest.data.report.risks.length > 0) {
    return <RisksCard risks={latest.data.report.risks} numberOf={buildNumbering(latest.data.report).numberOf} />;
  }
  return (
    <Panel title="Risks" kind="ai">
      <p className="p-6 text-sm text-muted">
        No risk analysis yet. Generate a report in the <strong>AI Research</strong> tab to see
        risk factors with citations.
      </p>
    </Panel>
  );
}
