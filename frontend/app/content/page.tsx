"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import {
  decideContent,
  generateCaptionDraft,
  getContent,
  getPersonas,
  updateContentCaption,
  type ContentItem,
  type Persona,
} from "@/lib/api";

export default function ContentPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [items, setItems] = useState<ContentItem[]>([]);
  const [personaId, setPersonaId] = useState("");
  const [topic, setTopic] = useState("");
  const [platform, setPlatform] = useState("unassigned");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [captionDraft, setCaptionDraft] = useState("");

  async function reload(signal?: AbortSignal) {
    const [personaRows, contentRows] = await Promise.all([getPersonas(signal), getContent(signal)]);
    setPersonas(personaRows);
    setItems(contentRows);
  }

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      reload(controller.signal)
        .catch((requestError: unknown) => {
          if (requestError instanceof Error && requestError.message === "unauthorized") {
            window.location.assign("/login");
            return;
          }
          setError("Data content factory tidak dapat dimuat.");
        })
        .finally(() => setLoading(false));
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, []);

  async function createDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const item = await generateCaptionDraft({ persona_id: personaId, topic, platform });
      setItems((current) => [item, ...current]);
      setTopic("");
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Caption draft gagal dibuat.");
    } finally {
      setBusy(false);
    }
  }

  async function review(item: ContentItem, decision: "approved" | "rejected") {
    setBusy(true);
    setError(null);
    try {
      const updated = await decideContent(item.id, decision);
      setItems((current) => current.map((row) => (row.id === updated.id ? updated : row)));
    } catch {
      setError("Keputusan approval gagal disimpan.");
    } finally {
      setBusy(false);
    }
  }

  async function saveCaption(item: ContentItem) {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateContentCaption(item.id, captionDraft);
      setItems((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      setEditingId(null);
      setCaptionDraft("");
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Caption tidak dapat disimpan.");
    } finally {
      setBusy(false);
    }
  }

  const approvedPersonas = personas.filter((persona) => persona.status === "approved");

  return (
    <WorkspaceShell>
      <main className="mx-auto max-w-5xl px-5 py-8 md:px-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">Provider MOCK</p>
            <h1 className="mt-1 text-2xl font-bold tracking-tight">Content factory</h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--muted)]">
              Caption dibuat dengan template lokal deterministik, bukan AI eksternal. Mengubah caption
              selalu membuat versi baru dan membutuhkan approval ulang. Image generation dan publikasi belum dikonfigurasi.
            </p>
          </div>
        </div>

        <section className="mt-7 rounded-xl border border-[var(--border)] bg-white p-5">
          <h2 className="font-semibold">Buat draft caption</h2>
          <form onSubmit={createDraft} className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="grid gap-1.5 text-sm font-medium">
              Persona approved
              <select
                required
                value={personaId}
                onChange={(event) => setPersonaId(event.target.value)}
                className="rounded-md border border-[var(--border)] px-3 py-2"
              >
                <option value="">Pilih persona</option>
                {approvedPersonas.map((persona) => (
                  <option key={persona.id} value={persona.id}>{persona.name}</option>
                ))}
              </select>
            </label>
            <label className="grid gap-1.5 text-sm font-medium">
              Platform tujuan
              <select
                value={platform}
                onChange={(event) => setPlatform(event.target.value)}
                className="rounded-md border border-[var(--border)] px-3 py-2"
              >
                <option value="unassigned">Belum ditentukan</option>
                <option value="facebook">Facebook</option>
                <option value="instagram">Instagram</option>
                <option value="threads">Threads</option>
                <option value="x">X</option>
              </select>
            </label>
            <label className="grid gap-1.5 text-sm font-medium md:col-span-2">
              Topik konten
              <input
                required
                minLength={3}
                maxLength={500}
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
                placeholder="Contoh: ide outfit kasual untuk akhir pekan"
                className="rounded-md border border-[var(--border)] px-3 py-2"
              />
            </label>
            <div className="md:col-span-2">
              <button
                disabled={busy || approvedPersonas.length === 0}
                className="rounded-md bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Memproses…" : "Buat draft MOCK"}
              </button>
              {approvedPersonas.length === 0 && (
                <p className="mt-2 text-sm text-[var(--muted)]">Setujui persona dewasa terlebih dahulu.</p>
              )}
            </div>
          </form>
          {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
        </section>

        <section className="mt-7">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Draft dan riwayat</h2>
            <span className="text-sm text-[var(--muted)]">{items.length} item</span>
          </div>
          {loading ? (
            <p className="mt-4 rounded-lg border border-[var(--border)] bg-white p-5 text-sm text-[var(--muted)]">Memuat konten…</p>
          ) : items.length === 0 ? (
            <p className="mt-4 rounded-lg border border-dashed border-[var(--border)] bg-white p-7 text-center text-sm text-[var(--muted)]">Belum ada draft konten.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {items.map((item) => (
                <li key={item.id} className="rounded-xl border border-[var(--border)] bg-white p-5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-semibold">{item.topic}</p>
                      <p className="mt-1 text-xs text-[var(--muted)]">{item.platform} · {item.provider} · versi {item.version_no}</p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium">{item.status}</span>
                  </div>
                  {editingId === item.id ? (
                    <div className="mt-4 grid gap-2">
                      <label className="text-sm font-medium" htmlFor={`caption-${item.id}`}>Caption versi baru</label>
                      <textarea
                        id={`caption-${item.id}`}
                        value={captionDraft}
                        onChange={(event) => setCaptionDraft(event.target.value)}
                        maxLength={10000}
                        rows={5}
                        className="rounded-md border border-[var(--border)] px-3 py-2 text-sm"
                      />
                      <div className="flex gap-2">
                        <button disabled={busy || !captionDraft.trim()} onClick={() => void saveCaption(item)} className="rounded-md bg-blue-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">Simpan versi baru</button>
                        <button disabled={busy} onClick={() => setEditingId(null)} className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium">Batal</button>
                      </div>
                    </div>
                  ) : (
                    <p className="mt-4 whitespace-pre-wrap text-sm leading-6">{item.caption}</p>
                  )}
                  {editingId !== item.id && (item.status === "draft" || item.status === "approved" || item.status === "rejected") && (
                    <button
                      disabled={busy}
                      onClick={() => { setEditingId(item.id); setCaptionDraft(item.caption); }}
                      className="mt-4 rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium disabled:opacity-50"
                    >
                      Ubah caption
                    </button>
                  )}
                  {item.status === "draft" && (
                    <div className="mt-4 flex gap-2">
                      <button disabled={busy} onClick={() => void review(item, "approved")} className="rounded-md bg-emerald-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">Setujui draft</button>
                      <button disabled={busy} onClick={() => void review(item, "rejected")} className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium disabled:opacity-50">Tolak</button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </WorkspaceShell>
  );
}
