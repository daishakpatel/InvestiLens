import { useSyncExternalStore } from "react";

/** Subscribe to a CSS media query. Use for behaviour that CSS alone cannot express (for example
 *  which items a menu contains); prefer responsive utility classes for pure styling. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => true,
  );
}

/** The shell's mobile breakpoint: below this the top bar collapses its links into the menu. */
export const DESKTOP_QUERY = "(min-width: 768px)";
