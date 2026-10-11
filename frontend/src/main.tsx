import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { ApiError } from "./lib/apiClient";
import { ApiStatusProvider } from "./lib/apiStatus";
import { AuthProvider } from "./lib/auth";
import { ThemeProvider } from "./lib/theme";
import "@fontsource-variable/inter";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // One retry for network and server errors. A 4xx is an answer (not found, not signed in),
      // so it is shown immediately instead of after a second identical request.
      retry: (failures, error) =>
        failures < 1 && !(error instanceof ApiError && error.status < 500),
      refetchOnWindowFocus: false,
    },
  },
});

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element in index.html");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ApiStatusProvider>
        <ThemeProvider>
          <AuthProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </AuthProvider>
        </ThemeProvider>
      </ApiStatusProvider>
    </QueryClientProvider>
  </StrictMode>,
);
