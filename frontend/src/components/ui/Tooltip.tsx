import { Tooltip as RadixTooltip } from "radix-ui";
import type { ReactNode } from "react";

/** Hover and keyboard-focus tooltip (UI-003). Wraps non-interactive content in a focusable span;
 *  pass `asChild` when the child is already a button or link. */
export function Tooltip({
  label,
  children,
  asChild = false,
  plain = false,
  focusable = true,
  onOpenChange,
}: {
  label: ReactNode;
  children: ReactNode;
  asChild?: boolean;
  plain?: boolean; // no dotted underline (the trigger is already visually distinct)
  focusable?: boolean; // false keeps it out of the tab order (dense grids offer another route)
  onOpenChange?: (open: boolean) => void; // e.g. to fetch the content only when first shown
}) {
  return (
    <RadixTooltip.Provider delayDuration={150}>
      <RadixTooltip.Root {...(onOpenChange ? { onOpenChange } : {})}>
        <RadixTooltip.Trigger asChild>
          {asChild ? (
            children
          ) : (
            <span
              tabIndex={focusable ? 0 : -1}
              className={`cursor-help rounded-[2px] ${
                plain ? "" : "underline decoration-border-strong decoration-dotted underline-offset-4"
              }`}
            >
              {children}
            </span>
          )}
        </RadixTooltip.Trigger>
        <RadixTooltip.Portal>
          <RadixTooltip.Content
            sideOffset={6}
            collisionPadding={8}
            className="z-50 max-w-xs data-[state=delayed-open]:animate-fade-in rounded-control border border-border-strong bg-surface px-2.5 py-2 text-caption text-text shadow-float"
          >
            {label}
          </RadixTooltip.Content>
        </RadixTooltip.Portal>
      </RadixTooltip.Root>
    </RadixTooltip.Provider>
  );
}
