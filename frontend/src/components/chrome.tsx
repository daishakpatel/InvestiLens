import { DISCLAIMER } from "../lib/config";
import { useTheme } from "../lib/theme";
import { Moon, Sun } from "lucide-react";

import { IconButton } from "./ui/Button";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <IconButton
      onClick={toggle}
      label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
    >
      {theme === "dark" ? (
        <Sun aria-hidden className="size-4" />
      ) : (
        <Moon aria-hidden className="size-4" />
      )}
    </IconButton>
  );
}

export function Disclaimer() {
  return (
    <p className="text-caption text-subtle" role="note">
      {DISCLAIMER}
    </p>
  );
}

export function Footer() {
  return (
    <footer className="mt-16 border-t border-border py-6">
      <Disclaimer />
    </footer>
  );
}
