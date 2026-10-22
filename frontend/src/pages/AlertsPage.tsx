import { AlertRuleList, NewAlertForm } from "../components/watch/AlertRules";
import { SignInHint } from "../components/SignInHint";
import { Container } from "../components/ui/Container";
import { Section } from "../components/ui/Section";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { useAuth } from "../lib/auth";
import { useAlertEventTypes, useAlerts } from "../lib/queries";
import { useDocumentTitle } from "../lib/useDocumentTitle";

function AlertSettings({ userId }: { userId: string }) {
  const types = useAlertEventTypes();
  const alerts = useAlerts(userId);

  if (types.isError || alerts.isError) {
    return (
      <ErrorState
        message="Your alerts could not be loaded."
        onRetry={() => void Promise.all([types.refetch(), alerts.refetch()])}
      />
    );
  }
  if (!types.data || !alerts.data) return <LoadingState label="Loading alerts" />;

  return (
    <div className="grid gap-x-16 gap-y-12 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Section title="Your alerts">
        {alerts.data.length === 0 ? (
          <EmptyState message="No alerts yet. Create one and new events will arrive in the bell at the top of the page." />
        ) : (
          <AlertRuleList alerts={alerts.data} types={types.data} />
        )}
      </Section>
      <Section title="New alert">
        <div className="pt-4">
          <NewAlertForm types={types.data} />
        </div>
      </Section>
    </div>
  );
}

/** Alert settings (Phase 7a, FR-AL-016): every rule the reader has, and a form for a new one. */
export default function AlertsPage() {
  const { user } = useAuth();
  useDocumentTitle("Alerts");

  return (
    <Container className="space-y-10 py-10">
      <header>
        <h1 className="text-heading font-semibold">Alerts</h1>
        <p className="mt-1 text-muted">Only events that happen after you create an alert are sent.</p>
      </header>
      {user ? (
        <AlertSettings userId={user.id} />
      ) : (
        <SignInHint>Sign in to be told about new filings, risk factors and price moves.</SignInHint>
      )}
    </Container>
  );
}
