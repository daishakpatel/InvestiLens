import { ArrowLeft, X } from "lucide-react";
import { Dialog } from "radix-ui";
import { useEffect, useRef } from "react";
import type { ReactNode, RefObject } from "react";

import { IconButton } from "../ui/Button";

/** How the one side panel is presented:
 *  - `docked`: part of the page layout, beside the content (the assistant on wide screens).
 *  - `overlay`: floats over the right edge without blocking the page, so the reader can keep
 *    scrolling and open another citation.
 *  - `sheet`: full screen and modal, for phones. */
export type PanelMode = "docked" | "overlay" | "sheet";

const FRAME: Record<PanelMode, string> = {
  docked:
    "sticky top-14 flex h-[calc(100dvh-3.5rem)] w-[440px] shrink-0 flex-col self-start border-l border-border bg-bg animate-fade-in print:hidden",
  overlay:
    "fixed bottom-0 right-0 top-14 z-30 flex w-[440px] max-w-[calc(100vw-3rem)] flex-col border-l border-border-strong bg-surface shadow-float animate-slide-in print:hidden",
  sheet: "fixed inset-0 z-50 flex flex-col bg-bg animate-slide-in print:hidden",
};

interface SidePanelProps {
  mode: PanelMode;
  title: string;
  /** Changes whenever the panel shows something different, so focus can follow the content. */
  viewKey: string;
  onClose: () => void;
  onBack?: (() => void) | undefined;
  backLabel?: string;
  /** Where focus goes when the panel opens; defaults to its title. */
  initialFocus?: RefObject<HTMLElement | null> | undefined;
  /** Where focus returns when the panel closes: whatever opened it. */
  returnFocus: RefObject<HTMLElement | null>;
  children: ReactNode;
}

/** The single side panel. Behaviour comes from Radix Dialog (focus handling, Escape, and, as a
 *  sheet, focus trapping and scroll lock); as a docked or overlay panel it is non-modal: nothing
 *  outside it is blocked, and clicking outside does not dismiss it. */
export function SidePanel({
  mode,
  title,
  viewKey,
  onClose,
  onBack,
  backLabel = "Back",
  initialFocus,
  returnFocus,
  children,
}: SidePanelProps) {
  const contentRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const firstView = useRef(viewKey);

  // When the panel swaps what it shows (chat → a source, one source → another), move focus to
  // the title so keyboard and screen-reader users land on the new content.
  useEffect(() => {
    if (firstView.current === viewKey) return;
    firstView.current = viewKey;
    titleRef.current?.focus();
  }, [viewKey]);

  const content = (
    <Dialog.Content
      ref={contentRef}
      aria-describedby={undefined}
      className={FRAME[mode]}
      onOpenAutoFocus={(event) => {
        event.preventDefault();
        (initialFocus?.current ?? titleRef.current)?.focus();
      }}
      onCloseAutoFocus={(event) => {
        event.preventDefault();
        const opener = returnFocus.current;
        if (opener && document.contains(opener)) opener.focus();
      }}
      // Non-modal: the page stays usable, so interacting with it must not close the panel.
      onInteractOutside={(event) => event.preventDefault()}
      onEscapeKeyDown={(event) => {
        // A docked panel is a fixture of the page: Escape pressed elsewhere is not for it.
        const inside = contentRef.current?.contains(document.activeElement) ?? false;
        if (mode === "docked" && !inside) return event.preventDefault();
        if (onBack) {
          event.preventDefault(); // one level at a time: back first, close second
          onBack();
        }
      }}
    >
      <header className="flex h-14 shrink-0 items-center gap-1 border-b border-border px-3">
        {onBack && (
          <IconButton label={backLabel} size="sm" onClick={onBack}>
            <ArrowLeft aria-hidden className="size-4" />
          </IconButton>
        )}
        <Dialog.Title
          ref={titleRef}
          tabIndex={-1}
          className="min-w-0 flex-1 truncate px-1 text-sm font-medium outline-none"
        >
          {title}
        </Dialog.Title>
        <IconButton label="Close panel" size="sm" onClick={onClose}>
          <X aria-hidden className="size-4" />
        </IconButton>
      </header>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </Dialog.Content>
  );

  return (
    <Dialog.Root open modal={mode === "sheet"} onOpenChange={(open) => !open && onClose()}>
      {mode === "sheet" ? <Dialog.Portal>{content}</Dialog.Portal> : content}
    </Dialog.Root>
  );
}
