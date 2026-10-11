import { DropdownMenu as RadixMenu } from "radix-ui";
import type { ReactNode } from "react";

export function DropdownMenu({
  trigger,
  children,
  align = "end",
}: {
  trigger: ReactNode; // a single button element
  children: ReactNode; // <MenuItem>s, <MenuLabel>s, <MenuSeparator>s
  align?: "start" | "center" | "end";
}) {
  return (
    <RadixMenu.Root>
      <RadixMenu.Trigger asChild>{trigger}</RadixMenu.Trigger>
      <RadixMenu.Portal>
        <RadixMenu.Content
          align={align}
          sideOffset={6}
          collisionPadding={8}
          className="z-50 min-w-48 rounded-surface border border-border-strong bg-surface p-1 text-sm shadow-float"
        >
          {children}
        </RadixMenu.Content>
      </RadixMenu.Portal>
    </RadixMenu.Root>
  );
}

export function MenuItem({
  onSelect,
  danger = false,
  children,
}: {
  onSelect: () => void;
  danger?: boolean;
  children: ReactNode;
}) {
  return (
    <RadixMenu.Item
      onSelect={onSelect}
      className={`flex h-8 cursor-default items-center gap-2 rounded-[4px] px-2 outline-none data-[highlighted]:bg-surface-2 ${
        danger ? "text-negative" : "text-text"
      }`}
    >
      {children}
    </RadixMenu.Item>
  );
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <RadixMenu.Label className="px-2 py-1.5 text-caption text-subtle">{children}</RadixMenu.Label>;
}

export function MenuSeparator() {
  return <RadixMenu.Separator className="my-1 h-px bg-border" />;
}
