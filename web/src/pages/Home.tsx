import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';

export function Home() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [patientDisplay, setPatientDisplay] = useState('');
  const [encounterId, setEncounterId] = useState('');
  const [patientId, setPatientId] = useState('');
  const [message, setMessage] = useState(
    "My eczema on my elbows is flaring and I can't sleep from the itch.",
  );
  const [reply, setReply] = useState('');
  const [transcript, setTranscript] = useState('');
  const [captureUrl, setCaptureUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState('');
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ok: false }));
  }, []);

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
      <p className="eyebrow">FlareCheck</p>
      <h1>Between-visit flare check-in</h1>
      <p className="lede">
        Speak or type. We chart into Medplum, send a short-lived secure photo link, and keep the
        clinician chart ready — not a diagnosis app.
      </p>

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
          <span className="eyebrow">Patient message (text)</span>
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
            <p className="lede">Open on a phone to photograph the flare. Bytes go to Medplum via the API proxy.</p>
          </div>
        ) : null}
      </div>
    </main>
  );
}
