import { ChevronDown } from "lucide-react";
import type { SelectHTMLAttributes } from "react";

import { cn } from "./cn";
import { FIELD } from "./Input";

/** Native select (best on mobile and for assistive tech), skinned to match `Input`. */
export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className={cn("relative inline-flex", className)}>
      <select {...rest} className={cn(FIELD, "appearance-none pr-8")}>
        {children}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-subtle"
      />
    </span>
  );
}
