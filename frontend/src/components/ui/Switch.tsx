import { Switch as RadixSwitch } from "radix-ui";
import type { ReactNode } from "react";

export function Switch({
  checked,
  onCheckedChange,
  disabled,
  children,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    // Top-aligned and never shrunk, so a long multi-line label can't squash the track.
    <label className="inline-flex cursor-pointer items-start gap-2 text-sm text-text">
      <RadixSwitch.Root
        checked={checked}
        disabled={disabled}
        onCheckedChange={onCheckedChange}
        className="relative h-5 w-9 shrink-0 rounded-full bg-surface-3 transition-colors data-[state=checked]:bg-primary disabled:opacity-50"
      >
        <RadixSwitch.Thumb className="block size-4 translate-x-0.5 rounded-full bg-text transition-transform duration-(--duration-slow) data-[state=checked]:translate-x-[18px] data-[state=checked]:bg-primary-contrast" />
      </RadixSwitch.Root>
      {children}
    </label>
  );
}
