import '../styles/hero.css';

export default function Hero() {
  const handleScrollDown = (e) => {
    e.preventDefault();
    document.querySelector('#mission')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <section className="hero" aria-label="Hero">
      {/* Animated background */}
      <div className="hero__bg" aria-hidden="true">
        <div className="hero__orb hero__orb--1" />
        <div className="hero__orb hero__orb--2" />
        <div className="hero__orb hero__orb--3" />
        <div className="hero__grid" />
      </div>

      <div className="container hero__container">
        {/* Badge */}
        <div className="hero__badge">
          <span className="hero__badge-dot" />
          Plataforma educativa integral
        </div>

        {/* Headline */}
        <h1 className="hero__title">
          <span className="hero__brand gradient-text">BIGA</span>
          <span className="hero__tagline">
            Tecnología al servicio de la
            <br />
            comunidad educativa
          </span>
        </h1>

        {/* Subtext */}
        <p className="hero__sub">
          Corresponsabilidad, protección y bienestar para niños, niñas
          y adolescentes — conectando familia, escuela e institución.
        </p>

        {/* CTAs */}
        <div className="hero__actions">
          <a
            href="#mission"
            className="btn btn--ghost btn--lg"
            onClick={(e) => {
              e.preventDefault();
              document.querySelector('#mission')?.scrollIntoView({ behavior: 'smooth' });
            }}
          >
            Conoce más
          </a>
          <a href="#cta" className="btn btn--primary btn--lg hero__btn-demo"
            onClick={(e) => {
              e.preventDefault();
              document.querySelector('#cta')?.scrollIntoView({ behavior: 'smooth' });
            }}
          >
            Solicita una demo
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </a>
        </div>

        {/* Stats strip */}
        <div className="hero__stats" aria-label="Cifras clave">
          {STATS.map(({ value, label }) => (
            <div key={label} className="hero__stat">
              <span className="hero__stat-value">{value}</span>
              <span className="hero__stat-label">{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Scroll indicator */}
      <a
        href="#mission"
        className="hero__scroll"
        onClick={handleScrollDown}
        aria-label="Ir al contenido principal"
      >
        <span className="hero__scroll-line" />
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <path d="M9 3v12M4 10l5 5 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </a>
    </section>
  );
}

const STATS = [
  { value: '100%', label: 'Multi-institución' },
  { value: 'Tiempo real', label: 'Seguimiento' },
  { value: 'IA integrada', label: 'Analítica predictiva' },
  { value: 'PAE + Convivencia', label: 'Procesos cubiertos' },
];
