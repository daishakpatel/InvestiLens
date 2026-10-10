// React Query hooks over the typed API client. Each query validates its payload with Zod
// (schemas.ts) before it reaches a component, so a malformed response fails fast and visibly.
import { useMutation, useQuery } from "@tanstack/react-query";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";

import { apiRequest } from "./apiClient";
import { parse } from "./schemas";
import type {
  CompanyResponse,
  CompanySearchResult,
  ComparisonResponse,
  DataFreshnessResponse,
  FilingSectionsResponse,
  FilingSummary,
  FinancialsResponse,
  JobState,
  MetricResult,
  NewsResponse,
  PeerSuggestionsResponse,
  PortfolioAnalysis,
  PricesResponse,
  ResearchAccepted,
  ResearchReportEnvelope,
  SourceDetail,
  ValuationResponse,
  VerifiedOutput,
} from "../types";

const MINUTE = 60_000;

export function useCompanySearch(query: string): UseQueryResult<CompanySearchResult[]> {
  const q = query.trim();
  return useQuery({
    queryKey: ["search", q],
    enabled: q.length >= 1,
    staleTime: 5 * MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>("/companies/search", { query: { q }, signal });
      return parse.searchResults(data);
    },
  });
}

export function useCompany(ticker: string): UseQueryResult<CompanyResponse> {
  return useQuery({
    queryKey: ["company", ticker],
    staleTime: 5 * MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/companies/${ticker}`, { signal });
      return parse.companyResponse(data);
    },
  });
}

export function useFinancials(
  ticker: string,
  metrics: string[],
  periodType: string,
): UseQueryResult<FinancialsResponse> {
  const metricsParam = metrics.join(",");
  return useQuery({
    queryKey: ["financials", ticker, metricsParam, periodType],
    staleTime: 5 * MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/companies/${ticker}/financials`, {
        query: { metrics: metricsParam, period_type: periodType },
        signal,
      });
      return parse.financials(data);
    },
  });
}

export function useValuation(ticker: string): UseQueryResult<ValuationResponse> {
  return useQuery({
    queryKey: ["valuation", ticker],
    staleTime: 5 * MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/companies/${ticker}/valuation`, { signal });
      return parse.valuation(data);
    },
  });
}

export function usePrices(ticker: string): UseQueryResult<PricesResponse> {
  return useQuery({
    queryKey: ["prices", ticker],
    staleTime: 5 * MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/companies/${ticker}/prices`, { signal });
      return parse.prices(data);
    },
  });
}

export function useFilings(ticker: string): UseQueryResult<FilingSummary[]> {
  return useQuery({
    queryKey: ["filings", ticker],
    staleTime: 5 * MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/companies/${ticker}/filings`, {
        query: { limit: 25 },
        signal,
      });
      return parse.filings(data);
    },
  });
}

export function useNews(ticker: string): UseQueryResult<NewsResponse> {
  return useQuery({
    queryKey: ["news", ticker],
    staleTime: 5 * MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/companies/${ticker}/news`, {
        query: { limit: 25 },
        signal,
      });
      return parse.news(data);
    },
  });
}

export function useDataFreshness(ticker: string): UseQueryResult<DataFreshnessResponse> {
  return useQuery({
    queryKey: ["freshness", ticker],
    staleTime: MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/meta/data-freshness/${ticker}`, { signal });
      return parse.dataFreshness(data);
    },
  });
}

export function useSource(sourceId: string | null): UseQueryResult<SourceDetail> {
  return useQuery({
    queryKey: ["source", sourceId],
    enabled: sourceId !== null,
    staleTime: 10 * MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/sources/${encodeURIComponent(sourceId ?? "")}`, {
        signal,
      });
      return parse.sourceDetail(data);
    },
  });
}

export function useLatestResearch(ticker: string): UseQueryResult<ResearchReportEnvelope> {
  return useQuery({
    queryKey: ["research-latest", ticker],
    retry: false, // a 404 ("no report yet") is an expected state, not a transient error
    staleTime: MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/companies/${ticker}/research/latest`, { signal });
      return parse.researchEnvelope(data);
    },
  });
}

export function useResearchReport(researchId: string | null): UseQueryResult<ResearchReportEnvelope> {
  return useQuery({
    queryKey: ["research", researchId],
    enabled: researchId !== null,
    staleTime: MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/research/${researchId}`, { signal });
      return parse.researchEnvelope(data);
    },
  });
}

export function useFilingSections(filingId: string | null): UseQueryResult<FilingSectionsResponse> {
  return useQuery({
    queryKey: ["filing-sections", filingId],
    enabled: filingId !== null,
    staleTime: 10 * MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/filings/${filingId}/sections`, { signal });
      return parse.filingSections(data);
    },
  });
}

export function useStartResearch(): UseMutationResult<ResearchAccepted, Error, string> {
  return useMutation({
    mutationFn: async (ticker: string) => {
      const { data } = await apiRequest<unknown>("/research", {
        method: "POST",
        body: { ticker },
      });
      return parse.researchAccepted(data);
    },
  });
}

export function useJob(jobId: string | null): UseQueryResult<JobState> {
  return useQuery({
    queryKey: ["job", jobId],
    enabled: jobId !== null,
    // Poll while the job is still running; stop once terminal.
    refetchInterval: (query) => {
      const status = (query.state.data as JobState | undefined)?.status;
      return status === "done" || status === "failed" ? false : 2000;
    },
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/research/jobs/${jobId}`, { signal });
      return parse.jobState(data);
    },
  });
}

export function useMetricLineage(
  ticker: string,
  metricName: string,
  period: string,
  enabled: boolean,
): UseQueryResult<MetricResult> {
  return useQuery({
    queryKey: ["lineage", ticker, metricName, period],
    enabled,
    staleTime: 10 * MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(
        `/companies/${ticker}/metrics/${metricName}/lineage`,
        { query: { period }, signal },
      );
      return parse.metricResult(data);
    },
  });
}

// --- Phase 6a: comparison & portfolio (§37.1/§37.2) ---

export function useComparison(
  tickers: string[],
  metrics: string[],
): UseQueryResult<ComparisonResponse> {
  const tickersParam = tickers.join(",");
  const metricsParam = metrics.join(",");
  return useQuery({
    queryKey: ["compare", tickersParam, metricsParam],
    enabled: tickers.length >= 2,
    staleTime: 5 * MINUTE,
    queryFn: async ({ signal }) => {
      const query: Record<string, string> = { tickers: tickersParam };
      if (metricsParam) query.metrics = metricsParam;
      const { data } = await apiRequest<unknown>("/compare", { query, signal });
      return parse.comparison(data);
    },
  });
}

export function usePeers(ticker: string): UseQueryResult<PeerSuggestionsResponse> {
  return useQuery({
    queryKey: ["peers", ticker],
    enabled: ticker.length > 0,
    staleTime: 10 * MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/compare/peers/${ticker}`, { signal });
      return parse.peers(data);
    },
  });
}

export function useComparisonCommentary(): UseMutationResult<
  VerifiedOutput,
  Error,
  { tickers: string[]; metrics?: string[]; period?: string }
> {
  return useMutation({
    mutationFn: async (body) => {
      const { data } = await apiRequest<unknown>("/compare/commentary", {
        method: "POST",
        body,
      });
      return parse.verifiedOutput(data);
    },
  });
}

export function usePortfolioAnalysis(): UseMutationResult<
  PortfolioAnalysis,
  Error,
  { ticker: string; weight: number }[]
> {
  return useMutation({
    mutationFn: async (holdings) => {
      const { data } = await apiRequest<unknown>("/portfolio/analyze", {
        method: "POST",
        body: { holdings: holdings.map((h) => ({ ticker: h.ticker, weight: String(h.weight) })) },
      });
      return parse.portfolio(data);
    },
  });
}
