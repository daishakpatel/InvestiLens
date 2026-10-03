import type { SourceRecord } from "../../types";

/** A human label for a source record, by type (powers the citation modal + reference list). */
export function sourceTitle(source: SourceRecord): string {
  switch (source.source_type) {
    case "text_chunk":
      return source.section_path.length ? source.section_path.join(" › ") : "Filing excerpt";
    case "table_chunk":
      return `Table ${source.table_id}`;
    case "xbrl_fact":
      return `${source.concept_tag} (${source.accession_number})`;
    case "derived_metric":
      return `${source.formula_id}${source.period ? ` · ${source.period}` : ""}`;
    case "news_item":
      return source.publisher ? `${source.publisher} article` : "News article";
    case "earnings_release":
    case "transcript":
      return source.source_type === "transcript" ? "Earnings call transcript" : "Earnings release";
    default:
      return "Source";
  }
}

export function sourceKindLabel(source: SourceRecord): string {
  const map: Record<SourceRecord["source_type"], string> = {
    text_chunk: "Filing text",
    table_chunk: "Filing table",
    xbrl_fact: "XBRL fact",
    derived_metric: "Derived metric",
    news_item: "News",
    earnings_release: "Earnings release",
    transcript: "Transcript",
  };
  return map[source.source_type];
}
