/* Estadísticas del colegio — cinco vistas sobre los datos que ya recolectamos.
   ────────────────────────────────────────────────────────────────────
   La sección está construida alrededor de decisiones, no de conteos:

   - **Resumen** abre con alertas accionables, no con gráficas. Un rector no
     necesita "23 casos"; necesita "este salón está 11 puntos por debajo".
   - **Cobertura de registro** aparece antes que cualquier tasa. Si solo se toma
     lista en el 47% de los bloques, la asistencia del 90% describe a quien
     registra, no al colegio, y todo lo demás hay que leerlo con esa reserva.
   - **Riesgo** es una lista de nombres con teléfono implícito, no un histograma:
     es la vista que termina en una llamada a una familia.

   Todo porcentaje viene calculado del backend (ver `schemas/stats.py`) y viaja
   junto a su `n`, que se muestra al lado: un 100% sobre 3 registros no es un
   100%. Las formas y colores siguen la guía de dataviz; la paleta está validada
   contra la superficie real del dashboard (ver cabecera de `Charts.jsx`). */
import { useState, useEffect, useCallback, useRef } from 'react';
import { adminService } from '../services/admin';
import { BarsH, Columns, LineChart, Meter, RAMPA_GRAVEDAD, StackedBars, StatTile }
  from '../components/Charts';
import '../styles/stats.css';

const PERIODOS = [
  { dias: 7, label: '7 días' },
  { dias: 30, label: '30 días' },
  { dias: 90, label: '90 días' },
  { dias: 180, label: 'Semestre' },
];

const TABS = [
  { id: 'resumen', label: 'Resumen' },
  { id: 'asistencia', label: 'Asistencia' },
  { id: 'pae', label: 'PAE' },
  { id: 'convivencia', label: 'Convivencia' },
  { id: 'riesgo', label: 'Estudiantes en riesgo' },
];

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun',
               'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
/* Fechas ISO cortadas a mano: `new Date('2026-08-15')` interpreta la cadena como
   UTC y en Bogotá (-05) devuelve el día anterior. Todo el módulo trabaja en hora
   local, igual que el backend. */
const diaCorto = (iso) => `${+iso.slice(8, 10)}/${+iso.slice(5, 7)}`;
const mesCorto = (iso) => `${MESES[+iso.slice(5, 7) - 1]} ${iso.slice(2, 4)}`;
const fechaLarga = (iso) => `${+iso.slice(8, 10)} ${MESES[+iso.slice(5, 7) - 1]}`;

function Spinner({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true"
      className="dash__spinner">
      <circle cx="12" cy="12" r="10" stroke="rgba(0,0,0,0.1)" strokeWidth="2.5" />
      <path d="M12 2a10 10 0 0110 10" stroke="#4f46e5" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

/* Carga con estado de error propio: una gráfica en blanco es indistinguible de
   "no hay datos", y confundir las dos cosas en un tablero de decisiones es
   justamente lo que no puede pasar.

   **Descarta las respuestas que llegan tarde.** Cada carga lleva un número de
   secuencia y solo la última puede escribir el estado. Sin esto, cambiar de
   período disparaba una carrera real: `?days=180` tarda 1,6 s y `?days=30`
   0,3 s, así que al pasar de Semestre a 30 días la respuesta vieja llegaba
   después y pintaba sus cifras bajo la etiqueta del período nuevo. El síntoma
   se lee como "los datos no cambian"; en realidad cambiaban al período que más
   tardara en responder. */
function useStats(fetcher, days, onPeriodo) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const gen = useRef(0);

  const cargar = useCallback(async () => {
    const mio = ++gen.current;
    setLoading(true); setError(null);
    try {
      const d = await fetcher(days);
      if (mio !== gen.current) return;      // otra carga la adelantó
      setData(d);
      // El rango de fechas de la barra sale de los datos que se están viendo,
      // no de una consulta aparte: así no puede quedar desfasado de ellos.
      onPeriodo?.(d.periodo);
    } catch (e) {
      if (mio !== gen.current) return;
      setError(e.message || 'No se pudieron cargar las estadísticas');
    } finally {
      if (mio === gen.current) setLoading(false);
    }
  }, [fetcher, days, onPeriodo]);

  useEffect(() => { cargar(); }, [cargar]);
  return { data, error, loading, recargar: cargar };
}

function Estado({ loading, error, vacio, hayDatos, children, recargar }) {
  // Spinner solo en la primera carga. Al cambiar de período ya hay contenido en
  // pantalla: vaciarlo entero produce un parpadeo que se lee como que algo se
  // rompió. Se atenúa y se deja quieto hasta que llegan los datos nuevos.
  if (loading && !hayDatos) {
    return <div className="dash__empty"><Spinner /><span>Calculando…</span></div>;
  }
  if (error) return (
    <div className="card sta-error">
      <p className="sta-error__title">No se pudieron cargar los datos</p>
      <p className="sta-error__text">{error}</p>
      <button type="button" className="btn--secondary" onClick={recargar}>Reintentar</button>
    </div>
  );
  if (vacio) return (
    <div className="card mat-empty">
      <p className="mat-empty__title">Sin datos en este período</p>
      <p className="mat-empty__text">
        Prueba con una ventana más amplia. Las estadísticas se alimentan de lo que
        registran los docentes y el operador del PAE día a día.
      </p>
    </div>
  );
  return <div className={loading ? 'sta-recargando' : undefined}>{children}</div>;
}

function Card({ titulo, ayuda, children, ancho }) {
  return (
    <section className={`card sta-card${ancho ? ' sta-card--ancho' : ''}`}>
      <header className="sta-card__head">
        <h3 className="sta-card__title">{titulo}</h3>
        {ayuda && <p className="sta-card__help">{ayuda}</p>}
      </header>
      {children}
    </section>
  );
}

/* ── Resumen ──────────────────────────────────────────────────────── */
function ResumenTab({ days, irA, onPeriodo }) {
  const { data, error, loading, recargar } = useStats(adminService.statsOverview, days, onPeriodo);
  return (
    <Estado loading={loading} error={error} hayDatos={!!data} recargar={recargar}>
      {data && (
        <>
          <div className="sta-tiles">
            {data.kpis.map(k => (
              <StatTile key={k.clave} etiqueta={k.etiqueta} valor={k.valor} unidad={k.unidad}
                delta={k.delta} subirEsBueno={k.subir_es_bueno} />
            ))}
          </div>

          <Card titulo="Qué revisar" ancho
            ayuda="Hallazgos del período con umbral explícito. No son todos los datos: son los que piden una acción.">
            <ul className="sta-alertas">
              {data.alertas.map((a, i) => (
                <li key={i} className={`sta-alerta sta-alerta--${a.nivel}`}>
                  <span className="sta-alerta__icono" aria-hidden="true">
                    {a.nivel === 'critico' ? '!' : a.nivel === 'atencion' ? '△' : '✓'}
                  </span>
                  <div className="sta-alerta__cuerpo">
                    <p className="sta-alerta__titulo">
                      <span className="sta-alerta__nivel">
                        {a.nivel === 'critico' ? 'Crítico'
                          : a.nivel === 'atencion' ? 'Atención' : 'Sin novedad'}
                      </span>
                      {a.titulo}
                    </p>
                    <p className="sta-alerta__detalle">{a.detalle}</p>
                    {a.vista && (
                      <button type="button" className="sta-alerta__link" onClick={() => irA(a.vista)}>
                        Ver detalle →
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Card>

          <div className="sta-grid">
            <Card titulo="Fiabilidad de los datos"
              ayuda="Porcentaje de bloques del horario en los que realmente se tomó lista.">
              <Meter valor={data.cobertura_registro} etiqueta="Cobertura de registro"
                umbral={70} detalle={
                  data.cobertura_registro < 70
                    ? 'Por debajo del 70% las tasas de asistencia describen a los docentes que registran, no al colegio.'
                    : 'Cobertura suficiente para leer el resto de indicadores con confianza.'} />
            </Card>
            <Card titulo="Canal con las familias"
              ayuda="Correos de inasistencia, salida anticipada y convivencia enviados en el período.">
              <div className="sta-pareja">
                <div><span className="sta-pareja__n">{data.notificaciones_enviadas}</span>
                  <span className="sta-pareja__l">entregados</span></div>
                <div className={data.notificaciones_fallidas ? 'sta-pareja--mal' : undefined}>
                  <span className="sta-pareja__n">{data.notificaciones_fallidas}</span>
                  <span className="sta-pareja__l">fallidos</span></div>
                <div><span className="sta-pareja__n">{data.estudiantes_activos}</span>
                  <span className="sta-pareja__l">estudiantes activos</span></div>
              </div>
            </Card>
          </div>
        </>
      )}
    </Estado>
  );
}

/* ── Asistencia ───────────────────────────────────────────────────── */
function AsistenciaTab({ days, onPeriodo }) {
  const { data, error, loading, recargar } = useStats(adminService.statsAttendance, days, onPeriodo);
  const vacio = data && data.registros === 0;
  // El peor salón con muestra suficiente: es el que se destaca. Con menos de 20
  // registros el porcentaje no sostiene una decisión.
  let peor = -1;
  if (data) {
    let min = Infinity;
    data.por_salon.forEach((s, i) => {
      if (s.registros >= 20 && s.tasa < min) { min = s.tasa; peor = i; }
    });
  }
  const peorDia = data ? data.por_dia_semana.reduce(
    (acc, d, i, arr) => (d.registros >= 20 && d.tasa < arr[acc].tasa ? i : acc), 0) : 0;
  const peorHora = data ? data.por_hora.reduce(
    (acc, h, i, arr) => (h.registros >= 20 && h.tasa < arr[acc].tasa ? i : acc), 0) : 0;

  return (
    <Estado loading={loading} error={error} vacio={vacio} hayDatos={!!data} recargar={recargar}>
      {data && !vacio && (
        <>
          <div className="sta-tiles">
            <StatTile etiqueta="Asistencia" valor={data.tasa_global} unidad="%"
              nota={`${data.registros.toLocaleString('es-CO')} registros`} />
            <StatTile etiqueta="Cobertura de registro" valor={data.cobertura} unidad="%"
              nota={`${data.bloques_con_lista} de ${data.bloques_programados} bloques`} />
            <StatTile etiqueta="Inasistencias" valor={data.ausencias} unidad=""
              nota="Registros marcados como ausente" />
            <StatTile etiqueta="Con justificación" valor={data.tasa_justificacion} unidad="%"
              nota={`${data.justificadas} de ${data.ausencias} ausencias`} />
          </div>

          <Card titulo="Asistencia día a día" ancho
            ayuda="Presentes y tardanzas sobre el total registrado. Los días sin toma de lista quedan en blanco, no en cero.">
            <LineChart data={data.serie.map(d => ({ ...d, _lbl: diaCorto(d.dia) }))}
              yKey="tasa" labelKey="_lbl" huecoSi={d => d.registros === 0} />
          </Card>

          <div className="sta-grid">
            <Card titulo="Por salón"
              ayuda="Se destaca el salón con menor asistencia entre los que tienen muestra suficiente.">
              <BarsH data={data.por_salon.map(s => ({
                ...s, _n: `${s.grado} ${s.salon}`,
                _nota: `${s.registros} registros · ${s.estudiantes} estudiantes`,
              }))} labelKey="_n" valueKey="tasa" notaKey="_nota" destacar={peor} maximo={100}
                muestraKey="registros" minMuestra={20} />
            </Card>
            <Card titulo="Por día de la semana"
              ayuda="Dónde se concentra el ausentismo dentro de la semana.">
              <Columns data={data.por_dia_semana.map(d => ({ ...d, _l: d.dia_semana.slice(0, 3) }))}
                labelKey="_l" valueKey="tasa" subKey="registros" destacar={peorDia}
                muestraKey="registros" minMuestra={20} />
            </Card>
          </div>

          <div className="sta-grid">
            <Card titulo="Por hora de clase"
              ayuda="Una caída sostenida en las últimas horas es fuga a media jornada, no ausencia de la mañana.">
              <Columns data={data.por_hora.map(h => ({ ...h, _l: `${h.orden}ª` }))}
                labelKey="_l" valueKey="tasa" subKey="registros" destacar={peorHora}
                muestraKey="registros" minMuestra={20} />
            </Card>
            <Card titulo="Respuesta de las familias"
              ayuda="Solo las inasistencias de primera hora generan enlace de justificación; el resto se contabiliza igual.">
              <Meter valor={data.tasa_justificacion} etiqueta="Inasistencias justificadas"
                umbral={30}
                detalle={`${data.justificadas} justificadas y ${data.cerradas} cerradas de ${data.ausencias} inasistencias.`} />
            </Card>
          </div>
        </>
      )}
    </Estado>
  );
}

/* ── PAE ──────────────────────────────────────────────────────────── */
function PaeTab({ days, onPeriodo }) {
  const { data, error, loading, recargar } = useStats(adminService.statsPae, days, onPeriodo);
  const vacio = data && data.inscritos === 0;
  return (
    <Estado loading={loading} error={error} vacio={vacio} hayDatos={!!data} recargar={recargar}>
      {data && !vacio && (
        <>
          <div className="sta-tiles">
            <StatTile etiqueta="Inscritos" valor={data.inscritos} unidad=""
              nota="Activos en el año en curso" />
            <StatTile etiqueta="Raciones entregadas" valor={data.entregas} unidad=""
              nota={`${data.dias_con_servicio} días con servicio`} />
            <StatTile etiqueta="Reclamo promedio" valor={data.tasa_reclamo} unidad="%"
              nota={`${data.promedio_diario} raciones por día`} />
            <StatTile etiqueta="No reclamadas" valor={data.raciones_no_reclamadas} unidad=""
              nota="Pedidas para inscritos que no las recogieron" />
          </div>

          <Card titulo="Entregas por día" ancho
            ayuda="Porcentaje de inscritos que reclamó cada día. Los días sin servicio quedan en blanco.">
            <LineChart data={data.serie.map(d => ({ ...d, _lbl: diaCorto(d.dia) }))}
              yKey="tasa" labelKey="_lbl" huecoSi={d => d.entregas === 0} dominio={[0, 100]} />
          </Card>

          <div className="sta-grid">
            <Card titulo="Cobertura por grado"
              ayuda="Inscritos al PAE sobre matriculados. Una cobertura baja en un grado suele ser un trámite pendiente, no falta de necesidad.">
              <BarsH data={data.cobertura_por_grado.map(c => ({
                ...c, _nota: `${c.inscritos} de ${c.matriculados}`,
              }))} labelKey="grado" valueKey="cobertura" notaKey="_nota" maximo={100} />
            </Card>
            <Card titulo="Inscritos que dejaron de reclamar"
              ayuda="Más de 14 días sin recoger su ración. Cada uno es una ración que se pide y se pierde, y a veces un estudiante que dejó de venir.">
              {data.inscritos_sin_reclamar.length === 0 ? (
                <p className="sta-vacio">Todos los inscritos reclamaron en las últimas dos semanas.</p>
              ) : (
                <ul className="sta-lista">
                  {data.inscritos_sin_reclamar.map(e => (
                    <li key={e.student_id} className="sta-lista__item">
                      <span className="sta-lista__nombre">{e.nombre}</span>
                      <span className="sta-lista__meta">
                        {e.grado ? `${e.grado} ${e.salon || ''}` : 'Sin salón'} · doc. {e.documento}
                      </span>
                      <span className="sta-lista__valor">
                        {e.dias_sin_reclamar != null
                          ? `${e.dias_sin_reclamar} días`
                          : 'Nunca reclamó'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}
    </Estado>
  );
}

/* ── Convivencia ──────────────────────────────────────────────────── */
function ConvivenciaTab({ days, onPeriodo }) {
  const { data, error, loading, recargar } = useStats(adminService.statsDiscipline, days, onPeriodo);
  const vacio = data && data.casos === 0;
  return (
    <Estado loading={loading} error={error} vacio={vacio} hayDatos={!!data} recargar={recargar}>
      {data && !vacio && (
        <>
          <div className="sta-tiles">
            <StatTile etiqueta="Casos" valor={data.casos} unidad="" nota="Registros de convivencia" />
            <StatTile etiqueta="Leves" valor={data.leve} unidad="" nota="Gravedad máxima del caso" />
            <StatTile etiqueta="Moderados" valor={data.moderada} unidad="" nota="Gravedad máxima del caso" />
            <StatTile etiqueta="Graves" valor={data.grave} unidad="" nota="Gravedad máxima del caso" />
          </div>

          <Card titulo="Casos por mes" ancho
            ayuda="Cada caso cuenta una vez, con la gravedad más alta de los artículos que cita.">
            <StackedBars data={data.serie_mensual.map(m => ({ ...m, _l: mesCorto(m.mes) }))}
              labelKey="_l" series={[
                { key: 'leve', label: 'Leve', color: RAMPA_GRAVEDAD[0] },
                { key: 'moderada', label: 'Moderada', color: RAMPA_GRAVEDAD[1] },
                { key: 'grave', label: 'Grave', color: RAMPA_GRAVEDAD[2] },
              ]} />
          </Card>

          <div className="sta-grid">
            <Card titulo="Artículos más citados"
              ayuda="Dónde concentrar la formación: el mismo artículo repetido es un patrón, no casos sueltos.">
              <BarsH data={data.top_articulos.map(t => ({
                ...t, _n: `${t.codigo} · ${t.titulo}`, _nota: t.gravedad.toLowerCase(),
              }))} labelKey="_n" valueKey="casos" unidad="" notaKey="_nota" />
            </Card>
            <Card titulo="Estudiantes con más de un caso"
              ayuda="Reincidencia en el período: no son casos sueltos, es un seguimiento individual.">
              {data.reincidentes.length === 0 ? (
                <p className="sta-vacio">Ningún estudiante acumula dos o más casos.</p>
              ) : (
                <ul className="sta-lista">
                  {data.reincidentes.map(r => (
                    <li key={r.student_id} className="sta-lista__item">
                      <span className="sta-lista__nombre">{r.nombre}</span>
                      <span className="sta-lista__meta">
                        {r.grado ? `${r.grado} ${r.salon || ''}` : 'Sin salón'} ·
                        último {fechaLarga(r.ultimo)}
                      </span>
                      <span className="sta-lista__valor">{r.casos} casos</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}
    </Estado>
  );
}

/* ── Estudiantes en riesgo ────────────────────────────────────────── */
function RiesgoTab({ days, onPeriodo }) {
  const { data, error, loading, recargar } = useStats(adminService.statsRisk, days, onPeriodo);
  const [nivel, setNivel] = useState('todos');
  const vacio = data && data.estudiantes.length === 0;
  const filas = data ? data.estudiantes.filter(e => nivel === 'todos' || e.nivel === nivel) : [];

  return (
    <Estado loading={loading} error={error} vacio={vacio} hayDatos={!!data} recargar={recargar}>
      {data && !vacio && (
        <>
          <div className="sta-tiles">
            <StatTile etiqueta="Riesgo alto" valor={data.alto} unidad=""
              nota={`Ausentismo ≥ 20% o varias señales`} />
            <StatTile etiqueta="Riesgo medio" valor={data.medio} unidad=""
              nota={`Ausentismo ≥ ${data.umbral_ausentismo}% o reincidencia`} />
            <StatTile etiqueta="Con alguna señal" valor={data.estudiantes.length} unidad=""
              nota={`De ${data.evaluados} estudiantes evaluados`} />
          </div>

          <Card titulo="A quién llamar primero" ancho
            ayuda={`Orden por puntaje: el ausentismo pesa más que el resto porque es el único con
                    evidencia de predecir deserción. Solo se calcula el porcentaje a partir de
                    ${data.minimo_registros} registros — por debajo, una ausencia daría un porcentaje
                    engañoso y encabezaría la lista sin motivo.`}>
            <div className="sta-filtros" role="tablist">
              {[['todos', 'Todos'], ['alto', 'Alto'], ['medio', 'Medio'], ['seguimiento', 'Seguimiento']]
                .map(([id, l]) => (
                  <button key={id} type="button" role="tab" aria-selected={nivel === id}
                    className={`sta-filtro${nivel === id ? ' sta-filtro--on' : ''}`}
                    onClick={() => setNivel(id)}>{l}</button>
                ))}
            </div>

            <div className="sta-tabla-scroll">
              <table className="sta-tabla">
                <thead>
                  <tr>
                    <th>Estudiante</th><th>Salón</th><th className="num">Ausentismo</th>
                    <th className="num">Convivencia</th><th className="num">Salidas</th>
                    <th>Señales</th><th className="num">Nivel</th>
                  </tr>
                </thead>
                <tbody>
                  {filas.map(e => (
                    <tr key={e.student_id}>
                      <td>
                        <span className="sta-tabla__nombre">{e.nombre}</span>
                        <span className="sta-tabla__doc">{e.documento}</span>
                      </td>
                      <td>{e.grado ? `${e.grado} ${e.salon || ''}` : '—'}</td>
                      <td className="num">
                        {e.registros >= data.minimo_registros ? (
                          <>
                            <strong>{e.ausentismo}%</strong>
                            <span className="sta-tabla__sub">{e.ausencias}/{e.registros}</span>
                          </>
                        ) : (
                          <span className="sta-tabla__sub">muestra insuficiente</span>
                        )}
                      </td>
                      <td className="num">{e.casos_convivencia || '—'}</td>
                      <td className="num">{e.salidas || '—'}</td>
                      <td>
                        <span className="sta-señales">
                          {e.señales.map((s, i) => <em key={i}>{s}</em>)}
                        </span>
                      </td>
                      <td className="num">
                        <span className={`sta-nivel sta-nivel--${e.nivel}`}>
                          {e.nivel === 'alto' ? 'Alto' : e.nivel === 'medio' ? 'Medio' : 'Seguimiento'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </Estado>
  );
}

/* ── Contenedor ───────────────────────────────────────────────────── */
export default function StatsView({ tabInicial = 'resumen' }) {
  // Solo es el valor inicial: al entrar desde una tarjeta del Resumen el
  // componente se monta de nuevo, así que basta con sembrarlo aquí. Cambiar de
  // pestaña después es estado local y no debe volver atrás.
  const [tab, setTab] = useState(tabInicial);
  const [days, setDays] = useState(30);
  // Lo reportan las pestañas al cargar (ver `useStats`): el rango rotulado es
  // siempre el de los datos en pantalla. Antes el contenedor pedía además
  // `statsOverview` solo para esto — una petición extra por clic, y un rango
  // que en las pestañas PAE o Convivencia describía otra consulta.
  const [periodo, setPeriodo] = useState(null);

  return (
    <>
      <div className="adm-tabs" role="tablist">
        {TABS.map(t => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id}
            className={`adm-tab${tab === t.id ? ' adm-tab--active' : ''}`}
            onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>

      <div className="sta-bar">
        <div className="sta-periodos" role="group" aria-label="Período">
          {PERIODOS.map(p => (
            <button key={p.dias} type="button"
              className={`sta-periodo${days === p.dias ? ' sta-periodo--on' : ''}`}
              onClick={() => setDays(p.dias)}>{p.label}</button>
          ))}
        </div>
        {periodo && (
          <span className="sta-rango">
            {fechaLarga(periodo.desde)} — {fechaLarga(periodo.hasta)}
          </span>
        )}
      </div>

      {tab === 'resumen' && <ResumenTab days={days} irA={setTab} onPeriodo={setPeriodo} />}
      {tab === 'asistencia' && <AsistenciaTab days={days} onPeriodo={setPeriodo} />}
      {tab === 'pae' && <PaeTab days={days} onPeriodo={setPeriodo} />}
      {tab === 'convivencia' && <ConvivenciaTab days={days} onPeriodo={setPeriodo} />}
      {tab === 'riesgo' && <RiesgoTab days={days} onPeriodo={setPeriodo} />}
    </>
  );
}
