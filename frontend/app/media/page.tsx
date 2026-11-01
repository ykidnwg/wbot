"use client";

import { useEffect, useState } from "react";
import Image from "next/image";

import { WorkspaceShell } from "@/components/workspace-shell";
import { generateImage, getMedia, getPersonas, type MediaAsset, type Persona } from "@/lib/api";

export default function MediaPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [personaId, setPersonaId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getPersonas(), getMedia()])
      .then(([personaRows, mediaRows]) => {
        setPersonas(personaRows.filter((persona) => persona.status === "approved"));
        setAssets(mediaRows);
      })
      .catch((requestError: unknown) => {
        if (requestError instanceof Error && requestError.message === "unauthorized") {
          window.location.assign("/login");
          return;
        }
        setError("Media library tidak dapat dimuat.");
      })
      .finally(() => setLoading(false));
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const asset = await generateImage({ persona_id: personaId, prompt });
      setAssets((current) => [asset, ...current]);
      setPrompt("");
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Image generation gagal.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <WorkspaceShell>
      <main className="mx-auto max-w-5xl px-5 py-8 md:px-8">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">Provider MOCK</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">Image generation & media library</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Output lokal deterministik untuk pengujian workflow. Belum ada provider berbayar atau konsistensi wajah.
        </p>
        <form onSubmit={submit} className="mt-7 grid gap-4 rounded-xl border border-[var(--border)] bg-white p-5">
          <label className="grid gap-1.5 text-sm font-medium">
            Persona approved
            <select required value={personaId} onChange={(event) => setPersonaId(event.target.value)} className="rounded-md border border-[var(--border)] px-3 py-2">
              <option value="">Pilih persona</option>
              {personas.map((persona) => <option key={persona.id} value={persona.id}>{persona.name}</option>)}
            </select>
          </label>
          <label className="grid gap-1.5 text-sm font-medium">
            Prompt adegan
            <textarea required minLength={3} value={prompt} onChange={(event) => setPrompt(event.target.value)} className="min-h-24 rounded-md border border-[var(--border)] px-3 py-2" />
          </label>
          <button disabled={busy || personas.length === 0} className="w-fit rounded-md bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
            {busy ? "Memproses..." : "Buat gambar MOCK"}
          </button>
          {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        </form>
        <section className="mt-7">
          <h2 className="font-semibold">Asset tersimpan</h2>
          {loading ? <p className="mt-4 text-sm text-[var(--muted)]">Memuat media...</p> : assets.length === 0 ? (
            <p className="mt-4 rounded-lg border border-dashed border-[var(--border)] p-7 text-center text-sm text-[var(--muted)]">Belum ada asset.</p>
          ) : (
            <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {assets.map((asset) => (
                <li key={asset.id} className="overflow-hidden rounded-xl border border-[var(--border)] bg-white">
                  <Image
                    src={`/api/backend/media/${asset.id}/preview`}
                    alt={asset.prompt}
                    width={1}
                    height={1}
                    unoptimized
                    className="aspect-square w-full object-cover"
                  />
                  <div className="p-4 text-sm">
                    <p className="font-medium">{asset.prompt}</p>
                    <p className="mt-1 text-xs text-[var(--muted)]">{asset.provider}/{asset.model} · {asset.width}x{asset.height}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </WorkspaceShell>
  );
}
