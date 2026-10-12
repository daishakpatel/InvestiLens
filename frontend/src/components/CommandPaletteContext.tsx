import { createContext, lazy, Suspense, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { isEditableTarget, isPaletteShortcut } from "../lib/shortcuts";

// cmdk and the palette UI load on demand (UI-004): nothing here is in the entry bundle except the
// key listener. The chunk is fetched when the browser is idle, so the first ⌘K is still instant.
const loadPalette = () => import("./CommandPalette");
const CommandPalette = lazy(loadPalette);

/** Use the palette to choose a company for the page, instead of navigating to it. */
export interface PickRequest {
  title: string; // the prompt, for example "Add a company to compare"
  exclude: readonly string[]; // tickers already chosen
  onPick: (company: { ticker: string; name: string }) => void;
}

interface CommandPaletteContextValue {
  open: () => void;
  pick: (request: PickRequest) => void;
}

const CommandPaletteContext = createContext<CommandPaletteContextValue | null>(null);

/** Owns the global search palette: ⌘K / Ctrl+K / "/" from anywhere, or `open()` from a trigger. */
export function CommandPaletteProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [everOpened, setEverOpened] = useState(false);
  const [request, setRequest] = useState<PickRequest | null>(null);

  const open = useCallback(() => {
    setRequest(null);
    setEverOpened(true);
    setIsOpen(true);
  }, []);
  const pick = useCallback((next: PickRequest) => {
    setRequest(next);
    setEverOpened(true);
    setIsOpen(true);
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!isPaletteShortcut(event, isEditableTarget(event.target))) return;
      event.preventDefault();
      setRequest(null); // the shortcut is always the global search
      setEverOpened(true);
      setIsOpen((current) => !current);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    const id = window.setTimeout(() => void loadPalette(), 1500);
    return () => window.clearTimeout(id);
  }, []);

  const value = useMemo<CommandPaletteContextValue>(() => ({ open, pick }), [open, pick]);
  return (
    <CommandPaletteContext value={value}>
      {children}
      {everOpened && (
        <Suspense fallback={null}>
          <CommandPalette open={isOpen} onOpenChange={setIsOpen} pick={request} />
        </Suspense>
      )}
    </CommandPaletteContext>
  );
}

export function useCommandPalette(): CommandPaletteContextValue {
  const ctx = useContext(CommandPaletteContext);
  if (!ctx) throw new Error("useCommandPalette must be used within CommandPaletteProvider");
  return ctx;
}
