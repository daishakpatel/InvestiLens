import { Popover as RadixPopover } from "radix-ui";
import type { ReactNode } from "react";

export function Popover({
  trigger,
  children,
  align = "start",
  onOpenChange,
}: {
  trigger: ReactNode; // a single button element
  children: ReactNode;
  align?: "start" | "center" | "end";
  onOpenChange?: (open: boolean) => void;
}) {
  return (
    <RadixPopover.Root {...(onOpenChange ? { onOpenChange } : {})}>
      <RadixPopover.Trigger asChild>{trigger}</RadixPopover.Trigger>
      <RadixPopover.Portal>
        <RadixPopover.Content
          align={align}
          sideOffset={6}
          collisionPadding={8}
          className="z-50 w-72 data-[state=open]:animate-fade-in rounded-surface border border-border-strong bg-surface p-4 text-sm shadow-float"
        >
          {children}
        </RadixPopover.Content>
      </RadixPopover.Portal>
    </RadixPopover.Root>
  );
}
