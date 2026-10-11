import { useEffect, useState } from "react";

/** Scroll-spy: which of the given section ids is under the pinned bars right now. `topOffsetPx`
 *  is how much of the viewport's top is covered by sticky chrome. */
export function useActiveSection(ids: readonly string[], topOffsetPx = 170): string {
  const [active, setActive] = useState(ids[0] ?? "");
  const key = ids.join("|");
  useEffect(() => {
    const order = key ? key.split("|") : [];
    const visible = new Set<string>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) visible.add(entry.target.id);
          else visible.delete(entry.target.id);
        }
        const first = order.find((id) => visible.has(id));
        if (first) setActive(first);
      },
      { rootMargin: `-${topOffsetPx}px 0px -55% 0px` },
    );
    for (const id of order) {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    }
    return () => observer.disconnect();
  }, [key, topOffsetPx]);
  // An id that has since left the list (a section removed by a filter) is no longer "active".
  return ids.includes(active) ? active : (ids[0] ?? "");
}
