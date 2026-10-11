import { FileText } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../../lib/auth";
import { useJob, useStartResearch } from "../../lib/queries";
import { Button } from "../ui/Button";
import { EmptyState } from "../ui/States";

const LINK = "font-medium text-primary underline underline-offset-2";

/** FR-030: whatever happens to AI generation, the reported data is still there. */
function DataStillAvailable({ ticker, failed }: { ticker: string; failed: boolean }) {
  return (
    <p className="text-sm text-muted">
      {failed
        ? "Unable to generate the research report. Your financial data remains available: "
        : "The reported data does not depend on a report: "}
      <Link to={`/company/${ticker}/financials`} className={LINK}>
        Financials
      </Link>{" "}
      and{" "}
      <Link to={`/company/${ticker}/filings`} className={LINK}>
        Filings
      </Link>
      .
    </p>
  );
}

/** No report yet: say what one is and offer to make it (§10.16). Generation needs an account
 *  (ADR-0006) and runs as a background job, whose progress is shown while it runs. When it
 *  finishes, the page's "latest report" query is refreshed and the document takes its place. */
export function GenerateReport({
  ticker,
  unreadable,
}: {
  ticker: string;
  unreadable: boolean; // a saved report exists but could not be loaded
}) {
  const queryClient = useQueryClient();
  const { user, ready } = useAuth();
  const start = useStartResearch();
  const [job, setJob] = useState<{ jobId: string } | null>(null);
  const state = useJob(job?.jobId ?? null);
  const status = state.data?.status;

  useEffect(() => {
    if (status === "done") void queryClient.invalidateQueries({ queryKey: ["research-latest", ticker] });
  }, [status, queryClient, ticker]);

  const generate = async () => {
    const accepted = await start.mutateAsync(ticker);
    setJob({ jobId: accepted.job_id });
  };

  if (job && status !== "failed") {
    const progress = state.data?.progress ?? 0;
    return (
      <div className="mx-auto max-w-md space-y-4 py-10 text-center">
        <p className="text-body font-medium">Generating the research report…</p>
        <div
          role="progressbar"
          aria-label="Report generation"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
          className="h-1 overflow-hidden rounded-full bg-surface-2"
        >
          <div className="h-full bg-primary transition-[width]" style={{ width: `${progress}%` }} />
        </div>
        <p className="text-sm text-muted">
          {state.data?.stage ? `${state.data.stage}. ` : ""}
          Reports are written by a background worker and can take a couple of minutes. This page
          updates by itself when it is ready.
        </p>
        <DataStillAvailable ticker={ticker} failed={false} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md">
      {unreadable && (
        <p role="status" className="text-center text-sm text-warning">
          A saved report for {ticker.toUpperCase()} could not be read. You can generate a new one.
        </p>
      )}
      <EmptyState
        icon={<FileText className="size-5" />}
        message={`There is no research report for ${ticker.toUpperCase()} yet. A report covers the business, its financials, the cases for and against, and its risks, and every claim in it links to the filing passage it came from.`}
        action={
          !ready ? undefined : user ? (
            <Button variant="primary" loading={start.isPending} onClick={() => void generate()}>
              Generate research
            </Button>
          ) : (
            <Link
              to="/login"
              state={{ from: `/company/${ticker}/research` }}
              className="inline-flex h-9 items-center rounded-control bg-primary px-3.5 text-sm font-medium text-primary-contrast transition-colors hover:bg-primary/90"
            >
              Sign in to generate
            </Link>
          )
        }
      />
      <div className="space-y-2 text-center">
        {start.isError && (
          <p role="alert" className="text-sm text-negative">
            {start.error instanceof Error ? start.error.message : "The report could not be started."}
          </p>
        )}
        {(status === "failed" || start.isError) && <DataStillAvailable ticker={ticker} failed />}
      </div>
    </div>
  );
}
