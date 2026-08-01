import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api, type CaptureMeta } from '../api';

export function Capture() {
  const { token = '' } = useParams();
  const [params] = useSearchParams();
  const sig = params.get('s');
  const [meta, setMeta] = useState<CaptureMeta | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [done, setDone] = useState<{ encounter_id: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const expiresLabel = useMemo(() => {
    if (!meta) return '';
    const mins = Math.max(0, Math.round((meta.expires_at * 1000 - Date.now()) / 60000));
    return `${mins} min left`;
  }, [meta]);

  useEffect(() => {
    api
      .getCapture(token, sig)
      .then(setMeta)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [token, sig]);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError('');
    try {
      const result = await api.uploadCapture(token, file, sig);
      setDone({ encounter_id: result.encounter_id });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <main className="shell rise">
        <p className="eyebrow">FlareCheck</p>
        <h1>Photo attached</h1>
        <p className="lede">
          Your image is on the clinical chart for review. This is not a diagnosis — a clinician will
          use it with your history.
        </p>
        <div className="panel row">
          <Link className="btn" to={`/chart/${done.encounter_id}`}>
            View chart
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="shell rise">
      <p className="eyebrow">Secure capture · {expiresLabel || '…'}</p>
      <h1>Photograph the flare</h1>
      <p className="lede">
        {meta?.instructions ||
          'One-time link. Good light, fill the frame with the affected skin. No login required.'}
      </p>

      {meta ? (
        <p>
          For <strong>{meta.patient_display}</strong>
        </p>
      ) : null}

      {error ? <p className="warn panel">{error}</p> : null}

      <div className="panel stack">
        <div className="photo-frame">
          {preview ? <img src={preview} alt="Selected flare preview" /> : <span className="lede">Camera / gallery</span>}
        </div>
        <input
          type="file"
          accept="image/*"
          capture="environment"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <button type="button" disabled={!file || busy || !!error} onClick={submit}>
          {busy ? 'Uploading securely…' : 'Submit to chart'}
        </button>
      </div>
    </main>
  );
}
