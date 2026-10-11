import { X } from "lucide-react";
import { Dialog as RadixDialog } from "radix-ui";
import { useRef } from "react";
import type { ReactNode } from "react";

import { IconButton } from "./Button";

interface LayerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
}

const OVERLAY = "fixed inset-0 z-40 bg-black/60";

/** These layers are opened by state, not by a Radix Trigger, so Radix has nowhere to send focus
 *  on close. Remember what was focused when the layer opened and hand focus back to it. */
export function useReturnFocus() {
  const opener = useRef<Element | null>(null);
  return {
    onOpenAutoFocus: () => {
      opener.current = document.activeElement;
    },
    onCloseAutoFocus: (event: Event) => {
      if (opener.current instanceof HTMLElement) {
        event.preventDefault();
        opener.current.focus();
      }
    },
  };
}

function Header({ title, description }: { title: string; description?: string | undefined }) {
  return (
    <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
      <div>
        <RadixDialog.Title className="text-title font-medium">{title}</RadixDialog.Title>
        {description && (
          <RadixDialog.Description className="mt-0.5 text-label text-muted">
            {description}
          </RadixDialog.Description>
        )}
      </div>
      <RadixDialog.Close asChild>
        <IconButton label="Close" size="sm">
          <X aria-hidden className="size-4" />
        </IconButton>
      </RadixDialog.Close>
    </header>
  );
}

/** Centred modal. Focus is trapped and returned to the opener on close (Radix). */
export function Dialog({ open, onOpenChange, title, description, children }: LayerProps) {
  const returnFocus = useReturnFocus();
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={OVERLAY} />
        <RadixDialog.Content
          {...returnFocus}
          {...(description ? {} : { "aria-describedby": undefined })}
          className="fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 flex-col rounded-surface border border-border-strong bg-surface shadow-float"
        >
          <Header title={title} description={description} />
          <div className="overflow-auto p-5">{children}</div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

/** Right-side sheet: evidence and detail open beside the page instead of over it. Full width on
 *  phones. */
export function Drawer({ open, onOpenChange, title, description, children }: LayerProps) {
  const returnFocus = useReturnFocus();
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={OVERLAY} />
        <RadixDialog.Content
          {...returnFocus}
          {...(description ? {} : { "aria-describedby": undefined })}
          className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-border-strong bg-surface shadow-float sm:w-[420px]"
        >
          <Header title={title} description={description} />
          <div className="flex-1 overflow-auto p-5">{children}</div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
