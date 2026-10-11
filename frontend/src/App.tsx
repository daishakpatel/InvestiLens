import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { Section } from "./components/ui/Section";
import OverviewTab from "./pages/tabs/OverviewTab";
import ValuationTab from "./pages/tabs/ValuationTab";
import FilingsTab from "./pages/tabs/FilingsTab";
import NewsTab from "./pages/tabs/NewsTab";
import { OwnershipTab } from "./pages/tabs/PlaceholderTab";

// Route-level code splitting (UI-004). Recharts (Financials) and the report/chat views each get
// their own chunk, out of the initial bundle.
const HomePage = lazy(() => import("./pages/HomePage"));
const AuthPage = lazy(() => import("./pages/AuthPage"));
const CompanyDashboard = lazy(() => import("./pages/CompanyDashboard"));
const FinancialsTab = lazy(() => import("./pages/tabs/FinancialsTab"));
const ResearchTab = lazy(() => import("./pages/tabs/ResearchTab"));
const RisksTab = lazy(() => import("./pages/tabs/RisksTab"));
const ManagementTab = lazy(() => import("./pages/tabs/ManagementTab"));
const ChatTab = lazy(() => import("./pages/tabs/ChatTab"));
const ComparePage = lazy(() => import("./pages/ComparePage"));
const PortfolioPage = lazy(() => import("./pages/PortfolioPage"));
// Design-system review surface: dev server only, so it never ships in the production bundle.
const UiGallery = import.meta.env.DEV ? lazy(() => import("./pages/UiGallery")) : null;

function NotFound() {
  return (
    <div className="py-10">
      <Section title="Not found">
        <p className="p-6 text-sm text-muted">That page doesn’t exist.</p>
      </Section>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="login" element={<AuthPage />} />
        <Route path="compare" element={<ComparePage />} />
        <Route path="portfolio" element={<PortfolioPage />} />
        <Route path="company/:ticker" element={<CompanyDashboard />}>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<OverviewTab />} />
          <Route path="financials" element={<FinancialsTab />} />
          <Route path="valuation" element={<ValuationTab />} />
          <Route path="filings" element={<FilingsTab />} />
          <Route path="news" element={<NewsTab />} />
          <Route path="research" element={<ResearchTab />} />
          <Route path="risks" element={<RisksTab />} />
          <Route path="management" element={<ManagementTab />} />
          <Route path="ownership" element={<OwnershipTab />} />
          <Route path="chat" element={<ChatTab />} />
        </Route>
        {UiGallery && <Route path="_ui" element={<UiGallery />} />}
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
