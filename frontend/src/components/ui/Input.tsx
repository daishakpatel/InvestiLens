import type { InputHTMLAttributes, Ref } from "react";

import { cn } from "./cn";

export const FIELD =
  "h-9 w-full rounded-control border border-border-strong bg-surface-2 px-3 text-sm text-text " +
  "transition-colors placeholder:text-subtle hover:border-subtle " +
  "focus:border-primary focus:outline-none focus-visible:outline-none " +
  "focus:ring-2 focus:ring-primary/30 disabled:opacity-50 aria-invalid:border-negative";

export function Input({
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { ref?: Ref<HTMLInputElement> }) {
  return <input {...rest} className={cn(FIELD, className)} />;
}
