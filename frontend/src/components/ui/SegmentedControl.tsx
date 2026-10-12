import { ToggleGroup } from "radix-ui";

import { Tooltip } from "./Tooltip";

const ITEM = "h-7 rounded-[4px] px-2.5 text-label font-medium transition-colors pointer-coarse:min-w-10";

/** A single-choice row of text buttons: chart ranges, Annual / Quarterly. One is always selected.
 *  An option that cannot be chosen stays visible and says why (`hint`), rather than vanishing or
 *  leading to an empty screen. */
export function SegmentedControl<T extends string>({
  value,
  onValueChange,
  options,
  label,
}: {
  value: T;
  onValueChange: (value: T) => void;
  options: { value: T; label: string; disabled?: boolean; hint?: string }[];
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
      {options.map((option) =>
        option.disabled && option.hint ? (
          // Not a real button: a disabled button swallows hover and focus, so its reason could
          // never be shown. The tooltip's own trigger is focusable instead.
          <Tooltip key={option.value} label={option.hint} plain>
            <span aria-disabled="true" className={`${ITEM} flex items-center text-subtle opacity-60`}>
              {option.label}
            </span>
          </Tooltip>
        ) : (
          <ToggleGroup.Item
            key={option.value}
            value={option.value}
            disabled={option.disabled}
            className={`${ITEM} text-muted hover:text-text disabled:opacity-40 data-[state=on]:bg-surface-3 data-[state=on]:text-text`}
          >
            {option.label}
          </ToggleGroup.Item>
        ),
      )}
    </ToggleGroup.Root>
  );
}
