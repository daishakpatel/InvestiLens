// API base URL comes from the environment, never hard-coded, and carries no secret (UI-005).
// In dev the Vite proxy forwards same-origin `/api` to the backend; in prod set VITE_API_BASE_URL.
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export const DISCLAIMER =
  "InvestiLens provides data and AI-generated analysis for informational purposes only. " +
  "It is not investment advice.";
