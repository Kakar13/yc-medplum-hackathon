import type { Periochart } from '../api';

const SEVERITY_LABEL: Record<string, string> = {
  healthy: 'Healthy',
  early: 'Early loss',
  advanced: 'Advanced',
};

/**
 * The clinician's view of one mouth. Leads with the tooth the patient is actually complaining
 * about and what the record already knew about it, because the point of charting before the
 * visit is that nobody has to reconstruct the history in the room.
 */
export function PerioChart({ chart }: { chart: Periochart }) {
  const focus = chart.teeth.find((t) => t.focus);

  return (
    <div className="perio">
      {chart.alert && (
        <div className={`perio-alert ${chart.alert.status}`}>
          <div className="perio-alert-head">
            <span className="badge deny">{chart.alert.label}</span>
            <span className="sub">{chart.alert.prior_events} prior events on record</span>
          </div>
          <p className="perio-headline">{chart.alert.headline}</p>
          {chart.alert.known_history && <p className="sub">{chart.alert.known_history}</p>}
        </div>
      )}

      <div className="perio-grid">
        {chart.teeth.map((t) => (
          <div key={t.number} className={`perio-tooth ${t.severity} ${t.focus ? 'focus' : ''}`}>
            <div className="perio-tooth-head">
              <strong>{t.number}</strong>
              <span>{SEVERITY_LABEL[t.severity]}</span>
            </div>
            <div className="perio-depths">
              {t.depths_mm.map((d, i) => (
                <span
                  key={i}
                  className={d >= 6 ? 'deep' : d >= 4 ? 'mid' : 'shallow'}
                  style={{ height: `${Math.min(d, 9) * 3}px` }}
                  title={`${d}mm`}
                />
              ))}
            </div>
            <div className="perio-tooth-foot">
              <span>{t.max_depth_mm}mm</span>
              {t.bleeding_on_probing && <span className="bop">BOP</span>}
            </div>
          </div>
        ))}
      </div>

      {focus && focus.history.length > 0 && (
        <div className="perio-history">
          <h4>History — {focus.label}</h4>
          <ol>
            {focus.history.map((h, i) => (
              <li key={i}>
                <span className="perio-date">{h.date}</span>
                <div>
                  <strong>{h.event}</strong>
                  <p className="sub">{h.detail}</p>
                  <p className="sub">{h.provider}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="perio-pending">
        <h4>Pending</h4>
        <ul>
          {chart.summary.pending_treatment.map((p, i) => (
            <li key={i}>
              <span className={`badge ${p.urgency === 'urgent' ? 'deny' : 'draft'}`}>
                {p.urgency}
              </span>{' '}
              {p.tooth ? `Tooth ${p.tooth}: ` : ''}
              {p.plan}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
