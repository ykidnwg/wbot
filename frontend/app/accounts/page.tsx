"use client";

import { useEffect, useMemo, useState } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import {
  assignPersonaToTarget,
  getPersonas,
  getSocialConnections,
  getSocialProviderStatus,
  getSocialTargets,
  removePersonaAssignment,
  startFacebookOAuth,
  type Persona,
  type SocialConnection,
  type SocialProviderStatus,
  type SocialTarget,
} from "@/lib/api";

export default function AccountsPage() {
  const [connections, setConnections] = useState<SocialConnection[]>([]);
  const [targets, setTargets] = useState<SocialTarget[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [provider, setProvider] = useState<SocialProviderStatus | null>(null);
  const [filter, setFilter] = useState("");
  const [selectedTarget, setSelectedTarget] = useState<SocialTarget | null>(null);
  const [assignment, setAssignment] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    const [status, connectionRows, targetRows, personaRows] = await Promise.all([
      getSocialProviderStatus(),
      getSocialConnections(),
      getSocialTargets(),
      getPersonas(),
    ]);
    setProvider(status);
    setConnections(connectionRows);
    setTargets(targetRows);
    setPersonas(personaRows.filter((persona) => persona.status === "approved"));
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      load()
        .catch((requestError: unknown) => {
          if (requestError instanceof Error && requestError.message === "unauthorized") {
            window.location.assign("/login");
            return;
          }
          setError("Social accounts could not be loaded.");
        })
        .finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const filteredTargets = useMemo(
    () => targets.filter((target) => target.display_name.toLowerCase().includes(filter.toLowerCase())),
    [targets, filter],
  );

  async function connectFacebook() {
    setBusy(true);
    setError(null);
    try {
      const result = await startFacebookOAuth();
      window.location.assign(result.authorization_url);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error && requestError.message === "NEEDS_CREDENTIALS"
        ? "Meta credentials are not configured. Add them to the backend secret manager."
        : "Facebook connection could not be started.");
    } finally {
      setBusy(false);
    }
  }

  async function saveAssignment() {
    if (!selectedTarget) return;
    setBusy(true);
    setError(null);
    try {
      if (assignment) {
        await assignPersonaToTarget(selectedTarget.id, assignment);
        setTargets((current) => current.map((target) => target.id === selectedTarget.id
          ? { ...target, assigned_persona_id: assignment }
          : target));
        setNotice("Persona assignment saved.");
      } else {
        await removePersonaAssignment(selectedTarget.id);
        setTargets((current) => current.map((target) => target.id === selectedTarget.id
          ? { ...target, assigned_persona_id: null }
          : target));
        setNotice("Persona assignment removed.");
      }
    } catch {
      setError("Persona assignment could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  function selectTarget(target: SocialTarget) {
    setSelectedTarget(target);
    setAssignment(target.assigned_persona_id ?? "");
    setNotice(null);
  }

  return (
    <WorkspaceShell>
      <main className="mx-auto max-w-6xl px-5 py-8 md:px-8">
        <header className="flex flex-col justify-between gap-5 border-b border-[var(--border)] pb-6 md:flex-row md:items-end">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-700">Social operations</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">Social accounts</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
              Connect Facebook through official Meta OAuth, discover Pages, and assign approved personas to managed destinations.
            </p>
          </div>
          <button type="button" onClick={connectFacebook} disabled={busy} className="rounded-md bg-[var(--primary)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--primary-hover)] disabled:opacity-50">
            Connect Facebook
          </button>
        </header>

        {error && <div role="alert" className="mt-5 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>}
        {notice && <div role="status" className="mt-5 rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</div>}

        <section className="mt-7 grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-[var(--border)] bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Provider status</p>
            <p className="mt-3 text-lg font-semibold">{provider?.status ?? "Loading..."}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">Meta Graph {provider?.graph_api_version ?? "—"}</p>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Connected accounts</p>
            <p className="mt-3 text-2xl font-semibold">{connections.length}</p>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Managed Pages</p>
            <p className="mt-3 text-2xl font-semibold">{targets.length}</p>
          </div>
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-lg border border-[var(--border)] bg-white">
            <div className="flex flex-col gap-3 border-b border-[var(--border)] p-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="font-semibold">Managed destinations</h2>
                <p className="mt-1 text-sm text-[var(--muted)]">Only Pages returned by Meta are shown here.</p>
              </div>
              <input aria-label="Search Pages" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Search Pages" className="rounded-md border border-[var(--border)] px-3 py-2 text-sm" />
            </div>
            {loading ? <p className="p-5 text-sm text-[var(--muted)]">Loading accounts...</p> : filteredTargets.length === 0 ? (
              <div className="p-8 text-center">
                <p className="font-medium">No Pages connected</p>
                <p className="mt-2 text-sm text-[var(--muted)]">Connect a Facebook account to discover Pages you can manage.</p>
              </div>
            ) : (
              <ul className="divide-y divide-[var(--border)]">
                {filteredTargets.map((target) => (
                  <li key={target.id}>
                    <button type="button" onClick={() => selectTarget(target)} className={`flex w-full items-center justify-between gap-4 p-5 text-left hover:bg-slate-50 ${selectedTarget?.id === target.id ? "bg-blue-50" : ""}`}>
                      <span>
                        <span className="block font-medium">{target.display_name}</span>
                        <span className="mt-1 block text-xs text-[var(--muted)]">Facebook Page · {target.status}</span>
                      </span>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${target.assigned_persona_id ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                        {target.assigned_persona_id ? "Persona assigned" : "Unassigned"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <aside className="rounded-lg border border-[var(--border)] bg-white p-5">
            <h2 className="font-semibold">Persona assignment</h2>
            {!selectedTarget ? (
              <p className="mt-3 text-sm leading-6 text-[var(--muted)]">Select a managed Page to assign or change its approved persona.</p>
            ) : (
              <div className="mt-4">
                <p className="text-sm font-medium">{selectedTarget.display_name}</p>
                <label className="mt-5 grid gap-2 text-sm font-medium">
                  Approved persona
                  <select value={assignment} onChange={(event) => setAssignment(event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2">
                    <option value="">No persona</option>
                    {personas.map((persona) => <option key={persona.id} value={persona.id}>{persona.name}</option>)}
                  </select>
                </label>
                <button type="button" onClick={saveAssignment} disabled={busy} className="mt-5 w-full rounded-md bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50">
                  {busy ? "Saving..." : "Save assignment"}
                </button>
              </div>
            )}
          </aside>
        </section>
      </main>
    </WorkspaceShell>
  );
}
