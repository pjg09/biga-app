import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { attendanceService } from '../services/attendance';
import { departureService } from '../services/departures';
import { studentService } from '../services/students';
import { agendatorioService } from '../services/agendatorio';
import '../styles/dashboard.css';

const STATUS_LABEL = { PRESENT: 'Presente', ABSENT: 'Ausente', LATE: 'Tardanza', JUSTIFIED: 'Justificada' };
const STATUS_CLASS  = { PRESENT: 'green',   ABSENT: 'red',     LATE: 'yellow',   JUSTIFIED: 'blue' };

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
  const navigate = useNavigate();
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
      {/* Sidebar */}
      <aside className="dash__sidebar">
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
            <NavItem id="conduct"  active={activeNav} icon={<ShieldIcon />}  label="Convivencia" onClick={setActiveNav} />
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
          <div>
            <p className="dash__page-greeting">{greeting()} · {dateLabel()}</p>
            <h1 className="dash__page-title">{NAV_TITLES[activeNav]}</h1>
          </div>
          <span className="dash__page-badge dash__page-badge--teacher">Docente</span>
        </div>

        <main className="dash__content">
          {activeNav === 'attendance' && <AttendanceView />}
          {activeNav === 'departures' && <DeparturesView />}
          {activeNav === 'students'   && <TeacherStudentsView />}
          {activeNav === 'schedule'   && <ScheduleView />}
          {activeNav === 'conduct'    && <ConvivenciaView />}
          {activeNav === 'messages'   && <MensajesView />}
        </main>
      </div>
    </div>
  );
}

/* ── Attendance view ─────────────────────────────────────────── */
export function AttendanceView() {
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
      const res = await attendanceService.getFirstClass();
      setData(res);
      if (res.has_class && !res.already_taken) {
        const init = {};
        res.students.forEach(s => { init[s.student_id] = 'PRESENT'; });
        setMarks(init);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = useCallback((id) => {
    setMarks(prev => ({ ...prev, [id]: prev[id] === 'PRESENT' ? 'ABSENT' : 'PRESENT' }));
  }, []);

  const submit = useCallback(async () => {
    if (!data) return;
    setSaving(true);
    try {
      const entries = data.students.map(s => ({ student_id: s.student_id, status: marks[s.student_id] }));
      await attendanceService.submit(data.class_period_id, entries);
      showToast('Asistencia registrada. Los ausentes serán notificados.');
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

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando tu primera clase…</span></div>;
  if (error) {
    return (
      <div className="dash__empty">
        <AlertIcon color="#ef4444" /><span>{error}</span>
        <button className="btn--secondary" style={{ width: 'auto', marginTop: 8 }} onClick={load}>Reintentar</button>
      </div>
    );
  }
  if (!data.has_class) {
    return (
      <div className="dash__empty">
        <CalendarIcon />
        <span>No tienes una primera hora asignada para hoy.</span>
      </div>
    );
  }

  const present = data.students.filter(s => marksOrStatus(s, marks) === 'PRESENT').length;
  const absent  = data.students.filter(s => marksOrStatus(s, marks) === 'ABSENT').length;
  const late    = data.students.filter(s => marksOrStatus(s, marks) === 'LATE').length;
  const total   = data.students.length;

  return (
    <>
      {toast && (
        <div className={`dash__toast dash__toast--${toast.type}`} role="alert">
          {toast.type === 'success' ? <CheckIcon /> : <AlertIcon />}{toast.msg}
        </div>
      )}

      <div className="att-head card">
        <div>
          <p className="att-head__period">{data.period_name} · Grupo {data.group_name}</p>
          <p className="att-head__sub">
            {data.start_time?.slice(0, 5)}–{data.end_time?.slice(0, 5)} · {total} estudiantes
          </p>
        </div>
        <div className="att-head__counts">
          <span className="dash__badge dash__badge--green">{present} presentes</span>
          {late > 0   && <span className="dash__badge dash__badge--yellow">{late} tardanzas</span>}
          <span className="dash__badge dash__badge--red">{absent} ausentes</span>
        </div>
      </div>

      <div className="card dash__list-card">
        <div className="dash__list-header">
          <span className="dash__list-title">
            {data.already_taken ? 'Registro de hoy' : 'Toma de asistencia'}
          </span>
          {!data.already_taken && (
            <button className="btn--confirm" style={{ flex: '0 0 auto' }} onClick={submit} disabled={saving} aria-busy={saving}>
              {saving ? 'Guardando…' : 'Guardar asistencia'}
            </button>
          )}
        </div>

        {data.students.map((s, i) => {
          const av = AVATARS[i % AVATARS.length];
          const status = marksOrStatus(s, marks);
          return (
            <div className="dash__student-row" key={s.student_id}>
              {s.photo_url
                ? <img className="dash__table-photo" src={s.photo_url} alt="" />
                : <div className="dash__student-avatar" style={{ background: av.bg, color: av.color }}>{initials(s.first_name, s.last_name)}</div>}
              <div className="dash__student-info">
                <p className="dash__student-name">{s.first_name} {s.last_name}</p>
                <p className="dash__student-group">Doc. {s.document_number}</p>
              </div>

              {data.already_taken ? (
                <>
                  <span className={`dash__badge dash__badge--${STATUS_CLASS[s.status] || 'green'}`}>
                    {STATUS_LABEL[s.status] || s.status}
                  </span>
                  {s.status === 'ABSENT' && (
                    <button
                      className="dash__table-register-btn"
                      style={{ marginLeft: 10 }}
                      onClick={() => markArrived(s)}
                      disabled={arrivingId === s.student_id}
                    >
                      {arrivingId === s.student_id ? 'Marcando…' : 'Llegó (tardanza)'}
                    </button>
                  )}
                </>
              ) : (
                <button
                  className={`att-toggle att-toggle--${status === 'PRESENT' ? 'present' : 'absent'}`}
                  onClick={() => toggle(s.student_id)}
                >
                  {status === 'PRESENT' ? 'Presente' : 'Ausente'}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

function marksOrStatus(student, marks) {
  return marks[student.student_id] ?? student.status ?? 'PRESENT';
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

      <form className="card att-form" onSubmit={submit}>
        <p className="dash__list-title" style={{ marginBottom: 4 }}>Registrar salida anticipada</p>

        {selected ? (
          <div className="att-selected">
            <span className="dash__student-name">{selected.full_name}</span>
            <span className="dash__student-group">Doc. {selected.document_number}{selected.group_name ? ` · ${selected.group_name}` : ''}</span>
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
            <input className="dash__field-input" type="time" value={time} onChange={e => setTime(e.target.value)} required />
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
              <div className="dash__student-avatar" style={{ background: av.bg, color: av.color }}>
                {(d.student_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
              </div>
              <div className="dash__student-info">
                <p className="dash__student-name">{d.student_name || d.student_id}</p>
                <p className="dash__student-group">{d.reason || 'Sin motivo'}</p>
              </div>
              <span className="dash__student-time">{d.departure_time?.slice(0, 5)}</span>
            </div>
          );
        })}
      </div>
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
function TeacherStudentsView() {
  const [students, setStudents] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [query, setQuery]       = useState('');

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
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    return s.first_name.toLowerCase().includes(q)
      || s.last_name.toLowerCase().includes(q)
      || s.document_number.includes(q);
  });

  return (
    <div className="card dash__list-card">
      <div className="dash__list-header">
        <span className="dash__list-title">Estudiantes de la institución</span>
        <span className="dash__student-group">{filtered.length}</span>
      </div>

      <div style={{ padding: '0 18px 12px' }}>
        <input
          className="dash__field-input"
          type="search"
          placeholder="Buscar por nombre o documento…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          autoComplete="off"
        />
      </div>

      {filtered.length === 0 ? (
        <div className="dash__empty" style={{ padding: '32px 20px' }}>
          <UsersIcon /><span>{students.length === 0 ? 'Aún no hay estudiantes registrados.' : `Sin resultados para "${query}"`}</span>
        </div>
      ) : filtered.map((s, i) => {
        const av = AVATARS[i % AVATARS.length];
        return (
          <div className="dash__student-row" key={s.id}>
            {s.photo_url
              ? <img className="dash__table-photo" src={s.photo_url} alt="" />
              : <div className="dash__student-avatar" style={{ background: av.bg, color: av.color }}>{initials(s.first_name, s.last_name)}</div>}
            <div className="dash__student-info">
              <p className="dash__student-name">{s.first_name} {s.last_name}</p>
              <p className="dash__student-group">Doc. {s.document_number}</p>
            </div>
            <span className={`dash__badge dash__badge--${s.is_active ? 'green' : 'red'}`}>
              {s.is_active ? 'Activo' : 'Inactivo'}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ── Horario ─────────────────────────────────────────────────── */
const DAY_NAMES = { 1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes' };

export function ScheduleView() {
  const [items, setItems]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

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
    <div className="sched">
      {[1, 2, 3, 4, 5].map(day => (
        <div className="card sched__col" key={day}>
          <p className="sched__day">{DAY_NAMES[day]}</p>
          {(byDay[day] || []).length === 0 ? (
            <p className="sched__free">Sin clases</p>
          ) : byDay[day].map(it => (
            <div className="sched__slot" key={it.class_period_id}>
              <span className="sched__time">{it.start_time.slice(0, 5)}–{it.end_time.slice(0, 5)}</span>
              <span className="sched__name">{it.name}</span>
              <span className="sched__group">{it.grade_name} {it.group_name}{it.period_order === 1 ? ' · 1ª hora' : ''}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

/* ── Mensajes: excusas de los acudientes ─────────────────────── */
export function MensajesView() {
  const [msgs, setMsgs]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  useEffect(() => {
    attendanceService.justifications()
      .then(setMsgs)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando mensajes…</span></div>;
  if (error)   return <div className="dash__empty"><AlertIcon color="#ef4444" /><span>{error}</span></div>;
  if (msgs.length === 0) {
    return <div className="dash__empty"><MessageIcon /><span>Aún no hay excusas enviadas por los acudientes.</span></div>;
  }

  return (
    <div className="card dash__list-card">
      <div className="dash__list-header">
        <span className="dash__list-title">Excusas de los acudientes</span>
        <span className="dash__student-group">{msgs.length}</span>
      </div>
      {msgs.map((m, i) => {
        const av = AVATARS[i % AVATARS.length];
        return (
          <div className="msg" key={m.record_id}>
            <div className="dash__student-avatar" style={{ background: av.bg, color: av.color }}>
              {(m.student_name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()}
            </div>
            <div className="msg__body">
              <div className="msg__head">
                <span className="dash__student-name">{m.student_name}</span>
                <span className="msg__date">Inasistencia {fmtShort(m.date)}{m.group_name ? ` · ${m.group_name}` : ''}</span>
              </div>
              <p className="msg__reason">{m.reason}</p>
              <span className="msg__meta">Justificada el {fmtShort(m.submitted_at)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function fmtShort(iso) {
  if (!iso) return '';
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  return d.toLocaleDateString('es-CO', { day: 'numeric', month: 'short' });
}

/* ── Convivencia (agendatorio) ───────────────────────────────── */
const SEVERITY_CLASS = { LEVE: 'green', MODERADA: 'yellow', GRAVE: 'red' };

export function ConvivenciaView() {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  const [query, setQuery]       = useState('');
  const [results, setResults]   = useState([]);
  const [student, setStudent]   = useState(null);
  const [picked, setPicked]     = useState([]);   // article ids
  const [obs, setObs]           = useState('');
  const [saving, setSaving]     = useState(false);
  const [toast, setToast]       = useState(null);
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

  useEffect(() => {
    if (student || query.trim().length < 2) { setResults([]); return; }
    let active = true;
    const t = setTimeout(async () => {
      try { const r = await studentService.search(query.trim()); if (active) setResults(r); }
      catch { /* ignore */ }
    }, 250);
    return () => { active = false; clearTimeout(t); };
  }, [query, student]);

  const toggleArticle = (id) =>
    setPicked(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

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
      setStudent(null); setQuery(''); setPicked([]); setObs(''); clearCanvas();
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

      <div className="card att-form">
        <p className="dash__list-title" style={{ marginBottom: 4 }}>Nuevo registro de convivencia</p>

        {student ? (
          <div className="att-selected">
            <span className="dash__student-name">{student.full_name}</span>
            <span className="dash__student-group">Doc. {student.document_number}{student.group_name ? ` · ${student.group_name}` : ''}</span>
            <button type="button" className="att-selected__clear" onClick={() => setStudent(null)} aria-label="Cambiar">✕</button>
          </div>
        ) : (
          <div className="att-search">
            <input className="dash__field-input" placeholder="Buscar estudiante…" value={query}
              onChange={e => setQuery(e.target.value)} autoComplete="off" />
            {results.length > 0 && (
              <div className="att-search__results">
                {results.map(r => (
                  <button type="button" key={r.id} className="att-search__item" onClick={() => { setStudent(r); setResults([]); }}>
                    <span className="dash__student-name">{r.full_name}</span>
                    <span className="dash__student-group">Doc. {r.document_number}{r.group_name ? ` · ${r.group_name}` : ''}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div>
          <span className="dash__field-label">Artículos del manual infringidos</span>
          {articles.length === 0 ? (
            <p className="sched__free">No hay artículos cargados en el manual.</p>
          ) : (
            <div className="conv-articles">
              {articles.map(a => (
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
function MessageIcon({ color = 'currentColor' })   { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>; }
function LogoutIcon()    { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>; }
function CheckIcon({ color = 'currentColor' })     { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>; }
function AlertIcon({ color = 'currentColor' })     { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>; }
function ClockIcon({ color = 'currentColor' })     { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>; }
