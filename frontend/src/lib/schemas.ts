// Runtime validation of API responses (scope item 1). The OpenAPI-generated types remain the
// compile-time contract (UI-001); these Zod schemas guard the *runtime* shape and surface drift
// loudly instead of letting a malformed payload corrupt the UI. Parsed values are returned as the
// generated types so components keep importing from `types.ts`.
import { z } from "zod";

import type {
  CompanyResponse,
  CompanySearchResult,
  DataFreshnessResponse,
  FilingSummary,
  FinancialsResponse,
  MetricResult,
  NewsResponse,
  PricesResponse,
  TokenResponse,
  UserProfile,
  ValuationResponse,
} from "../types";

const freshness = z.object({
  as_of: z.string(),
  source: z.string(),
  freshness_status: z.enum(["fresh", "stale", "failed"]),
});

const company = z.object({
  ticker: z.string(),
  cik: z.string(),
  name: z.string(),
  exchange: z.string().nullish(),
  sector: z.string().nullish(),
  industry: z.string().nullish(),
  fiscal_year_end: z.string().nullish(),
});

const searchResult = z.object({
  ticker: z.string(),
  cik: z.string(),
  name: z.string(),
  exchange: z.string().nullish(),
  score: z.number(),
});

const metricInput = z.object({
  name: z.string(),
  value: z.string().nullish(),
  source_id: z.string().nullish(),
});

const metricResult = z.object({
  value: z.string().nullable(),
  unit: z.string(),
  inputs: z.array(metricInput),
  formula_id: z.string(),
  formula_version: z.string().nullish(),
  warnings: z.array(z.string()),
});

const metricPoint = z.object({
  period: z.string(),
  period_end: z.string().nullish(),
  value: z.string().nullable(),
  unit: z.string(),
});

const financials = z.object({
  ticker: z.string(),
  period_type: z.string(),
  series: z.array(z.object({ metric_name: z.string(), points: z.array(metricPoint) })),
  freshness,
});

const valuation = z.object({
  ticker: z.string(),
  metrics: z.array(metricResult),
  freshness,
});

const pricePoint = z.object({
  date: z.string(),
  open: z.string().nullish(),
  high: z.string().nullish(),
  low: z.string().nullish(),
  close: z.string().nullish(),
  adj_close: z.string().nullish(),
  volume: z.number().nullish(),
});

const prices = z.object({
  ticker: z.string(),
  unit: z.string(),
  interval: z.string(),
  points: z.array(pricePoint),
  freshness,
});

const filing = z.object({
  filing_id: z.string(),
  filing_type: z.string(),
  filing_date: z.string().nullish(),
  period_end: z.string().nullish(),
  accession_number: z.string(),
  primary_document_url: z.string().nullish(),
});

const newsItem = z.object({
  news_id: z.string(),
  title: z.string(),
  description: z.string().nullish(),
  url: z.string().nullish(),
  publisher: z.string().nullish(),
  published_at: z.string().nullish(),
  category: z.string().nullish(),
  relevance_score: z.number().nullish(),
});

const news = z.object({
  ticker: z.string(),
  items: z.array(newsItem),
  next_cursor: z.string().nullish(),
  freshness,
});

const dataFreshness = z.object({ ticker: z.string(), sources: z.array(freshness) });
const token = z.object({ access_token: z.string(), token_type: z.string(), expires_in: z.number() });
const profile = z.object({
  id: z.string(),
  email: z.string(),
  role: z.string(),
  email_verified: z.boolean(),
});

export const parse = {
  companyResponse: (d: unknown): CompanyResponse =>
    z.object({ company, freshness }).parse(d) as CompanyResponse,
  searchResults: (d: unknown): CompanySearchResult[] =>
    z.array(searchResult).parse(d) as CompanySearchResult[],
  financials: (d: unknown): FinancialsResponse => financials.parse(d) as FinancialsResponse,
  valuation: (d: unknown): ValuationResponse => valuation.parse(d) as ValuationResponse,
  prices: (d: unknown): PricesResponse => prices.parse(d) as PricesResponse,
  filings: (d: unknown): FilingSummary[] => z.array(filing).parse(d) as FilingSummary[],
  news: (d: unknown): NewsResponse => news.parse(d) as NewsResponse,
  metricResult: (d: unknown): MetricResult => metricResult.parse(d) as MetricResult,
  dataFreshness: (d: unknown): DataFreshnessResponse =>
    dataFreshness.parse(d) as DataFreshnessResponse,
  token: (d: unknown): TokenResponse => token.parse(d) as TokenResponse,
  profile: (d: unknown): UserProfile => profile.parse(d) as UserProfile,
};
