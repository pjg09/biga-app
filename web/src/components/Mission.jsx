import { useScrollReveal } from '../hooks/useScrollReveal';
import '../styles/mission.css';

export default function Mission() {
  const labelRef  = useScrollReveal();
  const titleRef  = useScrollReveal();
  const text1Ref  = useScrollReveal();
  const text2Ref  = useScrollReveal();

  return (
    <section id="mission" className="mission" aria-labelledby="mission-heading">
      <div className="mission__accent-bar" aria-hidden="true" />

      <div className="container mission__container">
        <div className="mission__left">
          <span ref={labelRef} className="section-label reveal">Nuestra misión</span>

          <h2 ref={titleRef} id="mission-heading" className="mission__title reveal reveal-delay-1">
            Tecnología con
            <span className="gradient-text--dark"> propósito social</span>
          </h2>

          <div className="mission__divider" aria-hidden="true" />
        </div>

        <div className="mission__right">
          <p ref={text1Ref} className="mission__text mission__text--lead reveal">
            Impulsar en la comunidad educativa una cultura de corresponsabilidad
            orientada a la <strong>protección integral de niños, niñas y adolescentes</strong>,
            mediante el uso ético, consciente y regulado de la tecnología.
          </p>

          <p ref={text2Ref} className="mission__text reveal reveal-delay-1">
            A través del desarrollo e implementación de soluciones digitales innovadoras,
            BIGA fortalece la comunicación efectiva entre familia, escuela e institución,
            facilitando el seguimiento oportuno de procesos académicos, convivenciales y
            de garantía de derechos como la asistencia y la alimentación.
          </p>
        </div>
      </div>

      {/* Feature pills */}
      <div className="container">
        <div className="mission__pills">
          {PILLARS.map(({ icon, label }, i) => (
            <MissionPill key={label} icon={icon} label={label} delay={i} />
          ))}
        </div>
      </div>
    </section>
  );
}

function MissionPill({ icon, label, delay }) {
  const ref = useScrollReveal();
  return (
    <div ref={ref} className={`mission__pill reveal reveal-delay-${delay + 1}`}>
      <span className="mission__pill-icon" aria-hidden="true">{icon}</span>
      <span>{label}</span>
    </div>
  );
}

const PILLARS = [
  { icon: <EthicsIcon />, label: 'Ético y consciente' },
  { icon: <ShieldIcon />, label: 'Enfoque de derechos' },
  { icon: <DataIcon />, label: 'Analítica de datos' },
  { icon: <AIIcon />, label: 'Inteligencia artificial' },
];

function EthicsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2l9 4.5V12c0 5.25-3.75 10.148-9 11.5C6.75 22.148 3 17.25 3 12V6.5L12 2z"/>
      <path d="M9 12l2 2 4-4"/>
    </svg>
  );
}

function DataIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 20V10M12 20V4M6 20v-6"/>
    </svg>
  );
}

function AIIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="3"/>
      <path d="M9 9h.01M15 9h.01M9 15h6"/>
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3"/>
    </svg>
  );
}
