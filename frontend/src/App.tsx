import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { Panel } from "./components/Panel";
import OverviewTab from "./pages/tabs/OverviewTab";
import ValuationTab from "./pages/tabs/ValuationTab";
import FilingsTab from "./pages/tabs/FilingsTab";
import NewsTab from "./pages/tabs/NewsTab";
import {
  ChatTab,
  ManagementTab,
  OwnershipTab,
  ResearchTab,
  RisksTab,
} from "./pages/tabs/PlaceholderTab";

// Route-level code splitting (UI-004). The Financials tab is split on its own so Recharts stays
// out of the initial bundle.
const HomePage = lazy(() => import("./pages/HomePage"));
const AuthPage = lazy(() => import("./pages/AuthPage"));
const CompanyDashboard = lazy(() => import("./pages/CompanyDashboard"));
const FinancialsTab = lazy(() => import("./pages/tabs/FinancialsTab"));

function NotFound() {
  return (
    <div className="py-10">
      <Panel title="Not found">
        <p className="p-6 text-sm text-muted">That page doesn’t exist.</p>
      </Panel>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="login" element={<AuthPage />} />
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
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
