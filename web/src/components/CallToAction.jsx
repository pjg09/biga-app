import { useState, useCallback } from 'react';
import { useScrollReveal } from '../hooks/useScrollReveal';
import { api } from '../services/api';
import '../styles/cta.css';

// Basic RFC 5322 email validation — no eval, no XSS risk
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const MESSAGES = {
  invalid: 'Por favor ingresa un correo electrónico válido.',
  success: '¡Gracias! Nos pondremos en contacto pronto.',
  rateLimited: 'Recibimos varias solicitudes desde aquí. Intenta de nuevo más tarde.',
  failed: 'No pudimos registrar tu solicitud. Intenta de nuevo en unos minutos.',
};

export default function CallToAction() {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('idle'); // idle | sending | success | error
  const [message, setMessage] = useState('');

  const titleRef = useScrollReveal();
  const formRef = useScrollReveal();

  const isSending = status === 'sending';

  const handleSubmit = useCallback(
    async (e) => {
      e.preventDefault();
      if (isSending) return;

      const trimmed = email.trim();
      if (!EMAIL_PATTERN.test(trimmed)) {
        setStatus('error');
        setMessage(MESSAGES.invalid);
        return;
      }

      setStatus('sending');
      setMessage('');
      try {
        await api.postPublic('/leads', { email: trimmed });
        setStatus('success');
        setMessage(MESSAGES.success);
        setEmail('');
      } catch (err) {
        // Solo se declara éxito cuando el backend confirma. Un fallo de red no
        // puede seguir pintando "nos pondremos en contacto": el lead se perdería
        // sin que nadie se entere, ni el visitante ni nosotros.
        setStatus('error');
        setMessage(err.status === 429 ? MESSAGES.rateLimited : MESSAGES.failed);
      }
    },
    [email, isSending]
  );

  const handleEmailChange = useCallback((e) => {
    setStatus('idle');
    setMessage('');
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
              aria-describedby={message ? 'cta-status' : undefined}
              aria-invalid={status === 'error'}
              maxLength={320}
              disabled={isSending}
            />
            <button
              type="submit"
              className="btn btn--primary cta__submit"
              disabled={isSending}
              aria-disabled={isSending}
            >
              {isSending ? 'Enviando…' : 'Solicitar demo'}
            </button>
          </div>

          {message && (
            <p
              id="cta-status"
              role="status"
              className={`cta__feedback${status === 'error' ? ' cta__feedback--error' : ' cta__feedback--success'}`}
            >
              {message}
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
