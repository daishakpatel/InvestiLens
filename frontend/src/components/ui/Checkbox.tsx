import { Check } from "lucide-react";
import { Checkbox as RadixCheckbox } from "radix-ui";
import type { ReactNode } from "react";

export function Checkbox({
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
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-text">
      <RadixCheckbox.Root
        checked={checked}
        disabled={disabled}
        onCheckedChange={(value) => onCheckedChange(value === true)}
        className="flex size-4 items-center justify-center rounded-[4px] border border-border-strong bg-surface-2 transition-colors hover:border-subtle data-[state=checked]:border-primary data-[state=checked]:bg-primary disabled:opacity-50"
      >
        <RadixCheckbox.Indicator>
          <Check aria-hidden className="size-3 text-primary-contrast" strokeWidth={3} />
        </RadixCheckbox.Indicator>
      </RadixCheckbox.Root>
      {children}
    </label>
  );
}
