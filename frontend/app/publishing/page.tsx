"use client";

import { useEffect, useMemo, useState } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import { EmptyState, Notice, PageBody, PageHeader, SectionTitle, StatusBadge, Stat } from "@/components/page";
import {
  getContent,
  getPublishingJobs,
  getSocialTargets,
  retryPublishingJob,
  type ContentItem,
  type PublishingJob,
  type SocialTarget,
} from "@/lib/api";

const filters = ["all", "queued", "running", "succeeded", "retry_wait", "failed", "needs_credentials", "uncertain"];

export default function PublishingPage() {
  const [jobs, setJobs] = useState<PublishingJob[]>([]);
  const [content, setContent] = useState<ContentItem[]>([]);
  const [targets, setTargets] = useState<SocialTarget[]>([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reload(signal?: AbortSignal) {
    const [jobRows, contentRows, targetRows] = await Promise.all([
      getPublishingJobs(signal),
      getContent(signal),
      getSocialTargets(),
    ]);
    setJobs(jobRows);
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
          setError("The publishing queue could not be loaded.");
        })
        .finally(() => setLoading(false));
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, []);

  const contentById = useMemo(() => new Map(content.map((item) => [item.id, item])), [content]);
  const targetById = useMemo(() => new Map(targets.map((item) => [item.id, item])), [targets]);
  const visible = filter === "all" ? jobs : jobs.filter((job) => job.status === filter);
  const counts = {
    queued: jobs.filter((job) => job.status === "queued" || job.status === "retry_wait").length,
    running: jobs.filter((job) => job.status === "running").length,
    published: jobs.filter((job) => job.status === "succeeded").length,
    attention: jobs.filter((job) => ["failed", "uncertain", "needs_credentials"].includes(job.status)).length,
  };

  async function retry(id: string) {
    setBusy(true);
    setError(null);
    try {
      await retryPublishingJob(id);
      await reload();
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The job could not be retried.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <WorkspaceShell>
      <PageBody>
        <PageHeader
          eyebrow="Publishing queue"
          title="Proof over optimism."
          description="Every job carries its attempt history and the provider’s actual result. Timeouts are marked uncertain rather than retried blindly, because retrying could create a duplicate post."
          action={<span className="badge badge-neutral">DB-backed worker</span>}
        />

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Waiting" value={counts.queued} hint="Queued or waiting for retry" />
          <Stat label="In flight" value={counts.running} hint="Claimed by the worker" />
          <Stat label="Confirmed" value={counts.published} hint="Provider returned a post ID" />
          <Stat label="Needs attention" value={counts.attention} hint="Failed, uncertain, or missing credentials" />
        </div>

        {error ? <div className="mt-6"><Notice>{error}</Notice></div> : null}

        <section className="card mt-8 p-5 md:p-6">
          <SectionTitle
            title="Jobs"
            hint="A published post always has an external post identifier or URL."
            action={
              <div className="flex flex-wrap gap-1">
                {filters.map((value) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setFilter(value)}
                    className={`rounded-full px-3 py-1.5 text-[0.68rem] font-semibold capitalize ${
                      filter === value ? "bg-[var(--ink)] text-[var(--surface)]" : "bg-[var(--surface-muted)] text-[var(--muted)]"
                    }`}
                  >
                    {value.replaceAll("_", " ")}
                  </button>
                ))}
              </div>
            }
          />

          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((key) => <div key={key} className="h-16 animate-pulse rounded-[var(--radius-sm)] bg-[var(--surface-muted)]" />)}
            </div>
          ) : visible.length === 0 ? (
            <EmptyState
              title={jobs.length ? "No jobs match this filter" : "No publishing attempts yet"}
              body="Jobs appear after the worker picks up a due schedule. Nothing is sent until the scheduled time and the target credentials are valid."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] border-collapse text-left">
                <thead>
                  <tr className="table-head">
                    <th className="pb-3 pr-4 font-bold">Content</th>
                    <th className="pb-3 pr-4 font-bold">Target</th>
                    <th className="pb-3 pr-4 font-bold">Status</th>
                    <th className="pb-3 pr-4 font-bold">Attempts</th>
                    <th className="pb-3 pr-4 font-bold">Result</th>
                    <th className="pb-3 font-bold"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody className="divide-line">
                  {visible.map((job) => {
                    const item = contentById.get(job.content_item_id);
                    const target = targetById.get(job.social_target_id);
                    return (
                      <tr key={job.id} className="align-top text-sm">
                        <td className="py-4 pr-4">
                          <p className="max-w-[220px] truncate font-semibold">{item?.topic ?? "Content unavailable"}</p>
                          <p className="mt-1 text-xs text-[var(--muted)]">{job.platform}</p>
                        </td>
                        <td className="py-4 pr-4 text-[var(--ink-soft)]">{target?.display_name ?? "Unavailable"}</td>
                        <td className="py-4 pr-4"><StatusBadge status={job.status} /></td>
                        <td className="py-4 pr-4 tabular-nums text-[var(--ink-soft)]">{job.attempts}</td>
                        <td className="max-w-[280px] py-4 pr-4">
                          {job.published_url ? (
                            <a href={job.published_url} target="_blank" rel="noreferrer" className="font-medium text-[var(--accent-strong)] underline underline-offset-2">
                              View post
                            </a>
                          ) : job.error_summary ? (
                            <span className="text-xs text-[var(--muted)]">{job.error_summary}</span>
                          ) : (
                            <span className="text-xs text-[var(--muted)]">No result yet</span>
                          )}
                        </td>
                        <td className="py-4 text-right">
                          {["failed", "needs_credentials"].includes(job.status) ? (
                            <button type="button" disabled={busy} onClick={() => void retry(job.id)} className="btn btn-secondary">
                              Retry
                            </button>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </PageBody>
    </WorkspaceShell>
  );
}
