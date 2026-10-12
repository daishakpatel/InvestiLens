import { Bell, BellRing } from "lucide-react";

import { useAuth } from "../../lib/auth";
import { useAlerts, useCreateAlert, useDeleteAlert } from "../../lib/queries";
import type { AlertType } from "../../types";
import { SignInHint } from "../SignInHint";
import { IconButton } from "../ui/Button";
import { Popover } from "../ui/Popover";
import { Switch } from "../ui/Switch";

// The alert types the API offers (§26.2), in the order a reader would look for them.
const TYPES: { type: AlertType; label: string; note?: string }[] = [
  { type: "new_10k", label: "New 10-K" },
  { type: "new_10q", label: "New 10-Q" },
  { type: "new_8k", label: "New 8-K" },
  { type: "new_risk_factor", label: "New risk factor", note: "A filing adds a risk the last one did not have" },
  { type: "price_move", label: "Price move", note: "A large one-day move" },
  { type: "news_category", label: "News", note: "New coverage of this company" },
];

function AlertSwitches({ ticker, userId }: { ticker: string; userId: string }) {
  const alerts = useAlerts(userId);
  const create = useCreateAlert();
  const remove = useDeleteAlert();
  const mine = (alerts.data ?? []).filter((alert) => alert.ticker.toUpperCase() === ticker);
  const busy = alerts.isPending || create.isPending || remove.isPending;

  return (
    <div className="space-y-3">
      <p className="text-label text-muted">Notify me about {ticker}</p>
      <ul className="space-y-3">
        {TYPES.map(({ type, label, note }) => {
          const existing = mine.find((alert) => alert.alert_type === type);
          return (
            <li key={type}>
              <Switch
                checked={existing !== undefined}
                disabled={busy}
                onCheckedChange={(on) => {
                  if (on) create.mutate({ ticker, alert_type: type });
                  else if (existing) remove.mutate(existing.id);
                }}
              >
                <span>
                  {label}
                  {note && <span className="block text-caption text-subtle">{note}</span>}
                </span>
              </Switch>
            </li>
          );
        })}
      </ul>
      {(alerts.isError || create.isError || remove.isError) && (
        <p role="alert" className="text-caption text-negative">
          Could not update your alerts. Try again.
        </p>
      )}
      <p className="text-caption text-subtle">Alerts arrive in the bell at the top of the page.</p>
    </div>
  );
}

/** Per-company alerts: each switch creates or deletes one alert. */
export function AlertsButton({ ticker }: { ticker: string }) {
  const { user } = useAuth();
  const symbol = ticker.toUpperCase();
  const alerts = useAlerts(user?.id ?? null);
  const active = (alerts.data ?? []).some((alert) => alert.ticker.toUpperCase() === symbol);

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
