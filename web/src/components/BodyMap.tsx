import type { SkinMap } from '../api';

/**
 * Where the skin disease is, and where it has been before.
 *
 * The dental case gets an odontogram; this is the same idea for a body site. Sites the patient
 * has just reported are filled, sites in the record are outlined — so a clinician can see at a
 * glance whether this is the same distribution as last time or somewhere new, which is the
 * question that changes what they do next.
 */
export function BodyMap({ map }: { map: SkinMap }) {
  const focused = map.regions.filter((r) => r.focus);

  return (
    <div className="bodymap">
      {map.alert && (
        <div className={`perio-alert ${map.alert.status}`}>
          <div className="perio-alert-head">
            <span className="badge deny">{map.alert.site}</span>
            <span className="sub">{map.alert.prior_events} prior episodes here</span>
          </div>
          <p className="perio-headline">{map.alert.headline}</p>
          <p className="sub">{map.alert.known_history}</p>
        </div>
      )}

      <div className="bodymap-figure">
        <svg viewBox="0 0 100 100" className="bodymap-svg" role="img" aria-label="Body map">
          {/* deliberately schematic: a recognisable silhouette, not an anatomical drawing */}
          <g className="body-outline">
            <circle cx="50" cy="8" r="6" />
            <rect x="44" y="14" width="12" height="4" rx="2" />
            <rect x="38" y="18" width="24" height="24" rx="6" />
            <rect x="41" y="42" width="18" height="14" rx="4" />
            <rect x="26" y="20" width="10" height="24" rx="5" />
            <rect x="64" y="20" width="10" height="24" rx="5" />
            <rect x="28" y="44" width="8" height="10" rx="4" />
            <rect x="64" y="44" width="8" height="10" rx="4" />
            <rect x="42" y="56" width="7" height="26" rx="3.5" />
            <rect x="51" y="56" width="7" height="26" rx="3.5" />
            <rect x="42" y="82" width="7" height="10" rx="3" />
            <rect x="51" y="82" width="7" height="10" rx="3" />
          </g>

          {map.regions.map((r) => (
            <g key={r.key}>
              <circle
                cx={r.x}
                cy={r.y}
                r={r.focus ? 5.5 : 4}
                className={`body-site ${r.focus ? 'active' : 'past'}`}
              />
              {r.focus && <circle cx={r.x} cy={r.y} r="8" className="body-pulse" />}
            </g>
          ))}
        </svg>

        <ul className="bodymap-key">
          {map.regions.map((r) => (
            <li key={r.key} className={r.focus ? 'active' : ''}>
              <span className={`dot ${r.focus ? 'active' : 'past'}`} />
              <div>
                <strong>{r.site}</strong>
                <span className="sub">
                  {r.focus
                    ? r.new_site
                      ? ' — reported now, new site'
                      : ' — reported now'
                    : ` — ${r.prior_events} prior episode${r.prior_events === 1 ? '' : 's'}`}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {focused.map((r) =>
        r.history.length ? (
          <div className="perio-history" key={r.key}>
            <h4>History — {r.site}</h4>
            <ol>
              {r.history.map((h, i) => (
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
        ) : null,
      )}

      {map.allergies?.length ? (
        <p className="bodymap-allergy">
          <strong>Allergies on record:</strong> {map.allergies.join('; ')}
        </p>
      ) : null}
    </div>
  );
}
