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
export type ChatCitation = Schemas["Citation"];
export type ChatSession = Schemas["ChatSession"];
export type ChatMessageDto = Schemas["ChatMessage"];
export type ToolTraceEntry = Schemas["ToolTraceEntry"];
export type FilingSectionsResponse = Schemas["FilingSectionsResponse"];
export type FilingSection = Schemas["FilingSection"];
