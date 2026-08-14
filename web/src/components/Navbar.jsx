import { useState, useCallback, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useNavScroll } from '../hooks/useNavScroll';
import '../styles/navbar.css';

const NAV_LINKS = [
  { label: 'Misión', href: '#mission' },
  { label: 'Qué hacemos', href: '#features' },
  { label: '¿Para quién?', href: '#audience' },
  { label: 'Visión', href: '#vision' },
];

// Mismo breakpoint que el @media de navbar.css: por encima el panel deja de ser
// un cajón flotante y vuelve a ser la nav en línea.
const MOBILE_QUERY = '(max-width: 768px)';

export default function Navbar() {
  const scrolled = useNavScroll();
  const [menuOpen, setMenuOpen] = useState(false);

  const toggleMenu = useCallback(() => setMenuOpen((v) => !v), []);
  const closeMenu = useCallback(() => setMenuOpen(false), []);

  // Bloquea el scroll del documento mientras el panel está abierto.
  // Se fija el body en vez de usar `overflow: hidden` porque en iOS Safari
  // `overflow: hidden` sobre body no detiene el scroll táctil de forma fiable.
  useEffect(() => {
    if (!menuOpen) return undefined;

    const mq = window.matchMedia(MOBILE_QUERY);
    if (!mq.matches) return undefined;

    const scrollY = window.scrollY;
    const { style } = document.body;
    const previous = {
      position: style.position,
      top: style.top,
      left: style.left,
      right: style.right,
      width: style.width,
    };

    style.position = 'fixed';
    style.top = `-${scrollY}px`;
    style.left = '0';
    style.right = '0';
    style.width = '100%';

    // Si la ventana crece por encima del breakpoint, el panel desaparece del
    // layout y el burger deja de mostrarse: sin esto el body quedaría bloqueado
    // sin ningún control visible para desbloquearlo.
    const handleBreakpoint = (e) => {
      if (!e.matches) closeMenu();
    };
    mq.addEventListener('change', handleBreakpoint);

    return () => {
      mq.removeEventListener('change', handleBreakpoint);
      Object.assign(style, previous);
      // `html` tiene `scroll-behavior: smooth`; restaurar la posición debe ser
      // instantáneo o se ve un salto animado al cerrar el menú.
      window.scrollTo({ top: scrollY, behavior: 'instant' });
    };
  }, [menuOpen, closeMenu]);

  const handleNavClick = useCallback(
    (e, href) => {
      e.preventDefault();
      closeMenu();
      const target = document.querySelector(href);
      if (!target) return;
      // El desbloqueo devuelve el scroll a donde estaba al abrir el menú, así
      // que hay que desplazarse DESPUÉS de que eso ocurra: en el mismo tick
      // este scrollIntoView se anularía.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
      });
    },
    [closeMenu]
  );

  return (
    <header className={`navbar${scrolled ? ' navbar--scrolled' : ''}`} role="banner">
      <div className="container navbar__inner">
        <a href="#" className="navbar__logo" aria-label="BIGA — inicio">
          <span className="navbar__logo-text">BIGA</span>
          <span className="navbar__logo-dot" aria-hidden="true" />
        </a>

        <nav className={`navbar__nav${menuOpen ? ' navbar__nav--open' : ''}`} aria-label="Navegación principal">
          <ul className="navbar__links">
            {NAV_LINKS.map(({ label, href }) => (
              <li key={href}>
                <a
                  href={href}
                  className="navbar__link"
                  onClick={(e) => handleNavClick(e, href)}
                >
                  {label}
                </a>
              </li>
            ))}
          </ul>

          <Link
            to="/login"
            className="btn btn--primary navbar__cta"
            onClick={closeMenu}
          >
            Iniciar sesión
          </Link>
        </nav>

        <button
          className={`navbar__burger${menuOpen ? ' navbar__burger--open' : ''}`}
          onClick={toggleMenu}
          aria-label={menuOpen ? 'Cerrar menú' : 'Abrir menú'}
          aria-expanded={menuOpen}
          aria-controls="main-nav"
        >
          <span />
          <span />
          <span />
        </button>
      </div>

      {menuOpen && (
        <div
          className="navbar__overlay"
          onClick={closeMenu}
          aria-hidden="true"
        />
      )}
    </header>
  );
}
