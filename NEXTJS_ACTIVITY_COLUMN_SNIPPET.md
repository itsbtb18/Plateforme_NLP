# Next.js Activity Column Snippet

Use this when your dashboard is rendered in React/Next.js and the API returns `last_scraped_at` and `update_count` for each event.

```tsx
import React from "react";

type EventRow = {
  id: string;
  title: string;
  start_date: string;
  last_scraped_at: string | null;
  update_count: number;
};

function formatRelativeTime(isoValue: string | null): string {
  if (!isoValue) return "Never";

  const date = new Date(isoValue);
  if (Number.isNaN(date.getTime())) return "Never";

  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.max(0, Math.floor(diffMs / 60000));

  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `Updated ${diffMinutes} minute${diffMinutes === 1 ? "" : "s"} ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `Updated ${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `Updated ${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
}

export function EventsActivityTable({ rows }: { rows: EventRow[] }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Event</th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Start Date</th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Activity</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {rows.map((row) => (
            <tr key={row.id} className="hover:bg-slate-50/80">
              <td className="px-4 py-4">
                <div className="font-medium text-slate-900">{row.title}</div>
              </td>
              <td className="px-4 py-4 text-sm text-slate-600">{row.start_date}</td>
              <td className="px-4 py-4">
                <div className="flex flex-col gap-1">
                  <span className="text-sm font-semibold text-slate-900">
                    {formatRelativeTime(row.last_scraped_at)}
                  </span>
                  <span className="text-xs text-slate-500">
                    {row.update_count} refresh{row.update_count === 1 ? "" : "es"}
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```