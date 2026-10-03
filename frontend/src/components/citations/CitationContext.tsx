import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { CitationModal } from "./CitationModal";

interface CitationContextValue {
  open: (sourceId: string) => void;
}

const CitationContext = createContext<CitationContextValue | null>(null);

/** Lets any citation chip (in a report card or a chat answer) open the shared source modal. */
export function CitationProvider({ children }: { children: ReactNode }) {
  const [sourceId, setSourceId] = useState<string | null>(null);
  const open = useCallback((id: string) => setSourceId(id), []);
  const value = useMemo<CitationContextValue>(() => ({ open }), [open]);
  return (
    <CitationContext value={value}>
      {children}
      <CitationModal sourceId={sourceId} onClose={() => setSourceId(null)} onOpenSource={open} />
    </CitationContext>
  );
}

export function useCitations(): CitationContextValue {
  const ctx = useContext(CitationContext);
  if (!ctx) throw new Error("useCitations must be used within CitationProvider");
  return ctx;
}
