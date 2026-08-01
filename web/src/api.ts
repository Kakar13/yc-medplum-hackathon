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
};

export const api = {
  health: () => json<Record<string, unknown>>('/health'),
  startSession: (message?: string) =>
    json<StartSession>('/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reason: 'Flare check-in — eczema / rash',
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
        reason: 'Eczema / rash flare photo',
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
