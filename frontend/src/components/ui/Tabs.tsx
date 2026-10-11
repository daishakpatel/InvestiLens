import { Tabs as RadixTabs } from "radix-ui";
import { useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

export interface TabDef {
  to: string;
  label: string;
}

/** Page-level tabs backed by routes: an underline that slides to the active tab (UI-003). */
export function RouteTabs({ base, tabs, label }: { base: string; tabs: TabDef[]; label: string }) {
  const listRef = useRef<HTMLUListElement>(null);
  const { pathname } = useLocation();
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null);

  useLayoutEffect(() => {
    const measure = () => {
      const active = listRef.current?.querySelector<HTMLElement>('[aria-current="page"]');
      setIndicator(active ? { left: active.offsetLeft, width: active.offsetWidth } : null);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [pathname, tabs]);

  return (
    <nav aria-label={label} className="border-b border-border">
      <ul ref={listRef} className="relative flex gap-6 overflow-x-auto [scrollbar-width:none]">
        {tabs.map((tab) => (
          <li key={tab.to}>
            <NavLink
              to={`${base}/${tab.to}`}
              className={({ isActive }) =>
                `inline-block whitespace-nowrap py-3 text-sm font-medium transition-colors ${
                  isActive ? "text-text" : "text-muted hover:text-text"
                }`
              }
            >
              {tab.label}
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
