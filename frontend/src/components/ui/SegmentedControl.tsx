import { ToggleGroup } from "radix-ui";

/** A single-choice row of text buttons: chart ranges, Annual / Quarterly. One is always selected. */
export function SegmentedControl<T extends string>({
  value,
  onValueChange,
  options,
  label,
}: {
  value: T;
  onValueChange: (value: T) => void;
  options: { value: T; label: string; disabled?: boolean }[];
  label: string;
}) {
  return (
    <ToggleGroup.Root
      type="single"
      value={value}
      aria-label={label}
      onValueChange={(next) => {
        if (next) onValueChange(next as T); // ignore the "deselect" Radix emits on re-click
      }}
      className="inline-flex items-center gap-0.5 rounded-control bg-surface-2 p-0.5"
    >
      {options.map((option) => (
        <ToggleGroup.Item
          key={option.value}
          value={option.value}
          disabled={option.disabled}
          className="h-7 rounded-[4px] px-2.5 text-label font-medium text-muted transition-colors hover:text-text disabled:opacity-40 data-[state=on]:bg-surface-3 data-[state=on]:text-text"
        >
          {option.label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
