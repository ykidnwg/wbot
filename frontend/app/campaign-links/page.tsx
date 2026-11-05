"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { WorkspaceShell } from "@/components/workspace-shell";
import { Card, EmptyState, Notice, PageBody, PageHeader, SectionTitle, StatusBadge } from "@/components/page";
import {
  createCampaign,
  createCampaignLink,
  getCampaignLinks,
  getCampaigns,
  setCampaignStatus,
  type Campaign,
  type CampaignLink,
} from "@/lib/api";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [links, setLinks] = useState<CampaignLink[]>([]);
  const [name, setName] = useState("");
  const [destination, setDestination] = useState("");
  const [label, setLabel] = useState("");
  const [affiliateUrl, setAffiliateUrl] = useState("");
  const [utmSource, setUtmSource] = useState("facebook");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function loadCampaigns() {
    const rows = await getCampaigns();
    setCampaigns(rows);
    setSelectedId((current) => (current && rows.some((row) => row.id === current) ? current : rows[0]?.id ?? ""));
    return rows;
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadCampaigns()
        .catch((requestError: unknown) => {
          if (requestError instanceof Error && requestError.message === "unauthorized") {
            window.location.assign("/login");
            return;
          }
          setError("Campaigns could not be loaded.");
        })
        .finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      getCampaignLinks(selectedId, controller.signal)
        .then(setLinks)
        .catch((requestError: unknown) => {
          if (requestError instanceof Error && requestError.message !== "AbortError") {
            setError("Tracked links could not be loaded.");
          }
        });
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [selectedId]);

  const selected = campaigns.find((campaign) => campaign.id === selectedId) ?? null;

  async function submitCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const campaign = await createCampaign({
        name,
        platform: "facebook",
        destination_url: destination || undefined,
      });
      await loadCampaigns();
      setSelectedId(campaign.id);
      setName("");
      setDestination("");
      setNotice("Campaign created as a draft. Activate it when the destination is ready.");
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The campaign could not be created.");
    } finally {
      setBusy(false);
    }
  }

  async function submitLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await createCampaignLink(selectedId, {
        label,
        affiliate_url: affiliateUrl,
        utm_source: utmSource || undefined,
        utm_medium: "social",
        utm_campaign: selected?.name,
      });
      setLinks(await getCampaignLinks(selectedId));
      setLabel("");
      setAffiliateUrl("");
      setNotice("Tracked link created. Clicks are recorded first-party on this server.");
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The tracked link could not be created.");
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(status: string) {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await setCampaignStatus(selected.id, status);
      await loadCampaigns();
      setNotice(`Campaign marked ${status}.`);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The campaign status could not be changed.");
    } finally {
      setBusy(false);
    }
  }

  async function copyLink(link: CampaignLink) {
    const url = `${window.location.origin}${link.tracking_path}`;
    try {
      await navigator.clipboard.writeText(url);
      setNotice("Tracking URL copied. Use this URL in the published caption.");
    } catch {
      setError(`Copy failed. The tracking URL is ${url}`);
    }
  }

  return (
    <WorkspaceShell>
      <PageBody>
        <PageHeader
          eyebrow="Campaigns and links"
          title="Know which posts actually moved people."
          description="Create campaigns, attach affiliate destinations, and publish first-party tracking URLs. Click counts are recorded by this app, not imported from a platform."
        />

        <div className="mt-8 grid gap-6 lg:grid-cols-[0.85fr_1.4fr]">
          <div className="space-y-5">
            <Card>
              <SectionTitle title="New campaign" hint="Destination is optional; links carry the final URL." />
              <form onSubmit={submitCampaign} className="grid gap-3">
                <label className="label">
                  Campaign name
                  <input required minLength={2} maxLength={160} className="field" value={name} onChange={(event) => setName(event.target.value)} placeholder="Spring collection" />
                </label>
                <label className="label">
                  Primary destination
                  <input type="url" className="field" value={destination} onChange={(event) => setDestination(event.target.value)} placeholder="https://example.com/landing" />
                </label>
                <button disabled={busy} className="btn btn-primary">Create draft</button>
              </form>
              {error ? <div className="mt-3"><Notice>{error}</Notice></div> : null}
              {notice ? <div className="mt-3"><Notice tone="info">{notice}</Notice></div> : null}
            </Card>

            <Card>
              <SectionTitle title="Campaigns" hint={`${campaigns.length} total`} />
              {loading ? (
                <div className="h-20 animate-pulse rounded-[var(--radius-sm)] bg-[var(--surface-muted)]" />
              ) : campaigns.length === 0 ? (
                <EmptyState title="No campaigns yet" body="Create a campaign to group links and measure first-party clicks." />
              ) : (
                <ul className="divide-line">
                  {campaigns.map((campaign) => (
                    <li key={campaign.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(campaign.id)}
                        className={`flex w-full items-center justify-between gap-3 py-3 text-left ${
                          selectedId === campaign.id ? "text-[var(--accent-strong)]" : "text-[var(--ink-soft)]"
                        }`}
                      >
                        <span className="truncate text-sm font-semibold">{campaign.name}</span>
                        <StatusBadge status={campaign.status} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <Card>
            {selected ? (
              <>
                <SectionTitle
                  title={selected.name}
                  hint={`${selected.platform} · ${links.length} tracked link${links.length === 1 ? "" : "s"}`}
                  action={
                    <div className="flex gap-2">
                      {selected.status !== "active" ? (
                        <button type="button" disabled={busy} onClick={() => void changeStatus("active")} className="btn btn-accent">Activate</button>
                      ) : (
                        <button type="button" disabled={busy} onClick={() => void changeStatus("paused")} className="btn btn-secondary">Pause</button>
                      )}
                    </div>
                  }
                />

                <form onSubmit={submitLink} className="grid gap-3 rounded-[var(--radius-md)] bg-[var(--surface-muted)] p-4 md:grid-cols-2">
                  <label className="label">
                    Link label
                    <input required minLength={2} className="field" value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Instagram story" />
                  </label>
                  <label className="label">
                    Affiliate URL
                    <input required type="url" className="field" value={affiliateUrl} onChange={(event) => setAffiliateUrl(event.target.value)} placeholder="https://shop.example.com/product" />
                  </label>
                  <label className="label">
                    UTM source
                    <input className="field" value={utmSource} onChange={(event) => setUtmSource(event.target.value)} />
                  </label>
                  <div className="flex items-end">
                    <button disabled={busy} className="btn btn-primary w-full">Add tracked link</button>
                  </div>
                </form>

                <div className="mt-6">
                  {links.length === 0 ? (
                    <EmptyState title="No tracked links" body="Add a link to generate a short tracking path and an attributed destination URL." />
                  ) : (
                    <ul className="divide-line">
                      {links.map((link) => (
                        <li key={link.id} className="py-4 first:pt-0 last:pb-0">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-sm font-semibold">{link.label}</p>
                              <p className="mt-1 truncate text-xs text-[var(--muted)]">{link.destination_url}</p>
                              <code className="mt-2 inline-block rounded bg-[var(--paper-deep)] px-2 py-1 text-[0.7rem] text-[var(--ink-soft)]">{link.tracking_path}</code>
                            </div>
                            <button type="button" onClick={() => void copyLink(link)} className="btn btn-secondary">Copy tracking URL</button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </>
            ) : (
              <EmptyState title="Select a campaign" body="Choose a campaign to manage its tracked links and status." />
            )}
          </Card>
        </div>
      </PageBody>
    </WorkspaceShell>
  );
}
