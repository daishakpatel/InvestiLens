import { useIsFetching } from "@tanstack/react-query";
import { useEffect, useState } from "react";

const SHOW_AFTER_MS = 300;

/** A 2 px line across the top while a screen is waiting on its first data. Only first loads
 *  count (background refreshes and polling stay silent), and only once they have run longer than
 *  300 ms, so fast responses never flash it. */
export function RouteProgress() {
  const pending = useIsFetching({
    // Search-as-you-type has its own skeleton rows in the palette.
    predicate: (query) => query.state.status === "pending" && query.queryKey[0] !== "search",
  });
  // Mounted only while something is loading, so each wait starts its own 300 ms clock.
  return pending > 0 ? <DelayedLine /> : null;
}

function DelayedLine() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const id = setTimeout(() => setVisible(true), SHOW_AFTER_MS);
    return () => clearTimeout(id);
  }, []);

  if (!visible) return null;
  return (
    <div
      role="progressbar"
      aria-label="Loading"
      className="pointer-events-none fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden"
    >
      <div className="h-full w-2/5 animate-progress bg-primary motion-reduce:w-full motion-reduce:animate-none motion-reduce:opacity-60" />
    </div>
  );
}
