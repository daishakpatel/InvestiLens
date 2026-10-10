// Single source of UI types: the OpenAPI-generated client (UI-001). No hand-written duplicates —
// these aliases just give the generated `components["schemas"][...]` shapes readable names.
import type { components } from "./services/api";

type Schemas = components["schemas"];

export type Company = Schemas["Company"];
export type CompanyResponse = Schemas["CompanyResponse"];
export type CompanySearchResult = Schemas["CompanySearchResult"];
export type Freshness = Schemas["Freshness"];
export type FreshnessStatus = Freshness["freshness_status"];
export type FinancialsResponse = Schemas["FinancialsResponse"];
export type MetricSeries = Schemas["MetricSeries"];
export type MetricSeriesPoint = Schemas["MetricSeriesPoint"];
export type MetricResult = Schemas["MetricResult"];
export type MetricInput = Schemas["MetricInput"];
export type ValuationResponse = Schemas["ValuationResponse"];
export type PricesResponse = Schemas["PricesResponse"];
export type PricePoint = Schemas["PricePoint"];
export type FilingSummary = Schemas["FilingSummary"];
export type NewsResponse = Schemas["NewsResponse"];
export type NewsItem = Schemas["NewsItem"];
export type DataFreshnessResponse = Schemas["DataFreshnessResponse"];
export type TokenResponse = Schemas["TokenResponse"];
export type UserProfile = Schemas["UserProfile"];

// --- Phase 4d: research report, citations, chat ---
export type SourceDetail = Schemas["SourceDetail"];
export type SourceRecord = SourceDetail["source"];
export type ResearchReportEnvelope = Schemas["ResearchReportEnvelope"];
export type ResearchReport = Schemas["ResearchReport"];
export type ResearchClaim = Schemas["ResearchClaim"];
export type Risk = Schemas["Risk"];
export type Factor = Schemas["Factor"];
export type NewsItemSummary = Schemas["NewsItemSummary"];
export type ManagementTopicStatement = Schemas["ManagementTopicStatement"];
export type ResearchAccepted = Schemas["ResearchAccepted"];
export type JobState = Schemas["JobState"];
export type EvidenceLabel = NonNullable<ResearchClaim["confidence_label"]>;
export type ChatResponse = Schemas["ChatResponse"];
// Two `Citation` schemas now coexist in the contract (chat's and the citation pipeline's, exposed
// via /compare/commentary), so FastAPI fully-qualifies both names (Phase 6a).
export type ChatCitation = Schemas["app__schemas__chat__Citation"];
export type ChatSession = Schemas["ChatSession"];
export type ChatMessageDto = Schemas["ChatMessage"];
export type ToolTraceEntry = Schemas["ToolTraceEntry"];
export type FilingSectionsResponse = Schemas["FilingSectionsResponse"];
export type FilingSection = Schemas["FilingSection"];

// --- Phase 6a: company comparison & portfolio analysis (§37.1/§37.2) ---
export type ComparisonResponse = Schemas["ComparisonResponse"];
export type ComparisonCompany = Schemas["ComparisonCompany"];
export type ComparisonMetricRow = Schemas["ComparisonMetricRow"];
export type ComparisonCell = Schemas["ComparisonCell"];
export type PeerSuggestionsResponse = Schemas["PeerSuggestionsResponse"];
export type PeerSuggestion = Schemas["PeerSuggestion"];
export type VerifiedOutput = Schemas["VerifiedOutput"];
export type PortfolioAnalysis = Schemas["PortfolioAnalysis"];
export type NormalizedHolding = Schemas["NormalizedHolding"];
export type WeightedMetric = Schemas["WeightedMetric"];
export type SectorExposure = Schemas["SectorExposure"];
export type Concentration = Schemas["Concentration"];
export type RiskTheme = Schemas["RiskTheme"];
export type RiskStats = Schemas["RiskStats"];
export type HoldingData = Schemas["HoldingData"];
