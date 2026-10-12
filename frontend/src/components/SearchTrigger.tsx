import { Search } from "lucide-react";

import { PALETTE_HINT } from "../lib/shortcuts";
import { useCommandPalette } from "./CommandPaletteContext";
import { Button, IconButton } from "./ui/Button";

function Kbd() {
  return (
    <kbd className="rounded-[4px] border border-border-strong px-1.5 py-0.5 font-sans text-caption text-subtle">
      {PALETTE_HINT}
    </kbd>
  );
}

/** Opens the command palette. It looks like a search field because that is what people look for,
 *  but it is a button: all typing happens in the palette, so there is one search to learn. */
export function SearchTrigger({ variant }: { variant: "bar" | "hero" | "icon" | "button" }) {
  const { open } = useCommandPalette();

  if (variant === "icon") {
    return (
      <IconButton label="Search companies" onClick={open}>
        <Search aria-hidden className="size-4" />
      </IconButton>
    );
  }
  if (variant === "button") {
    return (
      <Button variant="primary" onClick={open}>
        <Search aria-hidden className="size-4" />
        Search companies
      </Button>
    );
  }

  const hero = variant === "hero";
  return (
    <button
      type="button"
      onClick={open}
      aria-keyshortcuts="Meta+K Control+K /"
      className={`flex w-full items-center gap-3 border border-border-strong bg-surface-2 text-left text-subtle transition-colors hover:border-subtle hover:text-muted ${
        hero ? "h-14 rounded-surface px-5 text-body" : "h-9 rounded-control px-3 text-sm"
      }`}
    >
      <Search aria-hidden className={hero ? "size-5 shrink-0" : "size-4 shrink-0"} />
      <span className="min-w-0 flex-1 truncate">Search a company or ticker</span>
      {/* The shortcut is announced through aria-keyshortcuts; the button's name is its text. */}
      <span aria-hidden className="hidden sm:block">
        <Kbd />
      </span>
    </button>
  );
}
