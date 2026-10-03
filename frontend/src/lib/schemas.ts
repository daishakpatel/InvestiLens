// Runtime validation of API responses (scope item 1). The OpenAPI-generated types remain the
// compile-time contract (UI-001); these Zod schemas guard the *runtime* shape and surface drift
// loudly instead of letting a malformed payload corrupt the UI. Parsed values are returned as the
// generated types so components keep importing from `types.ts`.
import { z } from "zod";

import type {
  ChatResponse,
  CompanyResponse,
  CompanySearchResult,
  DataFreshnessResponse,
  FilingSectionsResponse,
  FilingSummary,
  FinancialsResponse,
  JobState,
  MetricResult,
  NewsResponse,
  PricesResponse,
  ResearchAccepted,
  ResearchReportEnvelope,
  SourceDetail,
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
  tier: z.number().nullish(),
  cluster_id: z.string().nullish(),
});

const news = z.object({
  ticker: z.string(),
  items: z.array(newsItem),
  next_cursor: z.string().nullish(),
  freshness,
});

const evidenceLabel = z.enum(["strongly_supported", "supported", "limited_evidence"]);

const claim = z.object({
  claim_id: z.string(),
  text: z.string(),
  source_ids: z.array(z.string()),
  confidence_label: evidenceLabel.nullish(),
});
const risk = z.object({
  category: z.string(),
  description: z.string(),
  source_ids: z.array(z.string()),
  change_status: z.string().nullish(),
  evidence_label: evidenceLabel.nullish(),
});
const factor = z.object({
  title: z.string(),
  claims: z.array(claim),
  counterpoint_source_ids: z.array(z.string()).default([]),
  monitoring_indicator: z.string().nullish(),
});
const newsSummary = z.object({
  news_id: z.string(),
  summary: z.string(),
  category: z.string(),
  source_ids: z.array(z.string()),
});
const mgmt = z.object({
  topic: z.string(),
  period: z.string(),
  text: z.string(),
  speaker: z.string().nullish(),
  source_ids: z.array(z.string()),
});
const report = z.object({
  executive_summary: z.array(claim),
  company_overview: z.array(claim),
  revenue_analysis: z.array(claim),
  profitability_analysis: z.array(claim),
  balance_sheet_analysis: z.array(claim),
  cash_flow_analysis: z.array(claim),
  valuation_analysis: z.array(claim),
  news_summary: z.array(newsSummary),
  risks: z.array(risk),
  management_commentary: z.array(mgmt),
  bull_factors: z.array(factor),
  bear_factors: z.array(factor),
  insufficient_evidence_sections: z.array(z.string()).default([]),
});
const researchEnvelope = z.object({
  research_id: z.string(),
  ticker: z.string(),
  generated_at: z.string().nullish(),
  model: z.string().nullish(),
  prompt_version: z.string().nullish(),
  data_version: z.string().nullish(),
  report,
});
const researchAccepted = z.object({
  research_id: z.string(),
  job_id: z.string(),
  status: z.enum(["queued", "processing", "done", "failed"]),
});
const jobState = z.object({
  status: z.enum(["queued", "processing", "done", "failed"]),
  progress: z.number(),
  stage: z.string().nullish(),
  stages: z
    .array(z.object({ name: z.string(), status: z.string(), message: z.string().nullish() }))
    .default([]),
});
const sourceDetail = z.object({
  source: z
    .object({ source_type: z.string(), source_id: z.string(), tier: z.number() })
    .passthrough(),
  text: z.string().nullish(),
  highlight_start: z.number().nullish(),
  highlight_end: z.number().nullish(),
  deep_link: z.string().nullish(),
  lineage: z.array(z.record(z.string(), z.string())).default([]),
});
const chatCitation = z.object({
  number: z.number(),
  source_id: z.string(),
  title: z.string().nullish(),
  section_path: z.array(z.string()).default([]),
  page: z.number().nullish(),
  tier: z.number().nullish(),
});
const chatResponse = z.object({
  answer: z.string(),
  citations: z.array(chatCitation).default([]),
  evidence_label: evidenceLabel.nullish(),
  abstained: z.boolean(),
  refused: z.boolean(),
  tool_trace: z.array(z.object({ tool: z.string(), latency_ms: z.number().nullish() })).default([]),
  suggested_questions: z.array(z.string()).default([]),
  session_id: z.string().nullish(),
  message_id: z.string().nullish(),
});
const filingSections = z.object({
  filing_id: z.string(),
  sections: z.array(
    z.object({
      section_path: z.array(z.string()),
      title: z.string(),
      char_start: z.number().nullish(),
      char_end: z.number().nullish(),
    }),
  ),
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
  researchEnvelope: (d: unknown): ResearchReportEnvelope =>
    researchEnvelope.parse(d) as ResearchReportEnvelope,
  researchAccepted: (d: unknown): ResearchAccepted =>
    researchAccepted.parse(d) as ResearchAccepted,
  jobState: (d: unknown): JobState => jobState.parse(d) as JobState,
  sourceDetail: (d: unknown): SourceDetail => sourceDetail.parse(d) as SourceDetail,
  chatResponse: (d: unknown): ChatResponse => chatResponse.parse(d) as ChatResponse,
  filingSections: (d: unknown): FilingSectionsResponse =>
    filingSections.parse(d) as FilingSectionsResponse,
};
