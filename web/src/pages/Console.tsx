import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type ChartPayload } from '../api';
import { VitalsViz } from '../components/VitalsViz';
import {
  VoiceClient,
  voiceUrl,
  type LatencySummary,
  type ToolCallEvent,
  type VoiceState,
} from '../lib/voice';

/**
 * The pre-visit console: patient on the left, the agent's own working in the middle, the
 * clinician's chart on the right — one conversation seen from three sides at once.
 *
 * The middle pane exists because "the agent charted this for you" is a claim, and a claim about
 * a clinical record should be inspectable while it is being made rather than after.
 */

type Line = { role: 'user' | 'assistant'; text: string; at: number };

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080';

// Plain-language names. The patient pane should never make someone learn a code system to read
// their own body.
const FRIENDLY: Record<string, string> = {
  'Heart rate resting': 'Resting heart rate',
  'Heart rate variability (RMSSD)': 'Heart rate variability',
  'Oxygen saturation by pulse oximetry': 'Blood oxygen',
  'Body temperature (skin)': 'Skin temperature',
  'Wearable recovery score': 'Recovery',
  'Sleep duration': 'Sleep last night',
  'Sleep efficiency': 'Sleep quality',
  'Time awake during sleep period': 'Awake overnight',
};

export function Console() {
  const [state, setState] = useState<VoiceState>('idle');
  const [lines, setLines] = useState<Line[]>([]);
  const [tools, setTools] = useState<(ToolCallEvent & { at: number })[]>([]);
  const [latency, setLatency] = useState<LatencySummary>({ turns: 0 });
  const [lastMs, setLastMs] = useState<number | null>(null);
  const [level, setLevel] = useState(0);
  const [bound, setBound] = useState<Record<string, unknown> | null>(null);
  const [ready, setReady] = useState<Record<string, unknown> | null>(null);
  const [chart, setChart] = useState<ChartPayload | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [muted, setMuted] = useState(false);
  const [typed, setTyped] = useState('');

  const client = useRef<VoiceClient | null>(null);
  const transcriptEnd = useRef<HTMLDivElement | null>(null);
  const encounterId = (bound?.encounter_id as string) || '';

  const pushLine = useCallback((role: 'user' | 'assistant', text: string) => {
    if (!text.trim()) return;
    setLines((prev) => [...prev, { role, text, at: Date.now() }]);
  }, []);

  const start = useCallback(async () => {
    setError('');
    const c = new VoiceClient(voiceUrl(API_BASE), {
      onState: setState,
      onTranscript: pushLine,
      onToolCall: (t) => setTools((prev) => [{ ...t, at: Date.now() }, ...prev].slice(0, 40)),
      onLatency: (ms, summary) => {
        setLastMs(ms);
        setLatency(summary);
      },
      onBound: setBound,
      onReady: setReady,
      onLevel: setLevel,
      onNotice: setNotice,
      onError: setError,
      onClosed: () => setState('idle'),
    });
    client.current = c;
    try {
      await c.start();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setState('idle');
    }
  }, [pushLine]);

  const stop = useCallback(async () => {
    await client.current?.stop();
    client.current = null;
    setLevel(0);
  }, []);

  useEffect(() => () => void client.current?.stop(), []);

  // Poll the chart while the call is live: this is the "documentation accrues as you talk"
  // claim, and it should be visibly true rather than asserted.
  useEffect(() => {
    if (!encounterId || state === 'idle') return;
    let alive = true;
    const tick = () =>
      api
        .chart(encounterId)
        .then((c) => alive && setChart(c))
        .catch(() => undefined);
    tick();
    const id = setInterval(tick, 3000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [encounterId, state]);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [lines.length]);

  const live = state !== 'idle' && state !== 'connecting';
  const proposal = chart?.proposals?.[0];
  const note = useMemo(() => {
    const comps = chart?.compositions ?? [];
    return comps.length ? comps[comps.length - 1] : null;
  }, [chart]);

  return (
    <div className="console">
      <header className="console-head">
        <div className="brand">
          <span className="mark" aria-hidden />
          <div>
            <h1>Preflight</h1>
            <p>Pre-visit check-in</p>
          </div>
        </div>

        <div className="head-meta">
          {bound?.patient_display ? (
            <span className="pill subject">{String(bound.patient_display)}</span>
          ) : null}
          {lastMs !== null ? (
            <span className="pill latency" title="Measured from end of your turn to first spoken audio">
              {lastMs} ms response
              {latency.median_ms ? <em> · median {latency.median_ms}</em> : null}
            </span>
          ) : null}
          <nav className="head-links">
            <Link to="/review">Review queue</Link>
            <Link to="/trust">Trust</Link>
          </nav>
        </div>
      </header>

      {error ? <p className="banner error">{error}</p> : null}
      {notice ? <p className="banner notice">{notice}</p> : null}

      <div className="triptych">
        {/* ── Patient ─────────────────────────────────────────────── */}
        <section className="pane patient" aria-label="Patient">
          <div className="pane-head">
            <h2>You</h2>
            <span className="pane-tag">voice-first</span>
          </div>

          <div className="stage">
            <button
              type="button"
              className={`orb ${state}`}
              onClick={live ? stop : start}
              style={{ ['--level' as string]: String(Math.min(1, level * 3)) }}
              aria-label={live ? 'End check-in' : 'Start check-in'}
            >
              <span className="orb-ring" aria-hidden />
              <span className="orb-core" aria-hidden />
              <span className="orb-label">{live ? 'End' : 'Start'}</span>
            </button>

            <p className="stage-state">
              {state === 'idle' && 'Tap to begin. Speak normally — you can interrupt at any time.'}
              {state === 'connecting' && 'Connecting…'}
              {state === 'listening' && 'Listening'}
              {state === 'thinking' && 'Thinking'}
              {state === 'speaking' && 'Speaking — talk over me if you need to'}
            </p>
          </div>

          <div className="transcript" aria-live="polite">
            {lines.length === 0 ? (
              <p className="empty">Your words appear here as you speak, and go straight into the note your clinician reads.</p>
            ) : (
              lines.map((l, i) => (
                <p key={`${l.at}-${i}`} className={`line ${l.role}`}>
                  <span className="who">{l.role === 'user' ? 'You' : 'Preflight'}</span>
                  {l.text}
                </p>
              ))
            )}
            <div ref={transcriptEnd} />
          </div>

          <form
            className="say"
            onSubmit={(e) => {
              e.preventDefault();
              client.current?.say(typed);
              pushLine('user', typed);
              setTyped('');
            }}
          >
            <input
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={live ? 'Or type instead of speaking…' : 'Start the check-in to type'}
              disabled={!live}
            />
            <button type="submit" disabled={!live || !typed.trim()} className="ghost">
              Send
            </button>
            <button
              type="button"
              className="ghost"
              disabled={!live}
              onClick={() => {
                const next = !muted;
                setMuted(next);
                client.current?.setMuted(next);
              }}
            >
              {muted ? 'Unmute' : 'Mute'}
            </button>
          </form>

          {chart?.observations?.length ? (
            <div className="patient-block">
              <h3>Your numbers</h3>
              <VitalsViz observations={chart.observations} friendly={FRIENDLY} />
            </div>
          ) : null}

          {chart?.eligibility ? (
            <div className="patient-block cost">
              <h3>What this should cost you</h3>
              <p>{chart.eligibility}</p>
            </div>
          ) : null}
        </section>

        {/* ── Agent ───────────────────────────────────────────────── */}
        <section className="pane agent" aria-label="Agent activity">
          <div className="pane-head">
            <h2>Agent</h2>
            <span className={`pane-tag state-${state}`}>{state}</span>
          </div>

          <dl className="facts">
            <div>
              <dt>Hearing</dt>
              <dd className="mono">{(ready?.listen_model as string) || '—'}</dd>
            </div>
            <div>
              <dt>Speaking</dt>
              <dd className="mono">{(ready?.speak_model as string) || '—'}</dd>
            </div>
            <div>
              <dt>Turns measured</dt>
              <dd className="mono">
                {latency.turns || 0}
                {latency.best_ms ? ` · best ${latency.best_ms} ms` : ''}
              </dd>
            </div>
          </dl>

          {bound?.capability ? (
            <div className="binding">
              <h3>Bound to one patient</h3>
              <p className="mono scope">
                {String((bound.capability as Record<string, unknown>).smart_scope ?? '')}
              </p>
              <p className="binding-note">
                The subject of care comes from this capability, not from anything the model says.
                A tool call naming another patient is refused before it runs.
              </p>
            </div>
          ) : null}

          <h3 className="tools-title">
            Tool calls
            {tools.length ? <span className="count">{tools.length}</span> : null}
          </h3>
          <ol className="tool-feed">
            {tools.length === 0 ? (
              <li className="empty">
                Every action the agent takes shows up here as it happens, with the gateway's
                decision attached.
              </li>
            ) : (
              tools.map((t, i) => (
                <li key={`${t.at}-${i}`} className={t.denied ? 'denied' : 'allowed'}>
                  <div className="tool-row">
                    <code>{t.name}</code>
                    <span className={`verdict ${t.denied ? 'deny' : 'allow'}`}>
                      {t.denied ? 'denied' : 'allowed'}
                    </span>
                    <span className="ms">{t.ms} ms</span>
                  </div>
                  {Object.keys(t.arguments || {}).length ? (
                    <p className="args mono">{JSON.stringify(t.arguments)}</p>
                  ) : null}
                  <p className="preview">{t.preview}</p>
                </li>
              ))
            )}
          </ol>
        </section>

        {/* ── Clinician ───────────────────────────────────────────── */}
        <section className="pane clinician" aria-label="Clinician view">
          <div className="pane-head">
            <h2>Clinician</h2>
            {encounterId ? (
              <Link className="pane-tag link" to={`/chart/${encounterId}`}>
                full chart
              </Link>
            ) : (
              <span className="pane-tag">awaiting</span>
            )}
          </div>

          <div className="clin-block">
            <h3>Note, written live</h3>
            {note ? (
              <article className="note">
                <p className="note-title">{String((note as Record<string, unknown>).title ?? 'Intake note')}</p>
                <pre>{extractNarrative(note)}</pre>
              </article>
            ) : (
              <p className="empty">The intake note appears here as the conversation happens.</p>
            )}
          </div>

          <div className="clin-block">
            <h3>Proposed plan (n=1)</h3>
            {proposal ? (
              <article className="proposal-card">
                <header>
                  <strong>{proposal.title || 'Draft plan'}</strong>
                  <span className={`badge ${proposal.status === 'active' ? 'active' : 'draft'}`}>
                    {proposal.status || 'draft'}
                  </span>
                </header>
                <p>{proposal.summary}</p>
                {proposal.activities?.length ? (
                  <ul>
                    {proposal.activities.filter(Boolean).map((a, i) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ul>
                ) : null}
                <p className="attribution">
                  Authored by the agent, awaiting human review. Nothing here is active care.
                </p>
                <Link className="btn small" to="/review">
                  Open peer review
                </Link>
              </article>
            ) : (
              <p className="empty">
                A draft plan is proposed once the complaint is clear. It stays a proposal until a
                clinician commits it.
              </p>
            )}
          </div>

          <div className="clin-block">
            <h3>Evidence</h3>
            {chart?.research?.length ? (
              <ol className="cites">
                {chart.research.map((c, i) => (
                  <li key={c.pmid || c.doi || i}>
                    <a href={c.url || '#'} target="_blank" rel="noreferrer">
                      {c.title}
                    </a>
                    <span className="cite-meta">
                      {[c.journal, c.year].filter(Boolean).join(' · ')}
                    </span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="empty">Retrieved literature is listed here, or nothing is claimed.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

/** Compositions carry the narrative in section[].text.div — strip the wrapper for display. */
function extractNarrative(comp: Record<string, unknown>): string {
  const sections = (comp.section as Record<string, unknown>[]) || [];
  const parts: string[] = [];
  for (const s of sections) {
    const text = (s.text as Record<string, unknown>) || {};
    const div = String(text.div ?? '');
    const clean = div
      .replace(/<[^>]+>/g, '\n')
      .split('\n')
      .map((x) => x.trim())
      .filter(Boolean)
      .join('\n');
    if (clean) parts.push(clean);
  }
  return parts.join('\n\n') || '—';
}
