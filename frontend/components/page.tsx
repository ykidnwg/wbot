import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-5 border-b border-[var(--line)] pb-7 md:flex-row md:items-end md:justify-between">
      <div className="max-w-2xl">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="display mt-2 text-4xl font-semibold leading-[1.05] md:text-[2.9rem]">{title}</h1>
        <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{description}</p>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}

export function PageBody({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-6xl px-5 py-8 md:px-10 md:py-10">{children}</div>;
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`card p-5 md:p-6 ${className}`}>{children}</section>;
}

export function SectionTitle({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        {hint ? <p className="mt-1 text-xs text-[var(--muted)]">{hint}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-[var(--radius-md)] border border-dashed border-[var(--line-strong)] bg-[var(--surface-muted)] px-6 py-10 text-center">
      <p className="text-sm font-semibold">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-xs leading-5 text-[var(--muted)]">{body}</p>
    </div>
  );
}

export function Notice({ tone = "error", children }: { tone?: "error" | "info"; children: ReactNode }) {
  return (
    <p
      role={tone === "error" ? "alert" : "status"}
      className={`rounded-[var(--radius-sm)] border px-4 py-3 text-sm ${
        tone === "error"
          ? "border-[#e7c2b8] bg-[var(--danger-soft)] text-[var(--danger)]"
          : "border-[#d3ddcf] bg-[var(--success-soft)] text-[var(--success)]"
      }`}
    >
      {children}
    </p>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  let style = "badge-neutral";
  if (["published", "succeeded", "active", "connected", "approved", "ok", "configured", "ready"].includes(normalized)) {
    style = "badge-success";
  } else if (["failed", "uncertain", "needs_credentials", "error", "revoked"].includes(normalized)) {
    style = "badge-danger";
  } else if (["scheduled", "publishing", "running", "queued", "retry_wait", "draft", "pending_approval"].includes(normalized)) {
    style = "badge-warning";
  } else if (["mock"].includes(normalized)) {
    style = "badge-accent";
  }
  return <span className={`badge ${style}`}>{status.replaceAll("_", " ")}</span>;
}

export function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <div className="card-flat p-4">
      <p className="text-[0.66rem] font-bold uppercase tracking-[0.12em] text-[var(--muted)]">{label}</p>
      <p className="display mt-2 text-3xl font-semibold tabular-nums">{value}</p>
      {hint ? <p className="mt-1 text-[0.68rem] text-[var(--muted)]">{hint}</p> : null}
    </div>
  );
}
