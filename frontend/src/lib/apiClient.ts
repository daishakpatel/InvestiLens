// Thin typed fetch wrapper over the backend API.
// - Attaches the in-memory Bearer token (ADR-0005) and an X-Request-ID for correlation (API-007).
// - Parses RFC 7807 `application/problem+json` errors into a typed `ApiError` (API-001).
// - Exposes response headers so callers can read `X-Next-Cursor` pagination (API-002, ADR-0016).
// - Renews an expired access token from the refresh cookie and retries the request once (AUTH-002).
import { API_BASE_URL } from "./config";
import { getAccessToken, setAccessToken, setSessionHint } from "./authStore";
import { parse } from "./schemas";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string | undefined;
  readonly requestId: string | undefined;

  constructor(status: number, title: string, detail?: string, requestId?: string) {
    super(detail ?? title);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.requestId = requestId;
  }
}

export interface ApiResult<T> {
  data: T;
  headers: Headers;
}

function requestId(): string {
  return crypto.randomUUID();
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | undefined | null>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = `${API_BASE_URL}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

// One refresh at a time, shared by every request that finds its token expired. The refresh token
// rotates on use, so a second concurrent refresh would present a spent token, which the server
// treats as token reuse and answers by revoking the whole session (AUTH-002).
let refreshing: Promise<boolean> | null = null;

function refreshAccessToken(): Promise<boolean> {
  refreshing ??= fetch(`${API_BASE_URL}/auth/refresh`, { method: "POST", headers: { "X-Request-ID": requestId() } })
    .then(async (response) => {
      if (response.ok) {
        setAccessToken(parse.token(await response.json()).access_token);
        return true;
      }
      if (response.status === 401) {
        // The session itself has ended: sign out here so the UI shows it, not a stale account.
        setAccessToken(null);
        setSessionHint(false);
      }
      return false;
    }, () => false) // network failure: keep the session and let the original error surface
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

/** `fetch` with the in-memory Bearer token. A 401 on a signed-in request renews the token once
 *  and retries, so an access token expiring mid-session does not break the page. */
export async function authorizedFetch(
  url: string,
  init: RequestInit & { headers: Record<string, string> },
): Promise<Response> {
  const send = (token: string | null) =>
    fetch(url, { ...init, headers: token ? { ...init.headers, Authorization: `Bearer ${token}` } : init.headers });
  const token = getAccessToken();
  const response = await send(token);
  if (response.status !== 401 || !token) return response;
  // Another request may already have renewed it while this one was in flight.
  const renewed = getAccessToken() !== token || (await refreshAccessToken());
  return renewed ? send(getAccessToken()) : response;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<ApiResult<T>> {
  const headers: Record<string, string> = { "X-Request-ID": requestId() };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  const init: RequestInit & { headers: Record<string, string> } = { method: options.method ?? "GET", headers };
  if (options.body !== undefined) init.body = JSON.stringify(options.body);
  if (options.signal) init.signal = options.signal;

  const response = await authorizedFetch(buildUrl(path, options.query), init);

  if (!response.ok) throw await toApiError(response);

  const headersOut = response.headers;
  if (response.status === 204) return { data: undefined as T, headers: headersOut };
  return { data: (await response.json()) as T, headers: headersOut };
}

async function toApiError(response: Response): Promise<ApiError> {
  let title = response.statusText || "Request failed";
  let detail: string | undefined;
  let reqId: string | undefined = response.headers.get("X-Request-ID") ?? undefined;
  try {
    const body = (await response.json()) as {
      title?: string;
      detail?: string;
      request_id?: string;
    };
    if (body.title) title = body.title;
    if (body.detail) detail = body.detail;
    if (body.request_id) reqId = body.request_id;
  } catch {
    // Non-JSON error body; keep the status text.
  }
  return new ApiError(response.status, title, detail, reqId);
}
