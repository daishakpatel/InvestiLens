import { Suspense } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../lib/auth";
import { Footer, ThemeToggle } from "./chrome";
import { LoadingState } from "./primitives";

export function AppShell() {
  const { user, logout } = useAuth();
  return (
    <div className="mx-auto flex min-h-full max-w-6xl flex-col px-4">
      <header className="flex items-center justify-between gap-4 py-4">
        <div className="flex items-center gap-4">
          <Link to="/" className="text-lg font-bold tracking-tight">
            InvestiLens
          </Link>
          <nav className="hidden items-center gap-3 text-sm sm:flex" aria-label="Primary">
            <NavLink
              to="/compare"
              className={({ isActive }) =>
                isActive ? "font-medium text-primary" : "text-muted hover:text-text"
              }
            >
              Compare
            </NavLink>
            <NavLink
              to="/portfolio"
              className={({ isActive }) =>
                isActive ? "font-medium text-primary" : "text-muted hover:text-text"
              }
            >
              Portfolio
            </NavLink>
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm">
          {user ? (
            <>
              <span className="hidden text-muted sm:inline">{user.email}</span>
              <button
                type="button"
                onClick={() => void logout()}
                className="rounded-md border border-border px-3 py-1 hover:bg-surface-2"
              >
                Sign out
              </button>
            </>
          ) : (
            <Link to="/login" className="rounded-md border border-border px-3 py-1 hover:bg-surface-2">
              Sign in
            </Link>
          )}
          <ThemeToggle />
        </div>
      </header>
      <main className="flex-1">
        <Suspense fallback={<LoadingState />}>
          <Outlet />
        </Suspense>
      </main>
      <Footer />
    </div>
  );
}
