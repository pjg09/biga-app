import { useState, useCallback, useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { attendanceService } from '../services/attendance';
import { departureService } from '../services/departures';
import { studentService } from '../services/students';
import { agendatorioService } from '../services/agendatorio';
import '../styles/dashboard.css';

const STATUS_LABEL = { PRESENT: 'Presente', ABSENT: 'Ausente', LATE: 'Tardanza', JUSTIFIED: 'Justificada' };
const STATUS_CLASS  = { PRESENT: 'green',   ABSENT: 'red',     LATE: 'yellow',   JUSTIFIED: 'blue' };
const RELATIONSHIP_LABEL = { PADRE: 'Padre', MADRE: 'Madre', ACUDIENTE: 'Acudiente', OTRO: 'Otro' };
const uniqueSorted = (values) => [...new Set(values)].sort((a, b) => a.localeCompare(b, 'es'));

const AVATARS = [
  { bg: '#ede9fe', color: '#6d28d9' },
  { bg: '#dbeafe', color: '#1d4ed8' },
  { bg: '#fef3c7', color: '#b45309' },
  { bg: '#d1fae5', color: '#065f46' },
  { bg: '#fee2e2', color: '#991b1b' },
];

const NAV_TITLES = {
  attendance: 'Asistencia',
  departures: 'Salidas tempranas',
  students:   'Mis estudiantes',
  schedule:   'Horario',
  conduct:    'Convivencia',
  absences:   'Inasistencias sin justificar',
  history:    'Historial',
  messages:   'Mensajes',
};

function initials(first, last) {
  return `${first?.[0] ?? ''}${last?.[0] ?? ''}`.toUpperCase();
}

function nowTime() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'Buenos días' : h < 18 ? 'Buenas tardes' : 'Buenas noches';
}

function dateLabel() {
  return new Date().toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' });
}

export default function TeacherDashboard() {
  const [activeNav, setActiveNav] = useState('attendance');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => { document.title = 'BIGA - Profesores'; }, []);
  // Cierra el cajón móvil al navegar entre secciones sin tocar cada NavItem.
  useEffect(() => { setSidebarOpen(false); }, [activeNav]);
  const user     = JSON.parse(localStorage.getItem('user') || '{}');
  const initials = `${user.first_name?.[0] ?? ''}${user.last_name?.[0] ?? ''}`.toUpperCase();
  const fullName = `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim();

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  }, [navigate]);

  return (
    <div className="dash dash--teacher">
      {sidebarOpen && <div className="dash__sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      {/* Sidebar */}
      <aside className={`dash__sidebar${sidebarOpen ? ' dash__sidebar--open' : ''}`}>
        <a href="/" className="dash__logo">
          <LogoIcon />
          <span className="dash__logo-text">BIGA</span>
        </a>

        <nav className="dash__nav" aria-label="Navegación">
          <div className="dash__nav-section">
            <p className="dash__nav-label">General</p>
            <NavItem id="attendance" active={activeNav} icon={<ClipboardIcon />} label="Asistencia"        onClick={setActiveNav} />
            <NavItem id="departures" active={activeNav} icon={<LogoutIcon />}    label="Salidas tempranas" onClick={setActiveNav} />
            <NavItem id="students"   active={activeNav} icon={<UsersIcon />}     label="Estudiantes"       onClick={setActiveNav} />
            <NavItem id="schedule"   active={activeNav} icon={<CalendarIcon />}  label="Horario"           onClick={setActiveNav} />
          </div>
          <div className="dash__nav-section">
            <p className="dash__nav-label">Seguimiento</p>
            <NavItem id="conduct"  active={activeNav} icon={<ShieldIcon />}    label="Convivencia"   onClick={setActiveNav} />
            <NavItem id="absences" active={activeNav} icon={<ClipboardIcon />} label="Inasistencias" onClick={setActiveNav} />
            <NavItem id="history"  active={activeNav} icon={<BookIcon />}    label="Historial"   onClick={setActiveNav} />
            <NavItem id="messages" active={activeNav} icon={<MessageIcon />} label="Mensajes"    onClick={setActiveNav} />
          </div>
        </nav>

        <div className="dash__sidebar-footer">
          <div className="dash__user-card">
            <div className="dash__user-avatar">{initials || 'U'}</div>
            <div className="dash__user-info">
              <p className="dash__user-name">{fullName || 'Usuario'}</p>
              <p className="dash__user-role">Docente</p>
            </div>
            <button className="dash__logout-btn" onClick={logout} aria-label="Cerrar sesión">
              <LogoutIcon />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="dash__main">
        <div className="dash__page-header">
          <div className="dash__page-header-main">
            <button
              type="button"
              className={`dash__burger${sidebarOpen ? ' dash__burger--open' : ''}`}
              onClick={() => setSidebarOpen(v => !v)}
              aria-label={sidebarOpen ? 'Cerrar menú' : 'Abrir menú'}
              aria-expanded={sidebarOpen}
            >
              <span /><span /><span />
            </button>
            <div className="dash__page-header-text">
              <p className="dash__page-greeting">{greeting()} · {dateLabel()}</p>
              <h1 className="dash__page-title">{NAV_TITLES[activeNav]}</h1>
            </div>
          </div>
          <span className="dash__page-badge dash__page-badge--teacher">Docente</span>
        </div>

        <main className="dash__content">
          {activeNav === 'attendance' && <AttendanceView />}
          {activeNav === 'departures' && <DeparturesView />}
          {activeNav === 'students'   && <TeacherStudentsView />}
          {activeNav === 'schedule'   && <ScheduleView />}
          {activeNav === 'conduct'    && <ConvivenciaView />}
          {activeNav === 'absences'   && <AbsencesView />}
          {activeNav === 'history'    && <HistorialView />}
          {activeNav === 'messages'   && <MensajesView />}
        </main>
      </div>
    </div>
  );
}

/* ── Attendance view ─────────────────────────────────────────── */
export function AttendanceView() {
  const [classes, setClasses] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [selected, setSelected] = useState(null);  // class_period_id de la clase abierta

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await attendanceService.getToday();
      setClasses(res.classes || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Vista de una clase abierta: al volver, recargamos la lista para refrescar el
  // badge "Tomada".
  if (selected) {
    return (
      <ClassAttendance
        classPeriodId={selected}
        onBack={() => { setSelected(null); load(); }}
      />
    );
  }

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando tus clases de hoy…</span></div>;
  if (error) {
    return (
      <div className="dash__empty">
        <AlertIcon color="#ef4444" /><span>{error}</span>
        <button className="btn--secondary" style={{ width: 'auto', marginTop: 8 }} onClick={load}>Reintentar</button>
      </div>
    );
  }
  if (!classes || classes.length === 0) {
    return (
      <div className="dash__empty">
        <CalendarIcon />
        <span>No tienes clases asignadas para hoy.</span>
      </div>
    );
  }

  return (
    <div className="card dash__list-card att-today">
      <div className="dash__list-header">
        <span className="dash__list-title">Clases de hoy</span>
        <span className="dash__list-title">{classes.length}</span>
      </div>

      {classes.map(c => (
        <button
          key={c.class_period_id}
          className="dash__student-row att-class-row"
          onClick={() => setSelected(c.class_period_id)}
        >
          <div className="dash__student-avatar" style={{ background: '#ede9fe', color: '#6d28d9' }}>
            {c.period_order}
          </div>
          <div className="dash__student-info">
            <p className="dash__student-name">{c.name}</p>
            <p className="dash__student-group">
              {c.grade_name} {c.group_name} · {c.start_time?.slice(0, 5)} - {c.end_time?.slice(0, 5)}
            </p>
          </div>
          <div className="att-class-row__badges">
            {c.is_first_hour && <span className="dash__badge dash__badge--blue">1ª hora</span>}
            <span className={`dash__badge dash__badge--${c.already_taken ? 'green' : 'yellow'}`}>
              {c.already_taken ? 'Tomada' : 'Pendiente'}
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}

/* ── Toma de lista de una clase específica ───────────────────── */
function ClassAttendance({ classPeriodId, onBack }) {
  const [data, setData]       = useState(null);
  const [marks, setMarks]     = useState({});   // student_id -> 'PRESENT' | 'ABSENT'
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [saving, setSaving]   = useState(false);
  const [arrivingId, setArrivingId] = useState(null);
  const [toast, setToast]     = useState(null);

  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await attendanceService.getClass(classPeriodId);
      setData(res);
      // No se pre-selecciona nada: el docente debe marcar explícitamente
      // Presente/Ausente por cada estudiante antes de poder guardar.
      setMarks({});
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [classPeriodId]);

  useEffect(() => { load(); }, [load]);

  const setMark = useCallback((id, status) => {
    setMarks(prev => ({ ...prev, [id]: status }));
  }, []);

  const submit = useCallback(async () => {
    if (!data) return;
    setSaving(true);
    try {
      const entries = data.students.map(s => ({ student_id: s.student_id, status: marks[s.student_id] }));
      await attendanceService.submit(data.class_period_id, entries);
      showToast(data.is_first_hour
        ? 'Asistencia registrada. Los ausentes serán notificados.'
        : 'Asistencia registrada.');
      await load();
    } catch (e) {
      showToast(e.message, 'error');
    } finally {
      setSaving(false);
    }
  }, [data, marks, showToast, load]);

  const markArrived = useCallback(async (student) => {
    if (!student.record_id) return;
    setArrivingId(student.student_id);
    try {
      await attendanceService.markArrived(student.record_id);
      setData(prev => ({
        ...prev,
        students: prev.students.map(s =>
          s.student_id === student.student_id ? { ...s, status: 'LATE' } : s),
      }));
      showToast(`${student.first_name} marcado como tardanza`);
    } catch (e) {
      showToast(e.message, 'error');
    } finally {
      setArrivingId(null);
    }
  }, [showToast]);

  const backBtn = (
    <button className="btn--secondary att-back" style={{ width: 'auto' }} onClick={onBack}>
      Clases de hoy
    </button>
  );

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando la clase…</span></div>;
  if (error) {
    return (
      <div className="dash__empty">
        <AlertIcon color="#ef4444" /><span>{error}</span>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button className="btn--secondary" style={{ width: 'auto' }} onClick={load}>Reintentar</button>
          <button className="btn--secondary" style={{ width: 'auto' }} onClick={onBack}>Volver</button>
        </div>
      </div>
    );
  }

  const total = data.students.length;
  // En la toma de lista los marks son la fuente; en el registro de hoy, el status ya guardado.
  const stateOf = (s) => (data.already_taken ? s.status : marks[s.student_id]);
  const present = data.students.filter(s => stateOf(s) === 'PRESENT').length;
  const absent  = data.students.filter(s => stateOf(s) === 'ABSENT').length;
  const late    = data.students.filter(s => stateOf(s) === 'LATE').length;
  const pending = data.already_taken ? 0 : total - present - absent;
  const allMarked = pending === 0;

  return (
    <>
      {toast && (
        <div className={`dash__toast dash__toast--${toast.type}`} role="alert">
          {toast.type === 'success' ? <CheckIcon /> : <AlertIcon />}{toast.msg}
        </div>
      )}

      {backBtn}

      <div className="att-head card">
        <div>
          <p className="att-head__period">
            {data.period_name} · Grupo {data.group_name}
            {data.is_first_hour && <span className="dash__badge dash__badge--blue" style={{ marginLeft: 8 }}>1ª hora</span>}
          </p>
          <p className="att-head__sub">
            {data.start_time?.slice(0, 5)} - {data.end_time?.slice(0, 5)} · {total} estudiantes
            {!data.is_first_hour && ' · sin notificación'}
          </p>
        </div>
        <div className="att-head__counts">
          <span className="dash__badge dash__badge--green">{present} presentes</span>
          {late > 0   && <span className="dash__badge dash__badge--yellow">{late} tardanzas</span>}
          <span className="dash__badge dash__badge--red">{absent} ausentes</span>
          {!data.already_taken && pending > 0 && (
            <span className="dash__badge dash__badge--gray">{pending} pendientes</span>
          )}
        </div>
      </div>

      <div className="card dash__list-card att-today">
        <div className="dash__list-header">
          <span className="dash__list-title">
            {data.already_taken ? 'Registro de hoy' : 'Toma de asistencia'}
          </span>
          {!data.already_taken && (
            <button
              className="btn--confirm"
              style={{ flex: '0 0 auto' }}
              onClick={submit}
              disabled={saving || !allMarked}
              aria-busy={saving}
              title={allMarked ? undefined : 'Marca el estado de todos los estudiantes'}
            >
              {saving ? 'Guardando…' : allMarked ? 'Guardar asistencia' : `Faltan ${pending}`}
            </button>
          )}
        </div>

        {data.students.map((s, i) => {
          const av = AVATARS[i % AVATARS.length];
          const mark = marks[s.student_id];
          return (
            <div className="dash__student-row att-roster-row" key={s.student_id}>
              {s.photo_url
                ? <StudentPhoto src={s.photo_url} alt="" caption={`${s.first_name} ${s.last_name}`} />
                : <div className="dash__student-avatar" style={{ background: av.bg, color: av.color }}>{initials(s.first_name, s.last_name)}</div>}
              <div className="dash__student-info">
                <p className="dash__student-name">{s.first_name} {s.last_name}</p>
                <p className="dash__student-group">Doc. {s.document_number}</p>
              </div>

              {data.already_taken ? (
                <div className="att-roster-row__status">
                  <span className={`dash__badge dash__badge--${STATUS_CLASS[s.status] || 'green'}`}>
                    {STATUS_LABEL[s.status] || s.status}
                  </span>
                  {s.status === 'ABSENT' && (
                    <button
                      className="dash__table-register-btn"
                      onClick={() => markArrived(s)}
                      disabled={arrivingId === s.student_id}
                    >
                      {arrivingId === s.student_id ? 'Marcando…' : 'Llegó (tardanza)'}
                    </button>
                  )}
                </div>
              ) : (
                <div className="att-choice" role="group" aria-label={`Asistencia de ${s.first_name} ${s.last_name}`}>
                  <button
                    type="button"
                    className={`att-choice__btn att-choice__btn--present${mark === 'PRESENT' ? ' is-on' : ''}`}
                    aria-pressed={mark === 'PRESENT'}
                    onClick={() => setMark(s.student_id, 'PRESENT')}
                  >
                    Presente
                  </button>
                  <button
                    type="button"
                    className={`att-choice__btn att-choice__btn--absent${mark === 'ABSENT' ? ' is-on' : ''}`}
                    aria-pressed={mark === 'ABSENT'}
                    onClick={() => setMark(s.student_id, 'ABSENT')}
                  >
                    Ausente
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

/* ── Early departures view ───────────────────────────────────── */
export function DeparturesView() {
  const [query, setQuery]       = useState('');
  const [results, setResults]   = useState([]);
  const [selected, setSelected] = useState(null);
  const [time, setTime]         = useState(nowTime());
  const [reason, setReason]     = useState('');
  const [saving, setSaving]     = useState(false);
  const [list, setList]         = useState([]);
  const [toast, setToast]       = useState(null);
  const infoRef = useRef(null);
  const [photoSize, setPhotoSize] = useState(56);

  // La miniatura del estudiante seleccionado debe medir exactamente el alto
  // del bloque de texto (nombre + documento), borde a borde: se mide en JS
  // en vez de con CSS porque el tamaño intrínseco de la foto real (cientos
  // de px) rompe cualquier truco de `align-items: stretch` + `aspect-ratio`.
  useLayoutEffect(() => {
    if (!selected || !infoRef.current) return;
    const el = infoRef.current;
    const update = () => setPhotoSize(el.offsetHeight);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [selected]);

  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const loadList = useCallback(async () => {
    try {
      setList(await departureService.listToday());
    } catch { /* lista vacía si falla */ }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  useEffect(() => {
    if (selected || query.trim().length < 2) { setResults([]); return; }
    let active = true;
    const t = setTimeout(async () => {
      try {
        const r = await studentService.search(query.trim());
        if (active) setResults(r);
      } catch { /* ignore */ }
    }, 250);
    return () => { active = false; clearTimeout(t); };
  }, [query, selected]);

  const submit = useCallback(async (e) => {
    e.preventDefault();
    if (!selected) { showToast('Selecciona un estudiante', 'error'); return; }
    setSaving(true);
    try {
      await departureService.create({ student_id: selected.id, departure_time: `${time}:00`, reason });
      showToast(`Salida registrada para ${selected.full_name}. Se notificó al acudiente.`);
      setSelected(null); setQuery(''); setReason(''); setTime(nowTime());
      await loadList();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  }, [selected, time, reason, showToast, loadList]);

  return (
    <>
      {toast && (
        <div className={`dash__toast dash__toast--${toast.type}`} role="alert">
          {toast.type === 'success' ? <CheckIcon /> : <AlertIcon />}{toast.msg}
        </div>
      )}

      <div className="dep-scale dep-scale--sm">
      <form className="card att-form" onSubmit={submit}>
        <p className="dash__list-title" style={{ marginBottom: 4 }}>Registrar salida anticipada</p>

        {selected ? (
          <div className="att-selected att-selected--photo att-selected--dep">
            {selected.photo_url
              ? <StudentPhoto src={selected.photo_url} alt={selected.full_name} caption={selected.full_name} className="att-selected__photo" style={{ width: photoSize, height: photoSize }} />
              : <div className="dash__student-avatar att-selected__photo" style={{ background: '#ede9fe', color: '#6d28d9', width: photoSize, height: photoSize }}>
                  {(selected.full_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
                </div>}
            <div className="att-selected__info" ref={infoRef}>
              <span className="dash__student-name">{selected.full_name}</span>
              <span className="dash__student-group">Doc. {selected.document_number}{[selected.grade_name, selected.group_name].filter(Boolean).length ? ` · ${[selected.grade_name, selected.group_name].filter(Boolean).join(' ')}` : ''}</span>
            </div>
            <button type="button" className="att-selected__clear" onClick={() => setSelected(null)} aria-label="Cambiar">✕</button>
          </div>
        ) : (
          <div className="att-search">
            <input
              className="dash__field-input"
              placeholder="Buscar estudiante por nombre o documento…"
              value={query}
              onChange={e => setQuery(e.target.value)}
              autoComplete="off"
            />
            {results.length > 0 && (
              <div className="att-search__results">
                {results.map(r => (
                  <button type="button" key={r.id} className="att-search__item" onClick={() => { setSelected(r); setResults([]); }}>
                    <span className="dash__student-name">{r.full_name}</span>
                    <span className="dash__student-group">Doc. {r.document_number}{r.group_name ? ` · ${r.group_name}` : ''}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="att-form__row">
          <label className="dash__field" style={{ maxWidth: 160 }}>
            <span className="dash__field-label">Hora de salida</span>
            <input className="dash__field-input" type="time" value={time} onChange={e => setTime(e.target.value)} required style={{ width: 'auto', maxWidth: 110, textAlign: 'center' }} />
          </label>
        </div>

        <label className="dash__field">
          <span className="dash__field-label">Motivo <span className="dash__field-optional">(opcional)</span></span>
          <textarea
            className="dash__field-input"
            style={{ minHeight: 80, resize: 'vertical' }}
            value={reason}
            onChange={e => setReason(e.target.value)}
            maxLength={2000}
            placeholder="Ej: Cita médica"
          />
        </label>

        <button className="btn--confirm" type="submit" disabled={saving || !selected} aria-busy={saving}>
          {saving ? 'Registrando…' : 'Registrar y notificar'}
        </button>
      </form>

      <div className="card dash__list-card">
        <div className="dash__list-header">
          <span className="dash__list-title">Salidas de hoy</span>
          <span className="dash__student-group">{list.length}</span>
        </div>
        {list.length === 0 ? (
          <div className="dash__empty" style={{ padding: '32px 20px' }}>
            <LogoutIcon /><span>Sin salidas registradas hoy.</span>
          </div>
        ) : list.map((d, i) => {
          const av = AVATARS[i % AVATARS.length];
          return (
            <div className="dash__student-row" key={d.id}>
              {d.photo_url
                ? <StudentPhoto src={d.photo_url} alt="" caption={d.student_name} />
                : <div className="dash__student-avatar" style={{ background: av.bg, color: av.color }}>
                    {(d.student_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
                  </div>}
              <div className="dash__student-info">
                <p className="dash__student-name">{d.student_name || d.student_id}</p>
                <p className="dash__student-group">{d.reason || 'Sin motivo'}</p>
              </div>
              <span className="dash__student-time">{d.departure_time?.slice(0, 5)}</span>
            </div>
          );
        })}
      </div>
      </div>
    </>
  );
}

// Foto de estudiante con lightbox: click amplía la imagen a pantalla completa.
// Reutiliza el overlay .pae-lightbox. Se usa en todos los dashboards.
export function StudentPhoto({ src, alt = '', caption, className = 'dash__table-photo', style }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);
  // Cerrar el lightbox también es un clic, y varias filas que muestran una foto
  // son <button> que abren un detalle. Sin frenar la propagación aquí, el clic
  // con el que el usuario cierra el zoom activa la fila y lo mete en el reporte.
  const close = useCallback((e) => { e.stopPropagation(); setOpen(false); }, []);

  return (
    <>
      <img
        className={className}
        src={src}
        alt={alt}
        onClick={(e) => { e.stopPropagation(); setOpen(true); }}
        style={{ cursor: 'zoom-in', ...style }}
      />
      {/* Portal a <body>: el lightbox vive dentro de la fila, y una fila puede
          ser un <button>. Un <button> y un role="dialog" anidados dentro de otro
          <button> son HTML inválido. Ojo: el portal NO evita la propagación —
          React propaga por el árbol de componentes, no por el del DOM — así que
          los stopPropagation de arriba siguen siendo imprescindibles. */}
      {open && createPortal(
        <div className="pae-lightbox" onClick={close} role="dialog" aria-modal="true">
          <button className="pae-lightbox__close" onClick={close} aria-label="Cerrar">✕</button>
          <img className="pae-lightbox__img" src={src} alt={alt} onClick={(e) => e.stopPropagation()} />
          {caption && <p className="pae-lightbox__caption">{caption}</p>}
        </div>,
        document.body,
      )}
    </>
  );
}

function Spinner({ color = '#6d28d9', size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" className="dash__spinner">
      <circle cx="12" cy="12" r="10" stroke="rgba(0,0,0,0.1)" strokeWidth="2.5" />
      <path d="M12 2a10 10 0 0110 10" stroke={color} strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

/* ── Students view (lista real) ──────────────────────────────── */
export function TeacherStudentsView() {
  const [students, setStudents] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [query, setQuery]       = useState('');
  const [subjectFilter, setSubjectFilter] = useState('');
  const [gradeFilter, setGradeFilter]     = useState('');
  const [groupFilter, setGroupFilter]     = useState('');

  const [selectedId, setSelectedId]   = useState(null);
  const [detail, setDetail]           = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);
  const [zoomed, setZoomed]           = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStudents(await studentService.list());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Grado/salón dependen de los resultados reales del docente: no tiene
  // sentido ofrecer un grado sin estudiantes suyos ahí.
  const availableSubjects = useMemo(() => uniqueSorted(students.map(s => s.subject).filter(Boolean)), [students]);
  const availableGrades   = useMemo(() => uniqueSorted(students.map(s => s.grade_name).filter(Boolean)), [students]);
  const availableGroups   = useMemo(() => {
    const pool = gradeFilter ? students.filter(s => s.grade_name === gradeFilter) : students;
    return uniqueSorted(pool.map(s => s.group_name).filter(Boolean));
  }, [students, gradeFilter]);

  // Si el salón elegido deja de existir para el nuevo grado, se limpia.
  useEffect(() => {
    if (groupFilter && !availableGroups.includes(groupFilter)) setGroupFilter('');
  }, [gradeFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  const openDetail = useCallback(async (id) => {
    setSelectedId(id);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    try {
      setDetail(await studentService.getDetail(id));
    } catch (e) {
      setDetailError(e.message);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const closeDetail = useCallback(() => {
    setSelectedId(null);
    setDetail(null);
    setDetailError(null);
    setZoomed(false);
  }, []);

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando estudiantes…</span></div>;
  if (error) {
    return (
      <div className="dash__empty">
        <AlertIcon color="#ef4444" /><span>{error}</span>
        <button className="btn--secondary" style={{ width: 'auto', marginTop: 8 }} onClick={load}>Reintentar</button>
      </div>
    );
  }

  const filtered = students.filter(s => {
    if (query.trim()) {
      const q = query.toLowerCase();
      const matches = s.first_name.toLowerCase().includes(q)
        || s.last_name.toLowerCase().includes(q)
        || s.document_number.includes(q);
      if (!matches) return false;
    }
    if (subjectFilter && s.subject !== subjectFilter) return false;
    if (gradeFilter && s.grade_name !== gradeFilter) return false;
    if (groupFilter && s.group_name !== groupFilter) return false;
    return true;
  });

  const hasFilters = Boolean(query.trim() || subjectFilter || gradeFilter || groupFilter);

  return (
    <div className="card dash__list-card att-today">
      <div className="dash__list-header">
        {/* El backend acota este listado a los salones asignados al docente,
            así que el título ya no puede prometer la institución entera. */}
        <span className="dash__list-title">Mis estudiantes</span>
        <span className="dash__list-title">{filtered.length}</span>
      </div>

      <div className="stu-filters">
        <input
          className="dash__field-input"
          type="search"
          placeholder="Buscar por nombre o documento…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          autoComplete="off"
        />
        <div className="stu-filters__row">
          <label className="dash__field">
            <span className="dash__field-label">Materia</span>
            <select className="dash__field-input" value={subjectFilter} onChange={e => setSubjectFilter(e.target.value)}
              disabled={availableSubjects.length === 0}>
              <option value="">Todas</option>
              {availableSubjects.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="dash__field">
            <span className="dash__field-label">Grado</span>
            <select className="dash__field-input" value={gradeFilter} onChange={e => setGradeFilter(e.target.value)}>
              <option value="">Todos</option>
              {availableGrades.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </label>
          <label className="dash__field">
            <span className="dash__field-label">Salón</span>
            <select className="dash__field-input" value={groupFilter} onChange={e => setGroupFilter(e.target.value)}
              disabled={!gradeFilter}>
              <option value="">Todos</option>
              {availableGroups.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </label>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="dash__empty" style={{ padding: '32px 20px' }}>
          <UsersIcon />
          <span>
            {students.length === 0
              // Lista vacía ≠ institución vacía: lo normal es que el docente
              // no tenga salones asignados todavía.
              ? 'No tienes estudiantes asignados. Verifica con administración que tus salones estén registrados.'
              : hasFilters ? 'Sin resultados para ese criterio.' : 'Sin estudiantes.'}
          </span>
        </div>
      ) : filtered.map((s, i) => {
        const av = AVATARS[i % AVATARS.length];
        return (
          <button type="button" className="dash__student-row att-class-row stu-row" key={s.id} onClick={() => openDetail(s.id)}>
            <span className="stu-row__detail-icon" aria-hidden="true"><EyeIcon /></span>
            {s.photo_url
              ? <StudentPhoto src={s.photo_url} alt="" caption={`${s.first_name} ${s.last_name}`} />
              : <div className="dash__student-avatar" style={{ background: av.bg, color: av.color }}>{initials(s.first_name, s.last_name)}</div>}
            <div className="dash__student-info">
              <p className="dash__student-name">{s.first_name} {s.last_name}</p>
              <p className="dash__student-group">Doc. {s.document_number}</p>
            </div>
            <span className={`dash__badge dash__badge--${s.is_active ? 'green' : 'red'}`}>
              {s.is_active ? 'Activo' : 'Inactivo'}
            </span>
          </button>
        );
      })}

      {selectedId && (
        <div className="dash__modal-overlay" onClick={closeDetail}>
          <div className="dash__modal" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
            <button className="dash__modal-close" onClick={closeDetail} aria-label="Cerrar"><CloseIcon /></button>
            <p className="dash__modal-label">Ficha del estudiante</p>

            {detailLoading ? (
              <div className="dash__empty" style={{ padding: '24px 0' }}><Spinner /><span>Cargando…</span></div>
            ) : detailError ? (
              <div className="dash__empty" style={{ padding: '24px 0' }}><AlertIcon color="#ef4444" /><span>{detailError}</span></div>
            ) : detail && (
              <>
                <div className="dash__modal-student">
                  {detail.photo_url ? (
                    <button
                      type="button"
                      className="dash__modal-photo-btn"
                      onClick={() => setZoomed(true)}
                      title="Ver foto ampliada"
                      aria-label="Ver foto ampliada"
                    >
                      <img className="dash__modal-photo" src={detail.photo_url} alt={`${detail.first_name} ${detail.last_name}`} />
                      <span className="dash__modal-photo-zoom"><ZoomIcon /></span>
                    </button>
                  ) : (
                    <div className="dash__modal-avatar">{initials(detail.first_name, detail.last_name)}</div>
                  )}
                  <div className="dash__modal-info">
                    <p className="dash__modal-name">{detail.first_name} {detail.last_name}</p>
                    <p className="dash__modal-doc">Doc. {detail.document_number}</p>
                  </div>
                  <span className={`dash__badge dash__badge--${detail.is_active ? 'green' : 'red'}`}>
                    {detail.is_active ? 'Activo' : 'Inactivo'}
                  </span>
                </div>

                <div className="stu-detail__grid">
                  <div className="stu-detail__item">
                    <span className="dash__field-label">Grado</span>
                    <span className="dash__student-group">{detail.grade_name || '—'}</span>
                  </div>
                  <div className="stu-detail__item">
                    <span className="dash__field-label">Salón</span>
                    <span className="dash__student-group">{detail.group_name || '—'}</span>
                  </div>
                  <div className="stu-detail__item stu-detail__item--full">
                    <span className="dash__field-label">Materia</span>
                    <span className="dash__student-group">{detail.subject || 'Sin materia asignada'}</span>
                  </div>
                </div>

                <p className="dash__field-label stu-detail__guardians-label">Acudientes</p>
                {detail.guardians.length === 0 ? (
                  <p className="dash__student-group stu-detail__guardians-empty">Sin acudientes registrados.</p>
                ) : (
                  <div className="stu-detail__guardians">
                    {detail.guardians.map(g => (
                      <div className="stu-detail__guardian" key={g.id}>
                        <p className="dash__student-name">
                          {g.full_name}
                          {g.is_primary && <span className="dash__badge dash__badge--green stu-detail__primary">Principal</span>}
                        </p>
                        <p className="dash__student-group">
                          {RELATIONSHIP_LABEL[g.relationship] || g.relationship} · {g.email}{g.phone ? ` · ${g.phone}` : ''}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {zoomed && detail?.photo_url && (
        <div className="pae-lightbox" onClick={() => setZoomed(false)}>
          <img className="pae-lightbox__img" src={detail.photo_url} alt="" />
          <button className="pae-lightbox__close" onClick={() => setZoomed(false)} aria-label="Cerrar"><CloseIcon /></button>
        </div>
      )}
    </div>
  );
}

/* ── Horario ─────────────────────────────────────────────────── */
const DAY_NAMES = { 1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes' };

export function ScheduleView() {
  const [items, setItems]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);
  // Filtro de día solo visible en móvil (ver .sched__day-filter en dashboard.css):
  // arranca en el día de hoy si es entre semana, si no en lunes.
  const [mobileDay, setMobileDay] = useState(() => {
    const jsDay = new Date().getDay(); // 0=domingo … 6=sábado
    return jsDay >= 1 && jsDay <= 5 ? jsDay : 1;
  });

  useEffect(() => {
    attendanceService.schedule()
      .then(setItems)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando horario…</span></div>;
  if (error)   return <div className="dash__empty"><AlertIcon color="#ef4444" /><span>{error}</span></div>;
  if (items.length === 0) {
    return <div className="dash__empty"><CalendarIcon /><span>No tienes clases asignadas este año.</span></div>;
  }

  const byDay = {};
  items.forEach(it => { (byDay[it.day_of_week] ??= []).push(it); });

  return (
    <>
      {/* Solo se muestra en móvil (dashboard.css); en escritorio las 5
          columnas ya van una al lado de la otra y no hace falta filtrar. */}
      <label className="sched__day-filter">
        <span className="dash__field-label">Día</span>
        <select className="dash__field-input" value={mobileDay} onChange={e => setMobileDay(Number(e.target.value))}>
          {[1, 2, 3, 4, 5].map(day => <option key={day} value={day}>{DAY_NAMES[day]}</option>)}
        </select>
      </label>

      <div className="sched">
        {[1, 2, 3, 4, 5].map(day => (
          <div className={`card sched__col${day === mobileDay ? ' sched__col--mobile-active' : ''}`} key={day}>
            <p className="sched__day">{DAY_NAMES[day]}</p>
            {(byDay[day] || []).length === 0 ? (
              <p className="sched__free">Sin clases</p>
            ) : byDay[day].map(it => (
              <div className="sched__slot" key={it.class_period_id}>
                <span className="sched__time">{it.start_time.slice(0, 5)} - {it.end_time.slice(0, 5)}</span>
                <span className="sched__name">{it.name}</span>
                <span className="sched__group">{it.grade_name} {it.group_name}{it.period_order === 1 ? ' · 1ª hora' : ''}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </>
  );
}

/* ── Inasistencias de primera hora sin justificar ────────────── */
export function AbsencesView() {
  const [items, setItems]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);
  const [openId, setOpenId] = useState(null);
  const [filterStudent, setFilterStudent] = useState(null);
  const [includeClosed, setIncludeClosed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      setItems(await attendanceService.absences({
        studentId: filterStudent?.id,
        includeClosed,
      }));
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [filterStudent, includeClosed]);

  useEffect(() => { load(); }, [load]);

  // Al volver se recarga: pudieron añadirse notas, o el acudiente pudo haber
  // justificado entretanto y la fila ya no pertenece a esta sección.
  if (openId) {
    return <AbsenceDetail recordId={openId} onBack={() => { setOpenId(null); load(); }} />;
  }

  return (
    <div className="hist-scale">
      <div className="card att-form" style={{ gap: 12 }}>
        <p className="dash__list-title" style={{ marginBottom: 4 }}>Filtrar por estudiante</p>
        <StudentSearch
          selected={filterStudent}
          onSelect={r => setFilterStudent(r)}
          onClear={() => setFilterStudent(null)}
        />
        <label className="hist-toggle">
          <input
            type="checkbox"
            checked={includeClosed}
            onChange={e => setIncludeClosed(e.target.checked)}
          />
          Mostrar casos cerrados
        </label>
      </div>

      {loading ? (
        <div className="dash__empty"><Spinner /><span>Cargando inasistencias…</span></div>
      ) : error ? (
        <div className="dash__empty">
          <AlertIcon color="#ef4444" /><span>{error}</span>
          <button className="btn--secondary" style={{ width: 'auto', marginTop: 8 }} onClick={load}>Reintentar</button>
        </div>
      ) : items.length === 0 ? (
        <div className="dash__empty">
          <ClipboardIcon />
          <span>
            {filterStudent
              ? 'Este estudiante no tiene inasistencias pendientes de justificar.'
              : includeClosed
                ? 'No hay inasistencias sin justificar.'
                : 'No hay casos abiertos. Activa «Mostrar casos cerrados» para ver los ya gestionados.'}
          </span>
        </div>
      ) : (
        <div className="card dash__list-card">
          <div className="dash__list-header">
            <span className="dash__list-title">Pendientes de justificar</span>
            <span className="dash__student-group">{items.length}</span>
          </div>
          {items.map((a, i) => {
            const av = AVATARS[i % AVATARS.length];
            return (
              <button key={a.record_id} className="dash__student-row att-class-row" onClick={() => setOpenId(a.record_id)}>
                {a.photo_url
                  ? <StudentPhoto src={a.photo_url} alt={a.student_name} caption={a.student_name} />
                  : <div className="dash__student-avatar" style={{ background: av.bg, color: av.color }}>
                      {(a.student_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
                    </div>}
                <div className="dash__student-info">
                  <p className="dash__student-name">{a.student_name}</p>
                  <p className="dash__student-group">
                    {[a.grade_name, a.group_name].filter(Boolean).join(' ')}
                    {[a.grade_name, a.group_name].filter(Boolean).length ? ' · ' : ''}
                    {fmtShort(a.date)} · {a.period_name} {a.start_time?.slice(0, 5)}
                    {a.note_count > 0 ? ` · ${a.note_count} nota${a.note_count > 1 ? 's' : ''}` : ''}
                  </p>
                </div>
                <div className="att-class-row__badges att-class-row__badges--force-stack">
                  {a.closed && <span className="dash__badge dash__badge--gray">Cerrado</span>}
                  <span className={`dash__badge dash__badge--${a.guardian_notified ? 'blue' : 'yellow'}`}>
                    {a.guardian_notified ? 'Aviso enviado' : 'Sin aviso'}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Detalle de una inasistencia sin justificar + notas ──────── */
function AbsenceDetail({ recordId, onBack }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [note, setNote]       = useState('');
  const [saving, setSaving]   = useState(false);
  const [closing, setClosing] = useState(false);
  const [toast, setToast]     = useState(null);

  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setData(await attendanceService.absenceDetail(recordId)); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [recordId]);

  useEffect(() => { load(); }, [load]);

  const submitNote = useCallback(async () => {
    const texto = note.trim();
    if (!texto) return;
    setSaving(true);
    try {
      await attendanceService.addAbsenceNote(recordId, texto);
      setNote('');
      await load();
      showToast('Nota agregada');
    } catch (e) { showToast(e.message, 'error'); }
    finally { setSaving(false); }
  }, [note, recordId, load, showToast]);

  const toggleClosed = useCallback(async () => {
    setClosing(true);
    try {
      await attendanceService.setAbsenceClosed(recordId, !data.closed);
      await load();
      showToast(data.closed ? 'Caso reabierto' : 'Caso cerrado');
    } catch (e) { showToast(e.message, 'error'); }
    finally { setClosing(false); }
  }, [recordId, data, load, showToast]);

  const backBtn = (
    <button className="btn--secondary att-back" style={{ width: 'auto' }} onClick={onBack}>← Inasistencias</button>
  );

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando la inasistencia…</span></div>;
  if (error || !data) {
    return (
      <div className="rec-scale">
        {backBtn}
        <div className="dash__empty">
          <AlertIcon color="#ef4444" />
          <span>{error || 'No se encontró la inasistencia.'}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="rec-scale">
      {toast && (
        <div className={`dash__toast dash__toast--${toast.type}`} role="alert">
          {toast.type === 'success' ? <CheckIcon /> : <AlertIcon />}{toast.msg}
        </div>
      )}

      {backBtn}

      <div className="att-head card">
        <div className="rec-head__student">
          {data.photo_url
            ? <StudentPhoto src={data.photo_url} alt={data.student_name} caption={data.student_name} />
            : <div className="dash__student-avatar" style={{ background: '#ede9fe', color: '#6d28d9' }}>
                {(data.student_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
              </div>}
          <div className="rec-head__text">
            <p className="att-head__period">{data.student_name}</p>
            <p className="att-head__sub">
              {[data.grade_name, data.group_name].filter(Boolean).join(' ')}
              {[data.grade_name, data.group_name].filter(Boolean).length ? ' · ' : ''}
              {fmtShort(data.date)}
            </p>
            <div className="rec-head__badges">
              <span className="dash__badge dash__badge--red">Sin justificar</span>
              {data.closed && <span className="dash__badge dash__badge--gray">Cerrado</span>}
            </div>
          </div>
        </div>
        <button className="btn--secondary" style={{ width: 'auto' }} onClick={toggleClosed} disabled={closing}>
          {closing ? '…' : data.closed ? 'Reabrir caso' : 'Cerrar caso'}
        </button>
      </div>

      <div className="card att-form">
        <div>
          <span className="dash__field-label">Cuándo fue</span>
          <p className="hist-obs">
            {data.period_name} · {data.start_time?.slice(0, 5)} a {data.end_time?.slice(0, 5)} del {fmtShort(data.date)}.
            {' '}Lista tomada el {fmtShort(data.recorded_at)}.
          </p>
        </div>

        <div>
          <span className="dash__field-label">Aviso al acudiente</span>
          {data.guardian_notified ? (
            <p className="hist-obs">
              Se envió el enlace de justificación{data.guardian_email ? <> a <strong>{data.guardian_email}</strong></> : null}
              {' '}y nadie lo ha usado todavía.
            </p>
          ) : (
            <p className="hist-obs">
              Todavía no se ha enviado el aviso. Puede estar dentro de la ventana de gracia, o el
              estudiante no tener acudiente principal registrado.
              {data.guardian_email ? <> Contacto: <strong>{data.guardian_email}</strong>.</> : null}
            </p>
          )}
        </div>
      </div>

      <div className="card att-form">
        <p className="dash__list-title" style={{ marginBottom: 4 }}>
          Notas de seguimiento
          {data.notes.length > 0 && <span className="conv-count"> · {data.notes.length}</span>}
        </p>

        {data.notes.length === 0 ? (
          <p className="sched__free">Sin notas todavía.</p>
        ) : (
          <div className="hist-notes">
            {data.notes.map(n => (
              <div key={n.id} className="hist-note">
                <p className="hist-note__text">{n.note}</p>
                <span className="hist-note__meta">{n.author_name} · {fmtShort(n.created_at)}</span>
              </div>
            ))}
          </div>
        )}

        <label className="dash__field">
          <span className="dash__field-label">Agregar nota</span>
          <textarea
            className="dash__field-input"
            style={{ minHeight: 70, resize: 'vertical' }}
            value={note}
            onChange={e => setNote(e.target.value)}
            maxLength={2000}
            placeholder="Ej: Llamé al acudiente; enviará la excusa mañana…"
          />
        </label>
        <button className="btn--confirm" onClick={submitNote} disabled={saving || note.trim().length < 1} aria-busy={saving}>
          {saving ? 'Guardando…' : 'Agregar nota'}
        </button>
      </div>
    </div>
  );
}

/* ── Mensajes: excusas de los acudientes ─────────────────────── */
export function MensajesView() {
  const [msgs, setMsgs]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);
  const [openId, setOpenId] = useState(null);
  const [filterStudent, setFilterStudent] = useState(null);
  const [includeArchived, setIncludeArchived] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      setMsgs(await attendanceService.justifications({
        studentId: filterStudent?.id,
        includeArchived,
      }));
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [filterStudent, includeArchived]);

  useEffect(() => { load(); }, [load]);

  // Al volver del detalle se recarga: pudo cerrarse el caso o añadirse notas.
  if (openId) {
    return (
      <MessageDetail
        justificationId={openId}
        onBack={() => { setOpenId(null); load(); }}
      />
    );
  }

  return (
    <div className="hist-scale">
      <div className="card att-form" style={{ gap: 12 }}>
        <p className="dash__list-title" style={{ marginBottom: 4 }}>Filtrar por estudiante</p>
        <StudentSearch
          selected={filterStudent}
          onSelect={r => setFilterStudent(r)}
          onClear={() => setFilterStudent(null)}
        />
        <label className="hist-toggle">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={e => setIncludeArchived(e.target.checked)}
          />
          Mostrar casos cerrados
        </label>
      </div>

      {loading ? (
        <div className="dash__empty"><Spinner /><span>Cargando mensajes…</span></div>
      ) : error ? (
        <div className="dash__empty">
          <AlertIcon color="#ef4444" /><span>{error}</span>
          <button className="btn--secondary" style={{ width: 'auto', marginTop: 8 }} onClick={load}>Reintentar</button>
        </div>
      ) : msgs.length === 0 ? (
        <div className="dash__empty">
          <MessageIcon />
          <span>
            {filterStudent
              ? 'Este estudiante no tiene excusas para tus reportes.'
              : includeArchived
                ? 'Aún no hay excusas enviadas por los acudientes.'
                : 'No hay casos abiertos. Activa «Mostrar casos cerrados» para ver el histórico.'}
          </span>
        </div>
      ) : (
        <div className="card dash__list-card">
          <div className="dash__list-header">
            <span className="dash__list-title">Excusas de los acudientes</span>
            <span className="dash__student-group">{msgs.length}</span>
          </div>
          {msgs.map((m, i) => {
            const av = AVATARS[i % AVATARS.length];
            return (
              <button key={m.id} className="dash__student-row att-class-row" onClick={() => setOpenId(m.id)}>
                {m.photo_url
                  ? <StudentPhoto src={m.photo_url} alt={m.student_name} caption={m.student_name} />
                  : <div className="dash__student-avatar" style={{ background: av.bg, color: av.color }}>
                      {(m.student_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
                    </div>}
                <div className="dash__student-info">
                  <p className="dash__student-name">{m.student_name}</p>
                  <p className="dash__student-group">
                    {[m.grade_name, m.group_name].filter(Boolean).join(' ')}
                    {[m.grade_name, m.group_name].filter(Boolean).length ? ' · ' : ''}
                    Inasistencia {fmtShort(m.date)}
                    {m.note_count > 0 ? ` · ${m.note_count} nota${m.note_count > 1 ? 's' : ''}` : ''}
                  </p>
                </div>
                {m.archived && <span className="dash__badge dash__badge--gray">Cerrado</span>}
                <div className="hist-sev">
                  {m.attachment_url
                    ? <span className="dash__badge dash__badge--purple">
                        {m.attachment_content_type === 'application/pdf' ? 'PDF' : 'Imagen'}
                      </span>
                    : <span className="dash__badge dash__badge--gray">Sin soporte</span>}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Detalle de una excusa + notas + cierre de caso ──────────── */
function MessageDetail({ justificationId, onBack }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [note, setNote]       = useState('');
  const [savingNote, setSavingNote] = useState(false);
  const [closing, setClosing] = useState(false);
  const [toast, setToast]     = useState(null);

  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setData(await attendanceService.justificationDetail(justificationId)); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [justificationId]);

  useEffect(() => { load(); }, [load]);

  const submitNote = useCallback(async () => {
    const texto = note.trim();
    if (!texto) return;
    setSavingNote(true);
    try {
      await attendanceService.addJustificationNote(justificationId, texto);
      setNote('');
      await load();
      showToast('Nota agregada');
    } catch (e) { showToast(e.message, 'error'); }
    finally { setSavingNote(false); }
  }, [note, justificationId, load, showToast]);

  const toggleClosed = useCallback(async () => {
    setClosing(true);
    try {
      await attendanceService.setJustificationArchived(justificationId, !data.archived);
      await load();
      showToast(data.archived ? 'Caso reabierto' : 'Caso cerrado');
    } catch (e) { showToast(e.message, 'error'); }
    finally { setClosing(false); }
  }, [justificationId, data, load, showToast]);

  const backBtn = (
    <button className="btn--secondary att-back" style={{ width: 'auto' }} onClick={onBack}>← Mensajes</button>
  );

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando la excusa…</span></div>;
  if (error || !data) {
    return (
      <div className="rec-scale">
        {backBtn}
        <div className="dash__empty"><AlertIcon color="#ef4444" /><span>{error || 'No se encontró la excusa.'}</span></div>
      </div>
    );
  }

  return (
    <div className="rec-scale">
      {toast && (
        <div className={`dash__toast dash__toast--${toast.type}`} role="alert">
          {toast.type === 'success' ? <CheckIcon /> : <AlertIcon />}{toast.msg}
        </div>
      )}

      {backBtn}

      <div className="att-head card">
        <div className="rec-head__student">
          {data.photo_url
            ? <StudentPhoto src={data.photo_url} alt={data.student_name} caption={data.student_name} />
            : <div className="dash__student-avatar" style={{ background: '#ede9fe', color: '#6d28d9' }}>
                {(data.student_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
              </div>}
          <div>
            <p className="att-head__period">
              {data.student_name}
              {data.archived && <span className="dash__badge dash__badge--gray">Cerrado</span>}
            </p>
            <p className="att-head__sub">
              {[data.grade_name, data.group_name].filter(Boolean).join(' ')}
              {[data.grade_name, data.group_name].filter(Boolean).length ? ' · ' : ''}
              Inasistencia del {fmtShort(data.date)} · Excusa recibida el {fmtShort(data.submitted_at)}
            </p>
          </div>
        </div>
        <button className="btn--secondary" style={{ width: 'auto' }} onClick={toggleClosed} disabled={closing}>
          {closing ? '…' : data.archived ? 'Reabrir caso' : 'Cerrar caso'}
        </button>
      </div>

      <div className="card att-form">
        <div>
          <span className="dash__field-label">Motivo que reportó el acudiente</span>
          <p className="hist-obs">{data.reason}</p>
        </div>

        <div>
          <span className="dash__field-label">Soporte adjunto</span>
          {data.attachment_url ? (
            <a className="msg__attach" href={data.attachment_url} target="_blank" rel="noopener noreferrer">
              <PaperclipIcon />
              <span className="msg__attach-name">{data.attachment_filename || 'Soporte'}</span>
              <span className="msg__attach-tag">
                {data.attachment_content_type === 'application/pdf' ? 'PDF' : 'Imagen'}
                {data.attachment_size_bytes ? ` · ${Math.max(1, Math.round(data.attachment_size_bytes / 1024))} KB` : ''}
              </span>
            </a>
          ) : (
            <p className="sched__free">El acudiente no adjuntó ningún documento.</p>
          )}
        </div>
      </div>

      <div className="card att-form">
        <p className="dash__list-title" style={{ marginBottom: 4 }}>
          Notas de seguimiento
          {data.notes.length > 0 && <span className="conv-count"> · {data.notes.length}</span>}
        </p>

        {data.notes.length === 0 ? (
          <p className="sched__free">Sin notas todavía.</p>
        ) : (
          <div className="hist-notes">
            {data.notes.map(n => (
              <div key={n.id} className="hist-note">
                <p className="hist-note__text">{n.note}</p>
                <span className="hist-note__meta">{n.author_name} · {fmtShort(n.created_at)}</span>
              </div>
            ))}
          </div>
        )}

        <label className="dash__field">
          <span className="dash__field-label">Agregar nota</span>
          <textarea
            className="dash__field-input"
            style={{ minHeight: 70, resize: 'vertical' }}
            value={note}
            onChange={e => setNote(e.target.value)}
            maxLength={2000}
            placeholder="Ej: Se verificó la incapacidad con coordinación…"
          />
        </label>
        <button className="btn--confirm" onClick={submitNote} disabled={savingNote || note.trim().length < 1} aria-busy={savingNote}>
          {savingNote ? 'Guardando…' : 'Agregar nota'}
        </button>
      </div>
    </div>
  );
}

// La usan Mensajes, su detalle y el Historial.
function fmtShort(iso) {
  if (!iso) return '';
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  return d.toLocaleDateString('es-CO', { day: 'numeric', month: 'short' });
}

/* ── Convivencia (agendatorio) ───────────────────────────────── */
const SEVERITY_CLASS = { LEVE: 'green', MODERADA: 'yellow', GRAVE: 'red' };

const SEVERITIES = ['LEVE', 'MODERADA', 'GRAVE'];
const norm = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

/* ── Buscador de estudiante reutilizable (grado + salón + nombre/doc) ─── */
function StudentSearch({ selected, onSelect, onClear }) {
  const [grades, setGrades]   = useState([]);
  const [groups, setGroups]   = useState([]);
  const [gradeId, setGradeId] = useState('');
  const [groupId, setGroupId] = useState('');
  const [query, setQuery]     = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    Promise.all([agendatorioService.listGrades(), agendatorioService.listGroups()])
      .then(([g, gr]) => { setGrades(g); setGroups(gr); })
      .catch(() => { /* ignore */ });
  }, []);

  const groupsForGrade = groups.filter(g => !gradeId || g.grade_id === gradeId);

  useEffect(() => {
    if (groupId && !groupsForGrade.some(g => g.id === groupId)) setGroupId('');
  }, [gradeId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (selected) { setResults([]); return; }
    const term = query.trim();
    const canBrowse = Boolean(gradeId || groupId);
    if (term.length < 2 && !canBrowse) { setResults([]); return; }
    let active = true;
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const r = await studentService.search(term, { gradeId, groupId });
        if (active) setResults(r);
      } catch { /* ignore */ }
      finally { if (active) setSearching(false); }
    }, 250);
    return () => { active = false; clearTimeout(t); };
  }, [query, gradeId, groupId, selected]);

  if (selected) {
    return (
      <div className="att-selected att-selected--photo">
        {selected.photo_url
          ? <StudentPhoto src={selected.photo_url} alt={selected.full_name} caption={selected.full_name} />
          : <div className="dash__student-avatar" style={{ background: '#ede9fe', color: '#6d28d9' }}>
              {(selected.full_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
            </div>}
        <div className="att-selected__info">
          <span className="dash__student-name">{selected.full_name}</span>
          <span className="dash__student-group">
            Doc. {selected.document_number}
            {[selected.grade_name, selected.group_name].filter(Boolean).length
              ? ` · ${[selected.grade_name, selected.group_name].filter(Boolean).join(' ')}` : ''}
          </span>
        </div>
        <button type="button" className="att-selected__clear" onClick={onClear} aria-label="Cambiar">✕</button>
      </div>
    );
  }

  return (
    <div className="conv-search">
      <div className="conv-search__filters">
        <label className="dash__field">
          <span className="dash__field-label">Grado</span>
          <select className="dash__field-input" value={gradeId} onChange={e => setGradeId(e.target.value)}>
            <option value="">Todos</option>
            {grades.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </label>
        <label className="dash__field">
          <span className="dash__field-label">Salón</span>
          <select className="dash__field-input" value={groupId} onChange={e => setGroupId(e.target.value)}>
            <option value="">Todos</option>
            {groupsForGrade.map(g => <option key={g.id} value={g.id}>{g.grade_name} {g.name}</option>)}
          </select>
        </label>
      </div>

      <div className="att-search">
        <input className="dash__field-input" placeholder="Buscar por nombre o documento…" value={query}
          onChange={e => setQuery(e.target.value)} autoComplete="off" />
        {(results.length > 0 || searching) && (
          <div className="att-search__results">
            {searching && results.length === 0 && (
              <div className="att-search__item att-search__hint">Buscando…</div>
            )}
            {results.map(r => (
              <button type="button" key={r.id} className="att-search__item" onClick={() => onSelect(r)}>
                <span className="dash__student-name">{r.full_name}</span>
                <span className="dash__student-group">
                  Doc. {r.document_number}
                  {[r.grade_name, r.group_name].filter(Boolean).length
                    ? ` · ${[r.grade_name, r.group_name].filter(Boolean).join(' ')}` : ''}
                </span>
              </button>
            ))}
          </div>
        )}
        {!searching && results.length === 0 && (gradeId || groupId || query.trim().length >= 2) && (
          <p className="sched__free" style={{ marginTop: 6 }}>Sin estudiantes para ese criterio.</p>
        )}
      </div>
    </div>
  );
}

export function ConvivenciaView() {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  const [student, setStudent]   = useState(null);

  // Selección de artículos (2.2): filtro por severidad + buscador
  const [sevFilter, setSevFilter]       = useState('ALL');
  const [articleQuery, setArticleQuery] = useState('');
  const [picked, setPicked]     = useState([]);   // article ids

  const [obs, setObs]           = useState('');
  const [saving, setSaving]     = useState(false);
  const [toast, setToast]       = useState(null);
  // Grado/Salón viven como estado interno de StudentSearch (no son props
  // controladas); cambiar esta key fuerza un remount que los limpia junto
  // con el resto del formulario tras un envío exitoso.
  const [searchKey, setSearchKey] = useState(0);
  const canvasRef = useRef(null);
  const drawing   = useRef(false);
  const hasInk    = useRef(false);

  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  useEffect(() => {
    agendatorioService.listArticles()
      .then(setArticles)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const toggleArticle = (id) =>
    setPicked(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  const filteredArticles = articles.filter(a => {
    if (sevFilter !== 'ALL' && a.severity !== sevFilter) return false;
    const q = norm(articleQuery.trim());
    if (!q) return true;
    return norm(a.title).includes(q) || norm(a.code).includes(q);
  });

  // --- Firma en canvas ---
  const pos = (e) => {
    const c = canvasRef.current;
    const rect = c.getBoundingClientRect();
    const t = e.touches ? e.touches[0] : e;
    return { x: (t.clientX - rect.left) * (c.width / rect.width), y: (t.clientY - rect.top) * (c.height / rect.height) };
  };
  const start = (e) => { e.preventDefault(); drawing.current = true; const ctx = canvasRef.current.getContext('2d'); const p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); };
  const move = (e) => {
    if (!drawing.current) return;
    e.preventDefault();
    const ctx = canvasRef.current.getContext('2d');
    ctx.lineWidth = 2.5; ctx.lineCap = 'round'; ctx.strokeStyle = '#1a1730';
    const p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); hasInk.current = true;
  };
  const end = () => { drawing.current = false; };
  const clearCanvas = () => {
    const c = canvasRef.current; c.getContext('2d').clearRect(0, 0, c.width, c.height); hasInk.current = false;
  };

  const submit = useCallback(async () => {
    if (!student)        { showToast('Selecciona un estudiante', 'error'); return; }
    if (picked.length === 0) { showToast('Selecciona al menos un artículo', 'error'); return; }
    if (!obs.trim())     { showToast('Escribe las observaciones', 'error'); return; }
    if (!hasInk.current) { showToast('Falta la firma del estudiante', 'error'); return; }

    setSaving(true);
    try {
      const blob = await new Promise(res => canvasRef.current.toBlob(res, 'image/png'));
      const today = new Date().toISOString().slice(0, 10);
      await agendatorioService.createRecord(
        { student_id: student.id, article_ids: picked, observations: obs.trim(), date: today },
        blob,
      );
      showToast(`Registro creado para ${student.full_name}`);
      setStudent(null);
      setPicked([]); setSevFilter('ALL'); setArticleQuery(''); setObs(''); clearCanvas();
      setSearchKey(k => k + 1);
    } catch (e) {
      showToast(e.message, 'error');
    } finally {
      setSaving(false);
    }
  }, [student, picked, obs, showToast]);

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando convivencia…</span></div>;
  if (error)   return <div className="dash__empty"><AlertIcon color="#ef4444" /><span>{error}</span></div>;

  return (
    <>
      {toast && (
        <div className={`dash__toast dash__toast--${toast.type}`} role="alert">
          {toast.type === 'success' ? <CheckIcon /> : <AlertIcon />}{toast.msg}
        </div>
      )}

      <div className="card att-form dep-scale">
        <p className="dash__list-title" style={{ marginBottom: 4 }}>Nuevo registro de convivencia</p>

        <StudentSearch
          key={searchKey}
          selected={student}
          onSelect={r => setStudent(r)}
          onClear={() => setStudent(null)}
        />

        <div>
          <span className="dash__field-label">
            Artículos del manual infringidos
            {picked.length > 0 && <span className="conv-count"> · {picked.length} seleccionado{picked.length > 1 ? 's' : ''}</span>}
          </span>

          {articles.length === 0 ? (
            <p className="sched__free">No hay artículos cargados en el manual.</p>
          ) : (
            <>
              <div className="conv-article-filters">
                <div className="conv-sev-chips" role="group" aria-label="Filtrar por severidad">
                  <button type="button"
                    className={`conv-sev-chip${sevFilter === 'ALL' ? ' is-on' : ''}`}
                    onClick={() => setSevFilter('ALL')}>Todas</button>
                  {SEVERITIES.map(sev => (
                    <button type="button" key={sev}
                      className={`conv-sev-chip conv-sev-chip--${SEVERITY_CLASS[sev]}${sevFilter === sev ? ' is-on' : ''}`}
                      onClick={() => setSevFilter(sev)}>{sev}</button>
                  ))}
                </div>
                <input
                  className="dash__field-input"
                  placeholder="Buscar artículo… (ej: Uso del celular)"
                  value={articleQuery}
                  onChange={e => setArticleQuery(e.target.value)}
                  autoComplete="off"
                />
              </div>

              {filteredArticles.length === 0 ? (
                <p className="sched__free">Ningún artículo coincide con el filtro.</p>
              ) : (
                <div className="conv-articles">
                  {filteredArticles.map(a => (
                    <button type="button" key={a.id}
                      className={`conv-article${picked.includes(a.id) ? ' conv-article--on' : ''}`}
                      onClick={() => toggleArticle(a.id)}>
                      <span className={`dash__badge dash__badge--${SEVERITY_CLASS[a.severity] || 'yellow'}`}>{a.severity}</span>
                      <span className="conv-article__code">{a.code}</span>
                      <span className="conv-article__title">{a.title}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* Bandeja de agregados: los artículos elegidos arriba bajan
                  aquí; tocarlos de nuevo los quita (misma toggleArticle). */}
              {picked.length > 0 && (
                <div className="conv-picked">
                  <p className="conv-picked__label dash__field-label">
                    Agregados <span className="conv-count">· {picked.length}</span>
                  </p>
                  <div className="conv-picked-list">
                    {picked.map(id => {
                      const a = articles.find(x => x.id === id);
                      if (!a) return null;
                      return (
                        <button type="button" key={id} className="conv-picked-item"
                          onClick={() => toggleArticle(id)} aria-label={`Quitar ${a.code}`}>
                          <span className={`dash__badge dash__badge--${SEVERITY_CLASS[a.severity] || 'yellow'}`}>{a.severity}</span>
                          <span className="conv-article__code">{a.code}</span>
                          <span className="conv-article__title">{a.title}</span>
                          <span className="conv-picked-item__remove">✕</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <label className="dash__field">
          <span className="dash__field-label">Observaciones</span>
          <textarea className="dash__field-input" style={{ minHeight: 80, resize: 'vertical' }}
            value={obs} onChange={e => setObs(e.target.value)} maxLength={2000}
            placeholder="Describe el hecho…" />
        </label>

        <div>
          <div className="conv-sign-head">
            <span className="dash__field-label" style={{ margin: 0 }}>Firma del estudiante</span>
            <button type="button" className="conv-clear" onClick={clearCanvas}>Limpiar</button>
          </div>
          <canvas
            ref={canvasRef}
            width={600}
            height={160}
            className="conv-canvas"
            onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end}
            onTouchStart={start} onTouchMove={move} onTouchEnd={end}
          />
        </div>

        <button className="btn--confirm" onClick={submit} disabled={saving} aria-busy={saving}>
          {saving ? 'Guardando…' : 'Crear registro'}
        </button>
      </div>
    </>
  );
}

/* ── Historial de convivencia (registros del docente) ────────── */
export function HistorialView() {
  const [records, setRecords] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [filterStudent, setFilterStudent] = useState(null);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [openId, setOpenId]   = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRecords(await agendatorioService.listMyRecords({
        studentId: filterStudent?.id,
        includeArchived,
      }));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filterStudent, includeArchived]);

  useEffect(() => { load(); }, [load]);

  if (openId) {
    return <RecordDetail recordId={openId} onBack={() => { setOpenId(null); load(); }} onChanged={load} />;
  }

  return (
    <div className="hist-scale">
      <div className="card att-form" style={{ gap: 12 }}>
        <p className="dash__list-title" style={{ marginBottom: 4 }}>Filtrar por estudiante</p>
        <StudentSearch
          selected={filterStudent}
          onSelect={r => setFilterStudent(r)}
          onClear={() => setFilterStudent(null)}
        />
        <label className="hist-toggle">
          <input type="checkbox" checked={includeArchived} onChange={e => setIncludeArchived(e.target.checked)} />
          Mostrar registros ocultos
        </label>
      </div>

      {loading ? (
        <div className="dash__empty"><Spinner /><span>Cargando tu historial…</span></div>
      ) : error ? (
        <div className="dash__empty">
          <AlertIcon color="#ef4444" /><span>{error}</span>
          <button className="btn--secondary" style={{ width: 'auto', marginTop: 8 }} onClick={load}>Reintentar</button>
        </div>
      ) : records.length === 0 ? (
        <div className="dash__empty">
          <ShieldIcon />
          <span>{filterStudent ? 'Este estudiante no tiene registros tuyos.' : 'Aún no has creado registros de convivencia.'}</span>
        </div>
      ) : (
        <div className="card dash__list-card">
          <div className="dash__list-header">
            <span className="dash__list-title">Registros creados por ti</span>
            <span className="dash__student-group">{records.length}</span>
          </div>
          {records.map((r, i) => {
            const av = AVATARS[i % AVATARS.length];
            return (
              <button key={r.id} className="dash__student-row att-class-row" onClick={() => setOpenId(r.id)}>
                {r.photo_url
                  ? <StudentPhoto src={r.photo_url} alt={r.student_name} caption={r.student_name} />
                  : <div className="dash__student-avatar" style={{ background: av.bg, color: av.color }}>
                      {(r.student_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
                    </div>}
                <div className="dash__student-info">
                  <p className="dash__student-name">{r.student_name}</p>
                  <p className="dash__student-group">
                    {[r.grade_name, r.group_name].filter(Boolean).join(' ')}
                    {[r.grade_name, r.group_name].filter(Boolean).length ? ' · ' : ''}
                    {fmtShort(r.date)}
                    {r.note_count > 0 ? ` · ${r.note_count} nota${r.note_count > 1 ? 's' : ''}` : ''}
                  </p>
                </div>
                {r.archived && <span className="dash__badge dash__badge--gray">Oculto</span>}
                <div className="hist-sev">
                  {r.articles.map((a, j) => (
                    <span key={j} className={`dash__badge dash__badge--${SEVERITY_CLASS[a.severity] || 'yellow'}`}>{a.code}</span>
                  ))}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Detalle de un registro + notas + ocultar ────────────────── */
function RecordDetail({ recordId, onBack, onChanged }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  const [note, setNote]       = useState('');
  const [savingNote, setSavingNote] = useState(false);
  const [archiving, setArchiving]   = useState(false);
  const [toast, setToast]     = useState(null);

  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await agendatorioService.recordDetail(recordId));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [recordId]);

  useEffect(() => { load(); }, [load]);

  const submitNote = useCallback(async () => {
    if (note.trim().length < 1) return;
    setSavingNote(true);
    try {
      await agendatorioService.addNote(recordId, note.trim());
      setNote('');
      await load();
      onChanged?.();
      showToast('Nota agregada');
    } catch (e) {
      showToast(e.message, 'error');
    } finally {
      setSavingNote(false);
    }
  }, [note, recordId, load, onChanged, showToast]);

  const toggleArchive = useCallback(async () => {
    if (!data) return;
    setArchiving(true);
    try {
      if (data.archived) await agendatorioService.unarchiveRecord(recordId);
      else await agendatorioService.archiveRecord(recordId);
      await load();
      onChanged?.();
      showToast(data.archived ? 'Registro visible de nuevo' : 'Registro oculto de tu panel');
    } catch (e) {
      showToast(e.message, 'error');
    } finally {
      setArchiving(false);
    }
  }, [data, recordId, load, onChanged, showToast]);

  const backBtn = (
    <button className="btn--secondary att-back" style={{ width: 'auto' }} onClick={onBack}>← Historial</button>
  );

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando registro…</span></div>;
  if (error) {
    return (
      <div className="dash__empty">
        <AlertIcon color="#ef4444" /><span>{error}</span>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button className="btn--secondary" style={{ width: 'auto' }} onClick={load}>Reintentar</button>
          <button className="btn--secondary" style={{ width: 'auto' }} onClick={onBack}>Volver</button>
        </div>
      </div>
    );
  }

  return (
    <div className="rec-scale">
      {toast && (
        <div className={`dash__toast dash__toast--${toast.type}`} role="alert">
          {toast.type === 'success' ? <CheckIcon /> : <AlertIcon />}{toast.msg}
        </div>
      )}

      {backBtn}

      <div className="att-head card">
        <div className="rec-head__student">
          {data.photo_url
            ? <StudentPhoto src={data.photo_url} alt={data.student_name} caption={data.student_name} />
            : <div className="dash__student-avatar" style={{ background: '#ede9fe', color: '#6d28d9' }}>
                {(data.student_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
              </div>}
          <div>
            <p className="att-head__period">
              {data.student_name}
              {data.archived && <span className="dash__badge dash__badge--gray">Oculto</span>}
            </p>
            <p className="att-head__sub">
              {[data.grade_name, data.group_name].filter(Boolean).join(' ')}
              {[data.grade_name, data.group_name].filter(Boolean).length ? ' · ' : ''}
              {fmtShort(data.date)} · Registrado por {data.recorded_by_name}
            </p>
          </div>
        </div>
        <button className="btn--secondary" style={{ width: 'auto' }} onClick={toggleArchive} disabled={archiving}>
          {archiving ? '…' : data.archived ? 'Mostrar en panel' : 'Ocultar del panel'}
        </button>
      </div>

      <div className="card att-form">
        <div>
          <span className="dash__field-label">Artículos infringidos</span>
          <div className="conv-articles" style={{ marginTop: 8 }}>
            {data.articles.map(a => (
              <div key={a.id} className="conv-article" style={{ cursor: 'default' }}>
                <span className={`dash__badge dash__badge--${SEVERITY_CLASS[a.severity] || 'yellow'}`}>{a.severity}</span>
                <span className="conv-article__code">{a.code}</span>
                <span className="conv-article__title">{a.title}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <span className="dash__field-label">Observaciones</span>
          <p className="hist-obs">{data.observations}</p>
        </div>

        <div>
          <span className="dash__field-label">Firma del estudiante</span>
          {data.signature_url
            ? <img className="hist-signature" src={data.signature_url} alt="Firma del estudiante" />
            : <p className="sched__free">Sin firma.</p>}
        </div>
      </div>

      <div className="card att-form">
        <p className="dash__list-title" style={{ marginBottom: 4 }}>
          Notas de seguimiento
          {data.notes.length > 0 && <span className="conv-count"> · {data.notes.length}</span>}
        </p>

        {data.notes.length === 0 ? (
          <p className="sched__free">Sin notas todavía.</p>
        ) : (
          <div className="hist-notes">
            {data.notes.map(n => (
              <div key={n.id} className="hist-note">
                <p className="hist-note__text">{n.note}</p>
                <span className="hist-note__meta">{n.author_name} · {fmtShort(n.created_at)}</span>
              </div>
            ))}
          </div>
        )}

        <label className="dash__field">
          <span className="dash__field-label">Agregar nota</span>
          <textarea
            className="dash__field-input"
            style={{ minHeight: 70, resize: 'vertical' }}
            value={note}
            onChange={e => setNote(e.target.value)}
            maxLength={2000}
            placeholder="Ej: Se citó al acudiente; compromiso de seguimiento…"
          />
        </label>
        <button className="btn--confirm" onClick={submitNote} disabled={savingNote || note.trim().length < 1} aria-busy={savingNote}>
          {savingNote ? 'Guardando…' : 'Agregar nota'}
        </button>
      </div>
    </div>
  );
}

/* ── Reusable ────────────────────────────────────────────────── */
function NavItem({ id, active, icon, label, onClick, pae }) {
  return (
    <button
      className={`dash__nav-item${pae ? ' dash__nav-item--pae' : ''}${active === id ? ' dash__nav-item--active' : ''}`}
      onClick={() => onClick(id)}
    >
      <span className="dash__nav-item-icon">{icon}</span>
      {label}
    </button>
  );
}

function Empty({ icon, label }) {
  return (
    <div className="dash__empty">
      <div style={{ width: 36, height: 36, color: '#a8a4be' }}>{icon}</div>
      <span>Módulo <strong>{label}</strong> — próximamente.</span>
    </div>
  );
}

/* ── Icons ───────────────────────────────────────────────────── */
function LogoIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 100 100" aria-hidden="true" style={{ flexShrink: 0 }}>
      <defs>
        <radialGradient id="t-p" cx="38%" cy="28%" r="70%">
          <stop offset="0%" stopColor="#9B3FF5"/><stop offset="100%" stopColor="#4A0A9E"/>
        </radialGradient>
        <radialGradient id="t-g" cx="33%" cy="28%" r="68%">
          <stop offset="0%" stopColor="#D4F870"/><stop offset="100%" stopColor="#2E7008"/>
        </radialGradient>
      </defs>
      <circle cx="50" cy="52" r="44" fill="url(#t-p)"/>
      <path d="M50,24 L74,68 L26,68 Z" fill="white" stroke="white" strokeWidth="10" strokeLinejoin="round" strokeLinecap="round"/>
      <circle cx="50" cy="11" r="11" fill="url(#t-g)"/>
      <circle cx="80" cy="70" r="11" fill="url(#t-g)"/>
      <circle cx="20" cy="70" r="11" fill="url(#t-g)"/>
    </svg>
  );
}
function ClipboardIcon({ color = 'currentColor' }) { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="12" y2="16"/></svg>; }
function UsersIcon({ color = 'currentColor' })     { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>; }
function CalendarIcon({ color = 'currentColor' })  { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>; }
function ShieldIcon({ color = 'currentColor' })    { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>; }
function BookIcon({ color = 'currentColor' })      { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>; }
function PaperclipIcon() { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" /></svg>; }
function MessageIcon({ color = 'currentColor' })   { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>; }
function LogoutIcon()    { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>; }
function CheckIcon({ color = 'currentColor' })     { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>; }
function AlertIcon({ color = 'currentColor' })     { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>; }
function ClockIcon({ color = 'currentColor' })     { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>; }
function EyeIcon({ color = 'currentColor' })       { return <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>; }
function CloseIcon({ size = 18 })     { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>; }
function ZoomIcon({ size = 14 })      { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>; }
