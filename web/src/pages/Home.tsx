import { useEffect, useState } from 'react';
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
  const [captureUrl, setCaptureUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ok: false }));
  }, []);

  async function start() {
    setBusy(true);
    setError('');
    try {
      const session = await api.startSession();
      setPatientDisplay(session.patient_display);
      setEncounterId(session.encounter_id);
      setPatientId(session.patient_id);
      setThreadId(crypto.randomUUID());
      const turn = await api.turn(message, threadId);
      setReply(turn.reply);
      const link = await api.createCaptureLink(session.patient_id, session.encounter_id);
      setCaptureUrl(link.url);
      setEncounterId(link.encounter_id || session.encounter_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell rise">
      <p className="eyebrow">FlareCheck</p>
      <h1>Between-visit flare check-in</h1>
      <p className="lede">
        History-aware intake, a short-lived secure photo link for the phone, and a Medplum chart
        ready for the clinician — not a diagnosis app.
      </p>

      <div className="panel stack" style={{ marginTop: '2rem' }}>
        <div className="row">
          <span className="eyebrow">API</span>
          <span className="mono">
            {health ? `${health.product || 'agent'} · mode=${String(health.medplum_mode || health.agent_mode)}` : '…'}
          </span>
        </div>

        <label className="stack">
          <span className="eyebrow">Patient message</span>
          <textarea value={message} onChange={(e) => setMessage(e.target.value)} />
        </label>

        <div className="row">
          <button type="button" onClick={start} disabled={busy}>
            {busy ? 'Starting…' : 'Start flare check-in'}
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
