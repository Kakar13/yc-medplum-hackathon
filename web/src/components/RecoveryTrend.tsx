import type { Monitoring } from '../api';

/**
 * The patient's own fortnight, in the shape they'd recognise from their strap.
 *
 * The clinician gets "3 of 14 surfaced"; that phrasing means nothing to the person it describes.
 * Showing the run of nights with their own median drawn across it lets them see the dip rather
 * than be told about it, which is the difference between being informed and being alarmed.
 */
export function RecoveryTrend({ monitoring }: { monitoring: Monitoring }) {
  const nights = [...(monitoring.nights ?? [])].reverse(); // oldest to newest, left to right
  const withRecovery = nights.filter((n) => typeof n.recovery_score === 'number');
  if (withRecovery.length < 3) return null;

  const median = monitoring.baseline?.recovery_score ?? null;
  const sleepMax = Math.max(...nights.map((n) => n.duration_minutes ?? 0), 480);

  return (
    <div className="trend">
      <div className="trend-head">
        <span>Recovery, last {nights.length} nights</span>
        {median != null && <span className="sub">your usual is about {Math.round(median)}</span>}
      </div>

      <div className="trend-plot">
        {median != null && (
          <div className="trend-median" style={{ bottom: `${median}%` }}>
            <span>usual</span>
          </div>
        )}
        {nights.map((n) => {
          const v = n.recovery_score;
          return (
            <div key={n.date} className="trend-col" title={`${n.date}: ${n.reasons.join('; ') || 'a normal night'}`}>
              <div
                className={`trend-bar ${n.surfaced ? 'off' : ''}`}
                style={{ height: typeof v === 'number' ? `${Math.max(v, 3)}%` : '3%' }}
              />
            </div>
          );
        })}
      </div>

      <div className="trend-head sleep-head">
        <span>Sleep</span>
        <span className="sub">
          {monitoring.baseline?.duration_minutes
            ? `usually about ${Math.round((monitoring.baseline.duration_minutes as number) / 60)} hours`
            : ''}
        </span>
      </div>
      <div className="trend-plot short">
        {nights.map((n) => (
          <div key={n.date} className="trend-col" title={`${n.date}: ${Math.round((n.duration_minutes ?? 0) / 60)}h`}>
            <div
              className={`trend-bar sleep ${n.surfaced ? 'off' : ''}`}
              style={{ height: `${Math.max(((n.duration_minutes ?? 0) / sleepMax) * 100, 3)}%` }}
            />
          </div>
        ))}
      </div>

      <p className="trend-note">
        The highlighted nights are the ones that differed from your own normal. This is context for
        your clinician, not a test for anything.
      </p>
    </div>
  );
}
