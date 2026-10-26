// Phase 7k (FR-TH-015/017): the signed-in user's own theses on this company. A thesis is private;
// the app records and checks what the user wrote and never says what to believe or do.
import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { SignInHint } from "../../components/SignInHint";
import { DraftAssist } from "../../components/thesis/DraftAssist";
import { StateChip, ThesisEditor, ThesisView } from "../../components/thesis/ThesisView";
import { Button } from "../../components/ui/Button";
import { ErrorState, LoadingState } from "../../components/ui/States";
import { apiRequest } from "../../lib/apiClient";
import { useAuth } from "../../lib/auth";
import { STANCE_LABEL } from "../../lib/thesis";
import { useCreateThesis, useThesis, useTheses } from "../../lib/thesisQueries";
import type { KpiCreate } from "../../types";

export default function ThesisTab() {
  const { ticker = "" } = useParams();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const theses = useTheses(ticker, Boolean(user));
  const linked = Number(params.get("thesis")) || null;
  const selectedId = linked ?? theses.data?.[0]?.id ?? null;
  const thesis = useThesis(user ? selectedId : null);
  const create = useCreateThesis();
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState<{ title: string; kpis: KpiCreate[] }>({ title: "", kpis: [] });

  if (!user) {
    return (
      <SignInHint>
        Write down why you follow this company, with KPIs the app checks against reported figures. Theses are private
        to your account.
      </SignInHint>
    );
  }

  const select = (id: number | null) => {
    if (id === null) params.delete("thesis");
    else params.set("thesis", String(id));
    setParams(params, { replace: true });
  };

  const submitNew = (value: { title: string; body_md: string; stance: "long" | "short" | "watch" | "avoid" }) =>
    create.mutate(
      { ...value, ticker },
      {
        onSuccess: async (created) => {
          // Accepted draft KPIs are added only now, after the user saved the thesis (FR-TH-010).
          for (const kpi of draft.kpis) {
            await apiRequest(`/theses/${created.id}/kpis`, { method: "POST", body: kpi }).catch(() => undefined);
          }
          setDraft({ title: "", kpis: [] });
          setCreating(false);
          select(created.id);
        },
      },
    );

  if (creating) {
    return (
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <section aria-label="New thesis" className="space-y-4">
          <h2 className="text-title font-medium">New thesis on {ticker}</h2>
          <ThesisEditor
            key={draft.title}
            initial={{ title: draft.title, body_md: "", stance: "watch" }}
            submitLabel="Save thesis"
            busy={create.isPending}
            error={create.error?.message ?? null}
            onSubmit={submitNew}
            onCancel={() => setCreating(false)}
          />
          {draft.kpis.length > 0 && (
            <p className="text-sm text-muted">
              {draft.kpis.length} accepted KPI{draft.kpis.length === 1 ? "" : "s"} will be added when you save.
            </p>
          )}
        </section>
        <DraftAssist
          ticker={ticker}
          onAccept={(title, kpis) => setDraft((old) => ({ title: title ?? old.title, kpis: [...old.kpis, ...kpis] }))}
        />
      </div>
    );
  }

  if (theses.isPending) return <LoadingState />;
  if (theses.isError) return <ErrorState message="Your theses could not be loaded." onRetry={() => void theses.refetch()} />;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2" role="list" aria-label="Your theses on this company">
          {theses.data.map((t) => (
            <button
              key={t.id}
              type="button"
              role="listitem"
              onClick={() => select(t.id)}
              aria-current={t.id === selectedId}
              className={`rounded-control border px-3 py-1.5 text-left text-sm transition-colors ${
                t.id === selectedId ? "border-border-strong bg-surface-2" : "border-border hover:bg-surface"
              }`}
            >
              {t.title}
              <span className="ml-2 text-caption text-subtle">
                {STANCE_LABEL[t.stance]}
                {t.status === "closed" ? " · closed" : ""}
              </span>
              {t.kpi_states.broken > 0 && (
                <span className="ml-2 inline-block align-middle">
                  <StateChip state="broken" />
                </span>
              )}
            </button>
          ))}
        </div>
        <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
          New thesis
        </Button>
      </div>
      {theses.data.length === 0 ? (
        <div className="space-y-2 rounded-surface border border-border p-6">
          <p className="text-body">No thesis on {ticker} yet.</p>
          <p className="text-sm text-muted">
            Write why you follow it in your own words, then add KPIs (say, gross margin at or above 70%) that the app checks
            each time new figures are reported. You can also start from your rough notes with the draft assist.
          </p>
        </div>
      ) : thesis.isPending ? (
        <LoadingState />
      ) : thesis.isError ? (
        <ErrorState message="This thesis could not be loaded." onRetry={() => void thesis.refetch()} />
      ) : (
        <ThesisView thesis={thesis.data} onDeleted={() => select(null)} />
      )}
    </div>
  );
}
