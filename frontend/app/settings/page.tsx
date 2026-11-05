"use client";

import { useCallback, useEffect, useState } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import { Card, Notice, PageBody, PageHeader, SectionTitle, StatusBadge } from "@/components/page";
import {
  getProviders,
  getSettings,
  updateSetting,
  type ProviderStatus,
  type Setting,
} from "@/lib/api";

const sections: Array<{ title: string; hint: string; keys: string[] }> = [
  {
    title: "AI providers",
    hint: "Choose mock for local determinism or openai for a configured OpenAI-compatible API.",
    keys: [
      "caption_provider",
      "caption_model",
      "image_provider",
      "image_model",
      "openai_api_base",
    ],
  },
  {
    title: "Emergency controls",
    hint: "Kill switches are stored in PostgreSQL and are read by workers.",
    keys: ["generation_kill_switch", "publishing_kill_switch"],
  },
  {
    title: "Job limits",
    hint: "Concurrency and retry ceilings for background work.",
    keys: ["max_generation_concurrency", "max_publishing_concurrency", "max_retry_attempts"],
  },
  {
    title: "Generation budget (USD)",
    hint: "Budgets are recorded settings. No billing integration is connected yet.",
    keys: ["daily_generation_budget_usd", "monthly_generation_budget_usd"],
  },
  {
    title: "Workspace defaults",
    hint: "Timezone is used when a schedule does not specify one.",
    keys: ["default_timezone"],
  },
  {
    title: "Rate limits",
    hint: "Requests allowed per minute.",
    keys: ["rate_limit_login_per_minute", "rate_limit_api_per_minute"],
  },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const [result, providerRows] = await Promise.all([getSettings(signal), getProviders()]);
      setSettings(result);
      setProviders(providerRows);
      setDrafts(Object.fromEntries(result.map((item) => [item.key, item.value])));
      setError(null);
    } catch (requestError: unknown) {
      if (requestError instanceof Error && requestError.message === "unauthorized") {
        window.location.assign("/login");
        return;
      }
      setError("Settings could not be loaded. Reload the page and try again.");
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
      setSettings((current) => current.map((item) => (item.key === key ? updated : item)));
      setDrafts((current) => ({ ...current, [key]: updated.value }));
      setProviders(await getProviders());
      setNotice("Setting saved and written to the audit log.");
    } catch (requestError: unknown) {
      if (requestError instanceof Error && requestError.message === "unauthorized") {
        window.location.assign("/login");
        return;
      }
      setError(
        requestError instanceof Error && requestError.message !== "setting-update-failed"
          ? requestError.message
          : "The setting could not be saved. Check the value and try again.",
      );
    } finally {
      setSaving(null);
    }
  }

  return (
    <WorkspaceShell>
      <PageBody>
        <PageHeader
          eyebrow="Workspace controls"
          title="Configure the system, not the story."
          description="Provider selection, retry limits, timezone, and emergency switches are persisted in PostgreSQL. Secrets such as API keys stay in server environment variables and are never returned by the API."
        />

        {notice ? <div className="mt-5"><Notice tone="info">{notice}</Notice></div> : null}
        {error ? <div className="mt-5"><Notice>{error}</Notice></div> : null}

        {providers.length ? (
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {providers.map((provider) => (
              <div key={provider.id} className="card-flat p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold">{provider.label}</p>
                  <StatusBadge status={provider.status} />
                </div>
                <p className="mt-2 text-xs text-[var(--muted)]">{provider.model}</p>
                {provider.message ? <p className="mt-2 text-xs text-[var(--muted)]">{provider.message}</p> : null}
              </div>
            ))}
          </div>
        ) : null}

        {loading ? <p className="mt-6 text-sm text-[var(--muted)]">Loading settings…</p> : null}
        {!loading ? (
          <div className="mt-6 grid gap-5">
            {sections.map((section) => (
              <Card key={section.title}>
                <SectionTitle title={section.title} hint={section.hint} />
                <div className="divide-line">
                  {section.keys.map((key) => {
                    const setting = settings.find((item) => item.key === key);
                    if (!setting) return null;
                    const boolean = setting.value_type === "boolean";
                    const isProvider = key === "caption_provider" || key === "image_provider";
                    return (
                      <div key={key} className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <label htmlFor={`setting-${key}`} className="text-sm font-semibold">{key.replaceAll("_", " ")}</label>
                          <p className="mt-1 text-xs text-[var(--muted)]">{setting.description}</p>
                          <p className="mt-1 text-[0.66rem] text-[var(--muted)]">Updated {new Date(setting.updated_at).toLocaleString()}</p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          {boolean ? (
                            <select id={`setting-${key}`} value={drafts[key] ?? setting.value} onChange={(event) => setDrafts((current) => ({ ...current, [key]: event.target.value }))} className="field w-40">
                              <option value="false">Disabled</option>
                              <option value="true">Enabled</option>
                            </select>
                          ) : isProvider ? (
                            <select id={`setting-${key}`} value={drafts[key] ?? setting.value} onChange={(event) => setDrafts((current) => ({ ...current, [key]: event.target.value }))} className="field w-40">
                              <option value="mock">Mock</option>
                              <option value="openai">OpenAI-compatible</option>
                            </select>
                          ) : (
                            <input
                              id={`setting-${key}`}
                              value={drafts[key] ?? setting.value}
                              onChange={(event) => setDrafts((current) => ({ ...current, [key]: event.target.value }))}
                              type={setting.value_type === "integer" || setting.value_type === "float" ? "number" : "text"}
                              min={setting.value_type === "integer" || setting.value_type === "float" ? "0" : undefined}
                              step={setting.value_type === "float" ? "0.01" : setting.value_type === "integer" ? "1" : undefined}
                              className="field w-56"
                            />
                          )}
                          <button onClick={() => void save(key)} disabled={saving !== null || drafts[key] === setting.value} className="btn btn-primary">
                            {saving === key ? "Saving…" : "Save"}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>
            ))}
          </div>
        ) : null}
      </PageBody>
    </WorkspaceShell>
  );
}
