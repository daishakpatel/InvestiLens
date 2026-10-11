import { SlidersHorizontal } from "lucide-react";
import { useId, useState } from "react";
import { useParams } from "react-router-dom";

import { tierLabel } from "../../components/citations/sourceTitle";
import { Button } from "../../components/ui/Button";
import { Popover } from "../../components/ui/Popover";
import { Section } from "../../components/ui/Section";
import { Select } from "../../components/ui/Select";
import { AsyncContent } from "../../components/ui/States";
import { formatDate } from "../../lib/format";
import { NO_FILTERS, activeFilterCount, filterNews, groupByDay, toStories } from "../../lib/newsFeed";
import type { NewsFilters, Story } from "../../lib/newsFeed";
import { useNews } from "../../lib/queries";
import { EXTERNAL_LINK, safeHttpUrl } from "../../lib/safeUrl";
import type { NewsItem } from "../../types";

const timeFmt = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" });

function timeOf(item: NewsItem): string | null {
  const date = item.published_at ? new Date(item.published_at) : null;
  return date && !Number.isNaN(date.getTime()) ? timeFmt.format(date) : null;
}

const unique = (values: (string | null | undefined)[]) =>
  [...new Set(values.filter((value): value is string => Boolean(value)))].sort();

/** A headline that links out to the publisher (LGL-004: the article itself is never shown
 *  here). The address comes from a news feed, so only a plain web address becomes a link. */
function Headline({ item }: { item: NewsItem }) {
  const url = safeHttpUrl(item.url);
  if (!url) return <>{item.title}</>;
  return (
    <a href={url} {...EXTERNAL_LINK} className="hover:underline">
      {item.title}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}

/** Publisher and time. The source tier (§15) is named only for the weaker tiers, which is when
 *  the reader needs to know. */
function Byline({ item }: { item: NewsItem }) {
  const parts = [
    item.publisher ?? "Unknown publisher",
    timeOf(item),
    item.tier != null && item.tier >= 4 ? tierLabel(item.tier) : null,
  ].filter(Boolean);
  return <>{parts.join(" · ")}</>;
}

function StoryItem({ story }: { story: Story }) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const { lead, others } = story;
  return (
    <li className="py-4">
      <h4 className="text-body font-medium leading-snug">
        <Headline item={lead} />
      </h4>
      <p className="mt-1 text-caption text-subtle">
        <Byline item={lead} />
        {lead.category && <span className="text-muted"> · {lead.category}</span>}
      </p>
      {lead.description && <p className="mt-1.5 line-clamp-2 text-sm text-muted">{lead.description}</p>}
      {others.length > 0 && (
        <>
          <Button
            variant="ghost"
            size="sm"
            className="-ml-2.5 mt-1.5"
            aria-expanded={open}
            aria-controls={open ? listId : undefined}
            onClick={() => setOpen((v) => !v)}
          >
            +{others.length} more {others.length === 1 ? "source" : "sources"}
          </Button>
          {open && (
            <ul id={listId} className="mt-1 space-y-2 border-l border-border pl-4">
              {others.map((item) => (
                <li key={item.news_id}>
                  <p className="text-sm">
                    <Headline item={item} />
                  </p>
                  <p className="text-caption text-subtle">
                    <Byline item={item} />
                  </p>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </li>
  );
}

function Filters({
  items,
  filters,
  onChange,
}: {
  items: NewsItem[];
  filters: NewsFilters;
  onChange: (filters: NewsFilters) => void;
}) {
  const count = activeFilterCount(filters);
  const field = "flex flex-col gap-1.5 text-label text-muted";
  return (
    <Popover
      align="end"
      trigger={
        <Button size="sm" aria-label={count > 0 ? `Filter, ${count} active` : "Filter"}>
          <SlidersHorizontal aria-hidden className="size-3.5" />
          Filter
          {count > 0 && (
            <span className="tnum rounded-full bg-primary px-1.5 text-caption text-primary-contrast">{count}</span>
          )}
        </Button>
      }
    >
      <div className="space-y-4">
        <label className={field}>
          Category
          <Select value={filters.category} onChange={(e) => onChange({ ...filters, category: e.target.value })}>
            <option value="">All categories</option>
            {unique(items.map((item) => item.category)).map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </Select>
        </label>
        <label className={field}>
          Publisher
          <Select value={filters.publisher} onChange={(e) => onChange({ ...filters, publisher: e.target.value })}>
            <option value="">All publishers</option>
            {unique(items.map((item) => item.publisher)).map((publisher) => (
              <option key={publisher} value={publisher}>
                {publisher}
              </option>
            ))}
          </Select>
        </label>
        <label className={field}>
          Relevance to this company
          <Select
            value={String(filters.minRelevance)}
            onChange={(e) => onChange({ ...filters, minRelevance: Number(e.target.value) })}
          >
            <option value="0">Any</option>
            <option value="0.5">50% or higher</option>
            <option value="0.7">70% or higher</option>
            <option value="0.9">90% or higher</option>
          </Select>
        </label>
        {count > 0 && (
          <Button variant="ghost" size="sm" className="-ml-2.5" onClick={() => onChange(NO_FILTERS)}>
            Clear filters
          </Button>
        )}
      </div>
    </Popover>
  );
}

/** News as one feed: newest first under day headings, the same event from several outlets
 *  folded into one entry. Headlines only (LGL-004). */
export default function NewsTab() {
  const { ticker = "" } = useParams();
  const news = useNews(ticker);
  const [filters, setFilters] = useState<NewsFilters>(NO_FILTERS);
  const items = news.data?.items ?? [];

  return (
    <div className="max-w-[720px]">
      <Section
        title="News"
        freshness={news.data?.freshness}
        actions={items.length > 0 ? <Filters items={items} filters={filters} onChange={setFilters} /> : undefined}
      >
        <AsyncContent
          query={news}
          isEmpty={(data) => data.items.length === 0}
          emptyMessage={`No news has been collected for ${ticker.toUpperCase()} yet.`}
        >
          {(data) => {
            const days = groupByDay(toStories(filterNews(data.items, filters)));
            if (days.length === 0) {
              return (
                <div role="status" className="space-y-3 py-8 text-sm text-muted">
                  <p>No news matches these filters.</p>
                  <Button size="sm" onClick={() => setFilters(NO_FILTERS)}>
                    Clear filters
                  </Button>
                </div>
              );
            }
            return (
              <>
                {days.map(({ day, stories }) => (
                  <section key={day || "undated"} aria-label={day ? formatDate(day) : "Undated"} className="pt-6">
                    <h3 className="text-label font-medium text-muted">{day ? formatDate(day) : "Undated"}</h3>
                    <ul className="divide-y divide-border/60">
                      {stories.map((story) => (
                        <StoryItem key={story.key} story={story} />
                      ))}
                    </ul>
                  </section>
                ))}
                {data.next_cursor && (
                  <p className="border-t border-border/60 pt-4 text-caption text-subtle">
                    Showing the {data.items.length} most recent items.
                  </p>
                )}
              </>
            );
          }}
        </AsyncContent>
      </Section>
    </div>
  );
}
