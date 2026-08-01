import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type Proposal } from '../api';

export function Review() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [reviewer, setReviewer] = useState('Dr. A. Rivera');
  const [notes, setNotes] = useState<Record<string, string>>({});

  async function load() {
    try {
      const data = await api.reviewQueue();
      setProposals(data.proposals);
      setError('');
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  async function decide(id: string, approve: boolean) {
    setBusy(id);
    try {
      await api.review(id, approve, reviewer, notes[id] || '');
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  }

  const pending = proposals.filter((p) => p.awaiting_review);
  const decided = proposals.filter((p) => !p.awaiting_review);

  return (
    <main className="page">
      <header className="page-head">
        <div>
          <h1>Peer review queue</h1>
          <p className="sub">
            Every plan here was drafted by an AI agent and is <code>status: draft</code>.
            Nothing becomes active care until a human commits it.
          </p>
        </div>
        <nav className="links">
          <Link to="/">Intake</Link>
          <Link to="/trust">Trust</Link>
        </nav>
      </header>

      {error && <p className="error">{error}</p>}

      <label className="reviewer">
        Reviewing as
        <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
      </label>

      <section>
        <h2>
          Awaiting review <span className="count">{pending.length}</span>
        </h2>
        {pending.length === 0 && <p className="empty">Queue is clear.</p>}
        {pending.map((p) => (
          <article key={p.care_plan_id} className="proposal">
            <div className="proposal-head">
              <h3>{p.title}</h3>
              <span className="badge draft">draft · {p.intent}</span>
            </div>
            <p className="summary">{p.summary}</p>

            {p.activities.filter(Boolean).length > 0 && (
              <>
                <h4>Proposed steps</h4>
                <ol className="steps">
                  {p.activities.filter(Boolean).map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ol>
              </>
            )}

            {p.evidence.filter(Boolean).length > 0 && (
              <>
                <h4>Evidence attached</h4>
                {p.evidence.filter(Boolean).map((e, i) => (
                  <p key={i} className="evidence">
                    {e}
                  </p>
                ))}
              </>
            )}

            <dl className="attribution">
              <div>
                <dt>Author</dt>
                <dd>{p.author || 'AI agent'}</dd>
              </div>
              <div>
                <dt>Provenance</dt>
                <dd>AI author recorded, human verifier pending</dd>
              </div>
              <div>
                <dt>Task</dt>
                <dd>
                  {p.task_id ? `Task/${p.task_id}` : '—'} · {p.task_status}
                </dd>
              </div>
              {p.encounter_id && (
                <div>
                  <dt>Chart</dt>
                  <dd>
                    <Link to={`/chart/${p.encounter_id}`}>open encounter</Link>
                  </dd>
                </div>
              )}
            </dl>

            <textarea
              placeholder="Reason for your decision (recorded in Provenance)"
              value={notes[p.care_plan_id] || ''}
              onChange={(e) =>
                setNotes({ ...notes, [p.care_plan_id]: e.target.value })
              }
            />
            <div className="actions">
              <button
                className="primary"
                disabled={busy === p.care_plan_id}
                onClick={() => decide(p.care_plan_id, true)}
              >
                {busy === p.care_plan_id ? 'Committing…' : 'Commit as active care'}
              </button>
              <button
                className="ghost"
                disabled={busy === p.care_plan_id}
                onClick={() => decide(p.care_plan_id, false)}
              >
                Reject
              </button>
            </div>
          </article>
        ))}
      </section>

      {decided.length > 0 && (
        <section>
          <h2>Decided</h2>
          <ul className="decided">
            {decided.map((p) => (
              <li key={p.care_plan_id}>
                <span className={`badge ${p.status}`}>{p.status}</span>
                <span>{p.title}</span>
                <span className="muted">
                  {p.status === 'active' ? 'committed by a human' : 'rejected'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
