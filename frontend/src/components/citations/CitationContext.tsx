import { createContext, useContext } from "react";

/** A counted sentence and the source it came from (management language tracking, §37.5). */
export interface CountedStatement {
  source_id: string;
  text: string;
  mentions: number;
}

/** What the evidence panel can show. */
export type Evidence =
  | { kind: "source"; sourceId: string }
  | { kind: "statements"; title: string; subtitle: string; statements: CountedStatement[] };

export interface CitationContextValue {
  /** Show a source in the side panel (CIT-006). */
  open: (sourceId: string) => void;
  /** Show a list of counted statements, each of which opens its own source. */
  openStatements: (view: Extract<Evidence, { kind: "statements" }>) => void;
  /** The source on show, so its chip can be highlighted in the text. */
  activeSourceId: string | null;
}

export const CitationContext = createContext<CitationContextValue | null>(null);

export function useCitations(): CitationContextValue {
  const ctx = useContext(CitationContext);
  if (!ctx) throw new Error("useCitations must be used within a company page (CompanyPanels)");
  return ctx;
}
