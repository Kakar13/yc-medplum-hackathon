import type { ArchTooth } from '../api';

/**
 * A dental chart in the layout a dentist already reads: upper arch 1-16 left to right, lower
 * arch 32-17 beneath it, midline between right and left.
 *
 * Drawn as one SVG rather than a grid of cards because the whole point of an odontogram is the
 * scan — you find the problem tooth by seeing which one differs from the thirty-one around it,
 * and that comparison disappears the moment you show only the interesting teeth.
 */

const W = 30; // per-tooth column width
const CROWN_H = 26;
const ROOT_H = 20;

const FILL: Record<string, string> = {
  composite: '#34d399',
  amalgam: '#94a3b8',
  crown: '#fbbf24',
};

function Tooth({ t, x, upper }: { t: ArchTooth; x: number; upper: boolean }) {
  const crownY = upper ? 22 : 4;
  const rootY = upper ? 22 + CROWN_H : 4 - ROOT_H;

  if (!t.present) {
    return (
      <g className="odo-tooth missing">
        <line x1={x + 5} y1={crownY + 6} x2={x + W - 11} y2={crownY + CROWN_H - 6} />
        <line x1={x + W - 11} y1={crownY + 6} x2={x + 5} y2={crownY + CROWN_H - 6} />
      </g>
    );
  }

  return (
    <g className={`odo-tooth ${t.focus ? 'focus' : ''}`}>
      {/* root, drawn away from the midline; endodontic treatment fills it */}
      <rect
        x={x + 8}
        y={upper ? rootY : rootY + ROOT_H - ROOT_H}
        width={W - 22}
        height={ROOT_H}
        rx={3}
        className={`odo-root ${t.root_canal ? 'treated' : ''}`}
      />
      {/* crown, filled by restoration type */}
      <rect
        x={x + 3}
        y={crownY}
        width={W - 12}
        height={CROWN_H}
        rx={5}
        className="odo-crown"
        fill={t.restoration_kind ? FILL[t.restoration_kind] : '#ffffff'}
      />
      {t.focus && (
        <rect
          x={x - 1}
          y={upper ? crownY - 4 : rootY - 4}
          width={W - 4}
          height={CROWN_H + ROOT_H + 8}
          rx={7}
          className="odo-focus-ring"
        />
      )}
      {t.problem && (
        <circle cx={x + (W - 6) / 2} cy={upper ? 10 : 78} r={4} className="odo-flag" />
      )}
      {t.bleeding && (
        <circle cx={x + W - 12} cy={crownY + CROWN_H - 4} r={2.5} className="odo-bop" />
      )}
    </g>
  );
}

export function Odontogram({ arch }: { arch: ArchTooth[] }) {
  const upper = arch.filter((t) => t.number <= 16).sort((a, b) => a.number - b.number);
  const lower = arch.filter((t) => t.number >= 17).sort((a, b) => b.number - a.number);
  const width = 16 * W + 10;
  const focus = arch.find((t) => t.focus);

  return (
    <div className="odo">
      <svg viewBox={`0 0 ${width} 200`} className="odo-svg" role="img" aria-label="Dental chart">
        {/* midline: patient's right on the left of the chart, as a dentist views it */}
        <line x1={8 * W + 2} y1={4} x2={8 * W + 2} y2={196} className="odo-midline" />
        <text x={8 * W - 8} y={102} className="odo-side">R</text>
        <text x={8 * W + 10} y={102} className="odo-side">L</text>

        <g transform="translate(0, 8)">
          {upper.map((t, i) => (
            <Tooth key={t.number} t={t} x={i * W + 4} upper />
          ))}
          {upper.map((t, i) => (
            <text key={`n${t.number}`} x={i * W + 4 + (W - 6) / 2} y={4} className="odo-num">
              {t.number}
            </text>
          ))}
        </g>

        <g transform="translate(0, 108)">
          {lower.map((t, i) => (
            <Tooth key={t.number} t={t} x={i * W + 4} upper={false} />
          ))}
          {lower.map((t, i) => (
            <text key={`n${t.number}`} x={i * W + 4 + (W - 6) / 2} y={92} className="odo-num">
              {t.number}
            </text>
          ))}
        </g>
      </svg>

      <div className="odo-key">
        <span><i className="sw" style={{ background: FILL.composite }} /> Composite</span>
        <span><i className="sw" style={{ background: FILL.amalgam }} /> Amalgam</span>
        <span><i className="sw" style={{ background: FILL.crown }} /> Crown</span>
        <span><i className="sw rct" /> Root canal</span>
        <span><i className="sw flag" /> Needs attention</span>
        <span><i className="sw missing" /> Missing</span>
      </div>

      {focus && (
        <p className="odo-focus-note">
          Highlighted: <strong>{focus.label}</strong> — the tooth the patient localized.
        </p>
      )}
    </div>
  );
}
