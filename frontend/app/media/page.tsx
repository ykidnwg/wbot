"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import { Card, EmptyState, Notice, PageBody, PageHeader, SectionTitle, StatusBadge } from "@/components/page";
import { generateImage, getMedia, getPersonas, type MediaAsset, type Persona } from "@/lib/api";

export default function MediaPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [personaId, setPersonaId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [aspectRatio, setAspectRatio] = useState("square");
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
        setError("The media library could not be loaded.");
      })
      .finally(() => setLoading(false));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const asset = await generateImage({
        persona_id: personaId,
        prompt,
        aspect_ratio: aspectRatio,
      });
      setAssets((current) => [asset, ...current]);
      setPrompt("");
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error && requestError.message === "NEEDS_CREDENTIALS"
          ? "The selected image provider needs an API key on the server."
          : requestError instanceof Error
            ? requestError.message
            : "Image generation failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <WorkspaceShell>
      <PageBody>
        <PageHeader
          eyebrow="Media library"
          title="Images that stay inside the workspace."
          description="Generated images are validated, checksummed, and stored owner-scoped. The mock provider produces a local image; a live OpenAI-compatible provider is used only when configured with a key."
          action={<span className="badge badge-accent">Validated storage</span>}
        />

        <div className="mt-8 grid gap-6 lg:grid-cols-[0.8fr_1.4fr]">
          <Card>
            <SectionTitle title="Generate an image" hint="Portrait and landscape sizes map to documented provider sizes." />
            <form onSubmit={submit} className="grid gap-4">
              <label className="label">
                Approved persona
                <select required className="field" value={personaId} onChange={(event) => setPersonaId(event.target.value)}>
                  <option value="">Select persona</option>
                  {personas.map((persona) => <option key={persona.id} value={persona.id}>{persona.name}</option>)}
                </select>
              </label>
              <label className="label">
                Scene prompt
                <textarea required minLength={3} maxLength={4000} className="field min-h-28" value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="A calm editorial portrait in warm morning light" />
              </label>
              <label className="label">
                Aspect ratio
                <select className="field" value={aspectRatio} onChange={(event) => setAspectRatio(event.target.value)}>
                  <option value="square">Square · 1:1</option>
                  <option value="portrait">Portrait · 2:3</option>
                  <option value="vertical">Vertical · 9:16</option>
                  <option value="landscape">Landscape · 3:2</option>
                </select>
              </label>
              <button disabled={busy || !personas.length} className="btn btn-accent w-full">
                {busy ? "Generating…" : "Generate image"}
              </button>
              {!personas.length ? <p className="text-xs text-[var(--muted)]">Approve a persona first.</p> : null}
              {error ? <Notice>{error}</Notice> : null}
            </form>
          </Card>

          <section className="card p-5 md:p-6">
            <SectionTitle
              title="Stored assets"
              hint={`${assets.length} image${assets.length === 1 ? "" : "s"} · previews are served from the backend`}
            />
            {loading ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {[1, 2].map((key) => <div key={key} className="h-48 animate-pulse rounded-[var(--radius-md)] bg-[var(--surface-muted)]" />)}
              </div>
            ) : assets.length === 0 ? (
              <EmptyState title="No images yet" body="Generate an image to populate the owner-scoped media library." />
            ) : (
              <ul className="grid gap-4 sm:grid-cols-2">
                {assets.map((asset) => (
                  <li key={asset.id} className="overflow-hidden rounded-[var(--radius-md)] border border-[var(--line)] bg-[var(--surface-muted)]">
                    <Image
                      src={`/api/backend/media/${asset.id}/preview`}
                      alt={asset.prompt}
                      width={asset.width}
                      height={asset.height}
                      unoptimized
                      className="aspect-[4/3] w-full object-cover"
                    />
                    <div className="p-4">
                      <p className="line-clamp-2 text-sm font-medium leading-5">{asset.prompt}</p>
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <p className="text-[0.68rem] text-[var(--muted)]">{asset.width} × {asset.height} · {asset.mime_type}</p>
                        <StatusBadge status={asset.provider} />
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </PageBody>
    </WorkspaceShell>
  );
}
