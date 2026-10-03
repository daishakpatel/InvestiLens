import { useParams } from "react-router-dom";

import { ManagementCard } from "../../components/research/ReportView";
import { Panel } from "../../components/Panel";
import { LoadingState } from "../../components/primitives";
import { buildNumbering } from "../../lib/reportCitations";
import { useLatestResearch } from "../../lib/queries";

export default function ManagementTab() {
  const { ticker = "" } = useParams();
  const latest = useLatestResearch(ticker);

  if (latest.isPending) return <LoadingState />;
  if (latest.isSuccess && latest.data.report.management_commentary.length > 0) {
    return (
      <ManagementCard
        statements={latest.data.report.management_commentary}
        numberOf={buildNumbering(latest.data.report).numberOf}
      />
    );
  }
  return (
    <Panel title="Management commentary" kind="ai">
      <p className="p-6 text-sm text-muted">
        No management analysis yet. Generate a report in the <strong>AI Research</strong> tab to see
        management commentary with citations.
      </p>
    </Panel>
  );
}
