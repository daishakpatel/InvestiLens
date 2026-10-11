import { Star } from "lucide-react";

import { Section } from "../ui/Section";
import { EmptyState } from "../ui/States";

/** Where the signed-in user's watchlist will render on Home. UI plan Step 5 replaces the body of
 *  this component with the real list (price, day change, sparkline); nothing else on the page
 *  needs to change. */
export function WatchlistSlot() {
  return (
    <Section title="Watchlist">
      <EmptyState
        icon={<Star className="size-5" />}
        message="Watchlists aren’t available yet. Companies you choose to watch will be listed here."
      />
    </Section>
  );
}
