import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Placeholder shell; the real app (routing, React Query, pages) lands in Phase 4c.
const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element in index.html");

createRoot(root).render(
  <StrictMode>
    <h1>InvestiLens</h1>
  </StrictMode>,
);
