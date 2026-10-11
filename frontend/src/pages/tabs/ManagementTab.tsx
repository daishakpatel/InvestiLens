import { useParams } from "react-router-dom";

import { LanguageTracker } from "../../components/filings/LanguageTracker";
import { ManagementCard } from "../../components/research/ReportView";
import { Section } from "../../components/ui/Section";
import { LoadingState } from "../../components/ui/States";
import { buildNumbering } from "../../lib/reportCitations";
import { useLatestResearch } from "../../lib/queries";

export default function ManagementTab() {
  const { ticker = "" } = useParams();
  const latest = useLatestResearch(ticker);

  return (
    <div className="space-y-4">
      <LanguageTracker ticker={ticker} />
      {latest.isPending ? (
        <LoadingState />
      ) : latest.isSuccess && latest.data.report.management_commentary.length > 0 ? (
        <ManagementCard
          statements={latest.data.report.management_commentary}
          numberOf={buildNumbering(latest.data.report).numberOf}
        />
      ) : (
        <Section title="Management commentary" kind="ai">
          <p className="p-6 text-sm text-muted">
            No management analysis yet. Generate a report in the <strong>AI Research</strong> tab
            to see management commentary with citations.
          </p>
        </Section>
      )}
    </div>
  );
}
