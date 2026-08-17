/* Primitivas de gráfico en SVG puro.
   ────────────────────────────────────────────────────────────────────
   Sin librería de charts a propósito: el proyecto no tiene ninguna, y agregar
   una arrastra el gotcha del volumen anónimo de `node_modules` (web/CLAUDE.md)
   por cuatro formas que caben en un archivo.

   Decisiones de codificación (paleta validada con el script del skill dataviz
   contra la superficie real `#FFFFFF` del dashboard):

   - **Un solo color para todas las barras de una serie.** Los salones y los días
     de la semana son categorías, no magnitudes: pintarlas más oscuras cuanto más
     altas duplicaría en color lo que ya dice el largo de la barra.
   - **Emphasis en vez de arcoíris**: la barra que importa (la peor) va en el
     acento y el resto en el mismo tono atenuado. Es la forma correcta cuando la
     historia es "este de aquí", no "compara estos ocho".
   - **La gravedad SÍ es una escala ordenada**, así que usa rampa de una sola hue
     (claro→oscuro). El trío amarillo/naranja/rojo que se usa por costumbre falla
     el piso de separación para visión normal (ΔE 13.6 < 15): dos de las tres
     clases se confunden entre sí.
   - **Un día sin registros no es 0%**: la línea se corta. Dibujar el cero haría
     ver un colegio vacío donde solo hubo un festivo.
*/
import { useState } from 'react';
import '../styles/charts.css';

export const SERIE = '#059669';        // acento de marca; pasa todos los checks
export const SERIE_SUAVE = '#a7d9c6';  // mismo tono atenuado, para el resto
export const RAMPA_GRAVEDAD = ['#e8977c', '#dd6042', '#a32d1e'];  // leve→grave

const fmt = (n) => (Number.isInteger(n) ? n : n.toFixed(1));

/* Tooltip compartido. Se posiciona en coordenadas del contenedor, no del SVG,
   para que no lo recorte el viewBox. */
function Tip({ x, y, children }) {
  return (
    <div className="chart-tip" style={{ left: x, top: y }} role="tooltip">
      {children}
    </div>
  );
}

/* ── Línea temporal ───────────────────────────────────────────────────
   Una sola serie: sin leyenda (el título la nombra). Crosshair + tooltip.

   **Las etiquetas de los ejes son HTML, no `<text>` del SVG.** Dentro de un
   `viewBox` que se estira al ancho del contenedor, el texto escala con él: los
   mismos 12,5px del CSS se veían a 19px en escritorio (más grandes que el
   título de la tarjeta) y a 5,5px en móvil (ilegibles). Posicionadas por
   porcentaje sobre el gráfico, miden lo que dicen en cualquier ancho. */
export function LineChart({ data, yKey, labelKey, alto = 190, unidad = '%',
                            dominio, huecoSi }) {
  const [hover, setHover] = useState(null);
  const W = 760, H = alto;   // el viewBox ya no reserva márgenes para texto

  const vals = data.filter(d => !huecoSi?.(d)).map(d => d[yKey]);
  const min = dominio ? dominio[0] : Math.max(0, Math.floor(Math.min(...vals, 100) / 10) * 10 - 5);
  const max = dominio ? dominio[1] : Math.ceil(Math.max(...vals, 1) / 10) * 10;
  const rango = max - min || 1;

  const px = (i) => (data.length > 1 ? (i / (data.length - 1)) * W : W / 2);
  const py = (v) => H - ((v - min) / rango) * H;
  const pct = (n, total) => `${(n / total) * 100}%`;

  // Tramos: cada corte por falta de datos abre una polilínea nueva, así la
  // línea se interrumpe en vez de bajar a cero.
  const tramos = [];
  let actual = [];
  data.forEach((d, i) => {
    if (huecoSi?.(d)) { if (actual.length) tramos.push(actual); actual = []; return; }
    actual.push([px(i), py(d[yKey])]);
  });
  if (actual.length) tramos.push(actual);

  const ticks = [min, min + rango / 2, max];
  const cadaN = Math.ceil(data.length / 8);

  return (
    <div className="chart">
      <div className="chart__plot">
        <div className="chart__ylabels" aria-hidden="true">
          {ticks.map(t => (
            <span key={t} style={{ top: pct(py(t), H) }}>{fmt(t)}{unidad}</span>
          ))}
        </div>

        <svg viewBox={`0 0 ${W} ${H}`} className="chart__svg" role="img"
          onMouseLeave={() => setHover(null)}>
          {ticks.map(t => (
            <line key={t} x1={0} x2={W} y1={py(t)} y2={py(t)} className="chart__grid" />
          ))}

          {tramos.map((t, i) => (
            <polyline key={i} className="chart__line" points={t.map(p => p.join(',')).join(' ')}
              style={{ stroke: SERIE }} />
          ))}

          {hover !== null && !huecoSi?.(data[hover]) && (
            <>
              <line x1={px(hover)} x2={px(hover)} y1={0} y2={H} className="chart__crosshair" />
              <circle cx={px(hover)} cy={py(data[hover][yKey])} r={4.5}
                className="chart__dot" style={{ fill: SERIE }} />
            </>
          )}

          {/* Bandas de captura: el objetivo del ratón es más ancho que la marca. */}
          {data.map((d, i) => (
            <rect key={i} x={px(i) - W / (data.length * 2) - 1} y={0}
              width={W / data.length + 2} height={H} fill="transparent"
              onMouseEnter={() => setHover(i)} />
          ))}
        </svg>

        {hover !== null && (
          <Tip x={pct(px(hover), W)} y={4}>
            <strong>{data[hover][labelKey]}</strong>
            {huecoSi?.(data[hover])
              ? <span>Sin registros</span>
              : <span>{fmt(data[hover][yKey])}{unidad}</span>}
          </Tip>
        )}
      </div>

      <div className="chart__xlabels" aria-hidden="true">
        {data.map((d, i) => (i % cadaN === 0 ? (
          <span key={i} style={{ left: pct(px(i), W) }}>{d[labelKey]}</span>
        ) : null))}
      </div>
    </div>
  );
}

/* ── Barras horizontales ──────────────────────────────────────────────
   Para categorías con nombre largo (salones, artículos). `peor` recibe el
   índice a destacar: el resto queda en el tono atenuado. */
export function BarsH({ data, labelKey, valueKey, unidad = '%', notaKey, destacar,
                        maximo, muestraKey, minMuestra = 0 }) {
  const max = maximo ?? Math.max(...data.map(d => d[valueKey]), 1);
  const flojo = (d) => muestraKey && d[muestraKey] < minMuestra;
  return (
    <div className="barsh">
      {data.map((d, i) => (
        <div className={`barsh__row${flojo(d) ? ' barsh__row--flojo' : ''}`} key={i}>
          <span className="barsh__label" title={d[labelKey]}>{d[labelKey]}</span>
          <span className="barsh__track">
            <span className="barsh__fill"
              style={{
                width: `${Math.max((d[valueKey] / max) * 100, 1.5)}%`,
                // Muestra insuficiente = gris, nunca el acento: un 75% sobre 16
                // registros no puede competir visualmente con uno sobre 1.800.
                background: flojo(d) ? '#d8d6e4' : destacar === i ? SERIE : SERIE_SUAVE,
              }} />
          </span>
          <span className="barsh__value">
            {fmt(d[valueKey])}{unidad}
            {flojo(d) && <span className="barsh__flag" title="Muestra insuficiente">*</span>}
            {notaKey && <em className="barsh__note">{d[notaKey]}</em>}
          </span>
        </div>
      ))}
      {muestraKey && data.some(flojo) && (
        <p className="barsh__aviso">
          * Menos de {minMuestra} registros: el porcentaje no sostiene una comparación.
        </p>
      )}
    </div>
  );
}

/* ── Columnas ─────────────────────────────────────────────────────────
   Para categorías cortas y ordenadas (día de la semana, hora de clase). */
export function Columns({ data, labelKey, valueKey, unidad = '%', destacar, subKey,
                          muestraKey, minMuestra = 0 }) {
  const [hover, setHover] = useState(null);
  const flojo = (d) => muestraKey && d[muestraKey] < minMuestra;
  // El dominio se calcula IGNORANDO las columnas sin muestra: un 100% sobre 4
  // registros estiraba el eje y aplastaba las diferencias reales del resto.
  const vals = data.filter(d => !flojo(d)).map(d => d[valueKey]);
  const base = vals.length ? vals : data.map(d => d[valueKey]);
  // Base recortada, con el eje rotulado: en tasas del 85–95% una base en 0
  // aplasta todas las diferencias que la gráfica existe para mostrar.
  const min = Math.max(0, Math.floor(Math.min(...base) / 5) * 5 - 5);
  const max = Math.ceil(Math.max(...base) / 5) * 5;
  const rango = max - min || 1;

  return (
    <div className="cols">
      <div className="cols__plot">
        {data.map((d, i) => (
          <div className="cols__col" key={i}
            onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <span className="cols__value">
              {fmt(d[valueKey])}{unidad}{flojo(d) && <span className="cols__flag">*</span>}
            </span>
            <span className="cols__bar"
              style={{
                height: `${Math.max(Math.min(((d[valueKey] - min) / rango) * 100, 100), 2)}%`,
                background: flojo(d) ? '#d8d6e4' : destacar === i ? SERIE : SERIE_SUAVE,
              }} />
            <span className="cols__label">{d[labelKey]}</span>
            {hover === i && subKey && (
              <span className="cols__tip">
                {d[subKey]} registros{flojo(d) ? ' · muestra insuficiente' : ''}
              </span>
            )}
          </div>
        ))}
      </div>
      <p className="cols__base">
        {muestraKey && data.some(flojo) && (
          <span className="cols__aviso">* menos de {minMuestra} registros · </span>
        )}
        Eje desde {min}{unidad}
      </p>
    </div>
  );
}

/* ── Barras apiladas (gravedad por mes) ───────────────────────────────
   Rampa ordinal de una hue + leyenda siempre visible: la identidad nunca queda
   solo en el color. Separación de 2px entre segmentos. */
export function StackedBars({ data, labelKey, series, alto = 150 }) {
  const [hover, setHover] = useState(null);
  const total = (d) => series.reduce((s, k) => s + (d[k.key] || 0), 0);
  const max = Math.max(...data.map(total), 1);

  return (
    <div className="stack">
      <div className="stack__plot" style={{ height: alto }}>
        {data.map((d, i) => (
          <div className="stack__col" key={i}
            onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <span className="stack__total">{total(d)}</span>
            <span className="stack__bar" style={{ height: `${(total(d) / max) * 100}%` }}>
              {series.map((s, j) => (
                d[s.key] > 0 && (
                  <span key={j} className="stack__seg"
                    style={{ flexGrow: d[s.key], background: s.color }}
                    title={`${s.label}: ${d[s.key]}`} />
                )
              ))}
            </span>
            <span className="stack__label">{d[labelKey]}</span>
            {hover === i && (
              <span className="stack__tip">
                {series.map(s => (
                  <span key={s.key}>
                    <i style={{ background: s.color }} />{s.label}: {d[s.key] || 0}
                  </span>
                ))}
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="chart-legend">
        {series.map(s => (
          <span key={s.key} className="chart-legend__item">
            <i style={{ background: s.color }} />{s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ── Medidor ──────────────────────────────────────────────────────────
   Una razón contra un límite. Es la forma correcta para "cobertura": un dato
   único con contexto, donde una gráfica de una sola barra sería ruido. */
export function Meter({ valor, etiqueta, detalle, umbral, invertir = false }) {
  const malo = umbral != null && (invertir ? valor > umbral : valor < umbral);
  return (
    <div className={`meter${malo ? ' meter--alerta' : ''}`}>
      <div className="meter__head">
        <span className="meter__label">{etiqueta}</span>
        <span className="meter__value">{fmt(valor)}%</span>
      </div>
      <span className="meter__track">
        <span className="meter__fill" style={{ width: `${Math.min(valor, 100)}%` }} />
        {umbral != null && <span className="meter__umbral" style={{ left: `${umbral}%` }} />}
      </span>
      {detalle && <p className="meter__detail">{detalle}</p>}
    </div>
  );
}

/* ── Tarjeta de indicador ─────────────────────────────────────────────
   Un número con su variación. No es una gráfica y no debe serlo. */
export function StatTile({ etiqueta, valor, unidad, delta, subirEsBueno = true, nota }) {
  const hayDelta = delta && delta.disponible && delta.valor !== 0;
  const bueno = hayDelta && (delta.valor > 0) === subirEsBueno;
  return (
    <div className="tile">
      <span className="tile__label">{etiqueta}</span>
      <span className="tile__value">
        {fmt(valor)}<em>{unidad}</em>
      </span>
      {hayDelta ? (
        <span className={`tile__delta tile__delta--${bueno ? 'ok' : 'mal'}`}>
          {delta.valor > 0 ? '▲' : '▼'} {fmt(Math.abs(delta.valor))}{unidad} vs. período anterior
        </span>
      ) : (
        <span className="tile__delta tile__delta--none">
          {nota || 'Sin período anterior comparable'}
        </span>
      )}
    </div>
  );
}
