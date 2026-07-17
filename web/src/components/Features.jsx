import { useScrollReveal } from '../hooks/useScrollReveal';
import '../styles/features.css';

const FEATURES = [
  {
    id: 'comunicacion',
    icon: <ChatIcon />,
    title: 'Comunicación familia - escuela',
    description:
      'Canales directos y trazables entre padres, docentes e institución. Cada mensaje queda registrado, nada se pierde ni queda sin respuesta.',
    tag: 'Mensajería',
  },
  {
    id: 'seguimiento',
    icon: <ChartIcon />,
    title: 'Seguimiento académico y convivencial',
    description:
      'Registro en tiempo real de asistencia, alimentación PAE y procesos de convivencia escolar. Trazabilidad completa desde el aula.',
    tag: 'Registro',
  },
  {
    id: 'analitica',
    icon: <BrainIcon />,
    title: 'Analítica e inteligencia artificial',
    description:
      'Detección temprana de riesgos y patrones que afectan el aprendizaje y el bienestar estudiantil. Decisiones basadas en datos, no en intuición.',
    tag: 'IA',
  },
  {
    id: 'proteccion',
    icon: <RightsIcon />,
    title: 'Protección de derechos',
    description:
      'Herramientas alineadas con el enfoque de garantía de derechos de NNA. Flujos que aseguran el cumplimiento normativo y la protección efectiva.',
    tag: 'Derechos',
  },
];

export default function Features() {
  const labelRef = useScrollReveal();
  const titleRef = useScrollReveal();

  return (
    <section id="features" className="features" aria-labelledby="features-heading">
      <div className="container">
        <div className="features__header">
          <span ref={labelRef} className="section-label reveal">¿Qué hace BIGA?</span>
          <h2 ref={titleRef} id="features-heading" className="features__title reveal reveal-delay-1">
            Todo lo que tu institución
            <br />
            <span className="gradient-text--dark">necesita, integrado</span>
          </h2>
        </div>

        <div className="features__grid">
          {FEATURES.map((feature, i) => (
            <FeatureCard key={feature.id} feature={feature} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}

function FeatureCard({ feature, index }) {
  const ref = useScrollReveal();
  const delay = (index % 4) + 1;

  return (
    <article
      ref={ref}
      className={`feature-card reveal reveal-delay-${delay}`}
      aria-labelledby={`feature-${feature.id}`}
    >
      <div className="feature-card__top">
        <div className="feature-card__icon" aria-hidden="true">
          {feature.icon}
        </div>
        <span className="feature-card__tag">{feature.tag}</span>
      </div>

      <h3 id={`feature-${feature.id}`} className="feature-card__title">
        {feature.title}
      </h3>

      <p className="feature-card__desc">{feature.description}</p>

      <div className="feature-card__glow" aria-hidden="true" />
    </article>
  );
}

/* ── SVG Icons ───────────────────────────────────────── */
function ChatIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18" />
      <path d="M7 16l4-5 4 3 4-6" />
    </svg>
  );
}

function BrainIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
      <path d="M5.636 5.636l2.122 2.122M16.243 16.243l2.121 2.121M5.636 18.364l2.122-2.122M16.243 7.757l2.121-2.121" />
    </svg>
  );
}

function RightsIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  );
}
