import { useState, useCallback } from 'react';
import { useScrollReveal } from '../hooks/useScrollReveal';
import '../styles/cta.css';

// Basic RFC 5322 email validation — no eval, no XSS risk
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function CallToAction() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('idle'); // idle | success | error

  const titleRef = useScrollReveal();
  const formRef = useScrollReveal();

  const isEmailValid = EMAIL_PATTERN.test(email.trim());

  const handleSubmit = useCallback(
    (e) => {
      e.preventDefault();

      const trimmed = email.trim();
      if (!EMAIL_PATTERN.test(trimmed)) {
        setStatus('error');
        return;
      }

      // Placeholder: connect to your API endpoint
      setStatus('success');
      setEmail('');
    },
    [email]
  );

  const handleEmailChange = useCallback((e) => {
    setStatus('idle');
    setEmail(e.target.value);
  }, []);

  return (
    <section id="cta" className="cta" aria-labelledby="cta-heading">
      <div className="cta__bg" aria-hidden="true">
        <div className="cta__orb cta__orb--1" />
        <div className="cta__orb cta__orb--2" />
        <div className="cta__grid" />
      </div>

      <div className="container cta__container">
        <div className="cta__badge">
          <span className="cta__badge-dot" />
          Demo gratuita sin compromiso
        </div>

        <h2
          ref={titleRef}
          id="cta-heading"
          className="cta__title reveal"
        >
          ¿Listo para transformar tu
          <br />
          comunidad educativa?
        </h2>

        <p className="cta__sub">
          Agenda una demo personalizada y descubre cómo BIGA puede adaptarse
          a las necesidades específicas de tu institución.
        </p>

        <form
          ref={formRef}
          className="cta__form reveal reveal-delay-2"
          onSubmit={handleSubmit}
          noValidate
          aria-label="Formulario para solicitar demo"
        >
          <div className="cta__input-wrap">
            <label htmlFor="demo-email" className="sr-only">
              Correo electrónico institucional
            </label>
            <input
              id="demo-email"
              type="email"
              className={`cta__input${status === 'error' ? ' cta__input--error' : ''}`}
              placeholder="tu@institucion.edu.co"
              value={email}
              onChange={handleEmailChange}
              autoComplete="email"
              aria-describedby={status !== 'idle' ? 'cta-status' : undefined}
              aria-invalid={status === 'error'}
              maxLength={320}
            />
            <button
              type="submit"
              className="btn btn--primary cta__submit"
              disabled={!isEmailValid}
              aria-disabled={!isEmailValid}
            >
              Solicitar demo
            </button>
          </div>

          {status !== 'idle' && (
            <p
              id="cta-status"
              role="status"
              className={`cta__feedback${status === 'error' ? ' cta__feedback--error' : ' cta__feedback--success'}`}
            >
              {status === 'success'
                ? '¡Gracias! Nos pondremos en contacto pronto.'
                : 'Por favor ingresa un correo electrónico válido.'}
            </p>
          )}
        </form>

        <p className="cta__note">
          Implementación acompañada
        </p>
      </div>
    </section>
  );
}
