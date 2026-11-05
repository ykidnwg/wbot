"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import { Card, EmptyState, Notice, PageBody, PageHeader, SectionTitle, StatusBadge } from "@/components/page";
import {
  attachContentMedia,
  decideContent,
  generateCaptionDraft,
  getContent,
  getMedia,
  getPersonas,
  updateContentCaption,
  type ContentItem,
  type MediaAsset,
  type Persona,
} from "@/lib/api";

export default function ContentPage() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [media, setMedia] = useState<MediaAsset[]>([]);
  const [items, setItems] = useState<ContentItem[]>([]);
  const [personaId, setPersonaId] = useState("");
  const [topic, setTopic] = useState("");
  const [platform, setPlatform] = useState("facebook");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [captionDraft, setCaptionDraft] = useState("");

  async function reload(signal?: AbortSignal) {
    const [personaRows, contentRows, mediaRows] = await Promise.all([
      getPersonas(signal),
      getContent(signal),
      getMedia(signal),
    ]);
    setPersonas(personaRows);
    setItems(contentRows);
    setMedia(mediaRows);
  }

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void reload(controller.signal)
        .catch((requestError: unknown) => {
          if (requestError instanceof Error && requestError.message === "unauthorized") {
            window.location.assign("/login");
            return;
          }
          setError("The content studio could not be loaded.");
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
      setError(
        requestError instanceof Error && requestError.message === "NEEDS_CREDENTIALS"
          ? "The caption provider needs an API key on the server."
          : requestError instanceof Error
            ? requestError.message
            : "The caption draft could not be created.",
      );
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
      setError("The approval decision could not be saved.");
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
      setError(requestError instanceof Error ? requestError.message : "The caption could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function attachMedia(item: ContentItem, mediaAssetId: string) {
    setBusy(true);
    setError(null);
    try {
      const updated = await attachContentMedia(item.id, mediaAssetId || null);
      setItems((current) => current.map((row) => (row.id === updated.id ? updated : row)));
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The media could not be attached.");
    } finally {
      setBusy(false);
    }
  }

  const approvedPersonas = personas.filter((persona) => persona.status === "approved");
  const mediaById = new Map(media.map((asset) => [asset.id, asset]));

  return (
    <WorkspaceShell>
      <PageBody>
        <PageHeader
          eyebrow="Content studio"
          title="Draft with speed. Publish with evidence."
          description="Captions are versioned and must be approved before scheduling. Editing a caption creates a new version and returns it to draft, so an old approval can never leak into a new post."
          action={<span className="badge badge-neutral">Immutable versions</span>}
        />

        <div className="mt-8 grid gap-6 lg:grid-cols-[0.8fr_1.5fr]">
          <Card>
            <SectionTitle title="New caption draft" hint="The active provider is shown on every generated item." />
            <form onSubmit={createDraft} className="grid gap-4">
              <label className="label">
                Approved persona
                <select required className="field" value={personaId} onChange={(event) => setPersonaId(event.target.value)}>
                  <option value="">Select persona</option>
                  {approvedPersonas.map((persona) => (
                    <option key={persona.id} value={persona.id}>{persona.name}</option>
                  ))}
                </select>
              </label>
              <label className="label">
                Platform
                <select className="field" value={platform} onChange={(event) => setPlatform(event.target.value)}>
                  <option value="facebook">Facebook</option>
                  <option value="instagram">Instagram</option>
                  <option value="threads">Threads</option>
                  <option value="x">X</option>
                  <option value="unassigned">Unassigned</option>
                </select>
              </label>
              <label className="label">
                Topic
                <input required minLength={3} maxLength={500} className="field" value={topic} onChange={(event) => setTopic(event.target.value)} placeholder="A quiet morning routine for a slow weekend" />
              </label>
              <button disabled={busy || !approvedPersonas.length} className="btn btn-accent w-full">
                {busy ? "Drafting…" : "Generate caption"}
              </button>
              {!approvedPersonas.length ? <p className="text-xs text-[var(--muted)]">Approve an adult persona before generating content.</p> : null}
              {error ? <Notice>{error}</Notice> : null}
            </form>
          </Card>

          <section className="card p-5 md:p-6">
            <SectionTitle title="Drafts and history" hint={`${items.length} item${items.length === 1 ? "" : "s"} in this workspace`} />
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((key) => <div key={key} className="h-24 animate-pulse rounded-[var(--radius-md)] bg-[var(--surface-muted)]" />)}
              </div>
            ) : items.length === 0 ? (
              <EmptyState title="No drafts yet" body="Generate a caption to start the approval workflow. Media can be attached before scheduling." />
            ) : (
              <ul className="divide-line">
                {items.map((item) => {
                  const asset = item.media_asset_id ? mediaById.get(item.media_asset_id) : null;
                  return (
                    <li key={item.id} className="py-5 first:pt-0 last:pb-0">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold">{item.topic}</p>
                          <p className="mt-1 text-[0.68rem] text-[var(--muted)]">
                            {item.platform} · {item.provider} · version {item.version_no}
                          </p>
                        </div>
                        <StatusBadge status={item.status} />
                      </div>

                      {asset ? (
                        <div className="mt-3 flex items-center gap-3 rounded-[var(--radius-sm)] bg-[var(--surface-muted)] p-2">
                          <Image src={`/api/backend/media/${asset.id}/preview`} alt={asset.prompt} width={64} height={64} unoptimized className="h-14 w-14 rounded object-cover" />
                          <p className="line-clamp-2 text-xs text-[var(--muted)]">{asset.prompt}</p>
                        </div>
                      ) : null}

                      {editingId === item.id ? (
                        <div className="mt-4 grid gap-2">
                          <label className="label" htmlFor={`caption-${item.id}`}>New caption version</label>
                          <textarea id={`caption-${item.id}`} value={captionDraft} onChange={(event) => setCaptionDraft(event.target.value)} maxLength={10000} rows={5} className="field" />
                          <div className="flex gap-2">
                            <button disabled={busy || !captionDraft.trim()} onClick={() => void saveCaption(item)} className="btn btn-primary">Save new version</button>
                            <button disabled={busy} onClick={() => setEditingId(null)} className="btn btn-secondary">Cancel</button>
                          </div>
                        </div>
                      ) : (
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[var(--ink-soft)]">{item.caption}</p>
                      )}

                      <div className="mt-4 flex flex-wrap items-center gap-2">
                        {editingId !== item.id && ["draft", "approved", "rejected"].includes(item.status) ? (
                          <button disabled={busy} onClick={() => { setEditingId(item.id); setCaptionDraft(item.caption); }} className="btn btn-secondary">Edit caption</button>
                        ) : null}
                        {item.status === "draft" ? (
                          <>
                            <button disabled={busy} onClick={() => void review(item, "approved")} className="btn btn-primary">Approve</button>
                            <button disabled={busy} onClick={() => void review(item, "rejected")} className="btn btn-secondary">Reject</button>
                          </>
                        ) : null}
                        {["draft", "approved", "rejected"].includes(item.status) ? (
                          <select
                            aria-label="Attach media"
                            disabled={busy}
                            value={item.media_asset_id ?? ""}
                            onChange={(event) => void attachMedia(item, event.target.value)}
                            className="rounded-full border border-[var(--line-strong)] bg-transparent px-3 py-2 text-xs font-semibold text-[var(--ink-soft)]"
                          >
                            <option value="">No media</option>
                            {media.map((option) => (
                              <option key={option.id} value={option.id}>{option.prompt.slice(0, 48)}</option>
                            ))}
                          </select>
                        ) : null}
                        {item.status === "approved" ? (
                          <Link href="/calendar" className="btn btn-accent">Schedule</Link>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </div>
      </PageBody>
    </WorkspaceShell>
  );
}
