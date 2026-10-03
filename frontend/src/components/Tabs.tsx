import { NavLink } from "react-router-dom";

export interface TabDef {
  to: string;
  label: string;
}

/** Horizontal, keyboard-navigable tab bar backed by routes (UI-003). */
export function Tabs({ base, tabs }: { base: string; tabs: TabDef[] }) {
  return (
    <nav aria-label="Dashboard sections" className="border-b border-border">
      <ul className="flex gap-1 overflow-x-auto px-2">
        {tabs.map((tab) => (
          <li key={tab.to}>
            <NavLink
              to={`${base}/${tab.to}`}
              className={({ isActive }) =>
                [
                  "inline-block whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "border-primary text-primary"
                    : "border-transparent text-muted hover:text-text",
                ].join(" ")
              }
            >
              {tab.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
