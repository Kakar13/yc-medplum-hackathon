import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, type ChartPayload } from '../api';

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

  return (
    <main className="shell rise">
      <p className="eyebrow">Clinician chart · Medplum FHIR</p>
      <h1>Ready encounter</h1>
      <p className="lede">
        Live Composition, observations, and secure clinical photo — not a raw wearable dump.
      </p>

      <div className="row panel">
        <Link className="btn ghost" to="/">
          Back to intake
        </Link>
        <span className="mono">Encounter/{encounterId}</span>
        {data ? <span className="mono">mode={data.mode}</span> : null}
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
            <span className="eyebrow">Observations</span>
            {(data.observations || []).length === 0 ? (
              <p className="lede">None yet.</p>
            ) : (
              <ul>
                {(data.observations || []).map((o, i) => (
                  <li key={i}>
                    {String((o as { valueString?: string }).valueString || o.id || 'observation')}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="stack">
            <span className="eyebrow">Skin photo</span>
            {(data.photos || []).length === 0 ? (
              <p className="lede">No photo attached yet — open the secure capture link on a phone.</p>
            ) : (
              (data.photos || []).map((p, i) => (
                <div key={i} className="stack">
                  <span>{p.title || 'Clinical photo'}</span>
                  <span className="mono">{p.url}</span>
                  {p.url?.startsWith('http') ? (
                    <div className="photo-frame">
                      <img src={p.url} alt={p.title || 'Flare photo'} />
                    </div>
                  ) : (
                    <p className="lede">Binary reference on chart: {p.url}</p>
                  )}
                </div>
              ))
            )}
          </div>

          {data.eligibility ? (
            <div className="stack">
              <span className="eyebrow">Coverage (Stedi)</span>
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
