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
