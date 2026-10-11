import { Check } from "lucide-react";
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
    // Non-modal: the page behind stays in the accessibility tree and keeps its scrollbar, so
    // opening a menu neither hides content from assistive tech nor nudges the sticky bars.
    <RadixMenu.Root modal={false}>
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

/** A single-choice group inside a menu. Choosing an option leaves the menu open, so the effect
 *  (a theme change, say) is visible before the user moves on. */
export function MenuRadioGroup<T extends string>({
  label,
  value,
  onValueChange,
  options,
}: {
  label: string;
  value: T;
  onValueChange: (value: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <RadixMenu.RadioGroup
      aria-label={label}
      value={value}
      onValueChange={(next) => onValueChange(next as T)}
    >
      {options.map((option) => (
        <RadixMenu.RadioItem
          key={option.value}
          value={option.value}
          onSelect={(event) => event.preventDefault()}
          className="flex h-8 cursor-default items-center justify-between gap-2 rounded-[4px] px-2 text-text outline-none data-[highlighted]:bg-surface-2"
        >
          {option.label}
          <RadixMenu.ItemIndicator>
            <Check aria-hidden className="size-3.5 text-primary" />
          </RadixMenu.ItemIndicator>
        </RadixMenu.RadioItem>
      ))}
    </RadixMenu.RadioGroup>
  );
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <RadixMenu.Label className="px-2 py-1.5 text-caption text-subtle">{children}</RadixMenu.Label>;
}

export function MenuSeparator() {
  return <RadixMenu.Separator className="my-1 h-px bg-border" />;
}
