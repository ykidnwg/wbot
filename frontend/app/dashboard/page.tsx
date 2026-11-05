"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import { PageBody, PageHeader, Notice, SectionTitle, StatusBadge, Stat } from "@/components/page";
import { ArrowUpRightIcon, CalendarIcon, DocumentIcon, SendIcon } from "@/components/icons";
import { getDashboardSummary, type DashboardSummary } from "@/lib/api";

const metrics: Array<[keyof Omit<DashboardSummary, "services" | "estimated_ai_cost">, string, string]> = [
  ["connected_accounts", "Connected accounts", "Facebook Pages linked"],
  ["active_personas", "Approved personas", "Ready for content"],
  ["generated_images", "Media assets", "Stored in your library"],
  ["pending_approval", "Awaiting approval", "Drafts that need review"],
  ["scheduled_posts", "Scheduled", "Waiting for the worker"],
  ["published_posts", "Published", "Confirmed by the platform"],
  ["failed_posts", "Needs attention", "Failed or uncertain jobs"],
];

const quickActions = [
  { href: "/content", label: "Create a draft", detail: "Generate and approve a caption", Icon: DocumentIcon },
  { href: "/calendar", label: "Plan the week", detail: "Schedule approved content", Icon: CalendarIcon },
  { href: "/publishing", label: "Watch the queue", detail: "Inspect jobs and retries", Icon: SendIcon },
];

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getDashboardSummary(controller.signal)
      .then(setSummary)
      .catch((requestError: unknown) => {
        if (requestError instanceof Error && requestError.message === "unauthorized") {
          window.location.assign("/login");
          return;
        }
        setError("The overview could not be loaded. Check the backend connection and try again.");
      });
    return () => controller.abort();
  }, []);

  return (
    <WorkspaceShell>
      <PageBody>
        <PageHeader
          eyebrow="Operations overview"
          title="A calm view of the whole workspace."
          description="Only real, owner-scoped records are shown. Nothing is estimated, simulated, or marked published without a provider response."
          action={<span className="badge badge-neutral">Live data</span>}
        />

        {error ? <div className="mt-7"><Notice>{error}</Notice></div> : null}
        {!summary && !error ? (
          <div className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map((key) => (
              <div key={key} className="card-flat h-28 animate-pulse bg-[var(--surface-muted)]" />
            ))}
          </div>
        ) : null}

        {summary ? (
          <div className="mt-8 space-y-8">
            <section aria-labelledby="metrics">
              <SectionTitle title="This workspace" hint="Counts come directly from approved, scheduled, and published records." />
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {metrics.map(([key, label, hint]) => (
                  <Stat key={key} label={label} value={summary[key]} hint={hint} />
                ))}
                <div className="card-flat border-dashed p-4">
                  <p className="text-[0.66rem] font-bold uppercase tracking-[0.12em] text-[var(--muted)]">AI cost</p>
                  <p className="display mt-2 text-2xl font-semibold text-[var(--muted)]">Not tracked</p>
                  <p className="mt-1 text-[0.68rem] text-[var(--muted)]">No billing integration is connected.</p>
                </div>
              </div>
            </section>

            <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
              <section className="card p-5 md:p-6" aria-labelledby="quick-actions">
                <SectionTitle title="Next moves" hint="A short path from idea to confirmed post." />
                <div className="divide-line">
                  {quickActions.map(({ href, label, detail, Icon }) => (
                    <Link key={href} href={href} className="group flex items-center justify-between gap-4 py-4 first:pt-0 last:pb-0">
                      <span className="flex items-center gap-3">
                        <span className="grid h-10 w-10 place-items-center rounded-full bg-[var(--paper-deep)] text-[var(--forest)]">
                          <Icon />
                        </span>
                        <span>
                          <span className="block text-sm font-semibold">{label}</span>
                          <span className="block text-xs text-[var(--muted)]">{detail}</span>
                        </span>
                      </span>
                      <ArrowUpRightIcon className="text-[var(--muted)] transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                    </Link>
                  ))}
                </div>
              </section>

              <section className="card p-5 md:p-6" aria-labelledby="system-status">
                <SectionTitle title="System status" hint="Configured means the service is present and reachable." />
                <dl className="space-y-3">
                  {Object.entries(summary.services).map(([service, serviceStatus]) => (
                    <div key={service} className="flex items-center justify-between gap-3 rounded-[var(--radius-sm)] bg-[var(--surface-muted)] px-3 py-2.5">
                      <dt className="text-sm capitalize text-[var(--ink-soft)]">{service}</dt>
                      <dd>
                        <StatusBadge status={serviceStatus === "not_configured" ? "not configured" : "ready"} />
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            </div>
          </div>
        ) : null}
      </PageBody>
    </WorkspaceShell>
  );
}
