import type { ReactNode } from "react";

import { cn } from "./cn";

/** The page column: 1240 px max, 24 px gutters (16 px on phones). The shell's bars span the full
 *  viewport and put one of these inside; every page wraps its content in one. */
export function Container({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("mx-auto w-full max-w-[1240px] px-4 md:px-6", className)}>{children}</div>;
}
