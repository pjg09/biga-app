import { useScrollReveal } from '../hooks/useScrollReveal';
import '../styles/audience.css';

const AUDIENCES = [
  {
    id: 'instituciones',
    icon: <BuildingIcon />,
    title: 'Instituciones educativas',
    description: 'Digitaliza y centraliza tus procesos académicos, convivenciales y administrativos en una sola plataforma.',
    accent: '#7C3AED',
  },
  {
    id: 'docentes',
    icon: <TeacherIcon />,
    title: 'Docentes y coordinadores',
    description: 'Trazabilidad en tiempo real de asistencia, notas y eventos convivenciales sin papelería ni retrasos.',
    accent: '#9333EA',
  },
  {
    id: 'familias',
    icon: <FamilyIcon />,
    title: 'Familias',
    description: 'Mantente informado y participa activamente en el proceso educativo de tus hijos desde cualquier dispositivo.',
    accent: '#6D28D9',
  },
  {
    id: 'secretarias',
    icon: <GovIcon />,
    title: 'Secretarías de educación',
    description: 'Accede a datos confiables y comparables entre instituciones para tomar decisiones oportunas y basadas en evidencia.',
    accent: '#4F1DC1',
  },
];

export default function Audience() {
  const labelRef = useScrollReveal();
  const titleRef = useScrollReveal();

  return (
    <section id="audience" className="audience" aria-labelledby="audience-heading">
      <div className="audience__bg" aria-hidden="true" />

      <div className="container">
        <div className="audience__header">
          <span ref={labelRef} className="section-label section-label--light reveal">
            ¿Para quién es BIGA?
          </span>
          <h2
            ref={titleRef}
            id="audience-heading"
            className="audience__title reveal reveal-delay-1"
          >
            Diseñado para toda
            <br />
            la comunidad educativa
          </h2>
        </div>

        <div className="audience__grid">
          {AUDIENCES.map((item, i) => (
            <AudienceCard key={item.id} item={item} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}

function AudienceCard({ item, index }) {
  const ref = useScrollReveal();
  const delay = (index % 4) + 1;

  return (
    <article
      ref={ref}
      className={`audience-card reveal reveal-delay-${delay}`}
      aria-labelledby={`audience-${item.id}`}
    >
      <div className="audience-card__icon" aria-hidden="true">
        {item.icon}
      </div>
      <div className="audience-card__content">
        <h3 id={`audience-${item.id}`} className="audience-card__title">
          {item.title}
        </h3>
        <p className="audience-card__desc">{item.description}</p>
      </div>
      <div className="audience-card__arrow" aria-hidden="true">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
    </article>
  );
}

/* ── Icons ───────────────────────────────────────────── */
function BuildingIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2"/>
      <path d="M3 9h18M9 21V9M15 21V9"/>
    </svg>
  );
}

function TeacherIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="7" r="4"/>
      <path d="M6 21v-2a6 6 0 0112 0v2"/>
      <path d="M16 3.13a4 4 0 010 7.75"/>
    </svg>
  );
}

function FamilyIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
      <path d="M9 22V12h6v10"/>
    </svg>
  );
}

function GovIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L2 7l10 5 10-5-10-5z"/>
      <path d="M2 17l10 5 10-5M2 12l10 5 10-5"/>
    </svg>
  );
}
