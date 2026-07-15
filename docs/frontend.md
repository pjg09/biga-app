# Frontend — Referencia de arquitectura

> Cómo está estructurado el cliente React (`web/`): routing, autenticación, capa de
> servicios, dashboards y convenciones. Las decisiones de backend viven en
> `docs/architecture.md`; las reglas para trabajar con la IA en `CLAUDE.md`.

---

## Stack y arranque

- **React + Vite** (dev server en `:5173`). Sin TypeScript, sin librería de estado
  (solo hooks de React), sin librería de UI (CSS a mano).
- **Routing**: `react-router-dom` v7.
- Requiere `web/.env` (gitignored) con `VITE_API_URL=http://localhost:8000`. Sin esa
  var, todos los `fetch` van a `undefined/...` y el front falla en silencio.
- Levantar: `docker compose up -d web` (o `npm run dev` dentro de `web/`). Ver
  `docs/runbook.md`.

---

## Estructura de carpetas

```
web/src/
├── main.jsx              # entrypoint: BrowserRouter + <App/>
├── App.jsx               # tabla de rutas + ProtectedRoute + DashboardRedirect
├── index.css             # tokens globales y estilos base
├── pages/                # una página por ruta
│   ├── LandingPage.jsx   # landing pública (compone components/)
│   ├── LoginPage.jsx     # /login
│   ├── JustifyPage.jsx   # /justificar/:token (PÚBLICA, sin JWT)
│   ├── TeacherDashboard.jsx  # /dashboard/teacher (+ exporta vistas reutilizables)
│   ├── PAEDashboard.jsx      # /dashboard/pae
│   └── AdminDashboard.jsx    # /dashboard/admin
├── components/           # componentes de la landing + ProtectedRoute
├── services/             # un archivo por dominio + api.js (cliente HTTP)
├── styles/               # un CSS por componente/página (mismo nombre)
└── hooks/                # hooks reutilizables (scroll, etc.)
```

---

## Routing y autenticación

Rutas en `App.jsx`:

| Ruta | Página | Protección |
|---|---|---|
| `/` | LandingPage | pública |
| `/login` | LoginPage | pública |
| `/justificar/:token` | JustifyPage | **pública** (el token UUID es la autorización) |
| `/dashboard/teacher` | TeacherDashboard | `ProtectedRoute allowedRoles={['TEACHER']}` |
| `/dashboard/pae` | PAEDashboard | `ProtectedRoute allowedRoles={['PAE_OPERATOR']}` |
| `/dashboard/admin` | AdminDashboard | `ProtectedRoute allowedRoles={['ADMIN']}` |
| `/dashboard` | — | `DashboardRedirect` (manda al dashboard según rol) |
| `*` | — | redirige a `/` |

**Estado de sesión = `localStorage`.** No hay Context ni store: el token y el usuario
viven en `localStorage` (`token`, `user`) y se leen con `JSON.parse(localStorage.getItem('user'))`.

- `LoginPage` hace `POST /auth/login` (**form-urlencoded**, campos `username`/`password`),
  guarda `access_token`, luego `GET /auth/me` y guarda el `user`. Redirige por rol.
- `ProtectedRoute` (`components/ProtectedRoute.jsx`): sin token → `/login`; rol no
  permitido → lo manda a **su** dashboard. No valida el token contra el backend (lo
  hace cada request vía el 401).
- Logout: borra `token` y `user` de `localStorage` y navega a `/login`.

> El `institution_id` y el rol viven dentro del JWT/`user`; el front no los maneja
> explícitamente — el backend resuelve el tenant desde el token en cada request.

---

## Capa de servicios (`services/`)

Un archivo por dominio (`attendance.js`, `pae.js`, `students.js`, `agendatorio.js`,
`departures.js`, `admin.js`) sobre un cliente único **`api.js`**:

```js
api.get(path)              // GET  → JSON
api.post(path, body)       // POST  JSON
api.patch(path, body)      // PATCH JSON
api.postForm(path, formData) // POST multipart (archivos: firma, foto)
```

Reglas de `api.js`:
- Base URL desde `import.meta.env.VITE_API_URL`.
- Adjunta `Authorization: Bearer <token>` desde `localStorage` en cada request.
- `!res.ok` → lanza `Error` con `.status` y el `detail` del backend.
- **`204 No Content` → devuelve `null`** (ej. `archive`/`unarchive`); sin ese guard,
  `res.json()` rompería con body vacío.
- `postForm` **no** fija `Content-Type` (el browser pone el boundary del multipart).

Ejemplo de servicio con archivo:
```js
uploadPhoto: (id, file) => {
  const fd = new FormData();
  fd.append('photo', file, file.name);
  return api.postForm(`/students/${id}/photo`, fd);
},
```

---

## Dashboards: estructura y reutilización

Los tres dashboards siguen el mismo patrón: **sidebar con `NavItem`s + `activeNav`
(useState) + render condicional de vistas**. No hay sub-rutas; la navegación interna
es estado local.

**Regla clave — reutilización entre dashboards:** el operador PAE es un docente con
funciones extra, así que `TeacherDashboard.jsx` **exporta** sus vistas de aula
(`AttendanceView`, `DeparturesView`, `ScheduleView`, `ConvivenciaView`,
`HistorialView`, `MensajesView`) y `PAEDashboard.jsx` las **importa**. `AdminDashboard`
reutiliza `StudentsView` de `PAEDashboard`.

> Un módulo de aula nuevo debe exportarse desde `TeacherDashboard` y engancharse en
> **ambos** dashboards (agregar el `NavItem` + la línea de render + el título en
> `NAV_TITLES`). Olvidar uno deja la feature a medias.

Componente compartido: **`StudentSearch`** (en `TeacherDashboard.jsx`) — buscador de
estudiante con selectores de **grado** y **salón** + texto (nombre/documento), usado
en Convivencia e Historial. Recibe `selected`/`onSelect`/`onClear`.

Título de pestaña: cada dashboard setea `document.title` con un `useEffect` al montar
(`BIGA - Profesores`, `BIGA - PAE`, `BIGA - Administración`); Landing y Login también.

---

## Convenciones de estilo (CSS)

- **Un CSS por componente/página** en `web/src/styles/` con el mismo nombre
  (`Hero.jsx` → `styles/hero.css`).
- Los dashboards comparten **`styles/dashboard.css`** (clases `dash__*`); las variables
  de diseño (colores, sombras) son tokens en `:root` dentro de ese archivo.
- Estilos globales base en `web/src/index.css`.
- Clases con convención tipo BEM (`dash__stat-card`, `att-search__item`, `conv-article--on`).

---

## Gotchas del frontend

- **Escapes `\uXXXX` literales en JSX**: al escribir texto con acentos/caracteres
  especiales vía tools de edición, a veces quedan como escape literal (`Salón`,
  `…`). En **JSX-texto/atributo** NO se interpretan y se ven literales en la UI.
  Detectar: `grep -rn '\\u00\|\\u2026' web/src`. Corregir al carácter UTF-8 real.
- **Fotos y firmas**: el backend devuelve URLs **presignadas** (MinIO, expiran en 1h);
  se cargan directo en `<img src>`. La foto se sube con `studentService.uploadPhoto`
  (multipart). Ver `CLAUDE.md` (sección de foto del estudiante).
- **Dependencia npm nueva**: Vite falla con `Failed to resolve import "..."` por el
  volumen anónimo `node_modules`; rebuildear con `--renew-anon-volumes` (ver `CLAUDE.md`).
- **Verificar que compila sin navegador**:
  `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/src/pages/X.jsx`
  (200 = OK; 500 = error de sintaxis) + `docker compose logs web | grep -i error`.

---

*Referencia de arquitectura del frontend — BIGA*
