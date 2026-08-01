import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';

// The callback already tells us why authorization failed. Saying "check your credentials" for
// every reason sends you looking in the wrong place — a rejected scope and an expired link need
// completely different fixes.
function whoopError(reason: string | null): string {
  switch (reason) {
    case 'invalid_scope':
      return 'Whoop refused a scope this app is not granted. Enable read:recovery and read:sleep on the app in the Whoop developer dashboard.';
    case 'state_mismatch':
      return 'That Whoop link expired or was already used. Start the connection again.';
    case 'access_denied':
      return 'You declined the Whoop permission request. Retry and accept to connect.';
    case null:
      return 'Whoop authorization failed.';
    default:
      return `Whoop authorization failed (${reason}).`;
  }
}

export function Home() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [patientDisplay, setPatientDisplay] = useState('');
  const [encounterId, setEncounterId] = useState('');
  const [patientId, setPatientId] = useState('');
  const [message, setMessage] = useState(
    'My right knee has been swollen and painful for three weeks after I started running. ' +
      "It's a 6 out of 10, worse going downstairs, better with rest. No fever, no injury.",
  );
  const [redTeam, setRedTeam] = useState<{
    allowed: boolean;
    decision: string;
    reason: string;
    control: string;
  } | null>(null);
  const [reply, setReply] = useState('');
  const [transcript, setTranscript] = useState('');
  const [captureUrl, setCaptureUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState('');
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());
  const [whoop, setWhoop] = useState<{ configured: boolean; connected: boolean } | null>(null);
  const [wearableNote, setWearableNote] = useState('');
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ok: false }));
    api.whoopStatus().then(setWhoop).catch(() => setWhoop(null));
    const params = new URLSearchParams(window.location.search);
    const result = params.get('whoop');
    if (result === 'connected') setWearableNote('Whoop connected — pulling your latest recovery and sleep.');
    if (result === 'error') setError(whoopError(params.get('reason')));
  }, []);

  async function connectWhoop() {
    setError('');
    try {
      const { authorization_url } = await api.whoopAuthorize();
      window.location.href = authorization_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function pullWearable() {
    setBusy(true);
    setError('');
    try {
      const session = await ensureSession();
      const out = await api.wearablesToChart(session.patient_id, session.encounter_id);
      setEncounterId(out.encounter_id);
      setWearableNote(
        `${out.snapshot.provider} · risk ${out.snapshot.level} · ${out.observation_ids.length} FHIR Observations written` +
          (out.snapshot.reasons.length ? ` — ${out.snapshot.reasons.join('; ')}` : ''),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function runRedTeam() {
    setBusy(true);
    setError('');
    try {
      await ensureSession();
      setRedTeam(await api.redTeam());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function ensureSession() {
    if (patientId && encounterId) {
      return { patient_id: patientId, encounter_id: encounterId, patient_display: patientDisplay };
    }
    const session = await api.startSession();
    setPatientDisplay(session.patient_display);
    setEncounterId(session.encounter_id);
    setPatientId(session.patient_id);
    setThreadId(crypto.randomUUID());
    return session;
  }

  async function start() {
    setBusy(true);
    setError('');
    try {
      const session = await ensureSession();
      const turn = await api.turn(message, threadId);
      setReply(turn.reply);
      setTranscript('');
      const link = await api.createCaptureLink(session.patient_id, session.encounter_id);
      setCaptureUrl(link.url);
      setEncounterId(link.encounter_id || session.encounter_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function toggleMic() {
    setError('');
    if (recording && mediaRecorder.current) {
      mediaRecorder.current.stop();
      setRecording(false);
      return;
    }
    try {
      await ensureSession();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunks.current = [];
      rec.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunks.current.push(ev.data);
      };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks.current, { type: rec.mimeType || 'audio/webm' });
        setBusy(true);
        try {
          const out = await api.voiceTurn(blob, threadId);
          setTranscript(out.transcript || '');
          setReply(out.reply || '');
          if (out.session?.encounter_id) {
            setEncounterId(String(out.session.encounter_id));
          }
          if (out.session?.patient_id) {
            setPatientId(String(out.session.patient_id));
          }
          const pid = String(out.session?.patient_id || patientId);
          const eid = String(out.session?.encounter_id || encounterId);
          if (pid && eid) {
            const link = await api.createCaptureLink(pid, eid);
            setCaptureUrl(link.url);
          }
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e));
        } finally {
          setBusy(false);
        }
      };
      mediaRecorder.current = rec;
      rec.start();
      setRecording(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <main className="shell rise">
      <p className="eyebrow">Preflight</p>
      <h1>Check in before you're seen</h1>
      <p className="lede">
        Tell us what's going on, for anything — a knee, a cough, a rash, a worry. The
        conversation charts itself into Medplum, gets researched against real literature,
        and becomes a plan a clinician reviews before you arrive. Cost included.
      </p>

      <div className="row" style={{ marginTop: '1rem' }}>
        <Link className="btn ghost" to="/review">
          Clinician review queue
        </Link>
        <Link className="btn ghost" to="/trust">
          Trust &amp; governance
        </Link>
      </div>

      <div className="panel stack" style={{ marginTop: '2rem' }}>
        <div className="row">
          <span className="eyebrow">API</span>
          <span className="mono">
            {health
              ? `${health.product || 'agent'} · mode=${String(health.medplum_mode || health.agent_mode)} · deepgram=${String(health.deepgram)}`
              : '…'}
          </span>
        </div>

        <label className="stack">
          <span className="eyebrow">What brings you in? (speak or type)</span>
          <textarea value={message} onChange={(e) => setMessage(e.target.value)} />
        </label>

        <div className="row">
          <button type="button" onClick={start} disabled={busy || recording}>
            {busy && !recording ? 'Starting…' : 'Start with text'}
          </button>
          <button type="button" className={recording ? undefined : 'ghost'} onClick={toggleMic} disabled={busy && !recording}>
            {recording ? 'Stop & send voice' : 'Hold mic — Deepgram Nova-3'}
          </button>
          {encounterId ? (
            <Link className="btn ghost" to={`/chart/${encounterId}`}>
              Open clinician chart
            </Link>
          ) : null}
        </div>

        <div className="row">
          <span className="eyebrow">Wearable loop</span>
          {whoop?.connected ? (
            <span className="mono">whoop=connected</span>
          ) : (
            <button type="button" className="ghost" onClick={connectWhoop} disabled={!whoop?.configured}>
              {whoop?.configured ? 'Connect my Whoop' : 'Whoop app credentials needed'}
            </button>
          )}
          <button type="button" className="ghost" onClick={pullWearable} disabled={busy}>
            Pull signals into chart
          </button>
        </div>

        {wearableNote ? <p className="lede">{wearableNote}</p> : null}

        {error ? <p className="warn">{error}</p> : null}

        {patientDisplay ? (
          <p>
            Patient <strong>{patientDisplay}</strong>
            <span className="mono"> · Patient/{patientId}</span>
            <br />
            Encounter <span className="mono">{encounterId}</span>
          </p>
        ) : null}

        {transcript ? (
          <div className="stack">
            <span className="eyebrow">Transcript (Deepgram)</span>
            <div className="reply">{transcript}</div>
          </div>
        ) : null}

        {reply ? (
          <div className="stack">
            <span className="eyebrow">Agent</span>
            <div className="reply">{reply}</div>
          </div>
        ) : null}

        {captureUrl ? (
          <div className="stack">
            <span className="eyebrow">Secure capture link (15m · single-use)</span>
            <a className="mono" href={captureUrl}>
              {captureUrl}
            </a>
            <p className="lede">
              Open on a phone to photograph the finding. Bytes go to Medplum via the API
              proxy — the phone never holds a credential.
            </p>
          </div>
        ) : null}
      </div>

      <div className="panel stack" style={{ marginTop: '2rem' }}>
        <span className="eyebrow">Red team — HAARF RT-4, wrong patient</span>
        <p className="lede">
          Ask the agent to act on a different patient than its session is bound to. The
          published framework lets this through 94% of the time; here the subject of care
          isn't the model's to choose.
        </p>
        <div className="row">
          <button type="button" className="ghost" onClick={runRedTeam} disabled={busy}>
            Attempt order for SYN-003
          </button>
          {redTeam ? (
            <span className={redTeam.allowed ? 'warn mono' : 'mono'}>
              {redTeam.decision.toUpperCase()} · {redTeam.control}
            </span>
          ) : null}
        </div>
        {redTeam ? <div className="reply">{redTeam.reason}</div> : null}
      </div>
    </main>
  );
}
