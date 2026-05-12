import '../styles/footer.css';

const FOOTER_LINKS = [
  {
    heading: 'Plataforma',
    links: [
      { label: 'Características', href: '#features' },
      { label: '¿Para quién?', href: '#audience' },
      { label: 'Visión', href: '#vision' },
    ],
  },
  {
    heading: 'Empresa',
    links: [
      { label: 'Misión', href: '#mission' },
      { label: 'Privacidad', href: '#' },
      { label: 'Términos', href: '#' },
    ],
  },
  {
    heading: 'Contacto',
    links: [
      { label: 'Solicitar demo', href: '#cta' },
      { label: 'Soporte', href: '#' },
    ],
  },
];

export default function Footer() {
  const handleNav = (e, href) => {
    if (href.startsWith('#') && href.length > 1) {
      e.preventDefault();
      document.querySelector(href)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <footer className="footer" role="contentinfo">
      <div className="footer__top-line" aria-hidden="true" />

      <div className="container footer__container">
        <div className="footer__brand">
          <a href="#" className="footer__logo" aria-label="BIGA — inicio">
            <span className="footer__logo-text">BIGA</span>
            <span className="footer__logo-dot" aria-hidden="true" />
          </a>
          <p className="footer__tagline">
            Construyendo entornos protectores
            <br />
            con tecnología.
          </p>
          <p className="footer__mission-note">
            Tecnología ética al servicio de niños,
            niñas y adolescentes.
          </p>
        </div>

        <nav className="footer__nav" aria-label="Navegación del pie de página">
          {FOOTER_LINKS.map(({ heading, links }) => (
            <div key={heading} className="footer__col">
              <span className="footer__col-heading">{heading}</span>
              <ul className="footer__col-links">
                {links.map(({ label, href }) => (
                  <li key={label}>
                    <a
                      href={href}
                      className="footer__link"
                      onClick={(e) => handleNav(e, href)}
                      {...(href === '#' ? { 'aria-label': `${label} (próximamente)` } : {})}
                    >
                      {label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
      </div>

      <div className="container footer__bottom">
        <p className="footer__copy">
          © {new Date().getFullYear()} BIGA. Todos los derechos reservados.
        </p>
        <p className="footer__sub">
          Diseñado con propósito social · Colombia
        </p>
      </div>
    </footer>
  );
}
