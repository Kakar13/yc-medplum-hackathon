const API = import.meta.env.VITE_API_URL || 'http://localhost:8080';

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export type StartSession = {
  patient_id: string;
  patient_display: string;
  encounter_id: string;
  mode: string;
  turn?: { reply: string; handoff: boolean; session: Record<string, unknown> };
};

export type CaptureMeta = {
  token: string;
  patient_display: string;
  encounter_id: string;
  content_type: string;
  expires_at: number;
  proxy_upload_url: string;
  instructions: string;
};

export type ChartPayload = {
  mode: string;
  encounter: Record<string, unknown>;
  patient: Record<string, unknown>;
  observations: Record<string, unknown>[];
  compositions: Record<string, unknown>[];
  photos: {
    document_reference_id?: string;
    title?: string;
    url?: string;
    content_type?: string;
    binary_id?: string | null;
    preview_url?: string | null;
  }[];
  eligibility?: string;
  handoff_hint?: string;
  proposals?: Proposal[];
  research?: Citation[];
  capability?: Capability | null;
  periochart?: Periochart | null;
  monitoring?: Monitoring | null;
};

export type Citation = {
  title: string;
  authors?: string;
  journal?: string;
  year?: string;
  doi?: string;
  pmid?: string;
  cited_by?: number;
  open_access?: boolean;
  url?: string | null;
};

export type Proposal = {
  care_plan_id: string;
  title?: string;
  summary?: string;
  status?: string;
  intent?: string;
  author?: string;
  created?: string;
  encounter_id?: string;
  activities: (string | undefined)[];
  evidence: (string | undefined)[];
  task_id?: string;
  task_status?: string;
  reviewer?: string;
  awaiting_review?: boolean;
};

export type MonitoringNight = {
  date: string;
  level: string;
  score: number;
  reasons: string[];
  surfaced: boolean;
};

export type Monitoring = {
  available: boolean;
  reviewed?: number;
  surfaced?: number;
  suppressed?: number;
  context?: string;
  baseline?: Record<string, number | null>;
  nights?: MonitoringNight[];
};

export type PerioTooth = {
  number: number;
  name: string;
  quadrant_name: string;
  label: string;
  depths_mm: number[];
  max_depth_mm: number;
  bleeding_on_probing: boolean;
  severity: 'healthy' | 'early' | 'advanced';
  restoration: string;
  note: string;
  status: string;
  history: { date: string; event: string; detail: string; provider: string }[];
  focus: boolean;
};

export type Periochart = {
  system: string;
  months_since_prophylaxis: number;
  hygiene_due: boolean;
  alert: {
    tooth: number;
    label: string;
    status: string;
    headline: string;
    known_history: string;
    prior_events: number;
  } | null;
  teeth: PerioTooth[];
  summary: {
    advanced_sites: number[];
    pending_treatment: { tooth: number; plan: string; urgency: string }[];
  };
};

export type IdentityState = {
  verified: boolean;
  /** Set when a red flag ended the check early — the reason it was never completed. */
  bypassed?: string;
  identifiers_checked: number;
  name_match?: boolean;
  dob_match?: boolean;
  at: number;
};

export type Capability = {
  token: string;
  patient_id: string;
  encounter_id?: string | null;
  purpose_of_use: string;
  tools: string[];
  actor: string;
  on_behalf_of?: string | null;
  expires_at: number;
  expires_in_seconds: number;
  smart_scope: string;
};

export type AuditEntry = {
  at: number;
  bound_patient?: string | null;
  encounter_id?: string | null;
  purpose_of_use?: string | null;
  actor?: string;
  allowed: boolean;
  decision: string;
  reason: string;
  control: string;
  tool: string;
  requested_patient?: string | null;
  enforcing?: boolean;
  would_deny?: boolean;
};

export type Scorecard = {
  scenarios: {
    id: string;
    name: string;
    expected: string;
    rationale: string;
    verdict: string;
    haarf_published?: { metric: string; baseline: string; haarf: string };
    enforcing: { attempted: number; blocked: number; patient_boundary_blocked: number };
    observe_only: { blocked: number };
  }[];
  totals: {
    graded: number;
    correct: number;
    crossings_in_suite: number;
    crossings_blocked: number;
    false_positives: number;
    audited: number;
  };
};

export const api = {
  health: () => json<Record<string, unknown>>('/health'),
  startSession: (message?: string) =>
    json<StartSession>('/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reason: 'Pre-visit check-in',
        message: message || undefined,
      }),
    }),
  turn: (message: string, threadId?: string) =>
    json<{ reply: string; handoff: boolean; session: Record<string, unknown> }>('/turn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, thread_id: threadId }),
    }),
  createCaptureLink: (patientId?: string, encounterId?: string) =>
    json<{ url: string; token: string; encounter_id: string; expires_at: number }>('/capture-links', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        patient_id: patientId,
        encounter_id: encounterId,
        reason: 'Clinical photo for the visit',
      }),
    }),
  getCapture: (token: string, sig?: string | null) =>
    json<CaptureMeta>(`/capture/${token}${sig ? `?s=${encodeURIComponent(sig)}` : ''}`),
  uploadCapture: async (token: string, file: File, sig?: string | null) => {
    const form = new FormData();
    form.append('file', file);
    const qs = sig ? `?s=${encodeURIComponent(sig)}` : '';
    const res = await fetch(`${API}/capture/${token}/upload${qs}`, {
      method: 'POST',
      body: form,
      headers: sig ? { 'X-Capture-Sig': sig } : undefined,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{
      ok: boolean;
      encounter_id: string;
      document_reference_id?: string;
      media_id?: string;
      mode?: string;
    }>;
  },
  chart: (encounterId: string) => json<ChartPayload>(`/chart/${encounterId}`),
  whoopStatus: () =>
    json<{
      configured: boolean;
      connected: boolean;
      scope?: string;
      connected_at?: string;
      user?: Record<string, unknown> | null;
      redirect_uri?: string;
    }>('/wearables/whoop/status'),
  whoopAuthorize: () => json<{ authorization_url: string; state: string }>('/wearables/whoop/authorize'),
  whoopDisconnect: () => json<{ ok: boolean }>('/wearables/whoop/disconnect', { method: 'POST' }),
  wearableRisk: () =>
    json<{
      level: string;
      score: number;
      reasons: string[];
      provider: string;
      context: string;
      mode: string;
    }>('/wearables/risk'),
  wearablesToChart: (patientId?: string, encounterId?: string) =>
    json<{
      ok: boolean;
      patient_id: string;
      encounter_id: string;
      observation_ids: string[];
      level?: string;
      snapshot: { level: string; reasons: string[]; provider: string; mode: string };
    }>('/wearables/to-chart', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient_id: patientId, encounter_id: encounterId }),
    }),
  capability: () =>
    json<{
      active: Capability | null;
      enforcing: boolean;
      stats: Record<string, number | boolean>;
      identity: IdentityState | null;
      principle: string;
    }>('/capability'),
  audit: (limit = 100) =>
    json<{ entries: AuditEntry[]; stats: Record<string, number | boolean> }>(
      `/audit?limit=${limit}`,
    ),
  reviewQueue: () => json<{ proposals: Proposal[] }>('/review-queue'),
  review: (carePlanId: string, approve: boolean, reviewer = 'Dr. Reviewer', note = '') =>
    json<{ care_plan_id: string; status: string; reviewer: string; tasks_closed: string[] }>(
      `/review/${carePlanId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approve, reviewer, note }),
      },
    ),
  scorecard: () => json<Scorecard>('/haarf/scorecard'),
  redTeam: (
    tool = 'propose_care_plan',
    args: Record<string, unknown> = {
      mrn: 'SYN-003',
      medication: 'metoprolol',
      dose: '25mg PO BID',
    },
  ) =>
    json<{
      bound_patient: string | null;
      allowed: boolean;
      decision: string;
      reason: string;
      control: string;
      referenced_patients: string[];
    }>('/red-team/attempt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool, args }),
    }),
  voiceTurn: async (blob: Blob, threadId?: string) => {
    const form = new FormData();
    form.append('file', blob, 'mic.webm');
    if (threadId) form.append('thread_id', threadId);
    const res = await fetch(`${API}/voice/turn`, { method: 'POST', body: form });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<{
      transcript: string;
      confidence?: number;
      reply: string;
      handoff: boolean;
      session: Record<string, unknown>;
    }>;
  },
};

export { API };
