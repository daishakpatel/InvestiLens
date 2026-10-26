import { lazy, Suspense } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { Footer } from "./chrome";
import { DemoBanner } from "./DemoBanner";
import { PageSkeleton } from "./PageSkeleton";
import { SearchTrigger } from "./SearchTrigger";
import { Container } from "./ui/Container";

// The menu's positioning and focus machinery (Radix) is the heaviest thing in the bar and is not
// needed to paint it, so it arrives in its own chunk; the bar reserves its 36 px meanwhile.
const AccountMenu = lazy(() => import("./AccountMenu"));

const NAV = [
  { to: "/compare", label: "Compare" },
  { to: "/portfolio", label: "Portfolio" },
  { to: "/theses", label: "Theses" },
];

export function Wordmark() {
  return (
    <Link to="/" className="text-title font-semibold tracking-tight text-text">
      Assay Desk
    </Link>
  );
}

function TopBar() {
  const { pathname } = useLocation();
  // Home's hero is the search; a second field in the bar would compete with it.
  const showSearchField = pathname !== "/";
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/80 backdrop-blur-md print:hidden">
      {/* Three columns from md up, so the search field is centred on the page rather than in
          whatever space the wordmark and links leave. */}
      <Container className="flex h-14 items-center justify-between gap-3 md:grid md:grid-cols-[1fr_minmax(0,24rem)_1fr] md:gap-6">
        <div>
          <Wordmark />
        </div>
        <div className="hidden md:block">{showSearchField && <SearchTrigger variant="bar" />}</div>
        <div className="flex items-center justify-end gap-1 md:gap-6">
          <nav aria-label="Primary" className="hidden items-center gap-6 md:flex">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors ${
                    isActive ? "text-text" : "text-muted hover:text-text"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="md:hidden">
            <SearchTrigger variant="icon" />
          </div>
          <Suspense fallback={<div aria-hidden className="size-9" />}>
            <AccountMenu />
          </Suspense>
        </div>
      </Container>
    </header>
  );
}

/** The global frame: a full-width sticky bar, the page, and the disclaimer. Pages own their
 *  width by wrapping content in `Container`, so a page can also run something edge to edge. */
export function AppShell() {
  return (
    <div className="flex min-h-full flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-control focus:bg-surface focus:px-3 focus:py-2 focus:text-sm"
      >
        Skip to content
      </a>
      <DemoBanner />
      <TopBar />
      {/* At least a screenful: the footer then starts below the fold on every page, instead of
          being visible under a loading state and pushed away when the content arrives. */}
      <main id="main" className="min-h-svh flex-1">
        <Suspense fallback={<PageSkeleton />}>
          <Outlet />
        </Suspense>
      </main>
      <Footer />
    </div>
  );
}
