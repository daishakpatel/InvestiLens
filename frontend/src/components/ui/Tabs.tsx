import { Tabs as RadixTabs } from "radix-ui";
import { useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

export interface TabDef {
  to: string; // path under `base`; "" is the index route
  label: string;
  /** A small count beside the label, with what it counts for assistive tech. Hidden at 0. */
  count?: { value: number; label: string } | undefined;
}

/** Page-level tabs backed by routes: an underline that slides to the active tab (UI-003). 48 px
 *  tall with no border of its own, so it can sit inside a bar that draws the hairline. Scrolls
 *  horizontally, without a scrollbar, when the tabs do not fit. */
export function RouteTabs({ base, tabs, label }: { base: string; tabs: TabDef[]; label: string }) {
  const listRef = useRef<HTMLUListElement>(null);
  const { pathname } = useLocation();
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null);
  const [fade, setFade] = useState({ left: false, right: false });

  const updateFade = () => {
    const list = listRef.current;
    if (!list) return;
    setFade({
      left: list.scrollLeft > 1,
      right: list.scrollLeft + list.clientWidth < list.scrollWidth - 1,
    });
  };

  useLayoutEffect(() => {
    const measure = () => {
      const list = listRef.current;
      const active = list?.querySelector<HTMLElement>('[aria-current="page"]');
      setIndicator(active ? { left: active.offsetLeft, width: active.offsetWidth } : null);
      if (list && active) {
        // Bring the active tab into the strip's view. Done by hand: scrollIntoView would also
        // scroll the page when the strip itself is off screen.
        const right = active.offsetLeft + active.offsetWidth;
        if (active.offsetLeft < list.scrollLeft) list.scrollLeft = active.offsetLeft - 16;
        else if (right > list.scrollLeft + list.clientWidth) {
          list.scrollLeft = right - list.clientWidth + 16;
        }
      }
      updateFade();
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [pathname, tabs]);

  // A soft edge where tabs continue out of view, so a clipped label reads as "scroll for more".
  const stop = (on: boolean) => (on ? "24px" : "0px");
  const mask = `linear-gradient(to right, transparent, black ${stop(fade.left)}, black calc(100% - ${stop(fade.right)}), transparent)`;

  return (
    <nav aria-label={label} className="min-w-0">
      <ul
        ref={listRef}
        onScroll={updateFade}
        style={fade.left || fade.right ? { maskImage: mask, WebkitMaskImage: mask } : undefined}
        className="relative flex h-12 gap-6 overflow-x-auto [scrollbar-width:none]"
      >
        {tabs.map((tab) => (
          <li key={tab.to}>
            <NavLink
              to={tab.to ? `${base}/${tab.to}` : base}
              end={!tab.to}
              className={({ isActive }) =>
                `flex h-12 items-center whitespace-nowrap text-sm font-medium transition-colors ${
                  isActive ? "text-text" : "text-muted hover:text-text"
                }`
              }
            >
              {tab.label}
              {tab.count && tab.count.value > 0 && (
                <span
                  aria-label={tab.count.label}
                  className="ml-1.5 rounded-full bg-surface-2 px-1.5 text-caption tnum text-muted"
                >
                  {tab.count.value}
                </span>
              )}
            </NavLink>
          </li>
        ))}
        {indicator && (
          <li
            aria-hidden
            className="absolute bottom-0 h-0.5 rounded-full bg-primary transition-[left,width] duration-(--duration-slow) ease-out"
            style={indicator}
          />
        )}
      </ul>
    </nav>
  );
}

/** In-page pill tabs (Radix: arrow-key navigation and aria wiring come for free). */
export function PillTabs<T extends string>({
  value,
  onValueChange,
  tabs,
  label,
  children,
}: {
  value: T;
  onValueChange: (value: T) => void;
  tabs: { value: T; label: string }[];
  label: string;
  children?: ReactNode; // <PillTabPanel>s
}) {
  return (
    <RadixTabs.Root value={value} onValueChange={(next) => onValueChange(next as T)}>
      <RadixTabs.List aria-label={label} className="flex flex-wrap gap-1">
        {tabs.map((tab) => (
          <RadixTabs.Trigger
            key={tab.value}
            value={tab.value}
            className="h-7 rounded-full px-3 text-label font-medium text-muted transition-colors hover:text-text data-[state=active]:bg-surface-2 data-[state=active]:text-text"
          >
            {tab.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {children}
    </RadixTabs.Root>
  );
}

export const PillTabPanel = RadixTabs.Content;
