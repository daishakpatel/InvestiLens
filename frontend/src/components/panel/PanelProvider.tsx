import { createContext, lazy, Suspense, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";

import { DESKTOP_QUERY, useMediaQuery } from "../../lib/useMediaQuery";
import { useConversation } from "../assistant/useConversation";
import { CitationContext } from "../citations/CitationContext";
import type { CitationContextValue, Evidence } from "../citations/CitationContext";
import { SourceView } from "../citations/SourceView";
import { StatementsView } from "../citations/StatementsView";
import { LoadingState } from "../ui/States";
import { SidePanel } from "./SidePanel";
import type { PanelMode } from "./SidePanel";

// The assistant's interface arrives the first time it is opened (UI-004); most visits to a
// company page never open it. The conversation state stays here, so it survives tab changes.
const Assistant = lazy(() => import("../assistant/Assistant").then((module) => ({ default: module.Assistant })));

/** From this width the assistant docks beside the page instead of floating over it. */
const DOCK_QUERY = "(min-width: 1440px)";

interface AssistantContextValue {
  isOpen: boolean;
  open: () => void;
  /** Open the assistant and ask a question straight away (the `?ask=` deep link). */
  ask: (question: string) => void;
  toggle: () => void;
}

const AssistantContext = createContext<AssistantContextValue | null>(null);

export function useAssistant(): AssistantContextValue {
  const ctx = useContext(AssistantContext);
  if (!ctx) throw new Error("useAssistant must be used within PanelProvider");
  return ctx;
}

const focused = () => (document.activeElement instanceof HTMLElement ? document.activeElement : null);

/** Owns everything that can open beside a page: the evidence behind a citation and, on a company
 *  page (`assistantFor`), the assistant. Both live in one state and render through one
 *  `SidePanel`, so two side panels can never be open together: evidence wanted while the
 *  assistant is open is shown inside it, with a way back to the conversation.
 *
 *  Give this a `key` per company: the conversation and any open evidence belong to one company
 *  and must not follow the reader to another. */
export function PanelProvider({
  assistantFor,
  children,
}: {
  assistantFor?: string; // a ticker; without one the panel only ever shows evidence
  children: ReactNode;
}) {
  const ticker = assistantFor ?? "";
  const [assistantOpen, setAssistantOpen] = useState(false);
  // What the panel is showing as evidence, innermost last (statements → one of their sources).
  const [stack, setStack] = useState<Evidence[]>([]);
  const conversation = useConversation(ticker);
  const opener = useRef<HTMLElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const desktop = useMediaQuery(DESKTOP_QUERY);
  const wide = useMediaQuery(DOCK_QUERY);

  // Evidence opened from the page belongs to what the page was showing. When the reader moves on
  // (another tab, another filing, the browser's Back on a phone) it closes rather than linger
  // over content it has nothing to do with. The assistant, and anything open inside it, stays.
  const { pathname, search } = useLocation();
  const place = pathname + search;
  const [seenPlace, setSeenPlace] = useState(place);
  if (seenPlace !== place) {
    setSeenPlace(place);
    if (!assistantOpen) setStack([]);
  }

  const top = stack.at(-1) ?? null;
  const visible = assistantOpen || top !== null;
  const mode: PanelMode = !desktop ? "sheet" : assistantOpen && wide ? "docked" : "overlay";
  const activeSourceId = top?.kind === "source" ? top.sourceId : null;

  // Citations in the page replace whatever evidence is showing, and note what was clicked so
  // focus can return there when the panel closes.
  const pageCitations = useMemo<CitationContextValue>(
    () => ({
      open: (sourceId) => {
        opener.current = focused();
        setStack([{ kind: "source", sourceId }]);
      },
      openStatements: (view) => {
        opener.current = focused();
        setStack([view]);
      },
      activeSourceId,
    }),
    [activeSourceId],
  );

  // Citations inside the panel (in an answer, in a list of statements) go one level deeper, so
  // Back returns to where the reader was.
  const panelCitations = useMemo<CitationContextValue>(
    () => ({
      open: (sourceId) => setStack((current) => [...current, { kind: "source", sourceId }]),
      openStatements: (view) => setStack((current) => [...current, view]),
      activeSourceId,
    }),
    [activeSourceId],
  );

  // `open` and `toggle` keep one identity for the life of the provider. `/company/:ticker/chat`
  // calls `open` from an effect; were it to change whenever the panel closed, that effect would
  // run again and reopen a panel the reader had just closed.
  const open = useCallback(() => {
    opener.current ??= focused();
    setAssistantOpen(true);
  }, []);
  const toggle = useCallback(() => {
    opener.current = focused();
    setStack([]);
    setAssistantOpen((isOpen) => !isOpen);
  }, []);
  const { ask: askConversation } = conversation;
  const ask = useCallback(
    (question: string) => {
      open();
      askConversation(question);
    },
    [open, askConversation],
  );
  const assistant = useMemo<AssistantContextValue>(
    () => ({ isOpen: assistantOpen, open, ask, toggle }),
    [assistantOpen, open, ask, toggle],
  );

  const close = useCallback(() => {
    setAssistantOpen(false);
    setStack([]);
  }, []);
  const back = useCallback(() => setStack((current) => current.slice(0, -1)), []);
  // Back exists whenever closing the current view would reveal something: a previous evidence
  // view, or the conversation underneath.
  const canGoBack = stack.length > 1 || (stack.length === 1 && assistantOpen);

  const panel = visible && (
    <SidePanel
      mode={mode}
      title={
        top?.kind === "source" ? "Source" : top?.kind === "statements" ? "Counted statements" : `Ask about ${ticker}`
      }
      viewKey={top ? (top.kind === "source" ? `source:${top.sourceId}` : `statements:${top.title}`) : "assistant"}
      onClose={close}
      onBack={canGoBack ? back : undefined}
      backLabel={stack.length > 1 ? "Back" : "Back to conversation"}
      initialFocus={top ? undefined : composerRef}
      returnFocus={opener}
    >
      <CitationContext value={panelCitations}>
        {/* The conversation stays mounted beneath an open source, keeping its scroll position
            and any half-written question. */}
        {assistantOpen && (
          <div className={top ? "hidden" : "flex min-h-0 flex-1 flex-col"}>
            <Suspense fallback={<LoadingState label="Opening the assistant" />}>
              <Assistant ticker={ticker} conversation={conversation} composerRef={composerRef} />
            </Suspense>
          </div>
        )}
        {top?.kind === "source" && <SourceView key={top.sourceId} sourceId={top.sourceId} />}
        {top?.kind === "statements" && <StatementsView view={top} />}
      </CitationContext>
    </SidePanel>
  );

  return (
    <CitationContext value={pageCitations}>
      <AssistantContext value={assistant}>
        <div className="flex items-start">
          <div className="min-w-0 flex-1">{children}</div>
          {mode === "docked" && panel}
        </div>
        {mode !== "docked" && panel}
      </AssistantContext>
    </CitationContext>
  );
}
