import { Bell } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { evidenceHref } from "../../lib/alertEvidence";
import { formatDate } from "../../lib/format";
import { useMarkNotificationsRead, useNotifications } from "../../lib/queries";
import { IconButton } from "../ui/Button";
import { Popover, PopoverClose } from "../ui/Popover";

/** The reader's alerts, newest first (§26.2). An unread dot on the bell; opening the list marks
 *  what it shows as read, while the list itself keeps marking which ones were new. */
export function NotificationsBell({ userId }: { userId: string }) {
  const notifications = useNotifications(userId);
  const markRead = useMarkNotificationsRead();
  // What was unread when the list was last opened: still marked as new until it is closed.
  const [fresh, setFresh] = useState<ReadonlySet<string>>(new Set());
  const items = notifications.data ?? [];
  const unread = items.filter((item) => !item.read).map((item) => item.id);

  const onOpenChange = (open: boolean) => {
    if (!open) return setFresh(new Set());
    setFresh(new Set(unread));
    if (unread.length > 0) markRead.mutate(unread);
  };

  return (
    <Popover
      align="end"
      onOpenChange={onOpenChange}
      trigger={
        <IconButton
          label={unread.length > 0 ? `Notifications, ${unread.length} unread` : "Notifications"}
          className="relative"
        >
          <Bell aria-hidden className="size-5" />
          {unread.length > 0 && (
            <span aria-hidden className="absolute right-2 top-2 size-2 rounded-full bg-primary ring-2 ring-bg" />
          )}
        </IconButton>
      }
    >
      <div className="-m-1">
        <p className="px-1 pb-2 text-label text-muted">Notifications</p>
        {notifications.isError ? (
          <p role="alert" className="px-1 py-4 text-sm text-muted">
            Notifications could not be loaded.
          </p>
        ) : items.length === 0 ? (
          <p className="px-1 py-4 text-sm text-muted">
            Nothing yet. Turn on alerts from a company’s page or the Alerts page and they will arrive here.
          </p>
        ) : (
          <ul className="max-h-80 divide-y divide-border/60 overflow-y-auto">
            {items.map((item) => (
              <li key={item.id} className="flex gap-2.5 px-1 py-2.5">
                <span
                  aria-hidden
                  className={`mt-1.5 size-1.5 shrink-0 rounded-full ${fresh.has(item.id) ? "bg-primary" : "bg-transparent"}`}
                />
                <div className="min-w-0">
                  <p className="text-sm">
                    {fresh.has(item.id) && <span className="sr-only">New: </span>}
                    {evidenceHref(item) ? (
                      <PopoverClose asChild>
                        <Link to={evidenceHref(item) ?? ""} className="hover:text-primary hover:underline">
                          {item.title}
                        </Link>
                      </PopoverClose>
                    ) : (
                      item.title
                    )}
                  </p>
                  {item.body && <p className="mt-0.5 text-caption text-muted">{item.body}</p>}
                  <p className="mt-0.5 text-caption text-subtle">{formatDate(item.created_at)}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Popover>
  );
}
