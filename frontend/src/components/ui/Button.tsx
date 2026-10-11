import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "./cn";
import { Spinner } from "./Skeleton";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const BASE =
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-control font-medium " +
  "transition-colors disabled:pointer-events-none disabled:opacity-50";

const VARIANT: Record<Variant, string> = {
  primary: "bg-primary text-primary-contrast hover:bg-primary/90 active:bg-primary/80",
  secondary:
    "border border-border-strong text-text hover:bg-surface-2 active:bg-surface-3",
  ghost: "text-muted hover:bg-surface-2 hover:text-text active:bg-surface-3",
  danger: "border border-negative/40 text-negative hover:bg-negative/10 active:bg-negative/20",
};

const SIZE: Record<Size, string> = { sm: "h-7 px-2.5 text-label", md: "h-9 px-3.5 text-sm" };
const ICON_SIZE: Record<Size, string> = { sm: "size-7", md: "size-9" };

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(BASE, VARIANT[variant], SIZE[size], className)}
    >
      {loading && <Spinner label="Working" />}
      {children}
    </button>
  );
}

interface IconButtonProps extends Omit<ButtonProps, "children" | "loading"> {
  label: string; // required: an icon alone has no accessible name
  children: ReactNode;
}

export function IconButton({
  label,
  variant = "ghost",
  size = "md",
  className,
  children,
  ...rest
}: IconButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      aria-label={label}
      title={label}
      className={cn(BASE, VARIANT[variant], ICON_SIZE[size], className)}
    >
      {children}
    </button>
  );
}
