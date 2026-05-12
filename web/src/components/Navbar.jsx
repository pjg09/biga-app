import { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useNavScroll } from '../hooks/useNavScroll';
import '../styles/navbar.css';

const NAV_LINKS = [
  { label: 'Misión', href: '#mission' },
  { label: 'Qué hacemos', href: '#features' },
  { label: '¿Para quién?', href: '#audience' },
  { label: 'Visión', href: '#vision' },
];

export default function Navbar() {
  const scrolled = useNavScroll();
  const [menuOpen, setMenuOpen] = useState(false);

  const toggleMenu = useCallback(() => setMenuOpen((v) => !v), []);
  const closeMenu = useCallback(() => setMenuOpen(false), []);

  const handleNavClick = useCallback(
    (e, href) => {
      e.preventDefault();
      closeMenu();
      const target = document.querySelector(href);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
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
