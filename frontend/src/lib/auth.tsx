// Minimal auth context (Phase 4b frontend counterpart). The access token lives in memory
// (authStore); the httpOnly refresh cookie survives reloads, so we try a silent refresh on mount.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { apiRequest } from "./apiClient";
import { setAccessToken } from "./authStore";
import { parse } from "./schemas";
import type { UserProfile } from "../types";

interface AuthContextValue {
  user: UserProfile | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchProfile(): Promise<UserProfile> {
  const { data } = await apiRequest<unknown>("/auth/me");
  return parse.profile(data);
}

// One session restore per page load, shared by every caller. React StrictMode mounts effects
// twice in development; two refreshes carrying the same cookie rotate the token once and then
// present the old one, which the server rightly treats as token reuse (AUTH-002). The second
// mount must reuse the first request, not send its own.
let sessionRestore: Promise<string | null> | null = null;

function restoreSession(): Promise<string | null> {
  sessionRestore ??= apiRequest<unknown>("/auth/refresh", { method: "POST" }).then(
    ({ data }) => parse.token(data).access_token,
    () => null, // no valid refresh cookie: anonymous
  );
  return sessionRestore;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [ready, setReady] = useState(false);

  const applyToken = useCallback(async (token: string): Promise<void> => {
    setAccessToken(token);
    setUser(await fetchProfile());
  }, []);

  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      const { data } = await apiRequest<unknown>("/auth/login", {
        method: "POST",
        body: { email, password },
      });
      await applyToken(parse.token(data).access_token);
    },
    [applyToken],
  );

  const register = useCallback(
    async (email: string, password: string): Promise<void> => {
      await apiRequest<unknown>("/auth/register", { method: "POST", body: { email, password } });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await apiRequest<unknown>("/auth/logout", { method: "POST" });
    } catch {
      // Already logged out / network error — clear local state regardless.
    }
    setAccessToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const token = await restoreSession();
      if (cancelled) return;
      try {
        if (token) await applyToken(token);
      } catch {
        // The profile could not be loaded — stay anonymous.
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyToken]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, ready, login, register, logout }),
    [user, ready, login, register, logout],
  );
  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
