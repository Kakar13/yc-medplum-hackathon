import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { API, api, type ChartPayload } from '../api';
import { VitalsViz } from '../components/VitalsViz';

function patientName(patient: Record<string, unknown>): string {
  const names = (patient.name as { given?: string[]; family?: string }[]) || [];
  if (!names.length) return 'Patient';
  const n = names[0];
  return `${(n.given || []).join(' ')} ${n.family || ''}`.trim() || 'Patient';
}

export function Chart() {
  const { encounterId = '' } = useParams();
  const [data, setData] = useState<ChartPayload | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .chart(encounterId)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [encounterId]);

  const compositions = data?.compositions || [];
  const latest = compositions[compositions.length - 1] as
    | { title?: string; section?: { title?: string; text?: { div?: string } }[] }
    | undefined;
  // Narrative observations render as text; numeric ones go to the gauges.
  const narrative = (data?.observations || []).filter(
    (o) => (o as { valueString?: string }).valueString,
  );

  return (
    <main className="shell rise">
      <p className="eyebrow">Clinician chart · Medplum FHIR</p>
      <h1>Ready encounter</h1>
      <p className="lede">
        Everything the pre-visit conversation produced: note, observations, photo,
        retrieved evidence, cost, and the draft plan awaiting your signature.
      </p>

      <div className="row panel">
        <Link className="btn ghost" to="/">
          Back to intake
        </Link>
        <Link className="btn ghost" to="/review">
          Review queue
        </Link>
        <span className="mono">Encounter/{encounterId}</span>
        {data ? <span className="mono">mode={data.mode}</span> : null}
        {data?.capability ? (
          <span className="mono">scope={data.capability.smart_scope}</span>
        ) : null}
      </div>

      {error ? <p className="warn">{error}</p> : null}

      {data ? (
        <div className="stack panel">
          <div>
            <span className="eyebrow">Patient</span>
            <h2 style={{ margin: '0.25rem 0' }}>{patientName(data.patient)}</h2>
          </div>

          {latest ? (
            <div className="stack">
              <span className="eyebrow">Composition</span>
              <strong>{latest.title || 'Intake note'}</strong>
              {(latest.section || []).map((s, i) => (
                <div key={i}>
                  <div className="eyebrow">{s.title}</div>
                  <div
                    className="reply"
                    dangerouslySetInnerHTML={{ __html: s.text?.div || '' }}
                  />
                </div>
              ))}
            </div>
          ) : (
            <p className="lede">No composition yet — run an intake turn first.</p>
          )}

          <div className="stack">
            <span className="eyebrow">Your measurements</span>
            {(data.observations || []).length === 0 ? (
              <p className="lede">None yet.</p>
            ) : (
              <>
                <VitalsViz observations={data.observations || []} />
                {narrative.length > 0 ? (
                  <ul>
                    {narrative.map((o, i) => (
                      <li key={i}>{String((o as { valueString?: string }).valueString)}</li>
                    ))}
                  </ul>
                ) : null}
              </>
            )}
          </div>

          <div className="stack">
            <span className="eyebrow">Clinical photo</span>
            {(data.photos || []).length === 0 ? (
              <p className="lede">No photo attached yet — open the secure capture link on a phone.</p>
            ) : (
              (data.photos || []).map((p, i) => {
                const src = p.preview_url ? `${API}${p.preview_url}` : p.url;
                return (
                  <div key={i} className="stack">
                    <span>{p.title || 'Clinical photo'}</span>
                    <span className="mono">{p.url}</span>
                    {src ? (
                      <div className="photo-frame">
                        <img src={src} alt={p.title || 'Flare photo'} loading="lazy" />
                      </div>
                    ) : (
                      <p className="lede">Binary reference on chart: {p.url}</p>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {(data.proposals || []).length > 0 ? (
            <div className="stack">
              <span className="eyebrow">AI-proposed plan</span>
              {(data.proposals || []).map((p) => (
                <div key={p.care_plan_id} className="proposal">
                  <div className="proposal-head">
                    <h3>{p.title}</h3>
                    <span className={`badge ${p.status}`}>
                      {p.status} · {p.intent}
                    </span>
                  </div>
                  <p className="summary">{p.summary}</p>
                  <ol className="steps">
                    {p.activities.filter(Boolean).map((a, i) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ol>
                  <p className="muted" style={{ fontSize: '0.85rem' }}>
                    Authored by {p.author}. {p.awaiting_review
                      ? 'Awaiting human review — not active care.'
                      : `Committed by ${p.reviewer || 'a clinician'}.`}{' '}
                    {p.awaiting_review ? (
                      <Link to="/review">Review now →</Link>
                    ) : null}
                  </p>
                </div>
              ))}
            </div>
          ) : null}

          {(data.research || []).length > 0 ? (
            <div className="stack">
              <span className="eyebrow">Retrieved evidence (Europe PMC)</span>
              {(data.research || []).map((c, i) => (
                <div key={i} className="citation">
                  <div>
                    [{i + 1}]{' '}
                    {c.url ? (
                      <a href={c.url} target="_blank" rel="noreferrer">
                        {c.title}
                      </a>
                    ) : (
                      c.title
                    )}
                  </div>
                  <div className="meta">
                    {[c.journal, c.year, c.cited_by ? `cited ${c.cited_by}×` : null]
                      .filter(Boolean)
                      .join(' · ')}
                    {c.open_access ? ' · open access' : ''}
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          {data.eligibility ? (
            <div className="stack">
              <span className="eyebrow">Coverage &amp; cost (Stedi)</span>
              <div className="reply">{data.eligibility}</div>
            </div>
          ) : null}

          {data.handoff_hint ? (
            <p className="lede warn">{data.handoff_hint}</p>
          ) : null}
        </div>
      ) : null}
    </main>
  );
}
