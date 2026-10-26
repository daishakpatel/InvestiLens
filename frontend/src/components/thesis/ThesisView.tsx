// Phase 7k (FR-TH-015/016): one thesis. The user's text (safe markdown), the KPI table with
// state chips and neutral sparklines, the timeline with evidence links, and the revision history.
// State colours never use green/red (those mean gain/loss): `met` is neutral, `broken` warning.
import { CircleCheck, CircleDashed, History, TriangleAlert } from "lucide-react";
import { Dialog } from "radix-ui";
import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { Sparkline } from "../../charts/Sparkline";
import { formatDate, toNumber } from "../../lib/format";
import { renderMarkdown } from "../../lib/markdown";
import {
  COMPARATOR_SYMBOL,
  STANCE_LABEL,
  STATE_LABEL,
  evaluatedText,
  eventEvidence,
  eventText,
  valueText,
} from "../../lib/thesis";
import {
  useAddKpi,
  useAddNote,
  useDeleteKpi,
  useDeleteThesis,
  useThesisEvents,
  useThesisRevisions,
  useUpdateKpi,
  useUpdateThesis,
} from "../../lib/thesisQueries";
import type { KpiCreate, ThesisDetail, ThesisKpi } from "../../types";
import { useCitations } from "../citations/CitationContext";
import { WordDiff } from "../filings/FilingDiffView";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Section } from "../ui/Section";
import { Select } from "../ui/Select";
import { ErrorState, LoadingState } from "../ui/States";
import { KpiForm } from "./KpiForm";
import { TEXTAREA } from "./styles";

const CHIP = {
  met: { Icon: CircleCheck, className: "bg-surface-2 text-text" },
  broken: { Icon: TriangleAlert, className: "bg-warning/15 text-warning" },
  no_data: { Icon: CircleDashed, className: "bg-surface-2 text-subtle" },
} as const;

export function StateChip({ state }: { state: ThesisKpi["state"] }) {
  const { Icon, className } = CHIP[state];
  return (
    <span className={`inline-flex w-fit items-center gap-1 rounded-full px-2 py-0.5 text-caption font-medium ${className}`}>
      <Icon aria-hidden className="size-3.5" />
      {STATE_LABEL[state]}
    </span>
  );
}

export function ThesisEditor({
  initial,
  submitLabel,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial: { title: string; body_md: string; stance: ThesisDetail["stance"] };
  submitLabel: string;
  busy: boolean;
  error: string | null;
  onSubmit: (value: { title: string; body_md: string; stance: ThesisDetail["stance"] }) => void;
  onCancel?: () => void;
}) {
  const [title, setTitle] = useState(initial.title);
  const [body, setBody] = useState(initial.body_md);
  const [stance, setStance] = useState(initial.stance);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({ title: title.trim(), body_md: body, stance });
  };
  return (
    <form onSubmit={submit} className="space-y-3" aria-label="Thesis">
      <div className="grid gap-3 md:grid-cols-[1fr_10rem]">
        <label className="space-y-1">
          <span className="text-caption text-muted">Title</span>
          <Input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Title" />
        </label>
        <label className="space-y-1">
          <span className="text-caption text-muted">Your stance (your tag)</span>
          <Select
            value={stance}
            onChange={(e) => setStance(e.target.value as ThesisDetail["stance"])}
            className="w-full"
            aria-label="Stance"
          >
            {Object.entries(STANCE_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </label>
      </div>
      <label className="block space-y-1">
        <span className="text-caption text-muted">Thesis (markdown; private to you)</span>
        <textarea
          className={TEXTAREA}
          rows={8}
          maxLength={20000}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          aria-label="Thesis text"
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-negative">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm" loading={busy}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

function KpiRow({ kpi, thesis }: { kpi: ThesisKpi; thesis: ThesisDetail }) {
  const { open } = useCitations();
  const [editing, setEditing] = useState(false);
  const update = useUpdateKpi(thesis.id);
  const remove = useDeleteKpi(thesis.id);
  const values = kpi.history.map((p) => toNumber(p.value)).filter((n): n is number => n !== null);
  const source = kpi.last_source_ids[0];
  if (editing) {
    return (
      <li className="py-3">
        <KpiForm
          ticker={thesis.ticker}
          initial={kpi}
          submitLabel="Save KPI"
          busy={update.isPending}
          error={update.error?.message ?? null}
          onSubmit={(body) => update.mutate({ id: kpi.id, body }, { onSuccess: () => setEditing(false) })}
          onCancel={() => setEditing(false)}
        />
      </li>
    );
  }
  return (
    <li className="grid items-center gap-x-4 gap-y-1 py-3 md:grid-cols-[minmax(0,1.6fr)_7rem_minmax(0,1fr)_6rem_auto]">
      <div className="min-w-0">
        <p className="font-medium">{kpi.label}</p>
        <p className="text-caption text-muted">
          {kpi.metric_label} ({kpi.period_type === "LATEST" ? "latest close" : kpi.period_type}) {COMPARATOR_SYMBOL[kpi.comparator]}{" "}
          {valueText(kpi.threshold, kpi.unit)}
        </p>
        {kpi.rationale && <p className="text-caption text-subtle">{kpi.rationale}</p>}
      </div>
      <StateChip state={kpi.state} />
      <div>
        {source && kpi.last_value !== null ? (
          <button
            type="button"
            onClick={() => open(source)}
            className="tnum underline decoration-border-strong underline-offset-2 hover:decoration-text"
            aria-label={`Latest ${valueText(kpi.last_value, kpi.unit)}. Open source`}
          >
            {valueText(kpi.last_value, kpi.unit)}
          </button>
        ) : (
          <span className="text-muted">—</span>
        )}
        <p className="text-caption text-subtle">{evaluatedText(kpi)}</p>
      </div>
      <Sparkline values={values} tone="neutral" className="w-24" />
      <div className="flex gap-1">
        <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
          Edit
        </Button>
        <Button variant="ghost" size="sm" loading={remove.isPending} onClick={() => remove.mutate(kpi.id)}>
          Remove
        </Button>
      </div>
    </li>
  );
}

function Timeline({ thesis }: { thesis: ThesisDetail }) {
  const events = useThesisEvents(thesis.id);
  const addNote = useAddNote(thesis.id);
  const { open } = useCitations();
  const [note, setNote] = useState("");
  const kpis = new Map(thesis.kpis.map((k) => [k.id, k]));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (note.trim()) addNote.mutate(note.trim(), { onSuccess: () => setNote("") });
  };
  return (
    <Section title="Timeline">
      <form onSubmit={submit} className="flex gap-2 pt-4">
        <Input maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} aria-label="Add a note" placeholder="Add a note" />
        <Button type="submit" size="md" loading={addNote.isPending} disabled={!note.trim()}>
          Add
        </Button>
      </form>
      {events.isPending ? (
        <LoadingState />
      ) : events.isError ? (
        <ErrorState message="The timeline could not be loaded." onRetry={() => void events.refetch()} />
      ) : events.data.length === 0 ? (
        <p className="pt-4 text-sm text-muted">
          Nothing yet. KPI changes on newly reported data, red flags and earnings briefs for {thesis.ticker} appear here.
        </p>
      ) : (
        <ol className="divide-y divide-border/60 pt-2" aria-label="Thesis timeline">
          {events.data.map((event) => {
            const evidence = eventEvidence(event, thesis.ticker);
            const text = eventText(event, kpis);
            return (
              <li key={event.id} className="flex gap-3 py-3 text-sm">
                <span className="tnum w-24 shrink-0 text-caption text-subtle">{formatDate(event.occurred_at)}</span>
                {evidence.href ? (
                  <Link to={evidence.href} className="hover:text-primary">
                    {text}
                  </Link>
                ) : evidence.sourceId ? (
                  <button type="button" onClick={() => open(evidence.sourceId ?? "")} className="text-left hover:text-primary">
                    {text}
                  </button>
                ) : (
                  <span>{text}</span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </Section>
  );
}

function HistoryDrawer({ thesisId }: { thesisId: number }) {
  const [open, setOpen] = useState(false);
  const revisions = useThesisRevisions(thesisId, open);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button variant="ghost" size="sm">
          <History aria-hidden className="size-4" />
          History
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-scrim" />
        <Dialog.Content className="fixed inset-y-0 right-0 z-50 w-[min(36rem,100vw)] overflow-y-auto border-l border-border bg-bg p-6 shadow-float">
          <Dialog.Title className="text-title font-medium">History</Dialog.Title>
          <Dialog.Description className="mt-1 text-caption text-muted">
            Every saved version of the title and text. Edits never overwrite one.
          </Dialog.Description>
          {revisions.isPending ? (
            <LoadingState />
          ) : revisions.isError ? (
            <ErrorState message="History could not be loaded." />
          ) : (
            <ol className="mt-4 space-y-5">
              {revisions.data.map((r) => (
                <li key={r.revision} className="space-y-1.5">
                  <p className="text-caption text-subtle">
                    Revision {r.revision} · {formatDate(r.created_at)}
                  </p>
                  <div className="text-sm leading-relaxed">
                    {r.word_diff ? <WordDiff ops={r.word_diff} /> : <span className="text-muted">First version: {r.title}</span>}
                  </div>
                </li>
              ))}
            </ol>
          )}
          <Dialog.Close asChild>
            <Button variant="ghost" size="sm" className="mt-6">
              Close
            </Button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function ThesisView({ thesis, onDeleted }: { thesis: ThesisDetail; onDeleted: () => void }) {
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState(false);
  const update = useUpdateThesis(thesis.id);
  const remove = useDeleteThesis();
  const addKpi = useAddKpi(thesis.id);
  const closed = thesis.status === "closed";
  const add = (body: KpiCreate) => addKpi.mutate(body, { onSuccess: () => setAdding(false) });

  return (
    <article aria-label={thesis.title} className="space-y-10">
      {editing ? (
        <ThesisEditor
          initial={thesis}
          submitLabel="Save (adds a revision)"
          busy={update.isPending}
          error={update.error?.message ?? null}
          onSubmit={(value) => update.mutate(value, { onSuccess: () => setEditing(false) })}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <header className="space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-caption text-subtle">
                Your thesis · {STANCE_LABEL[thesis.stance]} · {closed ? "Closed" : "Active"} · updated {formatDate(thesis.updated_at)}
              </p>
              <h2 className="text-heading font-medium">{thesis.title}</h2>
            </div>
            <div className="flex flex-wrap gap-1">
              <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
                Edit
              </Button>
              <HistoryDrawer thesisId={thesis.id} />
              <Button variant="ghost" size="sm" onClick={() => update.mutate({ status: closed ? "active" : "closed" })}>
                {closed ? "Reopen" : "Close"}
              </Button>
              <Button
                variant="danger"
                size="sm"
                loading={remove.isPending}
                onClick={() => {
                  if (window.confirm("Delete this thesis, its KPIs, timeline and history? This cannot be undone.")) {
                    remove.mutate(thesis.id, { onSuccess: onDeleted });
                  }
                }}
              >
                Delete
              </Button>
            </div>
          </div>
          {update.isError && (
            <p role="alert" className="text-sm text-negative">
              {update.error.message}
            </p>
          )}
          <div className="max-w-3xl space-y-3 text-body leading-relaxed" data-testid="thesis-body">
            {thesis.body_md.trim() ? renderMarkdown(thesis.body_md) : <p className="text-muted">No text yet.</p>}
          </div>
        </header>
      )}

      <Section
        title="KPIs"
        actions={
          !adding && thesis.kpis.length < 10 ? (
            <Button size="sm" onClick={() => setAdding(true)}>
              Add KPI
            </Button>
          ) : undefined
        }
      >
        <p className="pt-3 text-caption text-subtle">
          Checked against reported data each time new figures arrive. A KPI is met, broken, or has no data yet; the app
          never judges the thesis itself.
        </p>
        {adding && (
          <div className="pt-4">
            <KpiForm
              ticker={thesis.ticker}
              submitLabel="Add KPI"
              busy={addKpi.isPending}
              error={addKpi.error?.message ?? null}
              onSubmit={add}
              onCancel={() => setAdding(false)}
            />
          </div>
        )}
        {thesis.kpis.length === 0 && !adding ? (
          <p className="pt-4 text-sm text-muted">No KPIs yet. Add one to have the app check it against reported figures.</p>
        ) : (
          <ul className="divide-y divide-border/60" aria-label="KPIs">
            {thesis.kpis.map((kpi) => (
              <KpiRow key={kpi.id} kpi={kpi} thesis={thesis} />
            ))}
          </ul>
        )}
      </Section>

      <Timeline thesis={thesis} />
    </article>
  );
}
