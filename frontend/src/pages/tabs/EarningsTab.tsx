// Phase 7j (FR-EB-013..015): the earnings view: the upcoming report date, then the latest
// post-earnings brief or pre-earnings preview with a version switcher, printable to PDF.
import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { useCitations } from "../../components/citations/CitationContext";
import { BriefTitle, BriefView, PreviewView } from "../../components/earnings/BriefSections";
import { Button } from "../../components/ui/Button";
import { SegmentedControl } from "../../components/ui/SegmentedControl";
import { Select } from "../../components/ui/Select";
import { AsyncContent, EmptyState, ErrorState } from "../../components/ui/States";
import { useAuth } from "../../lib/auth";
import { dateSourceText, pickVersions, reportDateText, versionLabel } from "../../lib/earnings";
import { useEarningsBriefs, useEarningsCalendar, useGenerateBrief } from "../../lib/queries";
import type { CalendarEvent, StoredBrief } from "../../types";

type Kind = StoredBrief["kind"];

function Upcoming({ event }: { event: CalendarEvent | null }) {
  const { open } = useCitations();
  return (
    <section aria-label="Upcoming earnings" className="rounded-surface border border-border bg-surface p-5 print:hidden">
      <p className="text-caption text-muted">Upcoming</p>
      {event ? (
        <>
          <p className="mt-1 text-title font-medium">
            {event.period_label} · {reportDateText(event.report_date, event.estimated, event.report_time)}
          </p>
          <p className="mt-1 text-caption text-subtle">
            {event.report_date ? `${dateSourceText(event.source)}.` : "No year-ago date to estimate from."}
            {event.estimated && event.report_date ? " An estimate never triggers a preview." : ""}
          </p>
          {event.quote && event.source_id && (
            <button
              type="button"
              onClick={() => event.source_id && open(event.source_id)}
              className="mt-2 block text-left text-caption text-muted hover:text-primary"
            >
              “{event.quote}”
            </button>
          )}
        </>
      ) : (
        <p className="mt-1 text-sm text-muted">No upcoming report found in the company's filings.</p>
      )}
    </section>
  );
}

export default function EarningsTab() {
  const { ticker = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const { user } = useAuth();
  const calendar = useEarningsCalendar(ticker);
  const briefs = useEarningsBriefs(ticker);
  const generate = useGenerateBrief(ticker);
  const linked = Number(params.get("brief")) || null;
  const linkedKind = briefs.data?.items.find((i) => i.id === linked)?.kind;
  const [kindChoice, setKind] = useState<Kind | null>(null);
  const kind: Kind = kindChoice ?? linkedKind ?? "brief";

  const select = (id: number) => {
    params.set("brief", String(id));
    setParams(params, { replace: true });
  };

  return (
    <div className="space-y-8">
      {calendar.isError ? (
        <ErrorState message="The earnings calendar could not be loaded." onRetry={() => void calendar.refetch()} />
      ) : (
        <Upcoming event={calendar.data?.upcoming ?? null} />
      )}
      <AsyncContent query={briefs}>
        {(data) => {
          const picked = pickVersions(data.items, kind, linked);
          return (
            <div className="space-y-8">
              <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
                <SegmentedControl
                  label="Document"
                  value={kind}
                  onValueChange={(value) => setKind(value)}
                  options={[
                    { value: "brief", label: "Post-earnings brief" },
                    { value: "preview", label: "Pre-earnings preview" },
                  ]}
                />
                <div className="flex flex-wrap items-center gap-2">
                  {picked && picked.versions.length > 1 && (
                    <Select
                      aria-label="Version"
                      value={String(picked.current.id)}
                      onChange={(e) => select(Number(e.target.value))}
                    >
                      {picked.versions.map((v) => (
                        <option key={v.id} value={v.id}>
                          {versionLabel(v)}
                        </option>
                      ))}
                    </Select>
                  )}
                  {user && (
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={generate.isPending}
                      onClick={() => generate.mutate(kind, { onSuccess: (r) => select(r.item.id) })}
                    >
                      {kind === "brief" ? "Refresh brief" : "Refresh preview"}
                    </Button>
                  )}
                  {picked && (
                    <Button variant="ghost" size="sm" onClick={() => window.print()}>
                      Print
                    </Button>
                  )}
                </div>
              </div>
              {generate.isError && (
                <p role="alert" className="text-sm text-negative print:hidden">
                  {generate.error.message}
                </p>
              )}
              {generate.data && !generate.data.created && (
                <p role="status" className="text-sm text-muted print:hidden">
                  Nothing changed since the stored version, so it was kept.
                </p>
              )}
              {!picked ? (
                <EmptyState
                  message={
                    kind === "brief"
                      ? "No post-earnings brief yet. One is made once the earnings 8-K and its press release are filed."
                      : "No preview yet. One is made three days before a confirmed (not estimated) report date."
                  }
                />
              ) : (
                <article aria-label={`${picked.current.period_label} ${kind}`} className="earnings-print space-y-8">
                  {picked.current.brief && (
                    <>
                      <BriefTitle header={picked.current.brief.header} kind="brief" version={versionLabel(picked.current)} />
                      <BriefView brief={picked.current.brief} />
                    </>
                  )}
                  {picked.current.preview && (
                    <>
                      <BriefTitle header={picked.current.preview.header} kind="preview" version={versionLabel(picked.current)} />
                      <PreviewView preview={picked.current.preview} />
                    </>
                  )}
                  <p className="text-caption text-subtle">{data.scope}</p>
                </article>
              )}
            </div>
          );
        }}
      </AsyncContent>
    </div>
  );
}
