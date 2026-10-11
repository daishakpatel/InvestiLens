import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { LanguageTracker } from "../../components/filings/LanguageTracker";
import { ReportView } from "../../components/research/ReportView";
import { Section } from "../../components/ui/Section";
import { Spinner } from "../../components/ui/Skeleton";
import { LoadingState } from "../../components/ui/States";
import { useAuth } from "../../lib/auth";
import { useJob, useLatestResearch, useResearchReport, useStartResearch } from "../../lib/queries";
import { useScrollToHash } from "../../lib/useScrollToHash";

/** Research tab: the AI report (which carries the Risks and Management sections that used to be
 *  tabs; `/risks` and `/management` redirect to anchors here), then management language tracking.
 *  UI plan Step 4 turns this into one reading document. */
export default function ResearchTab() {
  const { ticker = "" } = useParams();
  useScrollToHash();
  return (
    <div className="space-y-12">
      <Report ticker={ticker} />
      <LanguageTracker ticker={ticker} />
    </div>
  );
}

function Report({ ticker }: { ticker: string }) {
  const latest = useLatestResearch(ticker);

  if (latest.isPending) return <LoadingState label="Loading latest report…" />;
  if (latest.isSuccess) return <ReportView envelope={latest.data} />;
  // No completed report yet (typically a 404) → offer generation.
  return <GenerateFlow ticker={ticker} />;
}

function GenerateFlow({ ticker }: { ticker: string }) {
  const { user } = useAuth();
  const start = useStartResearch();
  const [jobId, setJobId] = useState<string | null>(null);
  const [researchId, setResearchId] = useState<string | null>(null);
  const job = useJob(jobId);
  const report = useResearchReport(job.data?.status === "done" ? researchId : null);

  if (report.isSuccess) return <ReportView envelope={report.data} />;

  const onGenerate = async () => {
    const res = await start.mutateAsync(ticker);
    setJobId(res.job_id);
    setResearchId(res.research_id);
  };

  return (
    <div className="space-y-4">
      <Section title="AI Research" kind="ai">
        <div className="space-y-3 p-6 text-sm">
          <p>No research report has been generated for {ticker} yet.</p>

          {!user ? (
            <p className="text-muted">
              <Link to="/login" className="text-primary underline underline-offset-2">
                Sign in
              </Link>{" "}
              to generate a report (AI generation requires an account).
            </p>
          ) : jobId === null ? (
            <button
              type="button"
              onClick={() => void onGenerate()}
              disabled={start.isPending}
              className="rounded-control bg-primary px-4 py-2 font-medium text-primary-contrast hover:opacity-90 disabled:opacity-60"
            >
              {start.isPending ? "Starting…" : "Generate research report"}
            </button>
          ) : (
            <JobProgress status={job.data?.status ?? "queued"} stage={job.data?.stage ?? null} />
          )}

          {start.isError && (
            <p role="alert" className="text-negative">
              {start.error instanceof Error ? start.error.message : "Could not start generation."}
            </p>
          )}
        </div>
      </Section>

      {/* FR-030 / §10.16: data stays available regardless of AI generation state. */}
      {(job.data?.status === "failed" || jobId === null) && (
        <Section title="Your data is still available" kind="data">
          <p className="p-4 text-sm text-muted">
            {job.data?.status === "failed"
              ? "Unable to generate the research report. Your financial data remains available — "
              : "While a report isn’t ready, the deterministic data is available — "}
            see{" "}
            <Link to={`/company/${ticker}/financials`} className="text-primary underline underline-offset-2">
              Financials
            </Link>
            ,{" "}
            <Link to={`/company/${ticker}/filings`} className="text-primary underline underline-offset-2">
              Filings
            </Link>
            , and{" "}
            <Link to={`/company/${ticker}/news`} className="text-primary underline underline-offset-2">
              News
            </Link>
            .
          </p>
        </Section>
      )}
    </div>
  );
}

function JobProgress({ status, stage }: { status: string; stage: string | null }) {
  const pending = status === "queued" || status === "processing";
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {pending && <Spinner />}
        <span className="font-medium capitalize">{status}</span>
        {stage && <span className="text-muted">· {stage}</span>}
      </div>
      {pending && (
        <p className="text-xs text-muted">
          Generation is queued and runs on the background worker (wired in Phase 5d). This view
          updates automatically when it completes.
        </p>
      )}
    </div>
  );
}
