"use client";

import { useEffect, useState } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import { EmptyState, Notice, PageBody, PageHeader, SectionTitle, StatusBadge, Stat } from "@/components/page";
import { getAnalytics, type Analytics } from "@/lib/api";

export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getAnalytics(controller.signal)
      .then(setData)
      .catch((requestError: unknown) => {
        if (requestError instanceof Error && requestError.message === "unauthorized") {
          window.location.assign("/login");
          return;
        }
        setError("Analytics could not be loaded.");
      });
    return () => controller.abort();
  }, []);

  const maxClicks = Math.max(1, ...(data?.clicks_by_day.map((point) => point.value) ?? [1]));

  return (
    <WorkspaceShell>
      <PageBody>
        <PageHeader
          eyebrow="First-party analytics"
          title="Numbers with a receipt."
          description="Every number on this page comes from owned records: content states, schedules, publishing jobs, and clicks recorded by this server. External reach and impressions are intentionally absent until an official integration provides them."
          action={<span className="badge badge-accent">First-party only</span>}
        />

        {error ? <div className="mt-6"><Notice>{error}</Notice></div> : null}
        {!data && !error ? (
          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((key) => <div key={key} className="card-flat h-28 animate-pulse bg-[var(--surface-muted)]" />)}
          </div>
        ) : null}

        {data ? (
          <div className="mt-8 space-y-8">
            <section>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Stat label="Tracked clicks" value={data.summary.total_clicks} hint="Recorded on this server" />
                <Stat label="Published posts" value={data.summary.published_content} hint="Confirmed by a provider" />
                <Stat label="Upcoming schedules" value={data.summary.upcoming_schedules} hint="Future scheduled records" />
                <Stat label="Active campaigns" value={data.summary.active_campaigns} hint={`${data.summary.tracked_links} tracked links`} />
              </div>
            </section>

            <section className="card p-5 md:p-6">
              <SectionTitle
                title="Clicks, last 30 days"
                hint="Daily first-party redirects. Missing days are zero, not estimates."
              />
              {data.summary.total_clicks === 0 ? (
                <EmptyState title="No clicks recorded yet" body="Add a campaign link and publish its tracking URL. Each redirect will be recorded here with a timestamp." />
              ) : (
                <div className="flex h-52 items-end gap-1.5" aria-label="Clicks per day" role="img">
                  {data.clicks_by_day.map((point) => (
                    <div key={point.date} className="group relative flex h-full flex-1 items-end">
                      <div
                        className="w-full rounded-t-[3px] bg-[var(--accent)] transition-opacity group-hover:opacity-80"
                        style={{ height: `${Math.max(3, (point.value / maxClicks) * 100)}%` }}
                        title={`${point.date}: ${point.value}`}
                      />
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-3 flex justify-between text-[0.66rem] text-[var(--muted)]">
                <span>{data.clicks_by_day[0]?.date}</span>
                <span>{data.clicks_by_day[data.clicks_by_day.length - 1]?.date}</span>
              </div>
            </section>

            <div className="grid gap-5 lg:grid-cols-2">
              <section className="card p-5 md:p-6">
                <SectionTitle title="Campaign performance" hint="Attributed by tracked-link clicks." />
                {data.campaign_performance.length === 0 ? (
                  <EmptyState title="No campaign data" body="Create a campaign and add a tracked link to begin measuring." />
                ) : (
                  <ul className="divide-line">
                    {data.campaign_performance.map((campaign) => (
                      <li key={campaign.campaign_id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold">{campaign.name}</p>
                          <div className="mt-1"><StatusBadge status={campaign.status} /></div>
                        </div>
                        <p className="display text-xl font-semibold tabular-nums">{campaign.clicks}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="card p-5 md:p-6">
                <SectionTitle title="Top links" hint="Every click is attributed to a stored campaign link." />
                {data.link_performance.length === 0 ? (
                  <EmptyState title="No links yet" body="Campaign links provide the only first-party click source in this workspace." />
                ) : (
                  <ul className="divide-line">
                    {data.link_performance.map((link) => (
                      <li key={link.link_id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold">{link.label}</p>
                          <p className="truncate text-xs text-[var(--muted)]">{link.campaign_name} · {link.tracking_id}</p>
                        </div>
                        <p className="display text-xl font-semibold tabular-nums">{link.clicks}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </div>
        ) : null}
      </PageBody>
    </WorkspaceShell>
  );
}
