import { DISCLAIMER } from "../lib/config";
import { useTheme } from "../lib/theme";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      className="rounded-md border border-border px-2 py-1 text-sm hover:bg-surface-2"
    >
      <span aria-hidden>{theme === "dark" ? "☀" : "☾"}</span>
    </button>
  );
}

export function Disclaimer() {
  return (
    <p className="text-xs text-muted" role="note">
      {DISCLAIMER}
    </p>
  );
}

export function Footer() {
  return (
    <footer className="mt-10 border-t border-border px-4 py-6">
      <Disclaimer />
    </footer>
  );
}
