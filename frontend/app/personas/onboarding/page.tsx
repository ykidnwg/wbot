"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import {
  approveSelectedCandidates,
  createPersonaBatch,
  getPersonaBatch,
  getPersonaBatches,
  regenerateCandidate,
  type PersonaBatch,
  type PersonaBatchSummary,
  type PersonaCandidate,
  type PersonaCandidateInput,
} from "@/lib/api";

const blankCandidate = {
  target_label: "",
  name: "",
  age: 18,
  language: "Bahasa Indonesia",
  personality: "",
  target_audience: "",
  clothing_style: "",
  identity_description: "",
  caption_preferences: { style: "", disclosure: "" },
  image_provider: null,
  image_model: null,
  prompt_version: "persona-v1",
};

export default function PersonaOnboardingPage() {
  const [batchName, setBatchName] = useState("");
  const [candidateForm, setCandidateForm] = useState(blankCandidate);
  const [draftCandidates, setDraftCandidates] = useState<PersonaCandidateInput[]>([]);
  const [batches, setBatches] = useState<PersonaBatchSummary[]>([]);
  const [activeBatch, setActiveBatch] = useState<PersonaBatch | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      getPersonaBatches(controller.signal)
        .then(setBatches)
        .catch((requestError: unknown) => {
          if (requestError instanceof Error && requestError.message === "unauthorized") {
            window.location.assign("/login");
            return;
          }
          setError("Daftar batch tidak dapat dimuat.");
        })
        .finally(() => setLoading(false));
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, []);

  function updateCandidate<K extends keyof typeof blankCandidate>(key: K, value: (typeof blankCandidate)[K]) {
    setCandidateForm((current) => ({ ...current, [key]: value }));
  }

  function addCandidate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDraftCandidates((current) => [...current, candidateForm]);
    setCandidateForm(blankCandidate);
    setError(null);
    setNotice("Kandidat ditambahkan ke draft batch.");
  }

  async function saveBatch() {
    if (!batchName.trim() || draftCandidates.length === 0) {
      setError("Isi nama batch dan tambahkan setidaknya satu kandidat.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await createPersonaBatch(batchName, draftCandidates);
      setActiveBatch(created);
      setSelected(new Set(created.candidates.filter((item) => item.status === "draft").map((item) => item.id)));
      setDraftCandidates([]);
      setBatchName("");
      setBatches((current) => [
        { id: created.id, name: created.name, status: created.status, candidate_count: created.candidate_count, created_at: created.created_at, updated_at: created.updated_at },
        ...current,
      ]);
      setNotice("Batch tersimpan. Anda bisa melanjutkannya dari daftar batch kapan saja.");
    } catch (requestError: unknown) {
      if (requestError instanceof Error && requestError.message === "unauthorized") {
        window.location.assign("/login");
        return;
      }
      setError("Batch tidak dapat disimpan. Periksa umur dan kelengkapan kandidat.");
    } finally {
      setBusy(false);
    }
  }

  async function resumeBatch(batchId: string) {
    setBusy(true);
    setError(null);
    try {
      const batch = await getPersonaBatch(batchId);
      setActiveBatch(batch);
      setSelected(new Set(batch.candidates.filter((item) => item.status === "draft").map((item) => item.id)));
    } catch (requestError: unknown) {
      if (requestError instanceof Error && requestError.message === "unauthorized") {
        window.location.assign("/login");
        return;
      }
      setError("Batch tidak dapat dibuka kembali.");
    } finally {
      setBusy(false);
    }
  }

  async function approveSelected() {
    if (!activeBatch || selected.size === 0) return;
    if (!window.confirm(`Setujui ${selected.size} kandidat terpilih sebagai persona immutable?`)) return;
    setBusy(true);
    setError(null);
    try {
      const approvedCount = await approveSelectedCandidates(activeBatch.id, [...selected]);
      const refreshed = await getPersonaBatch(activeBatch.id);
      setActiveBatch(refreshed);
      setSelected(new Set());
      setBatches((current) => current.map((item) => item.id === refreshed.id
        ? { ...item, status: refreshed.status, candidate_count: refreshed.candidate_count }
        : item));
      setNotice(`${approvedCount} kandidat disetujui. Kandidat lain di batch tidak berubah.`);
    } catch (requestError: unknown) {
      if (requestError instanceof Error && requestError.message === "unauthorized") {
        window.location.assign("/login");
        return;
      }
      setError("Kandidat tidak dapat disetujui. Muat ulang batch lalu coba lagi.");
    } finally {
      setBusy(false);
    }
  }

  async function regenerate(candidate: PersonaCandidate) {
    if (!activeBatch) return;
    setError(null);
    try {
      await regenerateCandidate(activeBatch.id, candidate.id);
    } catch (requestError: unknown) {
      if (requestError instanceof Error && requestError.message === "unauthorized") {
        window.location.assign("/login");
        return;
      }
      setError("GENERATE ULANG belum tersedia: provider AI belum dikonfigurasi. Kandidat lain tetap tidak berubah.");
    }
  }

  return (
    <WorkspaceShell>
      <main className="mx-auto max-w-6xl p-5 md:p-10">
        <header className="border-b border-[var(--border)] pb-6">
          <p className="text-sm font-semibold tracking-wide text-blue-700">BULK PERSONA ONBOARDING</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Onboarding persona</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--muted)]">
            Simpan beberapa kandidat dalam satu batch dengan label target yang eksplisit. Approval hanya memproses kandidat terpilih;
            kandidat lainnya tetap draft. Candidate generation AI membutuhkan provider credentials.
          </p>
        </header>

        {notice ? <p role="status" className="mt-5 rounded-md bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p> : null}
        {error ? <p role="alert" className="mt-5 rounded-md bg-amber-50 p-3 text-sm text-amber-900">{error}</p> : null}

        <div className="mt-7 grid items-start gap-7 xl:grid-cols-[minmax(0,1fr)_minmax(350px,0.85fr)]">
          <section className="rounded-lg border border-[var(--border)] bg-white p-5">
            <h2 className="text-lg font-semibold">Draft batch baru</h2>
            <label className="mt-4 grid gap-1.5 text-sm font-medium">Nama batch
              <input value={batchName} onChange={(event) => setBatchName(event.target.value)} maxLength={160} className="rounded-md border border-[var(--border)] px-3 py-2" />
            </label>
            <form onSubmit={addCandidate} className="mt-5 grid gap-3 border-t border-slate-100 pt-5">
              <h3 className="font-medium">Kandidat persona</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="grid gap-1 text-sm">Label target
                  <input required value={candidateForm.target_label} onChange={(event) => updateCandidate("target_label", event.target.value)} placeholder="mis. FB Page · Lifestyle" className="rounded-md border border-[var(--border)] px-3 py-2" />
                </label>
                <label className="grid gap-1 text-sm">Nama
                  <input required value={candidateForm.name} onChange={(event) => updateCandidate("name", event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2" />
                </label>
                <label className="grid gap-1 text-sm">Umur (18+)
                  <input required type="number" min={18} max={120} value={candidateForm.age} onChange={(event) => updateCandidate("age", Number(event.target.value))} className="rounded-md border border-[var(--border)] px-3 py-2" />
                </label>
                <label className="grid gap-1 text-sm">Bahasa
                  <input required value={candidateForm.language} onChange={(event) => updateCandidate("language", event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2" />
                </label>
              </div>
              <label className="grid gap-1 text-sm">Deskripsi identitas
                <textarea required value={candidateForm.identity_description} onChange={(event) => updateCandidate("identity_description", event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2" rows={2} />
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="grid gap-1 text-sm">Kepribadian
                  <textarea required value={candidateForm.personality} onChange={(event) => updateCandidate("personality", event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2" rows={2} />
                </label>
                <label className="grid gap-1 text-sm">Target audiens
                  <textarea required value={candidateForm.target_audience} onChange={(event) => updateCandidate("target_audience", event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2" rows={2} />
                </label>
              </div>
              <label className="grid gap-1 text-sm">Gaya berpakaian
                <input required value={candidateForm.clothing_style} onChange={(event) => updateCandidate("clothing_style", event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2" />
              </label>
              <label className="grid gap-1 text-sm">Preferensi caption
                <input value={String(candidateForm.caption_preferences.style ?? "")} onChange={(event) => updateCandidate("caption_preferences", { ...candidateForm.caption_preferences, style: event.target.value })} className="rounded-md border border-[var(--border)] px-3 py-2" />
              </label>
              <button className="w-fit rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium hover:bg-slate-50">Tambah ke batch</button>
            </form>
            {draftCandidates.length > 0 ? (
              <div className="mt-5 rounded-md bg-slate-50 p-4">
                <p className="font-medium">Draft lokal · {draftCandidates.length} kandidat</p>
                <ul className="mt-2 grid gap-1 text-sm text-slate-700">
                  {draftCandidates.map((candidate, index) => <li key={`${candidate.name}-${index}`}>{candidate.target_label} — {candidate.name}, {candidate.age} tahun</li>)}
                </ul>
                <button onClick={() => void saveBatch()} disabled={busy} className="mt-4 rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy ? "Menyimpan…" : "Simpan draft batch"}</button>
              </div>
            ) : null}
          </section>

          <section>
            <h2 className="text-lg font-semibold">Batch tersimpan</h2>
            {loading ? <p className="mt-3 text-sm text-[var(--muted)]">Memuat batch…</p> : null}
            {!loading && batches.length === 0 ? <p className="mt-3 rounded-md border border-dashed border-[var(--border)] bg-white p-4 text-sm text-[var(--muted)]">Belum ada batch tersimpan.</p> : null}
            <div className="mt-3 grid gap-2">
              {batches.map((batch) => (
                <button key={batch.id} onClick={() => void resumeBatch(batch.id)} className={`flex items-center justify-between gap-3 rounded-md border bg-white p-4 text-left hover:border-blue-400 ${activeBatch?.id === batch.id ? "border-blue-500" : "border-[var(--border)]"}`}>
                  <span><span className="block font-medium">{batch.name}</span><span className="mt-1 block text-xs text-[var(--muted)]">{batch.candidate_count} kandidat · {batch.status === "draft" ? "Draft" : "Selesai"}</span></span>
                  <span className="text-sm text-blue-700">Lanjutkan</span>
                </button>
              ))}
            </div>

            {activeBatch ? (
              <section className="mt-6 rounded-lg border border-[var(--border)] bg-white p-5" aria-labelledby="active-batch-title">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div><p className="text-xs font-semibold tracking-wide text-blue-700">TARGET LABELS</p><h3 id="active-batch-title" className="mt-1 font-semibold">{activeBatch.name}</h3></div>
                  <button onClick={() => void approveSelected()} disabled={busy || selected.size === 0} className="rounded-md bg-emerald-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">Setujui yang dipilih ({selected.size})</button>
                </div>
                <div className="mt-4 grid gap-3">
                  {activeBatch.candidates.map((candidate) => (
                    <article key={candidate.id} className="rounded-md border border-slate-200 p-4">
                      <div className="flex items-start gap-3">
                        {candidate.status === "draft" ? (
                          <input
                            aria-label={`Pilih ${candidate.name}`}
                            type="checkbox"
                            checked={selected.has(candidate.id)}
                            onChange={(event) => setSelected((current) => {
                              const next = new Set(current);
                              if (event.target.checked) next.add(candidate.id);
                              else next.delete(candidate.id);
                              return next;
                            })}
                            className="mt-1 size-4"
                          />
                        ) : <span className="mt-1 size-4" aria-hidden="true" />}
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-blue-700">{candidate.target_label}</p>
                          <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
                            <h4 className="font-medium">{candidate.name} · {candidate.age} tahun</h4>
                            <span className="text-xs text-[var(--muted)]">{candidate.status === "approved" ? "Disetujui" : candidate.status === "draft" ? "Draft" : "Ditolak"}</span>
                          </div>
                          <p className="mt-2 text-sm text-slate-700">{candidate.identity_description}</p>
                          {candidate.status === "draft" ? <button onClick={() => void regenerate(candidate)} className="mt-3 text-sm font-medium text-blue-700 underline">Generate ulang</button> : null}
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}
          </section>
        </div>
      </main>
    </WorkspaceShell>
  );
}
