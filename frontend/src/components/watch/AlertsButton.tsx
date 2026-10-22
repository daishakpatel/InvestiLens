import { Bell, BellRing } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../../lib/auth";
import { useAlertEventTypes, useAlerts, useCreateAlert, useDeleteAlert } from "../../lib/queries";
import { SignInHint } from "../SignInHint";
import { IconButton } from "../ui/Button";
import { Popover } from "../ui/Popover";
import { Switch } from "../ui/Switch";

function AlertSwitches({ ticker, userId }: { ticker: string; userId: string }) {
  const types = useAlertEventTypes();
  const alerts = useAlerts(userId);
  const create = useCreateAlert();
  const remove = useDeleteAlert();
  const mine = (alerts.data ?? []).filter((alert) => alert.ticker?.toUpperCase() === ticker);
  const busy = alerts.isPending || create.isPending || remove.isPending;

  return (
    <div className="space-y-3">
      <p className="text-label text-muted">Notify me about {ticker}</p>
      {types.isPending ? (
        <p className="text-caption text-subtle">Loading…</p>
      ) : (
        <ul className="space-y-3">
          {(types.data ?? []).map(({ key, label, description }) => {
            const existing = mine.filter((alert) => alert.event_type === key);
            return (
              <li key={key}>
                <Switch
                  checked={existing.length > 0}
                  disabled={busy}
                  onCheckedChange={(on) => {
                    // Default settings; thresholds and forms are edited on the Alerts page.
                    if (on) create.mutate({ ticker, event_type: key });
                    else existing.forEach((alert) => remove.mutate(alert.id));
                  }}
                >
                  <span>
                    {label}
                    <span className="block text-caption text-subtle">{description}</span>
                  </span>
                </Switch>
              </li>
            );
          })}
        </ul>
      )}
      {(types.isError || alerts.isError || create.isError || remove.isError) && (
        <p role="alert" className="text-caption text-negative">
          Could not update your alerts. Try again.
        </p>
      )}
      <p className="text-caption text-subtle">
        Alerts arrive in the bell at the top of the page.{" "}
        <Link to="/alerts" className="text-primary hover:underline">
          Manage alerts
        </Link>
      </p>
    </div>
  );
}

/** Per-company alerts: one switch per event type the server offers (FR-AL-016), each creating or
 *  deleting this company's rule with default settings. */
export function AlertsButton({ ticker }: { ticker: string }) {
  const { user } = useAuth();
  const symbol = ticker.toUpperCase();
  const alerts = useAlerts(user?.id ?? null);
  const active = (alerts.data ?? []).some((alert) => alert.ticker?.toUpperCase() === symbol);

  return (
    <Popover
      align="end"
      trigger={
        <IconButton
          variant="secondary"
          label={active ? `Alerts for ${symbol}, some on` : `Alerts for ${symbol}`}
        >
          {active ? <BellRing aria-hidden className="size-4" /> : <Bell aria-hidden className="size-4" />}
        </IconButton>
      }
    >
      {user ? (
        <AlertSwitches ticker={symbol} userId={user.id} />
      ) : (
        <SignInHint>Sign in to be told about new filings, risk factors and price moves.</SignInHint>
      )}
    </Popover>
  );
}
