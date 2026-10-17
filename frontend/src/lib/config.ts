// API base URL comes from the environment, never hard-coded, and carries no secret (UI-005).
// In dev the Vite proxy forwards same-origin `/api` to the backend; in prod set VITE_API_BASE_URL.
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export const DISCLAIMER =
  "Assay Desk provides data and AI-generated analysis for informational purposes only. " +
  "It is not investment advice.";

// Companies offered before the user has searched for anything (home page and command palette).
// Limited to the tickers every environment seeds (`make seed`), so none of them is a dead link.
export const POPULAR_COMPANIES: { ticker: string; name: string }[] = [
  { ticker: "NVDA", name: "NVIDIA" },
  { ticker: "AAPL", name: "Apple" },
  { ticker: "JPM", name: "JPMorgan Chase" },
];

// Mirrors the backend's `password_min_length` (AUTH-001); the server remains the authority.
export const PASSWORD_MIN_LENGTH = 12;
