"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { FormEvent } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import {
  approvePersona,
  createPersona,
  getPersonas,
  type Persona,
  type PersonaInput,
  updatePersona,
} from "@/lib/api";

const emptyForm: PersonaInput = {
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

export default function PersonasPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [form, setForm] = useState<PersonaInput>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      getPersonas(controller.signal)
        .then(setPersonas)
        .catch((requestError: unknown) => {
          if (requestError instanceof Error && requestError.message === "unauthorized") {
            window.location.assign("/login");
            return;
          }
          setError("Data persona gagal dimuat.");
        })
        .finally(() => setLoading(false));
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, []);

  function updateField<K extends keyof PersonaInput>(key: K, value: PersonaInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const persona = editingId ? await updatePersona(editingId, form) : await createPersona(form);
      setPersonas((current) => editingId
        ? current.map((item) => item.id === persona.id ? persona : item)
        : [persona, ...current]);
      setEditingId(null);
      setForm(emptyForm);
      setNotice(editingId ? "Perubahan draft persona tersimpan." : "Draft persona tersimpan.");
    } catch (requestError: unknown) {
      if (requestError instanceof Error && requestError.message === "unauthorized") {
        window.location.assign("/login");
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "Draft persona gagal disimpan.");
    } finally {
      setSaving(false);
    }
  }

  async function approve(persona: Persona) {
    if (!window.confirm(`Setujui persona ${persona.name} versi ${persona.version_no + 1}? Versi yang disetujui tidak dapat diedit.`)) return;
    setError(null);
    setNotice(null);
    try {
      await approvePersona(persona.id);
      setPersonas((current) => current.map((item) => item.id === persona.id
        ? { ...item, status: "approved", version_no: item.version_no + 1 }
        : item));
      setNotice(`Persona ${persona.name} telah disetujui sebagai versi ${persona.version_no + 1}.`);
    } catch (requestError: unknown) {
      if (requestError instanceof Error && requestError.message === "unauthorized") {
        window.location.assign("/login");
        return;
      }
      setError("Persona tidak dapat disetujui. Muat ulang daftar dan coba lagi.");
    }
  }

  return (
    <WorkspaceShell>
      <main className="mx-auto max-w-6xl p-5 md:p-10">
        <header className="border-b border-[var(--border)] pb-6">
          <p className="text-sm font-semibold tracking-wide text-blue-700">KARAKTER FIKTIF DEWASA</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Persona AI</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--muted)]">
            Buat profil persona berumur minimal 18 tahun. Draft bisa diedit; persetujuan menyimpan snapshot versi immutable.
            Provider gambar belum dikonfigurasi dan tidak ada gambar yang diklaim telah dibuat.
          </p>
          <Link href="/personas/onboarding" className="mt-4 inline-flex rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium hover:bg-white">
            Buka bulk onboarding
          </Link>
        </header>

        {notice ? <p role="status" className="mt-5 rounded-md bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p> : null}
        {error ? <p role="alert" className="mt-5 rounded-md bg-red-50 p-3 text-sm text-[var(--danger)]">{error}</p> : null}

        <div className="mt-7 grid items-start gap-7 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
          <section className="rounded-lg border border-[var(--border)] bg-white p-5">
            <h2 className="text-lg font-semibold">{editingId ? "Lanjutkan draft persona" : "Buat persona draft"}</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">Semua field profil disimpan per workspace. Umur divalidasi di UI, API, dan database.</p>
            <form onSubmit={(event) => void submit(event)} className="mt-5 grid gap-4">
              <label className="grid gap-1.5 text-sm font-medium">Nama
                <input required maxLength={120} value={form.name} onChange={(event) => updateField("name", event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2" />
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="grid gap-1.5 text-sm font-medium">Umur (18+)
                  <input required type="number" min={18} max={120} value={form.age} onChange={(event) => updateField("age", Number(event.target.value))} className="rounded-md border border-[var(--border)] px-3 py-2" />
                </label>
                <label className="grid gap-1.5 text-sm font-medium">Bahasa
                  <input required maxLength={80} value={form.language} onChange={(event) => updateField("language", event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2" />
                </label>
              </div>
              <label className="grid gap-1.5 text-sm font-medium">Deskripsi identitas
                <textarea required maxLength={4000} rows={3} value={form.identity_description} onChange={(event) => updateField("identity_description", event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2" />
              </label>
              <label className="grid gap-1.5 text-sm font-medium">Kepribadian
                <textarea required maxLength={4000} rows={3} value={form.personality} onChange={(event) => updateField("personality", event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2" />
              </label>
              <label className="grid gap-1.5 text-sm font-medium">Target audiens
                <textarea required maxLength={2000} rows={2} value={form.target_audience} onChange={(event) => updateField("target_audience", event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2" />
              </label>
              <label className="grid gap-1.5 text-sm font-medium">Gaya berpakaian
                <textarea required maxLength={2000} rows={2} value={form.clothing_style} onChange={(event) => updateField("clothing_style", event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2" />
              </label>
              <label className="grid gap-1.5 text-sm font-medium">Preferensi caption
                <textarea maxLength={1000} rows={2} value={String(form.caption_preferences.style ?? "")} onChange={(event) => updateField("caption_preferences", { ...form.caption_preferences, style: event.target.value })} className="rounded-md border border-[var(--border)] px-3 py-2" placeholder="Contoh: santai, informatif, tanpa klaim berlebihan" />
              </label>
              <button disabled={saving} className="w-fit rounded-md bg-[var(--primary)] px-4 py-2.5 text-sm font-medium text-white hover:bg-[var(--primary-hover)] disabled:opacity-60">
                {saving ? "Menyimpan…" : editingId ? "Simpan perubahan" : "Simpan draft"}
              </button>
              {editingId ? <button type="button" onClick={() => { setEditingId(null); setForm(emptyForm); }} className="w-fit rounded-md px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">Batal mengedit</button> : null}
            </form>
          </section>

          <section aria-labelledby="persona-list-heading">
            <h2 id="persona-list-heading" className="text-lg font-semibold">Persona tersimpan <span className="text-sm font-normal text-[var(--muted)]">({personas.length})</span></h2>
            {loading ? <p className="mt-4 text-sm text-[var(--muted)]">Memuat persona…</p> : null}
            {!loading && personas.length === 0 ? (
              <div className="mt-4 rounded-lg border border-dashed border-[var(--border)] bg-white p-6 text-sm text-[var(--muted)]">
                Belum ada persona. Persona yang dibuat di form akan muncul di sini sebagai draft, tanpa data demo.
              </div>
            ) : null}
            <div className="mt-4 grid gap-3">
              {personas.map((persona) => (
                <article key={persona.id} className="rounded-lg border border-[var(--border)] bg-white p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold">{persona.name}</h3>
                      <p className="mt-1 text-sm text-[var(--muted)]">{persona.age} tahun · {persona.language}</p>
                    </div>
                    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${persona.status === "approved" ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-700"}`}>
                      {persona.status === "approved" ? `Disetujui · v${persona.version_no}` : "Draft"}
                    </span>
                  </div>
                  <p className="mt-3 line-clamp-3 text-sm text-slate-700">{persona.identity_description}</p>
                  {persona.status === "draft" ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        onClick={() => {
                          setEditingId(persona.id);
                          setForm({
                            name: persona.name,
                            age: persona.age,
                            language: persona.language,
                            personality: persona.personality,
                            target_audience: persona.target_audience,
                            clothing_style: persona.clothing_style,
                            identity_description: persona.identity_description,
                            caption_preferences: persona.caption_preferences,
                            image_provider: persona.image_provider,
                            image_model: persona.image_model,
                            prompt_version: persona.prompt_version,
                          });
                        }}
                        className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium hover:bg-slate-50"
                      >
                        Lanjutkan draft
                      </button>
                      <button onClick={() => void approve(persona)} className="rounded-md border border-emerald-700 px-3 py-2 text-sm font-medium text-emerald-800 hover:bg-emerald-50">
                        Setujui dan bekukan versi
                      </button>
                    </div>
                  ) : (
                    <p className="mt-4 text-xs text-[var(--muted)]">Versi immutable · {persona.prompt_version}</p>
                  )}
                </article>
              ))}
            </div>
          </section>
        </div>
      </main>
    </WorkspaceShell>
  );
}
