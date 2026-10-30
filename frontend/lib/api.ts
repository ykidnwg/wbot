export type DashboardSummary = {
  connected_accounts: number;
  active_personas: number;
  generated_images: number;
  pending_approval: number;
  scheduled_posts: number;
  published_posts: number;
  failed_posts: number;
  estimated_ai_cost: null;
  services: {
    database: "ok";
    worker: "ok" | "not_configured";
    queue: "ok" | "not_configured";
    providers: "ok" | "not_configured";
  };
};

export type Setting = {
  id: string;
  key: string;
  value: string;
  value_type: string;
  description: string | null;
  updated_at: string;
};

export async function getSettings(signal?: AbortSignal): Promise<Setting[]> {
  const response = await fetch("/api/backend/settings", { credentials: "same-origin", signal });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) throw new Error("settings-unavailable");
  const payload: { settings: Setting[] } = await response.json();
  return payload.settings;
}

export async function updateSetting(key: string, value: string): Promise<Setting> {
  const response = await fetch(`/api/backend/settings/${encodeURIComponent(key)}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) {
    const payload: { detail?: string } = await response.json();
    throw new Error(payload.detail ?? "setting-update-failed");
  }
  return (await response.json()) as Setting;
}

export type Persona = {
  id: string;
  owner_id: string;
  name: string;
  age: number;
  language: string;
  personality: string;
  target_audience: string;
  clothing_style: string;
  identity_description: string;
  caption_preferences: Record<string, unknown>;
  image_provider: string | null;
  image_model: string | null;
  prompt_version: string;
  status: "draft" | "approved" | "archived";
  version_no: number;
  created_at: string;
  updated_at: string;
};

export type ContentItem = {
  id: string;
  persona_id: string;
  generation_job_id: string;
  platform: string;
  topic: string;
  caption: string;
  provider: string;
  status: string;
  version_no: number;
  created_at: string;
  updated_at: string;
};

export type ContentVersion = {
  id: string;
  content_item_id: string;
  version_no: number;
  caption: string;
  provider: string;
  created_at: string;
};

export async function getContent(signal?: AbortSignal): Promise<ContentItem[]> {
  const response = await fetch("/api/backend/content", { credentials: "same-origin", signal });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) throw new Error("content-unavailable");
  const payload: { items: ContentItem[] } = await response.json();
  return payload.items;
}

export async function generateCaptionDraft(input: {
  persona_id: string;
  topic: string;
  platform: string;
}): Promise<ContentItem> {
  const response = await fetch("/api/backend/content/generate-caption", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) {
    const payload: { detail?: string } = await response.json();
    throw new Error(payload.detail ?? "caption-generation-failed");
  }
  return (await response.json()) as ContentItem;
}

export async function decideContent(
  contentId: string,
  decision: "approved" | "rejected",
): Promise<ContentItem> {
  const response = await fetch(`/api/backend/content/${encodeURIComponent(contentId)}/approval`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) throw new Error("content-approval-failed");
  return (await response.json()) as ContentItem;
}

export async function updateContentCaption(contentId: string, caption: string): Promise<ContentItem> {
  const response = await fetch(`/api/backend/content/${encodeURIComponent(contentId)}/caption`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ caption }),
  });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) {
    const payload: { detail?: string } = await response.json();
    throw new Error(payload.detail ?? "content-caption-update-failed");
  }
  return (await response.json()) as ContentItem;
}

export async function getContentVersions(contentId: string): Promise<ContentVersion[]> {
  const response = await fetch(`/api/backend/content/${encodeURIComponent(contentId)}/versions`, {
    credentials: "same-origin",
  });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) throw new Error("content-versions-unavailable");
  return (await response.json()) as ContentVersion[];
}

export type PersonaInput = Omit<Persona, "id" | "owner_id" | "status" | "version_no" | "created_at" | "updated_at">;
export type PersonaCandidateInput = PersonaInput & { target_label: string };
export type PersonaCandidate = PersonaCandidateInput & {
  id: string;
  batch_id: string;
  status: "draft" | "approved" | "rejected";
  persona_id: string | null;
  created_at: string;
};
export type PersonaBatchSummary = {
  id: string;
  name: string;
  status: "draft" | "completed";
  candidate_count: number;
  created_at: string;
  updated_at: string;
};
export type PersonaBatch = PersonaBatchSummary & { candidates: PersonaCandidate[] };

export async function getPersonas(signal?: AbortSignal): Promise<Persona[]> {
  const response = await fetch("/api/backend/personas", { credentials: "same-origin", signal });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) throw new Error("personas-unavailable");
  const payload: { items: Persona[] } = await response.json();
  return payload.items;
}

export async function createPersona(input: PersonaInput): Promise<Persona> {
  const response = await fetch("/api/backend/personas", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) {
    const payload: { detail?: string } = await response.json();
    throw new Error(payload.detail ?? "persona-create-failed");
  }
  return (await response.json()) as Persona;
}

export async function updatePersona(id: string, input: PersonaInput): Promise<Persona> {
  const response = await fetch(`/api/backend/personas/${encodeURIComponent(id)}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) {
    const payload: { detail?: string } = await response.json();
    throw new Error(payload.detail ?? "persona-update-failed");
  }
  return (await response.json()) as Persona;
}

export async function approvePersona(id: string): Promise<void> {
  const response = await fetch(`/api/backend/personas/${encodeURIComponent(id)}/approve`, {
    method: "POST",
    credentials: "same-origin",
  });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) throw new Error("persona-approval-failed");
}

export async function getPersonaBatches(signal?: AbortSignal): Promise<PersonaBatchSummary[]> {
  const response = await fetch("/api/backend/personas/batches", { credentials: "same-origin", signal });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) throw new Error("persona-batches-unavailable");
  const payload: { items: PersonaBatchSummary[] } = await response.json();
  return payload.items;
}

export async function getPersonaBatch(id: string): Promise<PersonaBatch> {
  const response = await fetch(`/api/backend/personas/batches/${encodeURIComponent(id)}`, { credentials: "same-origin" });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) throw new Error("persona-batch-unavailable");
  return (await response.json()) as PersonaBatch;
}

export async function createPersonaBatch(name: string, candidates: PersonaCandidateInput[]): Promise<PersonaBatch> {
  const response = await fetch("/api/backend/personas/batches", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, candidates }),
  });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) {
    const payload: { detail?: string } = await response.json();
    throw new Error(payload.detail ?? "persona-batch-create-failed");
  }
  return (await response.json()) as PersonaBatch;
}

export async function approveSelectedCandidates(batchId: string, candidateIds: string[]): Promise<number> {
  const response = await fetch(`/api/backend/personas/batches/${encodeURIComponent(batchId)}/approve-selected`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_ids: candidateIds }),
  });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) throw new Error("candidate-approval-failed");
  const payload: { approved_count: number } = await response.json();
  return payload.approved_count;
}

export async function regenerateCandidate(batchId: string, candidateId: string): Promise<void> {
  const response = await fetch(`/api/backend/personas/batches/${encodeURIComponent(batchId)}/candidates/${encodeURIComponent(candidateId)}/regenerate`, {
    method: "POST",
    credentials: "same-origin",
  });
  if (response.status === 401) throw new Error("unauthorized");
  if (!response.ok) {
    const payload: { detail?: string } = await response.json();
    throw new Error(payload.detail ?? "candidate-regeneration-unavailable");
  }
}

export async function login(email: string, password: string): Promise<void> {
  const response = await fetch("/api/backend/auth/login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (response.status === 401) {
    throw new Error("invalid-credentials");
  }
  if (!response.ok) {
    throw new Error("login-failed");
  }
}

export async function getDashboardSummary(signal?: AbortSignal): Promise<DashboardSummary> {
  const response = await fetch("/api/backend/dashboard/summary", {
    credentials: "same-origin",
    signal,
  });
  if (response.status === 401) {
    throw new Error("unauthorized");
  }
  if (!response.ok) {
    throw new Error("dashboard-unavailable");
  }
  return (await response.json()) as DashboardSummary;
}
