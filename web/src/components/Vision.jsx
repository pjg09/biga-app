import { useScrollReveal } from '../hooks/useScrollReveal';
import '../styles/vision.css';

export default function Vision() {
  const labelRef  = useScrollReveal();
  const quoteRef  = useScrollReveal();
  const text1Ref  = useScrollReveal();
  const text2Ref  = useScrollReveal();

  return (
    <section id="vision" className="vision" aria-labelledby="vision-heading">
      <div className="container vision__container">
        <div className="vision__left">
          <span ref={labelRef} className="section-label reveal">Nuestra visión</span>

          <span className="vision__quote-mark" aria-hidden="true">"</span>
          <blockquote ref={quoteRef} id="vision-heading" className="vision__quote reveal reveal-delay-1">
            Consolidarse como un modelo referente en la transformación educativa y social,
            articulando tecnología, corresponsabilidad y enfoque de derechos para construir
            entornos protectores, seguros y conscientes.
          </blockquote>
        </div>

        <div className="vision__right">
          <p ref={text1Ref} className="vision__text reveal">
            A mediano y largo plazo, BIGA integrará de manera progresiva los procesos
            académicos, convivenciales, administrativos y jurídicos, apoyado en herramientas
            digitales inteligentes que permitan decisiones oportunas y pertinentes.
          </p>

          <p ref={text2Ref} className="vision__text reveal reveal-delay-1">
            Una iniciativa sostenible que, además de fortalecer la calidad educativa,
            promueve el uso responsable de la tecnología, la innovación con sentido social y
            el desarrollo integral de las comunidades educativas.
          </p>

          <div className="vision__roadmap">
            {ROADMAP.map(({ phase, items }, i) => (
              <RoadmapItem key={phase} phase={phase} items={items} delay={i + 1} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function RoadmapItem({ phase, items, delay }) {
  const ref = useScrollReveal();
  return (
    <div ref={ref} className={`roadmap-item reveal reveal-delay-${delay}`}>
      <div className="roadmap-item__phase">{phase}</div>
      <ul className="roadmap-item__list">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

const ROADMAP = [
  {
    phase: 'Fase 1 — MVP',
    items: ['Asistencia y PAE', 'Comunicación familia-escuela', 'Módulo convivencia'],
  },
  {
    phase: 'Fase 2 — Expansión',
    items: ['Reconocimiento facial', 'Analítica predictiva con IA', 'Módulo jurídico'],
  },
];
