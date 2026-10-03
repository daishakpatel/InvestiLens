// React Query hooks over the typed API client. Each query validates its payload with Zod
// (schemas.ts) before it reaches a component, so a malformed response fails fast and visibly.
import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";

import { apiRequest } from "./apiClient";
import { parse } from "./schemas";
import type {
  CompanyResponse,
  CompanySearchResult,
  DataFreshnessResponse,
  FilingSummary,
  FinancialsResponse,
  MetricResult,
  NewsResponse,
  PricesResponse,
  ValuationResponse,
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
