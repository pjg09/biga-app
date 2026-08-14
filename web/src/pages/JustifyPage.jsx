import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { attendanceService } from '../services/attendance';
import '../styles/justify.css';

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
}

// Debe coincidir con `_ALLOWED_ATTACHMENT_TYPES` y `JUSTIFICATION_MAX_UPLOAD_MB`
// del backend. Aquí solo evita un viaje inútil: la validación que manda es la
// del servidor.
const ACCEPTED_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];
const MAX_MB = 5;

function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function JustifyPage() {
  const { token } = useParams();
  const [info, setInfo]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [reason, setReason]   = useState('');
  const [file, setFile]       = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone]       = useState(null);
  const [error, setError]     = useState(null);

  useEffect(() => {
    attendanceService.justificationInfo(token)
      .then(setInfo)
      .catch(e => setInfo({ valid: false, message: e.message }))
      .finally(() => setLoading(false));
  }, [token]);

  const handleFile = useCallback((e) => {
    const f = e.target.files?.[0] ?? null;
    setError(null);
    if (!f) { setFile(null); return; }
    if (!ACCEPTED_TYPES.includes(f.type)) {
      setError('Formato no admitido. Adjunte un PDF o una imagen (JPG, PNG o WEBP).');
      e.target.value = '';
      setFile(null);
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`El archivo supera el máximo de ${MAX_MB} MB.`);
      e.target.value = '';
      setFile(null);
      return;
    }
    setFile(f);
  }, []);

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    if (reason.trim().length < 3) {
      setError('Escriba una justificación de al menos 3 caracteres.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await attendanceService.submitJustification(token, reason.trim(), file);
      setDone(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }, [token, reason, file]);

  return (
    <div className="justify">
      <div className="justify__card">
        <div className="justify__logo">
          <Logo />
          <span className="justify__logo-text">BIGA</span>
        </div>

        {loading && <p className="justify__muted">Cargando…</p>}

        {!loading && done && (
          <div className="justify__state">
            <div className="justify__state-icon justify__state-icon--ok"><CheckIcon /></div>
            <p className="justify__title">¡Justificación enviada!</p>
            <p className="justify__sub">
              Registramos la justificación de la inasistencia
              {done.student_name ? <> de <strong>{done.student_name}</strong></> : null}. Gracias.
            </p>
          </div>
        )}

        {!loading && !done && info && info.valid && (
          <form onSubmit={handleSubmit}>
            <p className="justify__label">Justificar inasistencia</p>
            <h1 className="justify__title">Reporte de inasistencia</h1>
            <p className="justify__sub">
              Su acudido no asistió a la primera hora de clase. Si la ausencia tiene
              una justificación, descríbala a continuación.
            </p>

            <div className="justify__student">
              <span className="justify__student-name">{info.student_name}</span>
              <span className="justify__student-meta">
                {[info.grade_name, info.group_name].filter(Boolean).join(' ')
                  ? `Grupo ${[info.grade_name, info.group_name].filter(Boolean).join(' ')} · `
                  : ''}{fmtDate(info.date)}
              </span>
            </div>

            <label className="justify__field-label" htmlFor="reason">Motivo de la inasistencia</label>
            <textarea
              id="reason"
              className="justify__textarea"
              value={reason}
              onChange={e => setReason(e.target.value)}
              placeholder="Ej: Cita médica, calamidad doméstica…"
              maxLength={2000}
              required
            />

            <p className="justify__field-label justify__field-label--spaced">
              Soporte <span className="justify__optional">(opcional)</span>
            </p>
            <p className="justify__hint">
              Adjunte una incapacidad, constancia u otro documento. PDF o imagen, hasta {MAX_MB} MB.
            </p>

            {file ? (
              <div className="justify__file">
                <span className="justify__file-icon" aria-hidden="true"><FileIcon /></span>
                <span className="justify__file-info">
                  <span className="justify__file-name">{file.name}</span>
                  <span className="justify__file-size">{fmtSize(file.size)}</span>
                </span>
                <button
                  type="button"
                  className="justify__file-remove"
                  onClick={() => setFile(null)}
                  aria-label="Quitar el archivo adjunto"
                  disabled={submitting}
                >
                  ✕
                </button>
              </div>
            ) : (
              <label className="justify__file-pick">
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp"
                  onChange={handleFile}
                  disabled={submitting}
                />
                <span className="justify__file-icon" aria-hidden="true"><UploadIcon /></span>
                <span>Seleccionar archivo</span>
              </label>
            )}

            {error && <p className="justify__error">{error}</p>}

            <button className="justify__btn" type="submit" disabled={submitting}>
              {submitting ? 'Enviando…' : 'Enviar justificación'}
            </button>
          </form>
        )}

        {!loading && !done && info && !info.valid && (
          <div className="justify__state">
            <div className={`justify__state-icon justify__state-icon--${info.already_justified ? 'ok' : 'warn'}`}>
              {info.already_justified ? <CheckIcon /> : <AlertIcon />}
            </div>
            <p className="justify__title">
              {info.already_justified ? 'Ya justificada' : 'Enlace no disponible'}
            </p>
            <p className="justify__sub">{info.message || 'Este enlace no es válido.'}</p>
            {info.student_name && (
              <p className="justify__muted">{info.student_name} · {fmtDate(info.date)}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Logo() {
  return (
    <svg width="28" height="28" viewBox="0 0 100 100" aria-hidden="true">
      <defs>
        <radialGradient id="j-p" cx="38%" cy="28%" r="70%">
          <stop offset="0%" stopColor="#9B3FF5" /><stop offset="100%" stopColor="#4A0A9E" />
        </radialGradient>
        <radialGradient id="j-g" cx="33%" cy="28%" r="68%">
          <stop offset="0%" stopColor="#D4F870" /><stop offset="100%" stopColor="#2E7008" />
        </radialGradient>
      </defs>
      <circle cx="50" cy="52" r="44" fill="url(#j-p)" />
      <path d="M50,24 L74,68 L26,68 Z" fill="white" stroke="white" strokeWidth="10" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx="50" cy="11" r="11" fill="url(#j-g)" />
      <circle cx="80" cy="70" r="11" fill="url(#j-g)" />
      <circle cx="20" cy="70" r="11" fill="url(#j-g)" />
    </svg>
  );
}
function CheckIcon() { return <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>; }
function AlertIcon() { return <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>; }
function UploadIcon() { return <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>; }
function FileIcon()   { return <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>; }
