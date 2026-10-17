import { CloudOff, WifiOff } from "lucide-react";

import { useApiStatus } from "../lib/apiStatus";
import { Button } from "./ui/Button";

/** The single announcement of an outage. Panels stay quiet and reload when it clears. */
export function ApiStatusBanner() {
  const { online, reachable, retry } = useApiStatus();
  if (online && reachable) return null;
  const Icon = online ? CloudOff : WifiOff;
  return (
    <div
      role="status"
      className="fixed bottom-4 left-1/2 z-40 flex w-max max-w-[calc(100vw-2rem)] -translate-x-1/2 items-center gap-3 rounded-full border border-border-strong bg-surface py-1.5 pl-4 pr-1.5 text-sm shadow-float"
    >
      <Icon aria-hidden className="size-4 shrink-0 text-warning" />
      <span>
        {online
          ? "Can’t reach Assay Desk. Reconnecting…"
          : "You’re offline. Data will load when you reconnect."}
      </span>
      {online && (
        <Button size="sm" variant="ghost" className="rounded-full" onClick={retry}>
          Retry now
        </Button>
      )}
    </div>
  );
}
