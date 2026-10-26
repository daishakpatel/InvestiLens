import { demoBannerText } from "../lib/demo";
import { useDemoInfo } from "../lib/queries";

/** One line above everything on the public demo (NFR-ME-007); absent everywhere else. */
export function DemoBanner() {
  const demo = useDemoInfo();
  if (!demo.data?.enabled) return null;
  return (
    <p role="note" className="border-b border-border bg-surface px-4 py-1.5 text-center text-caption text-muted print:hidden">
      {demoBannerText(demo.data.data_as_of)}
    </p>
  );
}
