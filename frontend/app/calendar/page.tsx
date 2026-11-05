"use client";

import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import { Card, EmptyState, Notice, PageBody, PageHeader, SectionTitle, StatusBadge } from "@/components/page";
import {
  cancelSchedule,
  createSchedule,
  getContent,
  getSchedules,
  getSocialTargets,
  type ContentItem,
  type Schedule,
  type SocialTarget,
} from "@/lib/api";

function defaultSlot(): string {
  const value = new Date();
  value.setDate(value.getDate() + 1);
  value.setHours(10, 0, 0, 0);
  const offset = value.getTimezoneOffset();
  return new Date(value.getTime() - offset * 60_000).toISOString().slice(0, 16);
}

function defaultTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export default function CalendarPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [content, setContent] = useState<ContentItem[]>([]);
  const [targets, setTargets] = useState<SocialTarget[]>([]);
  const [contentId, setContentId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [scheduledFor, setScheduledFor] = useState(defaultSlot);
  const [timezone, setTimezone] = useState(defaultTimezone);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function reload(signal?: AbortSignal) {
    const [scheduleRows, contentRows, targetRows] = await Promise.all([
      getSchedules(signal),
      getContent(signal),
      getSocialTargets(),
    ]);
    setSchedules(scheduleRows);
    setContent(contentRows);
    setTargets(targetRows);
  }

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void reload(controller.signal)
        .catch((requestError: unknown) => {
          if (requestError instanceof Error && requestError.message === "unauthorized") {
            window.location.assign("/login");
            return;
          }
          setError("The calendar could not be loaded.");
        })
        .finally(() => setLoading(false));
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, []);

  const approvedContent = useMemo(
    () => content.filter((item) => item.status === "approved"),
    [content],
  );
  const activeTargets = useMemo(() => targets.filter((target) => target.status === "active"), [targets]);
  const contentById = useMemo(() => new Map(content.map((item) => [item.id, item])), [content]);
  const targetById = useMemo(() => new Map(targets.map((item) => [item.id, item])), [targets]);
  const upcoming = schedules.filter((item) => item.status !== "cancelled");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await createSchedule({
        content_item_id: contentId,
        social_target_id: targetId,
        scheduled_for: scheduledFor,
        timezone,
      });
      await reload();
      setNotice("Schedule created. The publishing worker will pick it up when it is due.");
      setContentId("");
      setTargetId("");
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The schedule could not be created.");
    } finally {
      setBusy(false);
    }
  }

  async function cancel(id: string) {
    setBusy(true);
    setError(null);
    try {
      await cancelSchedule(id);
      await reload();
      setNotice("Schedule cancelled. The content is available for rescheduling.");
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The schedule could not be cancelled.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <WorkspaceShell>
      <PageBody>
        <PageHeader
          eyebrow="Content calendar"
          title="Give every approved idea a time and a place."
          description="Schedules are stored durably and dispatched by the publishing worker. A scheduled post is not published until the platform confirms it."
        />

        <div className="mt-8 grid gap-6 lg:grid-cols-[0.9fr_1.4fr]">
          <Card>
            <SectionTitle title="New schedule" hint="Only approved content and active targets are listed." />
            <form onSubmit={submit} className="grid gap-4">
              <label className="label">
                Approved content
                <select required className="field" value={contentId} onChange={(event) => setContentId(event.target.value)}>
                  <option value="">Select content</option>
                  {approvedContent.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.topic} · {item.platform}
                    </option>
                  ))}
                </select>
              </label>
              <label className="label">
                Social target
                <select required className="field" value={targetId} onChange={(event) => setTargetId(event.target.value)}>
                  <option value="">Select Page</option>
                  {activeTargets.map((target) => (
                    <option key={target.id} value={target.id}>
                      {target.display_name} · {target.platform}
                    </option>
                  ))}
                </select>
              </label>
              <label className="label">
                Publish at
                <input type="datetime-local" required className="field" value={scheduledFor} onChange={(event) => setScheduledFor(event.target.value)} />
              </label>
              <label className="label">
                Timezone
                <input required className="field" value={timezone} onChange={(event) => setTimezone(event.target.value)} />
              </label>
              <button disabled={busy || !approvedContent.length || !activeTargets.length} className="btn btn-accent w-full">
                {busy ? "Scheduling…" : "Schedule post"}
              </button>
              {!approvedContent.length ? <p className="text-xs text-[var(--muted)]">Approve a content draft first.</p> : null}
              {!activeTargets.length ? <p className="text-xs text-[var(--muted)]">Connect and activate a Facebook Page first.</p> : null}
              {error ? <Notice>{error}</Notice> : null}
              {notice ? <Notice tone="info">{notice}</Notice> : null}
            </form>
          </Card>

          <section className="card p-5 md:p-6">
            <SectionTitle
              title="Upcoming and recent"
              hint={`${upcoming.length} schedule${upcoming.length === 1 ? "" : "s"} in this workspace`}
            />
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((key) => <div key={key} className="h-16 animate-pulse rounded-[var(--radius-sm)] bg-[var(--surface-muted)]" />)}
              </div>
            ) : upcoming.length === 0 ? (
              <EmptyState title="Nothing on the calendar" body="Approved content can be scheduled here. The worker only publishes jobs whose time has arrived." />
            ) : (
              <ul className="divide-line">
                {upcoming.map((schedule) => {
                  const item = contentById.get(schedule.content_item_id);
                  const target = targetById.get(schedule.social_target_id);
                  return (
                    <li key={schedule.id} className="flex flex-wrap items-center justify-between gap-3 py-4 first:pt-0 last:pb-0">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">{item?.topic ?? "Content unavailable"}</p>
                        <p className="mt-1 text-xs text-[var(--muted)]">
                          {new Date(schedule.scheduled_for).toLocaleString(undefined, { timeZone: schedule.timezone })} · {schedule.timezone} · {target?.display_name ?? "Target unavailable"}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={schedule.status} />
                        {schedule.status === "scheduled" ? (
                          <button type="button" disabled={busy} onClick={() => void cancel(schedule.id)} className="btn btn-ghost">
                            Cancel
                          </button>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>
      </PageBody>
    </WorkspaceShell>
  );
}
