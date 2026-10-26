// Phase 7k (FR-TH-015): every thesis the signed-in user has written, with its KPI states.
import { Link } from "react-router-dom";

import { SignInHint } from "../components/SignInHint";
import { StateChip } from "../components/thesis/ThesisView";
import { Container } from "../components/ui/Container";
import { ErrorState, LoadingState } from "../components/ui/States";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/format";
import { STANCE_LABEL } from "../lib/thesis";
import { useTheses } from "../lib/thesisQueries";
import { useDocumentTitle } from "../lib/useDocumentTitle";

export default function ThesesPage() {
  const { user } = useAuth();
  const theses = useTheses(undefined, Boolean(user));
  useDocumentTitle("Theses");
  return (
    <Container className="space-y-6 py-8">
      <header className="space-y-1">
        <h1 className="text-heading font-medium">Your theses</h1>
        <p className="text-sm text-muted">
          Why you follow each company, in your words, with KPIs checked against reported figures. Private to your account.
        </p>
      </header>
      {!user ? (
        <SignInHint>Sign in to write theses and track their KPIs.</SignInHint>
      ) : theses.isPending ? (
        <LoadingState />
      ) : theses.isError ? (
        <ErrorState message="Your theses could not be loaded." onRetry={() => void theses.refetch()} />
      ) : theses.data.length === 0 ? (
        <p className="text-sm text-muted">
          No theses yet. Open a company and choose the Thesis tab to write your first one.
        </p>
      ) : (
        <table className="w-full text-sm">
          <caption className="sr-only">Your theses</caption>
          <thead>
            <tr className="border-b border-border text-left text-caption text-muted">
              <th scope="col" className="py-2 pr-4 font-medium">Company</th>
              <th scope="col" className="py-2 pr-4 font-medium">Thesis</th>
              <th scope="col" className="py-2 pr-4 font-medium">KPIs</th>
              <th scope="col" className="py-2 font-medium">Updated</th>
            </tr>
          </thead>
          <tbody>
            {theses.data.map((t) => (
              <tr key={t.id} className="border-b border-border/60">
                <td className="py-3 pr-4 font-medium">{t.ticker}</td>
                <td className="py-3 pr-4">
                  <Link to={`/company/${encodeURIComponent(t.ticker)}/thesis?thesis=${t.id}`} className="hover:text-primary">
                    {t.title}
                  </Link>
                  <span className="ml-2 text-caption text-subtle">
                    {STANCE_LABEL[t.stance]}
                    {t.status === "closed" ? " · closed" : ""}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <span className="flex flex-wrap gap-1.5">
                    {t.kpi_states.broken > 0 && <StateChip state="broken" />}
                    <span className="text-caption text-muted">
                      {t.kpi_states.met} met · {t.kpi_states.broken} broken · {t.kpi_states.no_data} no data
                    </span>
                  </span>
                </td>
                <td className="tnum py-3 text-caption text-muted">{formatDate(t.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Container>
  );
}
