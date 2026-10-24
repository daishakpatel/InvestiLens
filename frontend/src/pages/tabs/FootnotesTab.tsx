import { useState } from "react";
import { useParams } from "react-router-dom";

import { LadderChart } from "../../charts/LadderChart";
import { shortPeriod } from "../../charts/series";
import { useCitations } from "../../components/citations/CitationContext";
import { CitationChip } from "../../components/citations/CitationChip";
import { FilingDiffView } from "../../components/filings/FilingDiffView";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { DataTable } from "../../components/ui/DataTable";
import type { Column } from "../../components/ui/DataTable";
import { Section } from "../../components/ui/Section";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/States";
import { ApiError } from "../../lib/apiClient";
import { formatDate } from "../../lib/format";
import { categoriesFor, categoryLabel, formatFact, gapReason, ladderRows, tableFacts } from "../../lib/footnotes";
import { useFootnoteFacts, useNotes } from "../../lib/queries";
import type { FootnoteCategory, FootnoteFact, FilingSummary, NoteItem, NotesResponse } from "../../types";

// Schedules drawn as a chart rather than listed: (fact prefix, chart title).
const LADDERS: Record<string, [string, string][]> = {
  debt: [["debt_maturity", "Debt maturities"]],
  leases: [["lease_payments", "Undiscounted lease payments"]],
};

/** The XBRL figures for one category: ladders as charts, the rest as a table, then what the
 *  filing did not tag. Every figure opens its source (CIT-003). */
function Figures({ group, category }: { group: FootnoteCategory; category: string }) {
  const { open } = useCitations();
  const period = group.facts[0]?.period ?? group.gaps[0]?.period ?? "";
  const ladders = (LADDERS[category] ?? [])
    .map(([prefix, title]) => ({ prefix, title, rows: ladderRows(group.facts, prefix) }))
    .filter((l) => l.rows !== null);
  const rows = tableFacts(
    group.facts,
    ladders.map((l) => l.prefix),
  );
  const columns: Column<FootnoteFact>[] = [
    {
      key: "label",
      header: "Figure",
      render: (f) => (
        <span className="flex flex-wrap items-center gap-2">
          {f.label}
          {f.is_derived && (
            <span title={f.formula ?? undefined}>
              <Badge>Derived</Badge>
            </span>
          )}
        </span>
      ),
    },
    {
      key: "value",
      header: shortPeriod(period),
      numeric: true,
      render: (f) => (
        <button
          type="button"
          onClick={() => open(f.source_id)}
          className="underline decoration-border-strong underline-offset-2 hover:decoration-text"
          aria-label={`${f.label}: ${formatFact(f)}. Open source`}
        >
          {formatFact(f)}
        </button>
      ),
    },
  ];
  return (
    <Section title="Reported figures">
      <div className="space-y-8 pt-4">
        {ladders.map((l) => (
          <LadderChart key={l.prefix} title={l.title} rows={l.rows ?? []} period={period} slug={`${l.prefix}_${period}`} />
        ))}
        {rows.length > 0 && (
          <DataTable
            density="compact"
            label={`${categoryLabel(category)} figures`}
            columns={columns}
            rows={rows}
            rowKey={(f) => f.metric}
          />
        )}
        {group.gaps.length > 0 && (
          <div className="text-caption text-subtle">
            <p className="mb-1">Not available for {shortPeriod(period)}:</p>
            <ul className="space-y-0.5">
              {group.gaps.map((g) => (
                <li key={g.metric}>
                  {g.label} <span className="text-muted">· {gapReason(g.reason)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Section>
  );
}

/** The AI bullets for one note, each quoting the paragraph it cites (FR-FN-007). */
function Summary({ note }: { note: NoteItem }) {
  const summary = note.summary;
  if (!summary) return null;
  return (
    <Section title={`Summary · Note ${note.number}`} kind="ai">
      {summary.status === "summarised" ? (
        <ul className="space-y-4 pt-4" data-testid={`summary-${note.note_id}`}>
          {summary.bullets.map((b, i) => (
            <li key={`${b.paragraph_id}-${i}`} className="text-sm leading-relaxed">
              <p>
                {b.text}
                {"⁠"}
                <CitationChip number={i + 1} sourceId={b.paragraph_id} />
              </p>
              <q className="mt-1 block text-caption text-muted">{b.quote}</q>
            </li>
          ))}
        </ul>
      ) : (
        <p role="status" className="pt-4 text-sm text-muted">
          {summary.status === "abstained"
            ? "Not summarised. No statement in this note could be checked word for word against the filing, so none is shown."
            : "Not summarised yet. Summaries are written once after the filing is processed."}
        </p>
      )}
    </Section>
  );
}

function CategoryPanel({
  category,
  notes,
  group,
  filing,
}: {
  category: string;
  notes: NoteItem[];
  group: FootnoteCategory | undefined;
  filing: FilingSummary | null;
}) {
  const { open } = useCitations();
  const [comparing, setComparing] = useState(false);
  const label = categoryLabel(category);
  const comparable = filing !== null && category !== "other" && notes.length > 0;
  return (
    <div className="min-w-0 space-y-10">
      <div>
        <h2 className="text-title font-medium">{label}</h2>
        {notes.length > 0 ? (
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {notes.map((n) => (
              <li key={n.note_id}>
                <button
                  type="button"
                  onClick={() => open(n.paragraph_ids[0] ?? "")}
                  className="text-muted underline decoration-border-strong underline-offset-2 hover:text-text"
                >
                  Note {n.number} · {n.title}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-caption text-subtle">No note with this title was found in the filing.</p>
        )}
      </div>

      {group && (group.facts.length > 0 || group.gaps.length > 0) && <Figures group={group} category={category} />}

      {notes.map((n) => (
        <Summary key={n.note_id} note={n} />
      ))}

      {comparable && (
        <Section
          title="Compared with the prior year"
          actions={
            <Button size="sm" aria-expanded={comparing} onClick={() => setComparing((v) => !v)}>
              {comparing ? "Hide comparison" : "Compare with prior year"}
            </Button>
          }
        >
          {comparing ? (
            <div className="pt-4">
              <FilingDiffView filing={filing} candidates={[]} note={{ category, label }} />
            </div>
          ) : (
            <p className="pt-4 text-caption text-subtle">
              What changed in this note's wording since the previous {filing.filing_type}. Text matching, not AI.
            </p>
          )}
        </Section>
      )}
    </div>
  );
}

/** Notes to the financial statements (§13, Phase 7f): figures from XBRL first, AI summaries of
 *  the narrative only where numbers cannot carry it, and the year-over-year wording diff. */
export default function FootnotesTab() {
  const { ticker = "" } = useParams();
  const notesQuery = useNotes(ticker);
  const factsQuery = useFootnoteFacts(ticker);
  const [picked, setPicked] = useState<string | null>(null);

  if (notesQuery.isPending || factsQuery.isPending) return <LoadingState label="Loading footnotes" />;
  if (factsQuery.isError) {
    return <ErrorState message="Footnote figures could not be loaded." onRetry={() => void factsQuery.refetch()} />;
  }
  const missing = notesQuery.error instanceof ApiError && notesQuery.error.status === 404;
  if (notesQuery.isError && !missing) {
    return <ErrorState message="The filing's notes could not be loaded." onRetry={() => void notesQuery.refetch()} />;
  }
  const notesData: NotesResponse | undefined = notesQuery.data;
  const notes = notesData?.notes ?? [];
  const categories = categoriesFor(notes, factsQuery.data);
  if (categories.length === 0) {
    return <EmptyState message="No 10-K has been processed for this company yet, so there are no notes to show." />;
  }
  const selected = picked && categories.includes(picked) ? picked : (categories[0] ?? "");
  const groups = new Map((factsQuery.data.categories ?? []).map((g) => [g.category, g]));
  const filing = notesData?.filing ?? null;

  return (
    <div className="space-y-6">
      <p className="max-w-3xl text-caption text-subtle">
        {filing
          ? `Notes to the financial statements in the ${filing.filing_type} filed ${formatDate(filing.filing_date)}. `
          : "This company's 10-K has not been split into notes yet. "}
        Figures are read from the filing's XBRL tags. Summaries are written by AI and keep only statements that quote
        the filing word for word.
      </p>
      {(notesData?.low_confidence || missing) && (
        <p role="note" className="max-w-3xl text-caption text-warning">
          {missing
            ? "No processed 10-K was found, so only the tagged figures are shown."
            : "The notes in this filing could not all be told apart: some may be merged or missing below."}
        </p>
      )}
      <div className="grid gap-8 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <nav aria-label="Note categories">
          <ul className="-mx-1 flex gap-1 overflow-x-auto pb-1 lg:mx-0 lg:flex-col lg:overflow-visible">
            {categories.map((c) => (
              <li key={c} className="shrink-0">
                <button
                  type="button"
                  aria-current={c === selected ? "true" : undefined}
                  onClick={() => setPicked(c)}
                  className={`w-full rounded-control px-3 py-1.5 text-left text-sm transition-colors ${
                    c === selected ? "bg-surface-2 font-medium text-text" : "text-muted hover:text-text"
                  }`}
                >
                  {categoryLabel(c)}
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <CategoryPanel
          key={selected}
          category={selected}
          notes={notes.filter((n) => n.category === selected)}
          group={groups.get(selected)}
          filing={filing}
        />
      </div>
    </div>
  );
}
