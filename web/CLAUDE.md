# CLAUDE.md — Frontend (`web/`)

Complementa el `CLAUDE.md` de la raíz, que sigue siendo la referencia de arquitectura, multi-tenant y backend.
Referencia extensa del front: `docs/frontend.md`.

## Convenciones

- Cada componente tiene su propio archivo CSS en `web/src/styles/` con el mismo nombre: `Hero.jsx` → `styles/hero.css`.
- Los estilos globales y variables van en `web/src/index.css`.
- El CSS de `web/src` es plano y **global (sin scope por componente)**; `dashboard.css` lo comparten Teacher/PAE/Admin (los cambios se reflejan en los tres). Para retocar una sola vista, scopear con una clase wrapper/modificadora en el card (ej. `.att-today`, `.dep-scale`, `.hist-scale`); para pisar reglas base compartidas (`.btn`, `.dash__student-group`) usar selectores de **2 clases** (una sola pierde el desempate de especificidad). Colisión conocida: `dashboard.css` define `.btn--primary{width:100%}` sin scope → App.jsx importa los dashboards eager, así que se filtra a la landing (scopeado bajo `.dash`).
- Componente `StudentPhoto` (exportado de `TeacherDashboard.jsx`): miniatura de foto + lightbox click-para-ampliar (reusa `.pae-lightbox`). Usarlo en vez de `<img className="dash__table-photo">` suelto.
- Las páginas viven en `web/src/pages/`, los componentes reutilizables en `web/src/components/`.
- Los hooks personalizados van en `web/src/hooks/`.
- El frontend requiere `web/.env` (gitignored, sin `.env.example`) con `VITE_API_URL=http://localhost:8000`. Sin esa var, `fetch` va a `undefined/...` y todo el front falla en silencio. El CORS del API ya permite `http://localhost:5173`. (`vite.config.js` tiene un proxy `/api-proxy` que el código actual no usa.)
- `PAEDashboard.jsx` **reutiliza** las vistas de aula de `TeacherDashboard.jsx` (`import { AttendanceView, ConvivenciaView, HistorialView, ... }`). El operador PAE es un docente con funciones extra: un módulo de aula nuevo debe exportarse desde `TeacherDashboard` y engancharse en **ambos** dashboards (nav + render). El componente `StudentSearch` (buscador grado/salón/nombre) vive en `TeacherDashboard` y se reutiliza.

## Gotchas del navegador

- Los dashboards están tras `ProtectedRoute` (JWT), pero **sí se pueden conducir en headless**: navegar a `/login`, fijar los inputs con el setter nativo (`Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set` + evento `input`; asignar `.value` a secas React lo ignora), pulsar `.login__submit` y navegar por `.dash__nav-item`. Alternativa para CSS puro: repro estático con la hoja servida por Vite, o `google-chrome-stable --headless=new --remote-debugging-port=N` + Python `websockets` (CDP) para leer estilos/anchos computados reales (`CSS.getMatchedStylesForNode`, `getBoundingClientRect`). El hero de la landing es `100svh`: para capturar secciones inferiores en headless, overridear temporalmente `.hero{min-height:auto}` y `.reveal{opacity:1 !important;transform:none !important}`.
- En este headless, `Input.dispatchMouseEvent` (clic y `mouseMoved`) **no llega a la página**: ni los clics ni el `:hover` se disparan y todo parece roto. Usar eventos DOM (`el.click()`, que además burbujea y es justo lo que hay que probar en bugs de propagación) y, para `:hover`, `CSS.forcePseudoState` con un `nodeId` recién pedido (`DOM.getDocument` → `DOM.querySelector`), desanidando bien la respuesta CDP (`r["result"]["nodeId"]`).
- `backdrop-filter`, `filter`, `transform` y `will-change` convierten al elemento en **bloque contenedor de sus descendientes `position: fixed`**: esos hijos pasan a medirse contra la caja del padre, no contra el viewport. Rompió el menú móvil (`.navbar--scrolled` llevaba el `backdrop-filter` y recortaba el panel a los ~79px de la barra, solo tras hacer scroll). Solución aplicada: el cristal vive en `.navbar::before`, no en `.navbar`. Antes de poner uno de esos cuatro en un contenedor, comprobar si tiene hijos `fixed`.
- Al escribir texto con acentos/caracteres especiales en JSX vía las tools de edición, a veces quedan como escape literal (ej. `Sal\u00f3n` se ve literal en vez de `Salón`; `\u2026` en vez de `…`). En **JSX-texto/atributo** esos escapes NO se interpretan y se ven literales en la UI. Detectar con `grep -rn '\\u00\|\\u2026' web/src`; corregir con `perl -CSD -i -pe 's/\\u2026/\x{2026}/g' <archivo>` (al carácter UTF-8 real).
- El servicio `web` monta un volumen anónimo en `/app/node_modules` (compose). Tras agregar una dependencia npm nueva, Vite falla con `Failed to resolve import "..."` aunque esté en `package.json`: el volumen viejo tapa el `node_modules` de la imagen. Rebuildear renovando el volumen: `docker compose up -d --build --force-recreate --renew-anon-volumes web` (y matar el contenedor viejo con el workaround de AppArmor si `stop` falla).

## Verificar un cambio de front

`curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/src/pages/X.jsx` (200 = transforma; error de sintaxis da 500) y `docker compose logs web | grep -iE "error"`.

**200 y logs limpios NO significan que la pantalla funcione**: un error en tiempo de ejecución (p. ej. borrar un helper compartido como `fmtShort`) deja la app **en blanco** con Vite sirviendo 200 y sin registrar nada. Comprobar el DOM renderizado; para ver el error real, capturar `Runtime.exceptionThrown` / `Log.entryAdded` por CDP.
