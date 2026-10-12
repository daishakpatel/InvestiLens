import { useRef } from "react";

/** For a Radix layer opened by state rather than by a Radix Trigger: Radix then has nowhere to
 *  send focus on close. Remember what was focused when the layer opened and hand focus back. */
export function useReturnFocus() {
  const opener = useRef<Element | null>(null);
  return {
    onOpenAutoFocus: () => {
      opener.current = document.activeElement;
    },
    onCloseAutoFocus: (event: Event) => {
      if (opener.current instanceof HTMLElement) {
        event.preventDefault();
        opener.current.focus();
      }
    },
  };
}
