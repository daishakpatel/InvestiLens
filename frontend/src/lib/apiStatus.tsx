// Is the API reachable? One answer for the whole app, so an outage shows one banner instead of an
// error box in every panel (UI plan Step 2, §28.2 "never fail silently").
//
// A failed query alone is ambiguous (one broken endpoint vs. the whole backend), so a failure that
// looks like an outage triggers a probe of /health; only a failed probe marks the API unreachable.
// While it is, the probe repeats, and on recovery (only then) every errored query is refetched.
import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import type { ReactNode } from "react";

import { ApiError } from "./apiClient";
import { API_BASE_URL } from "./config";

const RETRY_MS = 5_000;

interface ApiStatus {
  online: boolean; // the browser has a network connection
  reachable: boolean; // the API answered its last health probe
  retry: () => void;
}

const ApiStatusContext = createContext<ApiStatus>({
  online: true,
  reachable: true,
  retry: () => undefined,
});

/** A network failure (fetch rejects with TypeError) or a gateway/server error. */
export function looksLikeOutage(error: unknown): boolean {
  if (error instanceof ApiError) return error.status >= 500;
  return error instanceof TypeError;
}

/** What a finished health probe means. Failed queries are refetched only when the API has just
 *  come back from an outage. If it was reachable all along, the failure belongs to one endpoint,
 *  and refetching it would fail again, trigger another probe, and loop forever. */
export function afterProbe(
  wasReachable: boolean,
  ok: boolean,
): { reachable: boolean; refetchFailed: boolean } {
  return { reachable: ok, refetchFailed: ok && !wasReachable };
}

async function probeHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}

function subscribeOnline(onChange: () => void): () => void {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

export function ApiStatusProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const online = useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
  const [reachable, setReachable] = useState(true);

  const reachableRef = useRef(true);
  const probing = useRef(false);

  const probe = useCallback(async () => {
    if (probing.current) return; // a burst of failures needs one answer, not one probe each
    probing.current = true;
    const ok = await probeHealth();
    probing.current = false;
    const next = afterProbe(reachableRef.current, ok);
    reachableRef.current = next.reachable;
    setReachable(next.reachable);
    if (next.refetchFailed) {
      void queryClient.refetchQueries({ predicate: (query) => query.state.status === "error" });
    }
  }, [queryClient]);

  // An outage-shaped query failure is the cue to check.
  useEffect(
    () =>
      queryClient.getQueryCache().subscribe((event) => {
        if (
          event.type === "updated" &&
          event.action.type === "error" &&
          looksLikeOutage(event.action.error)
        ) {
          void probe();
        }
      }),
    [queryClient, probe],
  );

  // While unreachable, keep checking; also check the moment the browser comes back online.
  useEffect(() => {
    if (reachable || !online) return;
    const id = setInterval(() => void probe(), RETRY_MS);
    return () => clearInterval(id);
  }, [reachable, online, probe]);

  const value = useMemo<ApiStatus>(
    () => ({ online, reachable, retry: () => void probe() }),
    [online, reachable, probe],
  );
  return <ApiStatusContext value={value}>{children}</ApiStatusContext>;
}

export function useApiStatus(): ApiStatus {
  return useContext(ApiStatusContext);
}
