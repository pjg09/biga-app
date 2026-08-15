import { useState, useCallback, useEffect, useId, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import {
  LoginBrandPanel,
  LogoIcon,
  EyeIcon,
  EyeOffIcon,
  ErrorIcon,
  ArrowIcon,
  Spinner,
} from './LoginPage';
import '../styles/login.css';
import '../styles/forgot.css';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const CODE_LENGTH = 6;
const MIN_PASSWORD = 8;

const STEPS = [
  { id: 'email',    label: 'Correo' },
  { id: 'code',     label: 'Código' },
  { id: 'password', label: 'Nueva clave' },
];

export default function ForgotPasswordPage() {
  const [step, setStep] = useState('email');
  const [email, setEmail] = useState('');
  const [resetToken, setResetToken] = useState(null);

  useEffect(() => { document.title = 'BIGA - Recuperar contraseña'; }, []);

  const stepIndex = STEPS.findIndex((s) => s.id === step);

  return (
    <div className="login">
      <LoginBrandPanel />

      <main className="login__panel" aria-label="Recuperación de contraseña">
        <div className="login__form-wrap">
          <Link to="/" className="login__logo login__logo--mobile" aria-label="Volver al inicio">
            <LogoIcon />
            <span className="login__logo-text">BIGA</span>
          </Link>

          <ol className="fp-steps" aria-label="Progreso">
            {STEPS.map((s, i) => (
              <li
                key={s.id}
                className={`fp-step${i === stepIndex ? ' fp-step--active' : ''}${i < stepIndex ? ' fp-step--done' : ''}`}
                aria-current={i === stepIndex ? 'step' : undefined}
              >
                <span className="fp-step__dot">{i < stepIndex ? <TickIcon /> : i + 1}</span>
                <span className="fp-step__label">{s.label}</span>
              </li>
            ))}
          </ol>

          {step === 'email' && (
            <EmailStep
              email={email}
              setEmail={setEmail}
              onSent={() => setStep('code')}
            />
          )}
          {step === 'code' && (
            <CodeStep
              email={email}
              onBack={() => setStep('email')}
              onVerified={(token) => { setResetToken(token); setStep('password'); }}
            />
          )}
          {step === 'password' && (
            <PasswordStep resetToken={resetToken} onExpired={() => setStep('email')} />
          )}

          <p className="login__back">
            ¿Ya la recordaste?{' '}
            <Link to="/login" className="login__back-link">Volver al ingreso</Link>
          </p>
        </div>
      </main>
    </div>
  );
}

/* ── Paso 1: correo ──────────────────────────────────── */
function EmailStep({ email, setEmail, onSent }) {
  const [status, setStatus] = useState('idle'); // idle | loading | error
  const [message, setMessage] = useState('');
  const emailId = useId();

  const submit = useCallback(async (e) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!EMAIL_PATTERN.test(trimmed)) {
      setStatus('error');
      setMessage('Correo electrónico inválido.');
      return;
    }
    setStatus('loading'); setMessage('');
    try {
      await api.postPublic('/auth/password-reset/request', { email: trimmed });
      setEmail(trimmed);
      onSent();
    } catch (err) {
      setStatus('error');
      setMessage(err.status === 429
        ? 'Demasiadas solicitudes desde esta red. Intenta más tarde.'
        : 'No pudimos procesar la solicitud. Intenta de nuevo en unos minutos.');
    }
  }, [email, setEmail, onSent]);

  return (
    <>
      <header className="login__form-header">
        <h2 className="login__form-title">Recuperar contraseña</h2>
        <p className="login__form-sub">
          Escribe tu correo institucional y te enviaremos un código de {CODE_LENGTH} dígitos.
        </p>
      </header>

      <form className="login__form" onSubmit={submit} noValidate>
        <div className="form-field">
          <label htmlFor={emailId} className="form-label">Correo electrónico</label>
          <input
            id={emailId}
            type="email"
            className={`form-input${status === 'error' ? ' form-input--error' : ''}`}
            placeholder="tu@institucion.edu.co"
            value={email}
            onChange={(e) => { setEmail(e.target.value); setStatus('idle'); setMessage(''); }}
            autoComplete="email"
            maxLength={320}
            disabled={status === 'loading'}
            autoFocus
          />
        </div>

        {message && <div role="alert" className="form-alert"><ErrorIcon />{message}</div>}

        <button
          type="submit"
          className="btn btn--primary btn--lg login__submit"
          disabled={status === 'loading'}
          aria-busy={status === 'loading'}
        >
          {status === 'loading'
            ? <><Spinner />Enviando…</>
            : <>Enviar código<ArrowIcon /></>}
        </button>
      </form>
    </>
  );
}

/* ── Paso 2: código OTP ──────────────────────────────── */
function CodeStep({ email, onBack, onVerified }) {
  const [code, setCode] = useState('');
  const [status, setStatus] = useState('idle'); // idle | loading | error | resent
  const [message, setMessage] = useState('');
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const submit = useCallback(async (e) => {
    e.preventDefault();
    if (code.length !== CODE_LENGTH) {
      setStatus('error');
      setMessage(`El código tiene ${CODE_LENGTH} dígitos.`);
      return;
    }
    setStatus('loading'); setMessage('');
    try {
      const { reset_token } = await api.postPublic('/auth/password-reset/verify', { email, code });
      onVerified(reset_token);
    } catch (err) {
      setStatus('error');
      setCode('');
      setMessage(err.status === 429
        ? 'Demasiados intentos desde esta red. Intenta más tarde.'
        : err.message);
      inputRef.current?.focus();
    }
  }, [code, email, onVerified]);

  const resend = useCallback(async () => {
    setStatus('loading'); setMessage('');
    try {
      await api.postPublic('/auth/password-reset/request', { email });
      setStatus('resent');
      setMessage('Te enviamos un código nuevo. El anterior dejó de servir.');
      setCode('');
    } catch (err) {
      setStatus('error');
      setMessage(err.status === 429
        ? 'Demasiadas solicitudes desde esta red. Intenta más tarde.'
        : 'No pudimos reenviar el código.');
    }
  }, [email]);

  return (
    <>
      <header className="login__form-header">
        <h2 className="login__form-title">Revisa tu correo</h2>
        <p className="login__form-sub">
          Si <strong>{email}</strong> tiene una cuenta activa, le enviamos un código de{' '}
          {CODE_LENGTH} dígitos. Vence en 10 minutos.
        </p>
      </header>

      <form className="login__form" onSubmit={submit} noValidate>
        <div className="form-field">
          <label htmlFor="fp-code" className="form-label">Código de verificación</label>
          <input
            id="fp-code"
            ref={inputRef}
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            className={`form-input fp-code-input${status === 'error' ? ' form-input--error' : ''}`}
            placeholder="000000"
            value={code}
            // Solo dígitos: pegar "123 456" o "código: 123456" no debe romperlo.
            onChange={(e) => {
              setCode(e.target.value.replace(/\D/g, '').slice(0, CODE_LENGTH));
              setStatus('idle'); setMessage('');
            }}
            maxLength={CODE_LENGTH}
            disabled={status === 'loading'}
          />
        </div>

        {message && (
          <div role="alert" className={`form-alert${status === 'resent' ? ' form-alert--ok' : ''}`}>
            {status === 'resent' ? <TickIcon /> : <ErrorIcon />}{message}
          </div>
        )}

        <button
          type="submit"
          className="btn btn--primary btn--lg login__submit"
          disabled={status === 'loading'}
          aria-busy={status === 'loading'}
        >
          {status === 'loading' ? <><Spinner />Verificando…</> : <>Verificar código<ArrowIcon /></>}
        </button>

        <div className="fp-actions">
          <button type="button" className="fp-link" onClick={onBack} disabled={status === 'loading'}>
            Cambiar correo
          </button>
          <button type="button" className="fp-link" onClick={resend} disabled={status === 'loading'}>
            Reenviar código
          </button>
        </div>
      </form>
    </>
  );
}

/* ── Paso 3: nueva contraseña ────────────────────────── */
function PasswordStep({ resetToken, onExpired }) {
  const [fields, setFields] = useState({ password: '', confirm: '' });
  const [show, setShow] = useState(false);
  const [status, setStatus] = useState('idle'); // idle | loading | error | done
  const [message, setMessage] = useState('');
  const navigate = useNavigate();
  const pwdId = useId();
  const confirmId = useId();

  const upd = (f) => (e) => {
    setFields((p) => ({ ...p, [f]: e.target.value }));
    setStatus('idle'); setMessage('');
  };

  const submit = useCallback(async (e) => {
    e.preventDefault();
    if (fields.password.length < MIN_PASSWORD) {
      setStatus('error');
      setMessage(`La contraseña debe tener al menos ${MIN_PASSWORD} caracteres.`);
      return;
    }
    if (fields.password !== fields.confirm) {
      setStatus('error');
      setMessage('Las contraseñas no coinciden.');
      return;
    }
    setStatus('loading'); setMessage('');
    try {
      await api.postPublic('/auth/password-reset/confirm', {
        reset_token: resetToken,
        new_password: fields.password,
      });
      setStatus('done');
      // Pequeña pausa para que se lea la confirmación antes de saltar al login.
      setTimeout(() => navigate('/login'), 1800);
    } catch (err) {
      setStatus('error');
      setMessage(err.message);
    }
  }, [fields, resetToken, navigate]);

  if (status === 'done') {
    return (
      <div className="fp-done" role="status">
        <span className="fp-done__icon"><TickIcon /></span>
        <h2 className="login__form-title">Contraseña actualizada</h2>
        <p className="login__form-sub">Te llevamos al ingreso para que entres con la nueva.</p>
      </div>
    );
  }

  return (
    <>
      <header className="login__form-header">
        <h2 className="login__form-title">Nueva contraseña</h2>
        <p className="login__form-sub">
          Elige una contraseña de al menos {MIN_PASSWORD} caracteres.
        </p>
      </header>

      <form className="login__form" onSubmit={submit} noValidate>
        <div className="form-field">
          <label htmlFor={pwdId} className="form-label">Nueva contraseña</label>
          <div className="form-input-wrap">
            <input
              id={pwdId}
              type={show ? 'text' : 'password'}
              className="form-input form-input--inset"
              placeholder="••••••••"
              value={fields.password}
              onChange={upd('password')}
              autoComplete="new-password"
              maxLength={128}
              disabled={status === 'loading'}
              autoFocus
            />
            <button
              type="button"
              className="form-eye"
              onClick={() => setShow((v) => !v)}
              aria-label={show ? 'Ocultar contraseña' : 'Mostrar contraseña'}
            >
              {show ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </div>
        </div>

        <div className="form-field">
          <label htmlFor={confirmId} className="form-label">Repite la contraseña</label>
          <input
            id={confirmId}
            type={show ? 'text' : 'password'}
            className="form-input"
            placeholder="••••••••"
            value={fields.confirm}
            onChange={upd('confirm')}
            autoComplete="new-password"
            maxLength={128}
            disabled={status === 'loading'}
          />
        </div>

        {message && (
          <div role="alert" className="form-alert">
            <ErrorIcon />{message}
            {/* El token caducado no se arregla reintentando: hay que volver al paso 1. */}
            {message.includes('expiró') && (
              <button type="button" className="fp-link fp-link--inline" onClick={onExpired}>
                Pedir un código nuevo
              </button>
            )}
          </div>
        )}

        <button
          type="submit"
          className="btn btn--primary btn--lg login__submit"
          disabled={status === 'loading'}
          aria-busy={status === 'loading'}
        >
          {status === 'loading' ? <><Spinner />Guardando…</> : <>Cambiar contraseña<ArrowIcon /></>}
        </button>
      </form>
    </>
  );
}

function TickIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M3 8.5l3.5 3.5L13 5" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
