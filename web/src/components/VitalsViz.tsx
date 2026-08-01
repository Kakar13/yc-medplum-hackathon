/**
 * Renders wearable/vital FHIR Observations as labelled gauges against a typical range.
 *
 * The bands are context so a patient can see where a number sits — deliberately not
 * thresholds, flags, or anything that reads as a diagnosis.
 */

type Observation = Record<string, unknown>;

type Band = {
  match: RegExp;
  low: number;
  high: number;
  min: number;
  max: number;
  /** true when values above the range are the healthier direction */
  higherIsBetter?: boolean;
  note?: string;
};

const BANDS: Band[] = [
  { match: /resting/i, low: 50, high: 80, min: 35, max: 120, note: 'typical adult at rest' },
  {
    match: /variability|rmssd/i,
    low: 30,
    high: 80,
    min: 0,
    max: 120,
    higherIsBetter: true,
    note: 'varies widely between people',
  },
  { match: /oxygen|spo2/i, low: 95, high: 100, min: 85, max: 100, higherIsBetter: true },
  {
    match: /recovery/i,
    low: 67,
    high: 100,
    min: 0,
    max: 100,
    higherIsBetter: true,
    note: 'device score, not a clinical measure',
  },
  {
    match: /sleep duration/i,
    low: 420,
    high: 540,
    min: 180,
    max: 660,
    higherIsBetter: true,
    note: '7–9 hours',
  },
  { match: /sleep efficiency/i, low: 85, high: 100, min: 50, max: 100, higherIsBetter: true },
  { match: /skin temp|temperature/i, low: 36.1, high: 37.2, min: 34, max: 39 },
];

function label(o: Observation): string {
  const coding = ((o.code as { coding?: { display?: string; code?: string }[] })?.coding ||
    [])[0];
  return coding?.display || coding?.code || 'Measurement';
}

export function VitalsViz({
  observations,
  friendly,
}: {
  observations: Observation[];
  /** Optional plain-language relabelling, for surfaces the patient reads. */
  friendly?: Record<string, string>;
}) {
  const quantities = observations
    .map((o) => {
      const vq = o.valueQuantity as { value?: number; unit?: string } | undefined;
      if (!vq || typeof vq.value !== 'number') return null;
      const coded = label(o);
      const band = BANDS.find((b) => b.match.test(coded));
      return { name: friendly?.[coded] ?? coded, value: vq.value, unit: vq.unit || '', band };
    })
    .filter((x): x is NonNullable<typeof x> => x !== null);

  if (quantities.length === 0) return null;

  return (
    <div className="viz">
      {quantities.map((q, i) => {
        const min = q.band?.min ?? 0;
        const max = q.band?.max ?? Math.max(100, q.value * 1.3);
        const span = max - min || 1;
        const pct = (v: number) => Math.max(0, Math.min(100, ((v - min) / span) * 100));

        const inRange = q.band ? q.value >= q.band.low && q.value <= q.band.high : true;
        const belowRange = q.band ? q.value < q.band.low : false;
        // "Outside typical" is only worth flagging in the unfavourable direction
        const notable = q.band
          ? q.band.higherIsBetter
            ? belowRange
            : !inRange
          : false;

        return (
          <div key={i} className="viz-row">
            <div className="viz-head">
              <span className="viz-name">{q.name}</span>
              <span className={`viz-value${notable ? ' notable' : ''}`}>
                {q.value}
                <em>{q.unit}</em>
              </span>
            </div>
            <svg
              className="viz-bar"
              viewBox="0 0 100 8"
              preserveAspectRatio="none"
              role="img"
              aria-label={`${q.name} ${q.value}${q.unit}`}
            >
              <rect x="0" y="3" width="100" height="2" rx="1" fill="var(--wash)" />
              {q.band ? (
                <rect
                  x={pct(q.band.low)}
                  y="2"
                  width={Math.max(1, pct(q.band.high) - pct(q.band.low))}
                  height="4"
                  rx="1"
                  fill="var(--glow)"
                />
              ) : null}
              <circle
                cx={pct(q.value)}
                cy="4"
                r="2.6"
                fill={notable ? 'var(--warn)' : 'var(--accent)'}
              />
            </svg>
            {q.band ? (
              <div className="viz-scale">
                <span>{q.band.min}</span>
                <span className="viz-note">
                  typical {q.band.low}–{q.band.high}
                  {q.band.note ? ` · ${q.band.note}` : ''}
                </span>
                <span>{q.band.max}</span>
              </div>
            ) : null}
          </div>
        );
      })}
      <p className="viz-caption">
        Bands show where a value typically sits, for context only — not thresholds, and not a
        diagnosis. Your clinician reads these alongside your history.
      </p>
    </div>
  );
}
