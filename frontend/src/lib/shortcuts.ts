// Global keyboard shortcuts for the command palette (UI-003: keyboard-first search).

interface KeyLike {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
  altKey: boolean;
}

/** ⌘K / Ctrl+K always; a bare "/" only when the user is not typing into a field. */
export function isPaletteShortcut(event: KeyLike, typing: boolean): boolean {
  if (event.altKey) return false;
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") return true;
  return event.key === "/" && !event.metaKey && !event.ctrlKey && !typing;
}

/** True when keystrokes are going into a text field, so "/" must be left alone. */
export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

const IS_MAC =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent);
export const PALETTE_HINT = IS_MAC ? "⌘K" : "Ctrl K";
