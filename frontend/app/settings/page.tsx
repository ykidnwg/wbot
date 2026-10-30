"use client";

import { useCallback, useEffect, useState } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import { getSettings, updateSetting, type Setting } from "@/lib/api";

const sections: Array<{ title: string; keys: string[] }> = [
  { title: "Emergency controls", keys: ["generation_kill_switch", "publishing_kill_switch"] },
  { title: "Job limits", keys: ["max_generation_concurrency", "max_publishing_concurrency", "max_retry_attempts"] },
  { title: "Generation budget (USD)", keys: ["daily_generation_budget_usd", "monthly_generation_budget_usd"] },
  { title: "Workspace defaults", keys: ["default_timezone"] },
  { title: "Configured rate limits", keys: ["rate_limit_login_per_minute", "rate_limit_api_per_minute"] },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const result = await getSettings(signal);
      setSettings(result);
      setDrafts(Object.fromEntries(result.map((item) => [item.key, item.value])));
      setError(null);
    } catch (requestError: unknown) {
      if (requestError instanceof Error && requestError.message === "unauthorized") {
        window.location.assign("/login");
        return;
      }
      setError("Pengaturan gagal dimuat. Coba muat ulang halaman.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  async function save(key: string) {
    setSaving(key);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateSetting(key, drafts[key] ?? "");
      setSettings((current) => current.map((item) => item.key === key ? updated : item));
      setDrafts((current) => ({ ...current, [key]: updated.value }));
      setNotice("Pengaturan tersimpan dan tercatat di audit log.");
    } catch (requestError: unknown) {
      if (requestError instanceof Error && requestError.message === "unauthorized") {
        window.location.assign("/login");
        return;
      }
      setError(requestError instanceof Error && requestError.message !== "setting-update-failed"
        ? requestError.message
        : "Pengaturan tidak dapat disimpan. Periksa nilainya lalu coba lagi.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <WorkspaceShell>
      <main className="mx-auto max-w-5xl p-5 md:p-10">
        <header className="border-b border-[var(--border)] pb-6">
          <p className="text-sm font-semibold tracking-wide text-blue-700">KONTROL OPERASIONAL</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Pengaturan</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
            Batas concurrency, retry, anggaran, timezone, dan kill switch tersimpan di PostgreSQL.
            Kill switch akan digunakan worker saat generation dan publishing tersedia.
          </p>
        </header>
        {notice ? <p role="status" className="mt-5 rounded-md bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p> : null}
        {error ? <p role="alert" className="mt-5 rounded-md bg-red-50 p-3 text-sm text-[var(--danger)]">{error}</p> : null}
        {loading ? <p className="mt-6 text-sm text-[var(--muted)]">Memuat pengaturan…</p> : null}
        {!loading && !error ? (
          <div className="mt-6 grid gap-5">
            {sections.map((section) => (
              <section key={section.title} className="rounded-lg border border-[var(--border)] bg-white p-5">
                <h2 className="font-semibold">{section.title}</h2>
                <div className="mt-4 divide-y divide-slate-100">
                  {section.keys.map((key) => {
                    const setting = settings.find((item) => item.key === key);
                    if (!setting) return null;
                    const boolean = setting.value_type === "boolean";
                    return (
                      <div key={key} className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <label htmlFor={`setting-${key}`} className="font-medium">{key.replaceAll("_", " ")}</label>
                          <p className="mt-1 text-sm text-[var(--muted)]">{setting.description}</p>
                          <p className="mt-1 text-xs text-slate-400">Diubah: {new Date(setting.updated_at).toLocaleString()}</p>
                        </div>
                        <div className="flex shrink-0 items-center gap-3">
                          {boolean ? (
                            <select
                              id={`setting-${key}`}
                              value={drafts[key] ?? setting.value}
                              onChange={(event) => setDrafts((current) => ({ ...current, [key]: event.target.value }))}
                              className="rounded-md border border-[var(--border)] bg-white px-3 py-2"
                            >
                              <option value="false">Nonaktif</option>
                              <option value="true">Aktif</option>
                            </select>
                          ) : (
                            <input
                              id={`setting-${key}`}
                              value={drafts[key] ?? setting.value}
                              onChange={(event) => setDrafts((current) => ({ ...current, [key]: event.target.value }))}
                              type={setting.value_type === "integer" || setting.value_type === "float" ? "number" : "text"}
                              min={setting.value_type === "integer" || setting.value_type === "float" ? "0" : undefined}
                              step={setting.value_type === "float" ? "0.01" : setting.value_type === "integer" ? "1" : undefined}
                              className="w-48 rounded-md border border-[var(--border)] bg-white px-3 py-2"
                            />
                          )}
                          <button
                            onClick={() => void save(key)}
                            disabled={saving !== null || drafts[key] === setting.value}
                            className="rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-white hover:bg-[var(--primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {saving === key ? "Menyimpan…" : "Simpan"}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        ) : null}
      </main>
    </WorkspaceShell>
  );
}
