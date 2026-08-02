/**
 * Where a panel's data came from.
 *
 * Everything on the clinician's screen is assembled from somewhere — the FHIR record, an
 * eligibility transaction, the patient's strap, the literature. Without the attribution a
 * clinician cannot tell a retrieved fact from a generated one, and that distinction is the
 * whole basis for trusting any of it.
 */
export function Source({ from, detail }: { from: string; detail?: string }) {
  return (
    <span className="source" title={detail}>
      <span className="source-dot" aria-hidden />
      {from}
      {detail ? <em>{detail}</em> : null}
    </span>
  );
}
