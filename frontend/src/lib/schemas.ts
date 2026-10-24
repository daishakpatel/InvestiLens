// Runtime validation of API responses (scope item 1). The OpenAPI-generated types remain the
// compile-time contract (UI-001); these Zod schemas guard the *runtime* shape and surface drift
// loudly instead of letting a malformed payload corrupt the UI. Parsed values are returned as the
// generated types so components keep importing from `types.ts`.
import { z } from "zod";

import type {
  Alert,
  AlertEventType,
  AppNotification,
  ChatResponse,
  CompanyResponse,
  CompanySearchResult,
  ComparisonResponse,
  DataFreshnessResponse,
  EarningsResponse,
  FilingDiffResponse,
  FilingSectionsResponse,
  FilingSummary,
  FinancialsResponse,
  JobState,
  ManagementLanguageResponse,
  MetricResult,
  MetricsCoverageResponse,
  EarningsQualityResponse,
  FootnoteFactsResponse,
  GovernanceHistoryResponse,
  GovernanceResponse,
  NotesResponse,
  RedFlagsResponse,
  NewsResponse,
  PeerSuggestionsResponse,
  PortfolioAnalysis,
  PricesResponse,
  ResearchAccepted,
  ResearchReportEnvelope,
  SourceDetail,
  TokenResponse,
  UserProfile,
  ValuationResponse,
  VerifiedOutput,
  Watchlist,
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
  source_id: z.string().nullish(),
  formula: z.string().nullish(),
});

const financials = z.object({
  ticker: z.string(),
  period_type: z.string(),
  series: z.array(z.object({ metric_name: z.string(), points: z.array(metricPoint) })),
  freshness,
});

// Phase 7b (FR-QT-010): which quarters / TTM windows each metric has, and why the rest are missing.
const metricsCoverage = z.object({
  ticker: z.string(),
  quarters: z.array(z.string()),
  metrics: z.array(
    z.object({
      metric_name: z.string(),
      applicable: z.boolean(),
      present: z.array(z.string()),
      missing: z.array(z.object({ period: z.string(), reason: z.string() })),
    }),
  ),
  freshness,
});

// Phase 7d (FR-EQ-009): earnings-quality measures per fiscal year, each with status and inputs.
const qualityPoint = z.object({
  period: z.string(),
  fiscal_year: z.number(),
  value: z.string().nullable(),
  status: z.enum(["ok", "insufficient_data", "not_applicable"]),
  band: z.string().nullish(),
  reason: z.string().nullish(),
  reason_text: z.string().nullish(),
  missing: z.array(z.string()),
  source_id: z.string().nullish(),
  formula_id: z.string().nullish(),
  inputs: z.array(metricInput),
  details: z.record(z.string(), z.unknown()),
});

const earningsQuality = z.object({
  ticker: z.string(),
  fiscal_years: z.array(z.number()),
  measures: z.array(
    z.object({
      metric_name: z.string(),
      label: z.string(),
      unit: z.string(),
      explanation: z.string(),
      caveat: z.string().nullish(),
      points: z.array(qualityPoint),
      latest_ttm: qualityPoint.nullish(),
      peer_percentile: z.string().nullish(),
      peer_count: z.number(),
    }),
  ),
  peers: z.array(z.string()),
  notes: z.array(z.string()),
  freshness,
});

// Phase 7e (FR-RF-009/010): reported filing events; an empty list still says when it was scanned.
const redFlags = z.object({
  items: z.array(
    z.object({
      source_id: z.string(),
      ticker: z.string(),
      rule_key: z.string(),
      label: z.string(),
      severity: z.enum(["info", "warning", "critical"]),
      explanation: z.string(),
      rule_source: z.string(),
      event_date: z.string().nullable(),
      snippet: z.string(),
      filing: z.object({
        id: z.number(),
        filing_type: z.string(),
        accession_number: z.string(),
        filing_date: z.string().nullish(),
        url: z.string().nullish(),
      }),
      details: z.record(z.string(), z.unknown()),
    }),
  ),
  last_scanned_at: z.string().nullable(),
  taxonomy_version: z.string(),
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

// Phase 7f (FR-FN-011): a filing's notes with their cached AI summaries, and the XBRL facts.
const noteBullet = z.object({ text: z.string(), quote: z.string(), paragraph_id: z.string() });
const notes = z.object({
  company_ticker: z.string(),
  filing,
  taxonomy: z.string(),
  low_confidence: z.boolean(),
  summarised_categories: z.array(z.string()),
  notes: z.array(
    z.object({
      note_id: z.string(),
      number: z.number(),
      title: z.string(),
      category: z.string(),
      also_matches: z.array(z.string()).default([]),
      paragraph_ids: z.array(z.string()),
      summary: z
        .object({
          status: z.enum(["summarised", "abstained", "pending"]),
          bullets: z.array(noteBullet).default([]),
          model: z.string().nullish(),
        })
        .nullish(),
    }),
  ),
});

const footnoteFacts = z.object({
  company_ticker: z.string(),
  fiscal_year: z.number().nullable(),
  categories: z.array(
    z.object({
      category: z.string(),
      facts: z.array(
        z.object({
          metric: z.string(),
          label: z.string(),
          value: z.string().nullable(),
          unit: z.string(),
          period: z.string(),
          source_id: z.string(),
          is_derived: z.boolean(),
          formula: z.string().nullish(),
          from_inline_xbrl: z.boolean().default(false),
        }),
      ),
      gaps: z.array(
        z.object({ metric: z.string(), label: z.string(), period: z.string(), reason: z.string() }),
      ),
    }),
  ),
});

// Phase 7g (FR-GV-011): proxy governance. Missing parts are nulls with a reason.
const decimal = z.string();
const governance = z.object({
  company_ticker: z.string(),
  fiscal_year: z.number().nullable(),
  fiscal_year_source: z.string().nullable(),
  filing: filing.nullable(),
  available_years: z.array(z.number()),
  proxies_ingested: z.number(),
  reason: z.string().nullish(),
  coverage: z.record(z.string(), z.boolean()).default({}),
  facts: z
    .object({
      status: z.enum(["extracted", "pending", "no_sections"]),
      model: z.string().nullish(),
      fields: z
        .array(
          z.object({
            name: z.string(),
            label: z.string(),
            value: z.union([decimal, z.boolean(), z.array(z.string())]).nullish(),
            quote: z.string().nullish(),
            paragraph_id: z.string().nullish(),
          }),
        )
        .default([]),
      independence_ratio: decimal.nullish(),
      reason: z.string().nullish(),
    })
    .nullish(),
  compensation: z
    .object({
      rows: z
        .array(
          z.object({
            person: z.string(),
            role: z.enum(["peo", "pfo", "neo"]),
            fiscal_year: z.number(),
            components: z.record(z.string(), decimal),
            total: decimal,
            source_id: z.string(),
          }),
        )
        .default([]),
      rejected_rows: z.number().default(0),
      reason: z.string().nullish(),
    })
    .nullish(),
  pay_vs_performance: z
    .object({
      points: z
        .array(
          z.object({
            fiscal_year: z.number(),
            values: z.record(z.string(), decimal),
            source_ids: z.record(z.string(), z.string()),
          }),
        )
        .default([]),
      company_selected_measure: z.string().nullish(),
      reason: z.string().nullish(),
    })
    .nullish(),
  pay_ratio: z
    .object({
      ratio: decimal.nullish(),
      median_pay: decimal.nullish(),
      ceo_total: decimal.nullish(),
      source_id: z.string().nullish(),
      reason: z.string().nullish(),
    })
    .nullish(),
});

const governanceHistory = z.object({
  company_ticker: z.string(),
  points: z.array(
    z.object({
      fiscal_year: z.number(),
      ceo_total_pay: decimal.nullish(),
      ceo_total_pay_source: z.string().nullish(),
      ceo_total_pay_source_id: z.string().nullish(),
      independence_ratio: decimal.nullish(),
    }),
  ),
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

// --- Phase 6a: comparison & portfolio (Decimals arrive as strings) ---
const verifiedClaim = z
  .object({ text: z.string(), status: z.string(), citation_numbers: z.array(z.number()).default([]) })
  .passthrough();
const verifiedCitation = z
  .object({ number: z.number(), source_id: z.string(), tier: z.number().nullish() })
  .passthrough();
const verifiedOutput = z.object({
  rendered_text: z.string(),
  claims: z.array(verifiedClaim).default([]),
  citations: z.array(verifiedCitation).default([]),
  sufficient: z.boolean().default(true),
});

const comparisonCell = z.object({
  ticker: z.string(),
  result: metricResult,
  percentile: z.string().nullish(),
});
const comparisonCompany = z.object({
  ticker: z.string(),
  name: z.string(),
  sic_code: z.string().nullish(),
  sector: z.string().nullish(),
  fiscal_year_end: z.string().nullish(),
  fiscal_period: z.string().nullish(),
  calendar_year: z.number().nullish(),
  period_end: z.string().nullish(),
});
const comparisonResponse = z.object({
  calendar_year: z.number().nullish(),
  companies: z.array(comparisonCompany).default([]),
  metrics: z
    .array(
      z.object({
        metric_name: z.string(),
        unit: z.string(),
        cells: z.array(comparisonCell).default([]),
      }),
    )
    .default([]),
  commentary: verifiedOutput.nullish(),
  notes: z.array(z.string()).default([]),
  disclaimer: z.string(),
});

const peerSuggestion = z.object({
  ticker: z.string(),
  name: z.string(),
  sic_code: z.string().nullish(),
  sector: z.string().nullish(),
  industry: z.string().nullish(),
  market_cap: metricResult.nullish(),
  reason: z.string(),
});
const peerSuggestions = z.object({
  target: z.string(),
  peers: z.array(peerSuggestion).default([]),
  notes: z.array(z.string()).default([]),
});

const weightedMetric = z.object({
  metric_name: z.string(),
  unit: z.string(),
  value: z.string().nullable(),
  coverage: z.string(),
  warnings: z.array(z.string()).default([]),
});
const riskTheme = z.object({
  category: z.string(),
  holding_count: z.number(),
  portfolio_weight: z.string(),
  contributions: z
    .array(
      z.object({
        ticker: z.string(),
        description: z.string(),
        source_ids: z.array(z.string()).default([]),
      }),
    )
    .default([]),
});
const riskStats = z.object({
  window_start: z.string().nullish(),
  window_end: z.string().nullish(),
  holding_volatility: z
    .array(
      z.object({
        ticker: z.string(),
        annualized_volatility: z.string().nullish(),
        observations: z.number(),
      }),
    )
    .default([]),
  correlation: z
    .array(z.object({ ticker: z.string(), correlations: z.record(z.string(), z.string()) }))
    .default([]),
  portfolio_volatility: z.string().nullish(),
  notes: z.array(z.string()).default([]),
});
const portfolioAnalysis = z.object({
  holdings: z
    .array(
      z.object({
        ticker: z.string(),
        name: z.string(),
        weight: z.string(),
        sector: z.string().nullish(),
      }),
    )
    .default([]),
  weighted_metrics: z.array(weightedMetric).default([]),
  sector_exposure: z.array(z.object({ sector: z.string(), weight: z.string() })).default([]),
  concentration: z
    .object({
      hhi: z.string(),
      effective_holdings: z.string(),
      top_holding: z.string().nullish(),
      top_weight: z.string().nullish(),
    })
    .nullish(),
  risk_stats: riskStats.nullish(),
  risk_themes: z.array(riskTheme).default([]),
  holdings_data: z
    .array(
      z.object({
        ticker: z.string(),
        sector: z.string().nullish(),
        metrics: z.record(z.string(), metricResult).default({}),
        annualized_volatility: z.string().nullish(),
      }),
    )
    .default([]),
  notes: z.array(z.string()).default([]),
  disclaimer: z.string(),
});

// --- Phase 6b: filing diff, earnings reaction, management language ---
const changeStatus = z.enum(["unchanged", "reworded", "new", "removed"]);
const diffPassage = z.object({
  heading: z.string(),
  source_ids: z.array(z.string()),
  text: z.string().nullish(),
});
const filingDiff = z.object({
  company_ticker: z.string(),
  filing,
  against: filing,
  similarity_method: z.enum(["lexical", "embedding"]),
  caption_detection: z.enum(["emphasis", "heuristic"]),
  counts: z.object({
    unchanged: z.number(),
    reworded: z.number(),
    new: z.number(),
    removed: z.number(),
  }),
  items: z.array(
    z.object({
      section: z.string(),
      kind: z.enum(["risk_factor", "section"]),
      status: changeStatus,
      decided_by: z.enum(["heading", "similarity", "llm", "threshold"]),
      similarity: z.number().nullish(),
      old: diffPassage.nullish(),
      new: diffPassage.nullish(),
      word_diff: z
        .array(z.object({ op: z.enum(["equal", "insert", "delete"]), text: z.string() }))
        .nullish(),
    }),
  ),
});
const earnings = z.object({
  ticker: z.string(),
  method: z.string(),
  events: z.array(
    z.object({
      filing,
      pre_date: z.string().nullish(),
      pre_close: z.string().nullish(),
      post_date: z.string().nullish(),
      post_close: z.string().nullish(),
      move: z.string().nullish(),
      reason: z.string().nullish(),
    }),
  ),
});
const languageSeries = z.object({
  topic: z.string(),
  label: z.string(),
  points: z.array(
    z.object({
      filing_id: z.string(),
      count: z.number(),
      per_1k_words: z.number(),
      flag: z.enum(["first_appearance", "disappeared"]).nullish(),
      statements: z.array(
        z.object({ source_id: z.string(), text: z.string(), mentions: z.number() }),
      ),
    }),
  ),
});
const managementLanguage = z.object({
  ticker: z.string(),
  taxonomy_version: z.string(),
  hedging_lexicon_version: z.string(),
  method: z.string(),
  periods: z.array(
    z.object({
      filing_id: z.string(),
      filing_type: z.string(),
      filing_date: z.string().nullish(),
      period_end: z.string().nullish(),
      word_count: z.number(),
    }),
  ),
  topics: z.array(languageSeries),
  hedging: languageSeries,
});

const channel = z.enum(["email", "in_app"]);
const watchlist = z.object({
  id: z.string(),
  name: z.string(),
  items: z.array(z.object({ ticker: z.string() })).default([]),
});
const alert = z.object({
  id: z.string(),
  event_type: z.string(),
  ticker: z.string().nullish(),
  params: z.record(z.string(), z.unknown()).default({}),
  channels: z.array(channel).default(["in_app"]),
  enabled: z.boolean().default(true),
  supported: z.boolean().default(true),
  created_at: z.string(),
});
const alertEventType = z.object({
  key: z.string(),
  label: z.string(),
  description: z.string(),
  params_schema: z.record(z.string(), z.unknown()),
  default_enabled: z.boolean().default(true),
});
const notification = z.object({
  id: z.string(),
  title: z.string(),
  body: z.string().nullish(),
  channel,
  company_id: z.string().nullish(),
  ticker: z.string().nullish(),
  event_type: z.string().nullish(),
  severity: z.enum(["info", "warning", "critical"]).nullish(),
  source_ids: z.array(z.string()).default([]),
  read: z.boolean().default(false),
  created_at: z.string(),
});

export const parse = {
  watchlist: (d: unknown): Watchlist => watchlist.parse(d) as Watchlist,
  watchlists: (d: unknown): Watchlist[] => z.array(watchlist).parse(d) as Watchlist[],
  alert: (d: unknown): Alert => alert.parse(d) as Alert,
  alerts: (d: unknown): Alert[] => z.array(alert).parse(d) as Alert[],
  alertEventTypes: (d: unknown): AlertEventType[] =>
    z.array(alertEventType).parse(d) as AlertEventType[],
  notifications: (d: unknown): AppNotification[] =>
    z.array(notification).parse(d) as AppNotification[],
  filingDiff: (d: unknown): FilingDiffResponse => filingDiff.parse(d) as FilingDiffResponse,
  earnings: (d: unknown): EarningsResponse => earnings.parse(d) as EarningsResponse,
  managementLanguage: (d: unknown): ManagementLanguageResponse =>
    managementLanguage.parse(d) as ManagementLanguageResponse,
  companyResponse: (d: unknown): CompanyResponse =>
    z.object({ company, freshness }).parse(d) as CompanyResponse,
  searchResults: (d: unknown): CompanySearchResult[] =>
    z.array(searchResult).parse(d) as CompanySearchResult[],
  financials: (d: unknown): FinancialsResponse => financials.parse(d) as FinancialsResponse,
  metricsCoverage: (d: unknown): MetricsCoverageResponse =>
    metricsCoverage.parse(d) as MetricsCoverageResponse,
  valuation: (d: unknown): ValuationResponse => valuation.parse(d) as ValuationResponse,
  redFlags: (d: unknown): RedFlagsResponse => redFlags.parse(d) as RedFlagsResponse,
  notes: (d: unknown): NotesResponse => notes.parse(d) as NotesResponse,
  governance: (d: unknown): GovernanceResponse => governance.parse(d) as GovernanceResponse,
  governanceHistory: (d: unknown): GovernanceHistoryResponse =>
    governanceHistory.parse(d) as GovernanceHistoryResponse,
  footnoteFacts: (d: unknown): FootnoteFactsResponse =>
    footnoteFacts.parse(d) as FootnoteFactsResponse,
  earningsQuality: (d: unknown): EarningsQualityResponse =>
    earningsQuality.parse(d) as EarningsQualityResponse,
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
  comparison: (d: unknown): ComparisonResponse => comparisonResponse.parse(d) as ComparisonResponse,
  peers: (d: unknown): PeerSuggestionsResponse =>
    peerSuggestions.parse(d) as PeerSuggestionsResponse,
  verifiedOutput: (d: unknown): VerifiedOutput => verifiedOutput.parse(d) as VerifiedOutput,
  portfolio: (d: unknown): PortfolioAnalysis => portfolioAnalysis.parse(d) as PortfolioAnalysis,
};
