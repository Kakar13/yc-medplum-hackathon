import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  api,
  type AuditEntry,
  type Capability,
  type IdentityState,
  type Scorecard,
} from '../api';

export function Trust() {
  const [cap, setCap] = useState<Capability | null>(null);
  const [identity, setIdentity] = useState<IdentityState | null>(null);
  const [stats, setStats] = useState<Record<string, number | boolean>>({});
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [score, setScore] = useState<Scorecard | null>(null);
  const [error, setError] = useState('');

  async function load() {
    try {
      const [c, a] = await Promise.all([api.capability(), api.audit(50)]);
      setCap(c.active);
      setIdentity(c.identity ?? null);
      setStats(a.stats);
      setEntries(a.entries);
    } catch (e) {
      setError(String(e));
    }
    try {
      setScore(await api.scorecard());
    } catch {
      setScore(null);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <main className="page">
      <header className="page-head">
        <div>
          <h1>Trust &amp; governance</h1>
          <p className="sub">
            The subject of care is a property of the agent's authorization — never an
            argument the model chooses.
          </p>
        </div>
        <nav className="links">
          <Link to="/">Intake</Link>
          <Link to="/review">Review queue</Link>
        </nav>
      </header>

      {error && <p className="error">{error}</p>}

      <section className="cards">
        <div className="card">
          <h2>Active capability</h2>
          {cap ? (
            <dl className="kv">
              <div>
                <dt>SMART scope</dt>
                <dd>
                  <code>{cap.smart_scope}</code>
                </dd>
              </div>
              <div>
                <dt>Purpose of use</dt>
                <dd>{cap.purpose_of_use}</dd>
              </div>
              <div>
                <dt>Actor</dt>
                <dd>{cap.actor}</dd>
              </div>
              <div>
                <dt>Expires in</dt>
                <dd>{cap.expires_in_seconds}s</dd>
              </div>
              <div>
                <dt>Identity</dt>
                <dd>
                  {identity?.bypassed ? (
                    <>
                      <span className="badge deny">bypassed — {identity.bypassed}</span>{' '}
                      <span className="sub">help takes priority over paperwork</span>
                    </>
                  ) : identity?.verified ? (
                    <>
                      <span className="badge allow">verified</span>{' '}
                      <span className="sub">
                        {identity.identifiers_checked} identifiers matched the record
                      </span>
                    </>
                  ) : (
                    <span className="badge draft">not yet checked</span>
                  )}
                </dd>
              </div>
              <div>
                <dt>Granted tools</dt>
                <dd className="tools">
                  {cap.tools.map((t) => (
                    <span key={t} className="chip">
                      {t}
                    </span>
                  ))}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="empty">
              No capability bound — the agent cannot touch clinical data. Start an intake.
            </p>
          )}
        </div>

        <div className="card">
          <h2>Gateway decisions</h2>
          <div className="metrics">
            <div>
              <strong>{String(stats.total_decisions ?? 0)}</strong>
              <span>adjudicated</span>
            </div>
            <div>
              <strong>{String(stats.blocked ?? 0)}</strong>
              <span>blocked</span>
            </div>
            <div>
              <strong>{String(stats.patient_boundary_events ?? 0)}</strong>
              <span>patient-boundary</span>
            </div>
            <div>
              <strong>{String(stats.audited ?? 0)}</strong>
              <span>AuditEvents</span>
            </div>
          </div>
        </div>
      </section>

      {score && (
        <section>
          <h2>HAARF red-team scorecard</h2>
          <p className="sub">
            Replaying RT-1…RT-6 from{' '}
            <a
              href="https://github.com/Task-force-for-AI-agents-in-Healthcare/haarf"
              target="_blank"
              rel="noreferrer"
            >
              the Healthcare AI Agents Regulatory Framework
            </a>
            . Their published RT-4 (wrong patient) pass rate is 6% with their middleware
            on, versus 16% with it off — none of their five layers binds the subject of
            care.
          </p>
          <table className="scorecard">
            <thead>
              <tr>
                <th>Scenario</th>
                <th>Expected</th>
                <th>Gateway off</th>
                <th>Gateway on</th>
                <th>HAARF published</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {score.scenarios.map((s) => (
                <tr key={s.id} className={s.verdict === 'FAIL' ? 'fail' : ''}>
                  <td>
                    <strong>{s.id}</strong> {s.name}
                  </td>
                  <td>{s.expected}</td>
                  <td className="mono">
                    {s.observe_only.blocked === 0 ? 'executed' : `blocked ${s.observe_only.blocked}`}
                  </td>
                  <td className="mono">
                    {s.enforcing.blocked === 0 ? 'executed' : `blocked ${s.enforcing.blocked}`}
                  </td>
                  <td className="mono">
                    {s.haarf_published
                      ? `${s.haarf_published.metric}: ${s.haarf_published.baseline} → ${s.haarf_published.haarf}`
                      : '—'}
                  </td>
                  <td>
                    <span className={`badge ${s.verdict.toLowerCase()}`}>{s.verdict}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="totals">
            {score.totals.correct}/{score.totals.graded} correct ·{' '}
            {score.totals.crossings_blocked}/{score.totals.crossings_in_suite} patient
            crossings blocked · {score.totals.false_positives} false positives ·{' '}
            {score.totals.audited} decisions audited
          </p>
        </section>
      )}

      <section>
        <h2>Audit ledger</h2>
        <p className="sub">
          Each row is a FHIR AuditEvent recording both the bound patient and the patient
          the call referenced — a crossing HAARF's own schema cannot represent.
        </p>
        {entries.length === 0 && <p className="empty">No decisions yet.</p>}
        <table className="ledger">
          <thead>
            <tr>
              <th>Time</th>
              <th>Tool</th>
              <th>Bound to</th>
              <th>Referenced</th>
              <th>Decision</th>
              <th>Control</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e, i) => (
              <tr key={i} className={e.allowed ? '' : 'deny'}>
                <td className="mono">
                  {new Date(e.at * 1000).toLocaleTimeString()}
                </td>
                <td className="mono">{e.tool}</td>
                <td className="mono">{e.bound_patient || '—'}</td>
                <td className="mono">{e.requested_patient || '—'}</td>
                <td>
                  <span className={`badge ${e.allowed ? 'allow' : 'deny'}`}>
                    {e.decision}
                  </span>
                </td>
                <td className="muted">{e.control}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
