// Dev-only review surface for the design system (UI plan Step 1). Not linked from navigation and
// not part of the production bundle; open /_ui while running `npm run dev`.
import { Bell, Search } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";

import { AiMark } from "../components/ui/AiMark";
import { Badge, EvidenceBadge, FreshnessBadge } from "../components/ui/Badge";
import { Button, IconButton } from "../components/ui/Button";
import { Checkbox } from "../components/ui/Checkbox";
import { DataTable } from "../components/ui/DataTable";
import type { Column } from "../components/ui/DataTable";
import { Delta } from "../components/ui/Delta";
import { Dialog, Drawer } from "../components/ui/Dialog";
import { DropdownMenu, MenuItem, MenuLabel, MenuSeparator } from "../components/ui/DropdownMenu";
import { Input } from "../components/ui/Input";
import { Popover } from "../components/ui/Popover";
import { Section, Surface } from "../components/ui/Section";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { Select } from "../components/ui/Select";
import { Skeleton, Spinner } from "../components/ui/Skeleton";
import { Stat } from "../components/ui/Stat";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { Switch } from "../components/ui/Switch";
import { PillTabPanel, PillTabs } from "../components/ui/Tabs";
import { Tooltip } from "../components/ui/Tooltip";

const COLORS = [
  "bg",
  "surface",
  "surface-2",
  "surface-3",
  "border",
  "border-strong",
  "text",
  "text-muted",
  "text-subtle",
  "primary",
  "positive",
  "negative",
  "warning",
  "ai",
  "chart-1",
  "chart-2",
  "chart-3",
  "chart-4",
  "chart-5",
  "chart-6",
];

const TYPE: [string, string][] = [
  ["text-display-l font-semibold", "$134.33 display-l 48"],
  ["text-display-s font-semibold", "Display small 32"],
  ["text-heading font-semibold", "Heading 24"],
  ["text-title font-medium", "Title 18"],
  ["text-body", "Body 15. Evidence-grounded research on US public companies."],
  ["text-sm", "Body small 14"],
  ["text-label text-muted", "Label 13"],
  ["text-caption text-subtle", "Caption 12"],
];

interface Row {
  metric: string;
  fy24: string;
  fy25: string;
  yoy: number;
}
const ROWS: Row[] = [
  { metric: "Revenue", fy24: "$60.9B", fy25: "$130.5B", yoy: 1.142 },
  { metric: "Net income", fy24: "$29.8B", fy25: "$72.9B", yoy: 1.449 },
  { metric: "Operating expenses", fy24: "$11.3B", fy25: "$16.4B", yoy: 0.451 },
  { metric: "Inventory", fy24: "$5.3B", fy25: "$5.1B", yoy: -0.038 },
];
const COLUMNS: Column<Row>[] = [
  { key: "metric", header: "Metric", render: (r) => r.metric },
  { key: "fy24", header: "FY2024", numeric: true, render: (r) => r.fy24 },
  { key: "fy25", header: "FY2025", numeric: true, render: (r) => r.fy25 },
  { key: "yoy", header: "YoY", numeric: true, render: (r) => <Delta value={r.yoy} digits={1} /> },
];

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-3 py-5 sm:grid-cols-[10rem_1fr]">
      <div className="text-label text-muted">{label}</div>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </div>
  );
}

export default function UiGallery() {
  const [range, setRange] = useState<"1M" | "3M" | "1Y" | "5Y">("1Y");
  const [tab, setTab] = useState<"income" | "margins" | "cash">("income");
  const [checked, setChecked] = useState(true);
  const [on, setOn] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [drawer, setDrawer] = useState(false);

  return (
    <div className="space-y-12 py-8">
      <header>
        <h1 className="text-display-s font-semibold">Design system</h1>
        <p className="mt-1 text-muted">Tokens and primitives. Switch theme from the account menu to check both.</p>
      </header>

      <Section title="Colour">
        <div className="grid grid-cols-2 gap-3 pt-5 sm:grid-cols-4 lg:grid-cols-5">
          {COLORS.map((name) => (
            <div key={name}>
              <div
                className="h-12 rounded-control border border-border"
                style={{ backgroundColor: `var(--${name})` }}
              />
              <div className="mt-1 text-caption text-muted">{name}</div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Type">
        <div className="space-y-3 pt-5">
          {TYPE.map(([cls, sample]) => (
            <p key={cls} className={`tnum ${cls}`}>
              {sample}
            </p>
          ))}
        </div>
      </Section>

      <Section title="Actions">
        <div className="divide-y divide-border/60">
          <Row label="Button">
            <Button variant="primary">Generate research</Button>
            <Button>Export</Button>
            <Button variant="ghost">Cancel</Button>
            <Button variant="danger">Remove</Button>
            <Button variant="primary" loading>
              Saving
            </Button>
            <Button disabled>Disabled</Button>
          </Row>
          <Row label="Button, small">
            <Button variant="primary" size="sm">
              Add
            </Button>
            <Button size="sm">Retry</Button>
            <Button variant="ghost" size="sm">
              Dismiss
            </Button>
          </Row>
          <Row label="IconButton">
            <IconButton label="Search">
              <Search aria-hidden className="size-4" />
            </IconButton>
            <IconButton label="Notifications" variant="secondary">
              <Bell aria-hidden className="size-4" />
            </IconButton>
            <IconButton label="Notifications" size="sm">
              <Bell aria-hidden className="size-3.5" />
            </IconButton>
          </Row>
        </div>
      </Section>

      <Section title="Inputs">
        <div className="divide-y divide-border/60">
          <Row label="Input">
            <Input aria-label="Example" placeholder="Search a company" className="max-w-64" />
            <Input aria-label="Invalid example" aria-invalid defaultValue="nvda@" className="max-w-40" />
            <Input aria-label="Disabled example" disabled placeholder="Disabled" className="max-w-40" />
          </Row>
          <Row label="Select">
            <Select aria-label="Baseline" defaultValue="prior">
              <option value="prior">vs prior 10-K</option>
              <option value="2024">vs 10-K · Feb 21, 2024</option>
            </Select>
          </Row>
          <Row label="Checkbox, Switch">
            <Checkbox checked={checked} onCheckedChange={setChecked}>
              Risk factors only
            </Checkbox>
            <Switch checked={on} onCheckedChange={setOn}>
              Show growth
            </Switch>
          </Row>
          <Row label="SegmentedControl">
            <SegmentedControl
              label="Range"
              value={range}
              onValueChange={setRange}
              options={[
                { value: "1M", label: "1M" },
                { value: "3M", label: "3M" },
                { value: "1Y", label: "1Y" },
                { value: "5Y", label: "5Y", disabled: true },
              ]}
            />
          </Row>
          <Row label="Pill tabs">
            <PillTabs
              label="Statement"
              value={tab}
              onValueChange={setTab}
              tabs={[
                { value: "income", label: "Income" },
                { value: "margins", label: "Margins" },
                { value: "cash", label: "Cash flow" },
              ]}
            >
              <PillTabPanel value={tab} className="pt-3 text-sm text-muted">
                Showing: {tab}
              </PillTabPanel>
            </PillTabs>
          </Row>
        </div>
      </Section>

      <Section title="Data display" freshness={{ as_of: "2026-10-09T02:00:00Z", source: "sec", freshness_status: "fresh" }}>
        <div className="divide-y divide-border/60">
          <Row label="Stat">
            <div className="flex flex-wrap gap-x-10 gap-y-4">
              <Stat
                label="Revenue"
                value="$130.5B"
                delta={<Delta value={1.142} digits={1} />}
                meta={{ source: "SEC filings (XBRL)", period: "FY2025" }}
              />
              <Stat label="Gross margin" value="75.0%" delta={<Delta value={-0.021} digits={1} />} />
              <Stat label="EPS" value="$2.94" />
            </div>
          </Row>
          <Row label="Delta">
            <Delta value={0.0123} />
            <Delta value={-0.0306} />
            <Delta value={0} />
          </Row>
          <Row label="Badge">
            <Badge>Unchanged</Badge>
            <Badge tone="data">Reworded</Badge>
            <Badge tone="warning">New</Badge>
            <Badge tone="negative">Removed</Badge>
            <Badge tone="positive">Fresh</Badge>
            <EvidenceBadge label="limited_evidence" />
            <FreshnessBadge
              freshness={{ as_of: "2026-10-01T02:00:00Z", source: "price", freshness_status: "stale" }}
            />
          </Row>
          <Row label="AiMark, Tooltip">
            <AiMark />
            <Tooltip label="Revenue less cost of revenue, divided by revenue.">Gross margin</Tooltip>
          </Row>
        </div>
        <div className="pt-5">
          <DataTable
            caption="DataTable, comfortable. USD, fiscal years."
            columns={COLUMNS}
            rows={ROWS}
            rowKey={(r) => r.metric}
          />
          <div className="mt-6">
            <DataTable
              caption="DataTable, compact."
              density="compact"
              columns={COLUMNS}
              rows={ROWS}
              rowKey={(r) => r.metric}
            />
          </div>
        </div>
      </Section>

      <Section title="AI research summary" kind="ai" actions={<Button size="sm">Export</Button>}>
        <p className="max-w-2xl pt-4 text-body text-text">
          A Section with <code>kind="ai"</code> carries the one AI mark for everything beneath it. Data
          sections carry no label at all.
        </p>
      </Section>

      <Section title="Containers and layers">
        <div className="divide-y divide-border/60">
          <Row label="Surface">
            <Surface className="max-w-sm p-4 text-sm text-muted">
              The one bordered container, for content that needs separating from the canvas.
            </Surface>
          </Row>
          <Row label="Popover, Menu">
            <Popover trigger={<Button>Filter</Button>}>
              <p className="text-muted">Popover content: filters, alert switches.</p>
            </Popover>
            <DropdownMenu trigger={<Button>Account</Button>}>
              <MenuLabel>analyst@example.com</MenuLabel>
              <MenuItem onSelect={() => undefined}>Light theme</MenuItem>
              <MenuSeparator />
              <MenuItem danger onSelect={() => undefined}>
                Sign out
              </MenuItem>
            </DropdownMenu>
          </Row>
          <Row label="Dialog, Drawer">
            <Button onClick={() => setDialog(true)}>Open dialog</Button>
            <Button onClick={() => setDrawer(true)}>Open drawer</Button>
            <Dialog open={dialog} onOpenChange={setDialog} title="Remove holding" description="This cannot be undone.">
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setDialog(false)}>
                  Cancel
                </Button>
                <Button variant="danger" onClick={() => setDialog(false)}>
                  Remove
                </Button>
              </div>
            </Dialog>
            <Drawer open={drawer} onOpenChange={setDrawer} title="Source" description="10-K · Item 1A · filed Feb 25, 2026">
              <p className="text-sm text-muted">
                Evidence opens beside the page, so the reader keeps their place.
              </p>
            </Drawer>
          </Row>
        </div>
      </Section>

      <Section title="States">
        <div className="grid grid-cols-1 gap-6 pt-5 md:grid-cols-3">
          <div>
            <div className="text-label text-muted">Loading</div>
            <LoadingState />
            <Skeleton shape="row" />
            <Skeleton shape="chart" className="mt-3 h-24" />
            <div className="mt-3">
              <Spinner />
            </div>
          </div>
          <div>
            <div className="text-label text-muted">Empty</div>
            <EmptyState
              message="No research report yet for this company."
              action={<Button variant="primary" size="sm">Generate research</Button>}
            />
          </div>
          <div>
            <div className="text-label text-muted">Error</div>
            <ErrorState message="Could not load filings." onRetry={() => undefined} />
          </div>
        </div>
      </Section>
    </div>
  );
}
