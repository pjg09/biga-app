import { useState, useCallback, useEffect, useId } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import '../styles/login.css';

export default function LoginPage() {
  const [fields, setFields] = useState({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => { document.title = 'BIGA - Ingreso'; }, []);
  const [status, setStatus] = useState('idle'); // idle | loading | error | invalid_credentials | server_error
  const [errors, setErrors] = useState({});

  const navigate   = useNavigate();
  const emailId    = useId();
  const passwordId = useId();

  const validate = useCallback(() => {
    const next = {};
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!fields.email.trim())                      next.email = 'Ingresa tu correo electrónico.';
    else if (!emailPattern.test(fields.email.trim())) next.email = 'Correo electrónico inválido.';
    if (!fields.password)                          next.password = 'Ingresa tu contraseña.';
    else if (fields.password.length < 6)           next.password = 'Mínimo 6 caracteres.';
    return next;
  }, [fields]);

  const handleChange = useCallback((e) => {
    const { name, value } = e.target;
    setFields((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: undefined }));
    setStatus('idle');
  }, []);

  const handleSubmit = useCallback(
    async (e) => {
      e.preventDefault();
      const next = validate();
      if (Object.keys(next).length) {
        setErrors(next);
        return;
      }
      setStatus('loading');
      const body = new URLSearchParams();
      body.append('username', fields.email.trim());
      body.append('password', fields.password);

      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body,
        });

        if (res.ok) {
          const { access_token } = await res.json();
          localStorage.setItem('token', access_token);

          const meRes = await fetch(`${import.meta.env.VITE_API_URL}/auth/me`, {
            headers: { Authorization: `Bearer ${access_token}` },
          });
          const user = await meRes.json();
          localStorage.setItem('user', JSON.stringify(user));

          navigate(user.role === 'PAE_OPERATOR' ? '/dashboard/pae' : '/dashboard/teacher');
          return;
        }

        setStatus(res.status === 401 ? 'invalid_credentials' : 'server_error');
      } catch {
        setStatus('server_error');
      }
    },
    [validate]
  );

  const togglePassword = useCallback(() => setShowPassword((v) => !v), []);

  return (
    <div className="login">
      {/* ── Left brand panel ── */}
      <aside className="login__brand" aria-label="BIGA — presentación">
        <div className="login__brand-bg" aria-hidden="true">
          <div className="login__orb login__orb--1" />
          <div className="login__orb login__orb--2" />
          <div className="login__grid" />
        </div>

        <div className="login__brand-content">
          <Link to="/" className="login__logo" aria-label="Volver al inicio">
            <LogoIcon />
            <span className="login__logo-text">BIGA</span>
          </Link>

          <div className="login__brand-body">
            <h1 className="login__brand-title">
              La plataforma que conecta
              <span className="gradient-text"> familia, escuela</span>
              <br />e institución.
            </h1>

            <ul className="login__brand-features" aria-label="Características principales">
              {BRAND_FEATURES.map(({ icon, text }) => (
                <li key={text} className="login__brand-feature">
                  <span className="login__brand-feature-icon" aria-hidden="true">{icon}</span>
                  <span>{text}</span>
                </li>
              ))}
            </ul>
          </div>

          <p className="login__brand-footer">
            BIGA — Construyendo entornos protectores con tecnología.
          </p>
        </div>
      </aside>

      {/* ── Right form panel ── */}
      <main className="login__panel" aria-label="Formulario de acceso">
        <div className="login__form-wrap">
          {/* Mobile-only logo */}
          <Link to="/" className="login__logo login__logo--mobile" aria-label="Volver al inicio">
            <LogoIcon />
            <span className="login__logo-text">BIGA</span>
          </Link>

          <header className="login__form-header">
            <h2 className="login__form-title">Bienvenido de nuevo</h2>
            <p className="login__form-sub">
              Ingresa a tu cuenta institucional para continuar.
            </p>
          </header>

          <form
            className="login__form"
            onSubmit={handleSubmit}
            noValidate
            aria-label="Formulario de inicio de sesión"
          >
            {/* Email */}
            <div className="form-field">
              <label htmlFor={emailId} className="form-label">
                Correo electrónico
              </label>
              <input
                id={emailId}
                type="email"
                name="email"
                className={`form-input${errors.email ? ' form-input--error' : ''}`}
                placeholder="tu@institucion.edu.co"
                value={fields.email}
                onChange={handleChange}
                autoComplete="email"
                aria-describedby={errors.email ? `${emailId}-error` : undefined}
                aria-invalid={!!errors.email}
                maxLength={320}
                disabled={status === 'loading'}
              />
              {errors.email && (
                <span id={`${emailId}-error`} role="alert" className="form-error">
                  <ErrorIcon />
                  {errors.email}
                </span>
              )}
            </div>

            {/* Password */}
            <div className="form-field">
              <div className="form-label-row">
                <label htmlFor={passwordId} className="form-label">
                  Contraseña
                </label>
                <a href="#" className="form-forgot" tabIndex={0}>
                  ¿Olvidaste tu contraseña?
                </a>
              </div>
              <div className={`form-input-wrap${errors.password ? ' form-input-wrap--error' : ''}`}>
                <input
                  id={passwordId}
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  className="form-input form-input--inset"
                  placeholder="••••••••"
                  value={fields.password}
                  onChange={handleChange}
                  autoComplete="current-password"
                  aria-describedby={errors.password ? `${passwordId}-error` : undefined}
                  aria-invalid={!!errors.password}
                  maxLength={128}
                  disabled={status === 'loading'}
                />
                <button
                  type="button"
                  className="form-eye"
                  onClick={togglePassword}
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  tabIndex={0}
                >
                  {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                </button>
              </div>
              {errors.password && (
                <span id={`${passwordId}-error`} role="alert" className="form-error">
                  <ErrorIcon />
                  {errors.password}
                </span>
              )}
            </div>

            {/* Server error */}
            {status === 'invalid_credentials' && (
              <div role="alert" className="form-alert">
                <ErrorIcon />
                Credenciales incorrectas. Verifica tu correo y contraseña.
              </div>
            )}
            {status === 'server_error' && (
              <div role="alert" className="form-alert">
                <ErrorIcon />
                Error de servidor. Intenta de nuevo en unos segundos.
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              className="btn btn--primary btn--lg login__submit"
              disabled={status === 'loading'}
              aria-busy={status === 'loading'}
            >
              {status === 'loading' ? (
                <>
                  <Spinner />
                  Verificando...
                </>
              ) : (
                <>
                  Iniciar sesión
                  <ArrowIcon />
                </>
              )}
            </button>
          </form>

          <p className="login__back">
            ¿Aún no tienes acceso?{' '}
            <Link to="/#cta" className="login__back-link">
              Solicita una demo
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}

/* ── Data ────────────────────────────────────────────── */
const BRAND_FEATURES = [
  { icon: <CheckIcon />, text: 'Asistencia y PAE en tiempo real' },
  { icon: <CheckIcon />, text: 'Comunicación directa familia-escuela' },
  { icon: <CheckIcon />, text: 'Seguimiento convivencial y académico' },
  { icon: <CheckIcon />, text: 'Analítica con inteligencia artificial' },
];

/* ── Icons ───────────────────────────────────────────── */
function LogoIcon() {
  // useId genera IDs únicos por instancia: el logo se renderiza dos veces
  // (desktop + mobile) y con IDs fijos los gradientes colisionaban, dejando
  // el ícono sin relleno en mobile. Sin colones para evitar edge cases en url().
  const uid = useId().replace(/:/g, '');
  const lp = `lp-${uid}`;
  const lg = `lg-${uid}`;
  return (
    <svg width="28" height="28" viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id={lp} cx="38%" cy="28%" r="70%">
          <stop offset="0%" stopColor="#9B3FF5"/>
          <stop offset="100%" stopColor="#4A0A9E"/>
        </radialGradient>
        <radialGradient id={lg} cx="33%" cy="28%" r="68%">
          <stop offset="0%" stopColor="#D4F870"/>
          <stop offset="55%" stopColor="#80CC20"/>
          <stop offset="100%" stopColor="#2E7008"/>
        </radialGradient>
      </defs>
      <circle cx="50" cy="52" r="44" fill={`url(#${lp})`}/>
      <path d="M50,24 L74,68 L26,68 Z" fill="white" stroke="white" strokeWidth="10" strokeLinejoin="round" strokeLinecap="round"/>
      <circle cx="50" cy="11" r="11" fill={`url(#${lg})`}/>
      <circle cx="80" cy="70" r="11" fill={`url(#${lg})`}/>
      <circle cx="20" cy="70" r="11" fill={`url(#${lg})`}/>
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="7.25" stroke="rgba(168,85,247,0.4)" strokeWidth="1.5"/>
      <path d="M5 8l2 2 4-4" stroke="#A855F7" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19M1 1l22 22"/>
      <path d="M14.12 14.12a3 3 0 01-4.24-4.24"/>
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 5v3.5M8 11h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function Spinner() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true" className="login__spinner">
      <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.25)" strokeWidth="2.5"/>
      <path d="M12 2a10 10 0 0110 10" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  );
}
