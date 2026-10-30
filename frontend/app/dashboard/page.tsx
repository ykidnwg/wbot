"use client";

import { useEffect, useState } from "react";

import { getDashboardSummary, type DashboardSummary } from "@/lib/api";
import { WorkspaceShell } from "@/components/workspace-shell";

const metricLabels: Array<[keyof Omit<DashboardSummary, "services" | "estimated_ai_cost">, string]> = [
  ["connected_accounts", "Akun terhubung"],
  ["active_personas", "Persona aktif"],
  ["generated_images", "Gambar berhasil dibuat"],
  ["pending_approval", "Menunggu persetujuan"],
  ["scheduled_posts", "Posting terjadwal"],
  ["published_posts", "Posting sukses"],
  ["failed_posts", "Posting gagal"],
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
        setError("Dashboard tidak dapat dimuat. Periksa koneksi backend lalu coba lagi.");
      });
    return () => controller.abort();
  }, []);

  return (
    <WorkspaceShell><main className="min-h-screen p-5 md:p-10">
      <header className="mx-auto flex max-w-6xl flex-col gap-4 border-b border-[var(--border)] pb-6 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-semibold tracking-wide text-blue-700">WORKSPACE</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Dashboard</h1>
          <p className="mt-2 text-sm text-[var(--muted)]">Ringkasan operasional yang hanya menampilkan data tersedia.</p>
        </div>
        <span className="w-fit rounded-full bg-slate-200 px-3 py-1 text-sm font-medium text-slate-700">Fondasi M0</span>
      </header>

      {error ? <p role="alert" className="mx-auto mt-8 max-w-6xl rounded-lg bg-red-50 p-4 text-[var(--danger)]">{error}</p> : null}
      {!summary && !error ? <p className="mx-auto mt-8 max-w-6xl text-[var(--muted)]">Memuat ringkasan…</p> : null}

      {summary ? (
        <section className="mx-auto mt-8 max-w-6xl">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {metricLabels.map(([key, label]) => (
              <article key={key} className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm">
                <p className="text-sm text-[var(--muted)]">{label}</p>
                <p className="mt-3 text-3xl font-semibold tabular-nums">{summary[key]}</p>
              </article>
            ))}
            <article className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm">
              <p className="text-sm text-[var(--muted)]">Estimasi biaya AI</p>
              <p className="mt-3 text-lg font-medium">Belum tersedia</p>
            </article>
          </div>

          <section className="mt-8 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm" aria-labelledby="system-status">
            <h2 id="system-status" className="text-lg font-semibold">Status sistem</h2>
            <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(summary.services).map(([service, serviceStatus]) => (
                <div key={service}>
                  <dt className="text-sm capitalize text-[var(--muted)]">{service}</dt>
                  <dd className="mt-1 font-medium">{serviceStatus === "not_configured" ? "Belum dikonfigurasi" : "Siap"}</dd>
                </div>
              ))}
            </dl>
          </section>
        </section>
      ) : null}
    </main></WorkspaceShell>
  );
}
