import type { ArchTooth } from '../api';

/**
 * A dental chart drawn the way charting software draws one.
 *
 * Two views per arch, because that is what a dentist reads: the facial silhouette, where root
 * anatomy and endodontic treatment live, and the occlusal circle, where restorations are marked.
 * Upper arch 1-16 with roots pointing up, lower arch 32-17 beneath with roots pointing down,
 * midline between the patient's right and left.
 *
 * Tooth outlines are generated per tooth class rather than drawn as generic boxes — a molar has
 * a wide multi-cusp crown on two or three roots, an incisor is a chisel on one. Getting that
 * wrong is the difference between a chart and a bar graph, because the scan a clinician does is
 * "which tooth differs from the ones beside it", and that only works if the ones beside it look
 * like teeth.
 */

const COL = 44;
const GUTTER = 34;
const CROWN_H = 32;
const ROOT_H = 42;
const OCCL_R = 13;

const UPPER_TOP = 30; // y of the upper root tips
const UPPER_OCCL = UPPER_TOP + ROOT_H + CROWN_H + 17;
const MIDLINE_Y = UPPER_OCCL + OCCL_R + 8;
const LOWER_OCCL = MIDLINE_Y + OCCL_R + 8;
const LOWER_CROWN = LOWER_OCCL + OCCL_R + 17;
const HEIGHT = LOWER_CROWN + CROWN_H + ROOT_H + 34;

type Kind = 'molar' | 'premolar' | 'canine' | 'incisor';

/** Position in the arch, counted from the third molar, so lower teeth mirror upper ones. */
function seat(n: number): number {
  return n <= 16 ? n : 33 - n;
}

function kindOf(n: number): Kind {
  const p = seat(n);
  if (p <= 3 || p >= 14) return 'molar';
  if (p === 4 || p === 5 || p === 12 || p === 13) return 'premolar';
  if (p === 6 || p === 11) return 'canine';
  return 'incisor';
}

function crownWidth(n: number): number {
  const k = kindOf(n);
  const lower = n >= 17;
  if (k === 'molar') return lower ? 30 : 28;
  if (k === 'premolar') return 22;
  if (k === 'canine') return 20;
  const p = seat(n);
  const central = p === 8 || p === 9;
  return lower ? (central ? 14 : 16) : central ? 21 : 16;
}

function rootCount(n: number): number {
  const k = kindOf(n);
  const upper = n <= 16;
  if (k === 'molar') return upper ? 3 : 2;
  if (k === 'premolar' && upper && (seat(n) === 4 || seat(n) === 13)) return 2;
  return 1;
}

/** Crown drawn cusps-up, cervix at y = CROWN_H. Flipped for the upper arch by the caller. */
function crownPath(n: number): string {
  const w = crownWidth(n);
  const cw = w * 0.74; // cervical width — crowns are widest at the contact point, not the neck
  const k = kindOf(n);
  const h = CROWN_H;
  const x = w / 2;
  const cx = cw / 2;

  let occlusal: string;
  if (k === 'molar') {
    // two cusps and a central fossa
    occlusal = `Q ${-x * 0.5} ${-3} ${0} ${2} Q ${x * 0.5} ${-3} ${x - 2} ${1}`;
  } else if (k === 'premolar') {
    occlusal = `Q ${-x * 0.4} ${-2} ${0} ${3} Q ${x * 0.4} ${-2} ${x - 2} ${1}`;
  } else if (k === 'canine') {
    occlusal = `L ${0} ${-4} L ${x - 2} ${1}`;
  } else {
    occlusal = `L ${x - 2} ${1}`;
  }

  return [
    `M ${-cx} ${h}`,
    `C ${-x} ${h * 0.6} ${-x} ${h * 0.2} ${-x + 2} ${1}`,
    occlusal,
    `C ${x} ${h * 0.2} ${x} ${h * 0.6} ${cx} ${h}`,
    'Z',
  ].join(' ');
}

/** One path per root, from the cervical line down to a rounded apex. */
function rootPaths(n: number): { d: string; canal: string }[] {
  const cw = crownWidth(n) * 0.74;
  const count = rootCount(n);
  const h = CROWN_H;
  const out: { d: string; canal: string }[] = [];

  const seats: { x: number; w: number; splay: number; len: number }[] =
    count === 1
      ? [{ x: 0, w: cw * 0.5, splay: 0, len: kindOf(n) === 'canine' ? ROOT_H : ROOT_H * 0.9 }]
      : count === 2
        ? [
            { x: -cw * 0.24, w: cw * 0.38, splay: -cw * 0.16, len: ROOT_H },
            { x: cw * 0.24, w: cw * 0.38, splay: cw * 0.16, len: ROOT_H },
          ]
        : [
            { x: -cw * 0.3, w: cw * 0.32, splay: -cw * 0.2, len: ROOT_H * 0.94 },
            { x: 0, w: cw * 0.3, splay: 0, len: ROOT_H * 0.8 },
            { x: cw * 0.3, w: cw * 0.32, splay: cw * 0.2, len: ROOT_H },
          ];

  for (const s of seats) {
    const tipX = s.x + s.splay;
    const half = s.w / 2;
    out.push({
      d: [
        `M ${s.x - half} ${h}`,
        `C ${s.x - half + s.splay * 0.6} ${h + s.len * 0.6} ${tipX - half * 0.5} ${h + s.len * 0.86} ${tipX} ${h + s.len}`,
        `C ${tipX + half * 0.5} ${h + s.len * 0.86} ${s.x + half + s.splay * 0.6} ${h + s.len * 0.6} ${s.x + half} ${h}`,
        'Z',
      ].join(' '),
      canal: `M ${s.x} ${h - CROWN_H * 0.45} C ${s.x + s.splay * 0.5} ${h + s.len * 0.55} ${tipX} ${h + s.len * 0.7} ${tipX} ${h + s.len - 3}`,
    });
  }
  return out;
}

const FILL: Record<string, string> = {
  composite: 'url(#hatch-composite)',
  amalgam: '#8fa0b4',
  crown: 'url(#hatch-crown)',
};

function ToothGlyph({ t, upper }: { t: ArchTooth; upper: boolean }) {
  const roots = rootPaths(t.number);
  const restored = Boolean(t.restoration_kind);

  return (
    <g transform={upper ? `translate(0, ${CROWN_H + ROOT_H}) scale(1, -1)` : undefined}>
      {roots.map((r, i) => (
        <path key={`r${i}`} d={r.d} className="odo-root" />
      ))}
      {t.root_canal &&
        roots.map((r, i) => <path key={`c${i}`} d={r.canal} className="odo-canal" />)}
      <path
        d={crownPath(t.number)}
        className="odo-crown"
        fill={restored ? FILL[t.restoration_kind] : '#f1f3f6'}
      />
    </g>
  );
}

function Occlusal({ t }: { t: ArchTooth }) {
  const restored = Boolean(t.restoration_kind);
  const k = kindOf(t.number);
  return (
    <g>
      <circle r={OCCL_R} className="odo-occl" />
      {restored && (
        <circle
          r={k === 'molar' ? OCCL_R - 1.5 : OCCL_R - 5}
          className="odo-occl-fill"
          fill={FILL[t.restoration_kind]}
        />
      )}
      {/* central fossa / groove, so an unrestored molar is not a blank disc */}
      {!restored && k === 'molar' && (
        <path d={`M ${-OCCL_R + 4} 0 L ${OCCL_R - 4} 0 M 0 ${-OCCL_R + 4} L 0 ${OCCL_R - 4}`} className="odo-groove" />
      )}
      {!restored && k === 'premolar' && (
        <path d={`M 0 ${-OCCL_R + 5} L 0 ${OCCL_R - 5}`} className="odo-groove" />
      )}
      {t.bleeding && <circle cx={OCCL_R - 2} cy={OCCL_R - 4} r={2.6} className="odo-bop" />}
    </g>
  );
}

function Column({ t, x }: { t: ArchTooth; x: number }) {
  const upper = t.number <= 16;
  const numY = upper ? 12 : HEIGHT - 8;
  const flagY = upper ? UPPER_TOP - 9 : LOWER_CROWN + CROWN_H + ROOT_H + 11;

  if (!t.present) {
    const top = upper ? UPPER_TOP : LOWER_CROWN;
    const bottom = top + CROWN_H + ROOT_H;
    return (
      <g className="odo-col missing">
        <text x={x} y={numY} className="odo-num">
          {t.number}
        </text>
        <line x1={x - 11} y1={top + 14} x2={x + 11} y2={bottom - 14} className="odo-x" />
        <line x1={x + 11} y1={top + 14} x2={x - 11} y2={bottom - 14} className="odo-x" />
      </g>
    );
  }

  return (
    <g className={`odo-col ${t.focus ? 'focus' : ''}`}>
      {t.focus && (
        <rect
          x={x - COL / 2 + 2}
          y={upper ? UPPER_TOP - 14 : LOWER_OCCL - OCCL_R - 6}
          width={COL - 4}
          height={CROWN_H + ROOT_H + OCCL_R * 2 + 34}
          rx={9}
          className="odo-focus-ring"
        />
      )}
      <text x={x} y={numY} className="odo-num">
        {t.number}
      </text>
      {t.problem && <circle cx={x} cy={flagY} r={4.5} className="odo-flag" />}
      <g transform={`translate(${x}, ${upper ? UPPER_TOP : LOWER_CROWN})`}>
        <ToothGlyph t={t} upper={upper} />
      </g>
      <g transform={`translate(${x}, ${upper ? UPPER_OCCL : LOWER_OCCL})`}>
        <Occlusal t={t} />
      </g>
    </g>
  );
}

export function Odontogram({ arch }: { arch: ArchTooth[] }) {
  const upper = arch.filter((t) => t.number <= 16).sort((a, b) => a.number - b.number);
  const lower = arch.filter((t) => t.number >= 17).sort((a, b) => b.number - a.number);
  const width = GUTTER + 16 * COL + 14;
  const midX = GUTTER + 8 * COL;
  const focus = arch.find((t) => t.focus);

  return (
    <div className="odo">
      <svg viewBox={`0 0 ${width} ${HEIGHT}`} className="odo-svg" role="img" aria-label="Dental chart">
        <defs>
          <pattern id="hatch-composite" width="5" height="5" patternUnits="userSpaceOnUse">
            <rect width="5" height="5" fill="#d8f3e3" />
            <path d="M0 5 L5 0 M-1 1 L1 -1 M4 6 L6 4" stroke="#16a34a" strokeWidth="1.1" />
          </pattern>
          <pattern id="hatch-crown" width="5" height="5" patternUnits="userSpaceOnUse">
            <rect width="5" height="5" fill="#fdf0d2" />
            <path d="M0 0 L5 5 M4 -1 L6 1 M-1 4 L1 6" stroke="#d99a10" strokeWidth="1.1" />
          </pattern>
        </defs>

        <line x1={midX} y1={20} x2={midX} y2={HEIGHT - 18} className="odo-midline" />
        <line x1={GUTTER - 8} y1={MIDLINE_Y} x2={width - 6} y2={MIDLINE_Y} className="odo-midline" />
        <text x={GUTTER - 4} y={MIDLINE_Y - 7} className="odo-side" textAnchor="end">
          R
        </text>
        <text x={width - 8} y={MIDLINE_Y - 7} className="odo-side">
          L
        </text>

        <text
          className="odo-axis"
          transform={`translate(12, ${UPPER_TOP + ROOT_H}) rotate(-90)`}
          textAnchor="middle"
        >
          Facial
        </text>
        <text className="odo-axis" transform={`translate(12, ${MIDLINE_Y}) rotate(-90)`} textAnchor="middle">
          Lingual
        </text>
        <text
          className="odo-axis"
          transform={`translate(12, ${LOWER_CROWN + CROWN_H + 12}) rotate(-90)`}
          textAnchor="middle"
        >
          Facial
        </text>

        {upper.map((t, i) => (
          <Column key={t.number} t={t} x={GUTTER + i * COL + COL / 2} />
        ))}
        {lower.map((t, i) => (
          <Column key={t.number} t={t} x={GUTTER + i * COL + COL / 2} />
        ))}
      </svg>

      <div className="odo-key">
        <span>
          <i className="sw" style={{ background: '#d8f3e3', borderColor: '#16a34a' }} /> Composite
        </span>
        <span>
          <i className="sw" style={{ background: '#8fa0b4', borderColor: '#64748b' }} /> Amalgam
        </span>
        <span>
          <i className="sw" style={{ background: '#fdf0d2', borderColor: '#d99a10' }} /> Crown
        </span>
        <span>
          <i className="sw rct" /> Root canal
        </span>
        <span>
          <i className="sw flag" /> Needs attention
        </span>
        <span>
          <i className="sw bop" /> Bleeding on probing
        </span>
        <span>
          <i className="sw missing" /> Missing
        </span>
      </div>

      {focus && (
        <p className="odo-focus-note">
          Highlighted: <strong>{focus.label}</strong> — the tooth the patient localized.
        </p>
      )}
    </div>
  );
}
