// In-memory access-token store (ADR-0005: the access token lives in memory, never localStorage,
// to limit XSS blast radius). A tiny observable so React and the API client share one source.
type Listener = () => void;

let accessToken: string | null = null;
const listeners = new Set<Listener>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  for (const l of listeners) l();
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// Whether this browser has signed in before, so the silent refresh is only tried when there is a
// session to restore: an anonymous visit then makes no doomed `/auth/refresh` call (whose 401 the
// browser logs as a console error). Only a flag; the token itself never touches storage.
const SESSION_HINT = "il-session";

export function hasSessionHint(): boolean {
  try {
    return localStorage.getItem(SESSION_HINT) === "1";
  } catch {
    return true; // storage blocked: try the refresh rather than lose a real session
  }
}

export function setSessionHint(signedIn: boolean): void {
  try {
    if (signedIn) localStorage.setItem(SESSION_HINT, "1");
    else localStorage.removeItem(SESSION_HINT);
  } catch {
    // storage blocked: the refresh is simply always tried
  }
}
