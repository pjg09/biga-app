import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminService } from '../services/admin';
import { studentService } from '../services/students';
import { StudentsView } from './PAEDashboard';
import '../styles/dashboard.css';

const ROLE_LABEL = { TEACHER: 'Docente', PAE_OPERATOR: 'Operador PAE', ADMIN: 'Administrador' };
const ROLE_CLASS = { TEACHER: 'green', PAE_OPERATOR: 'yellow', ADMIN: 'blue' };
const DAY_NAMES = { 1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 4: 'Jueves', 5: 'Viernes' };
const YEAR = new Date().getFullYear();

const NAV_TITLES = {
  overview:  'Resumen institucional',
  students:  'Estudiantes',
  staff:     'Personal',
  academic:  'Académico',
  schedule:  'Horarios',
};

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'Buenos días' : h < 18 ? 'Buenas tardes' : 'Buenas noches';
}
function dateLabel() {
  return new Date().toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' });
}
function initials(first, last) {
  return `${first?.[0] ?? ''}${last?.[0] ?? ''}`.toUpperCase();
}

function useToast() {
  const [toast, setToast] = useState(null);
  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);
  return { toast, showToast };
}
function Toast({ toast }) {
  if (!toast) return null;
  return (
    <div className={`dash__toast dash__toast--${toast.type}`} role="alert">
      {toast.type === 'success' ? <CheckIcon /> : <AlertIcon />}{toast.msg}
    </div>
  );
}

export default function AdminDashboard() {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const fullName = `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim();
  const [activeNav, setActiveNav] = useState('overview');

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  }, [navigate]);

  return (
    <div className="dash dash--admin">
      <aside className="dash__sidebar">
        <a href="/" className="dash__logo"><LogoIcon /><span className="dash__logo-text">BIGA</span></a>

        <nav className="dash__nav" aria-label="Navegación">
          <div className="dash__nav-section">
            <p className="dash__nav-label">Panel</p>
            <NavItem id="overview" active={activeNav} icon={<ChartIcon />}    label="Resumen"     onClick={setActiveNav} />
          </div>
          <div className="dash__nav-section">
            <p className="dash__nav-label">Gestión</p>
            <NavItem id="students" active={activeNav} icon={<UsersIcon />}    label="Estudiantes" onClick={setActiveNav} />
            <NavItem id="staff"    active={activeNav} icon={<ShieldIcon />}   label="Personal"    onClick={setActiveNav} />
            <NavItem id="academic" active={activeNav} icon={<ListIcon />}     label="Académico"   onClick={setActiveNav} />
            <NavItem id="schedule" active={activeNav} icon={<CalendarIcon />} label="Horarios"    onClick={setActiveNav} />
          </div>
        </nav>

        <div className="dash__sidebar-footer">
          <div className="dash__user-card">
            <div className="dash__user-avatar">{initials(user.first_name, user.last_name) || 'A'}</div>
            <div className="dash__user-info">
              <p className="dash__user-name">{fullName || 'Administrador'}</p>
              <p className="dash__user-role">Administrador</p>
            </div>
            <button className="dash__logout-btn" onClick={logout} aria-label="Cerrar sesión"><LogoutIcon /></button>
          </div>
        </div>
      </aside>

      <div className="dash__main">
        <div className="dash__page-header">
          <div>
            <p className="dash__page-greeting">{greeting()} · {dateLabel()}</p>
            <h1 className="dash__page-title">{NAV_TITLES[activeNav]}</h1>
          </div>
          <span className="dash__page-badge dash__page-badge--admin">Administrador</span>
        </div>

        <main className="dash__content">
          {activeNav === 'overview' && <OverviewView />}
          {activeNav === 'students' && <StudentsView />}
          {activeNav === 'staff'    && <StaffView />}
          {activeNav === 'academic' && <AcademicView />}
          {activeNav === 'schedule' && <ScheduleView />}
        </main>
      </div>
    </div>
  );
}

/* ── Resumen (estadísticas) ──────────────────────────────────── */
function OverviewView() {
  const [stats, setStats]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setStats(await adminService.getStats()); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando estadísticas…</span></div>;
  if (error) return (
    <div className="dash__empty"><AlertIcon color="#ef4444" /><span>{error}</span>
      <button className="btn--secondary" style={{ width: 'auto', marginTop: 8 }} onClick={load}>Reintentar</button>
    </div>
  );

  const s = stats;
  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <button className="btn--secondary" style={{ width: 'auto' }} onClick={load}>Actualizar</button>
      </div>
      <Section title="Población">
        <Stat icon={<UsersIcon />} value={s.students_active} label="Estudiantes activos" />
        <Stat icon={<UsersIcon />} value={s.staff_total} label="Personal" delta={`${s.teachers} docentes · ${s.pae_operators} PAE`} />
      </Section>
      <Section title="PAE — hoy y esta semana">
        <Stat icon={<ListIcon />}  value={s.pae_enrolled} label="Inscritos PAE" />
        <Stat icon={<CheckIcon />} value={s.pae_delivered_today} label="Entregas hoy" delta={`${s.pae_claim_rate}% reclamado`} />
        <Stat icon={<ChartIcon />} value={s.pae_delivered_week} label="Entregas esta semana" />
      </Section>
      <Section title="Asistencia de hoy">
        <Stat icon={<CheckIcon />} value={s.attendance_present_today} label="Presentes" delta={`${s.attendance_rate_today}% asistencia`} />
        <Stat icon={<ClockIcon />} value={s.attendance_late_today} label="Tardanzas" />
        <Stat icon={<AlertIcon />} value={s.attendance_absent_today} label="Ausentes" />
        <Stat icon={<MailIcon />}  value={s.attendance_justified_today} label="Justificadas" />
      </Section>
      <Section title="Salidas y convivencia">
        <Stat icon={<LogoutIcon />} value={s.departures_today} label="Salidas tempranas hoy" />
        <Stat icon={<ShieldIcon />} value={s.discipline_records} label="Registros de convivencia"
          delta={`${s.discipline_leve} leve · ${s.discipline_moderada} mod · ${s.discipline_grave} grave`} />
      </Section>
      <Section title="Notificaciones">
        <Stat icon={<MailIcon />}  value={s.notifications_sent} label="Enviadas" />
        <Stat icon={<AlertIcon />} value={s.notifications_failed} label="Fallidas" />
        <Stat icon={<ClockIcon />} value={s.notifications_pending} label="Pendientes" />
      </Section>
    </>
  );
}

/* ── Personal (usuarios) ─────────────────────────────────────── */
function StaffView() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ first_name: '', last_name: '', document_number: '', email: '', password: '', role: 'TEACHER' });
  const [saving, setSaving] = useState(false);
  const { toast, showToast } = useToast();

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setUsers(await adminService.listUsers()); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const upd = (f) => (e) => setForm(p => ({ ...p, [f]: e.target.value }));

  const submit = useCallback(async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await adminService.createUser(form);
      showToast(`${form.first_name} ${form.last_name} creado`);
      setForm({ first_name: '', last_name: '', document_number: '', email: '', password: '', role: 'TEACHER' });
      await load();
    } catch (err) {
      showToast(err.status === 409 ? 'Ya existe un usuario con ese correo' : err.message, 'error');
    } finally { setSaving(false); }
  }, [form, showToast, load]);

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando personal…</span></div>;
  if (error) return <div className="dash__empty"><AlertIcon color="#ef4444" /><span>{error}</span></div>;

  return (
    <>
      <Toast toast={toast} />
      <form className="card att-form" onSubmit={submit}>
        <p className="dash__list-title">Agregar miembro del personal</p>
        <div className="adm-grid">
          <Field label="Nombres"><input className="dash__field-input" value={form.first_name} onChange={upd('first_name')} required maxLength={100} /></Field>
          <Field label="Apellidos"><input className="dash__field-input" value={form.last_name} onChange={upd('last_name')} required maxLength={100} /></Field>
          <Field label="Documento"><input className="dash__field-input" value={form.document_number} onChange={upd('document_number')} required minLength={3} maxLength={20} /></Field>
          <Field label="Correo"><input className="dash__field-input" type="email" value={form.email} onChange={upd('email')} required /></Field>
          <Field label="Contraseña"><input className="dash__field-input" type="password" value={form.password} onChange={upd('password')} required minLength={8} placeholder="mín. 8 caracteres" /></Field>
          <Field label="Rol">
            <select className="dash__field-input" value={form.role} onChange={upd('role')}>
              <option value="TEACHER">Docente</option>
              <option value="PAE_OPERATOR">Operador PAE</option>
              <option value="ADMIN">Administrador</option>
            </select>
          </Field>
        </div>
        <button className="btn--confirm" type="submit" disabled={saving}>{saving ? 'Creando…' : 'Crear usuario'}</button>
      </form>

      <div className="card dash__list-card">
        <div className="dash__list-header"><span className="dash__list-title">Personal de la institución</span><span className="dash__student-group">{users.length}</span></div>
        {users.map((u, i) => (
          <div className="dash__student-row" key={u.id}>
            <div className="dash__student-avatar" style={{ background: '#e0e7ff', color: '#4f46e5' }}>{initials(u.first_name, u.last_name)}</div>
            <div className="dash__student-info">
              <p className="dash__student-name">{u.first_name} {u.last_name}</p>
              <p className="dash__student-group">{u.email}</p>
            </div>
            <span className={`dash__badge dash__badge--${ROLE_CLASS[u.role]}`}>{ROLE_LABEL[u.role]}</span>
          </div>
        ))}
      </div>
    </>
  );
}

/* ── Académico (grados, grupos, matrícula) ───────────────────── */
function AcademicView() {
  const [grades, setGrades] = useState([]);
  const [groups, setGroups] = useState([]);
  const { toast, showToast } = useToast();

  const [grade, setGrade] = useState({ name: '', level: '' });
  const [group, setGroup] = useState({ grade_id: '', name: '', academic_year: YEAR });

  // Matrícula
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [student, setStudent] = useState(null);
  const [enrollGroup, setEnrollGroup] = useState('');

  const load = useCallback(async () => {
    try {
      const [g, gr] = await Promise.all([adminService.listGrades(), adminService.listGroups()]);
      setGrades(g); setGroups(gr);
    } catch (e) { showToast(e.message, 'error'); }
  }, [showToast]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (student || q.trim().length < 2) { setResults([]); return; }
    let active = true;
    const t = setTimeout(async () => {
      try { const r = await studentService.search(q.trim()); if (active) setResults(r); } catch { /* */ }
    }, 250);
    return () => { active = false; clearTimeout(t); };
  }, [q, student]);

  const submitGrade = async (e) => {
    e.preventDefault();
    try { await adminService.createGrade({ name: grade.name, level: Number(grade.level) }); showToast('Grado creado'); setGrade({ name: '', level: '' }); load(); }
    catch (err) { showToast(err.message, 'error'); }
  };
  const submitGroup = async (e) => {
    e.preventDefault();
    try { await adminService.createGroup({ grade_id: group.grade_id, name: group.name, academic_year: Number(group.academic_year) }); showToast('Grupo creado'); setGroup({ grade_id: '', name: '', academic_year: YEAR }); load(); }
    catch (err) { showToast(err.message, 'error'); }
  };
  const submitEnroll = async (e) => {
    e.preventDefault();
    if (!student || !enrollGroup) { showToast('Elegí estudiante y grupo', 'error'); return; }
    try { await adminService.enrollStudentInGroup({ student_id: student.id, group_id: enrollGroup, academic_year: YEAR }); showToast(`${student.full_name} matriculado`); setStudent(null); setQ(''); setEnrollGroup(''); }
    catch (err) { showToast(err.status === 409 ? 'El estudiante ya está matriculado ese año' : err.message, 'error'); }
  };

  return (
    <>
      <Toast toast={toast} />
      <div className="adm-cols">
        <form className="card att-form" onSubmit={submitGrade}>
          <p className="dash__list-title">Crear grado</p>
          <Field label="Nombre"><input className="dash__field-input" value={grade.name} onChange={e => setGrade(p => ({ ...p, name: e.target.value }))} required placeholder="Once" /></Field>
          <Field label="Nivel (1–11)"><input className="dash__field-input" type="number" min={1} max={11} value={grade.level} onChange={e => setGrade(p => ({ ...p, level: e.target.value }))} required /></Field>
          <button className="btn--confirm" type="submit">Crear grado</button>
          <div className="adm-chips">{grades.map(g => <span className="adm-chip" key={g.id}>{g.level} · {g.name}</span>)}</div>
        </form>

        <form className="card att-form" onSubmit={submitGroup}>
          <p className="dash__list-title">Crear grupo (salón)</p>
          <Field label="Grado">
            <select className="dash__field-input" value={group.grade_id} onChange={e => setGroup(p => ({ ...p, grade_id: e.target.value }))} required>
              <option value="">Seleccionar…</option>
              {grades.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          </Field>
          <Field label="Nombre del grupo"><input className="dash__field-input" value={group.name} onChange={e => setGroup(p => ({ ...p, name: e.target.value }))} required placeholder="A" maxLength={10} /></Field>
          <Field label="Año académico"><input className="dash__field-input" type="number" value={group.academic_year} onChange={e => setGroup(p => ({ ...p, academic_year: e.target.value }))} required /></Field>
          <button className="btn--confirm" type="submit">Crear grupo</button>
          <div className="adm-chips">{groups.map(g => <span className="adm-chip" key={g.id}>{g.grade_name} {g.name} · {g.academic_year}</span>)}</div>
        </form>
      </div>

      <form className="card att-form" onSubmit={submitEnroll}>
        <p className="dash__list-title">Matricular estudiante en grupo</p>
        {student ? (
          <div className="att-selected">
            <span className="dash__student-name">{student.full_name}</span>
            <span className="dash__student-group">Doc. {student.document_number}</span>
            <button type="button" className="att-selected__clear" onClick={() => setStudent(null)}>✕</button>
          </div>
        ) : (
          <div className="att-search">
            <input className="dash__field-input" placeholder="Buscar estudiante…" value={q} onChange={e => setQ(e.target.value)} />
            {results.length > 0 && (
              <div className="att-search__results">
                {results.map(r => (
                  <button type="button" key={r.id} className="att-search__item" onClick={() => { setStudent(r); setResults([]); }}>
                    <span className="dash__student-name">{r.full_name}</span>
                    <span className="dash__student-group">Doc. {r.document_number}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        <Field label="Grupo">
          <select className="dash__field-input" value={enrollGroup} onChange={e => setEnrollGroup(e.target.value)} required>
            <option value="">Seleccionar…</option>
            {groups.map(g => <option key={g.id} value={g.id}>{g.grade_name} {g.name} · {g.academic_year}</option>)}
          </select>
        </Field>
        <button className="btn--confirm" type="submit">Matricular ({YEAR})</button>
      </form>
    </>
  );
}

/* ── Horarios (bloques + asignaciones) ───────────────────────── */
function ScheduleView() {
  const [groups, setGroups] = useState([]);
  const [users, setUsers] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const { toast, showToast } = useToast();

  const [selGroup, setSelGroup] = useState('');
  const [periods, setPeriods] = useState([]);
  const [cp, setCp] = useState({ name: 'Primera hora', period_order: 1, start_time: '07:00', end_time: '07:50', day_of_week: 1 });

  const [assign, setAssign] = useState({ user_id: '', group_id: '' });

  const load = useCallback(async () => {
    try {
      const [g, u, a] = await Promise.all([adminService.listGroups(), adminService.listUsers(), adminService.listAssignments()]);
      setGroups(g); setUsers(u); setAssignments(a);
    } catch (e) { showToast(e.message, 'error'); }
  }, [showToast]);
  useEffect(() => { load(); }, [load]);

  const loadPeriods = useCallback(async (gid) => {
    if (!gid) { setPeriods([]); return; }
    try { setPeriods(await adminService.listClassPeriods(gid)); } catch { setPeriods([]); }
  }, []);
  useEffect(() => { loadPeriods(selGroup); }, [selGroup, loadPeriods]);

  const submitCp = async (e) => {
    e.preventDefault();
    if (!selGroup) { showToast('Elegí un grupo', 'error'); return; }
    try {
      await adminService.createClassPeriod({
        group_id: selGroup, name: cp.name, period_order: Number(cp.period_order),
        start_time: `${cp.start_time}:00`, end_time: `${cp.end_time}:00`, day_of_week: Number(cp.day_of_week),
      });
      showToast('Bloque horario creado'); loadPeriods(selGroup);
    } catch (err) { showToast(err.status === 409 ? 'Ya existe un bloque con ese orden y día' : err.message, 'error'); }
  };

  const submitAssign = async (e) => {
    e.preventDefault();
    try {
      await adminService.assignTeacher({ user_id: assign.user_id, group_id: assign.group_id, academic_year: YEAR });
      showToast('Docente asignado'); setAssign({ user_id: '', group_id: '' }); load();
    } catch (err) { showToast(err.status === 409 ? 'Ya está asignado a ese grupo ese año' : err.message, 'error'); }
  };

  const groupLabel = (id) => { const g = groups.find(x => x.id === id); return g ? `${g.grade_name} ${g.name}` : id; };

  return (
    <>
      <Toast toast={toast} />
      <form className="card att-form" onSubmit={submitCp}>
        <p className="dash__list-title">Crear bloque horario</p>
        <Field label="Grupo">
          <select className="dash__field-input" value={selGroup} onChange={e => setSelGroup(e.target.value)} required>
            <option value="">Seleccionar…</option>
            {groups.map(g => <option key={g.id} value={g.id}>{g.grade_name} {g.name} · {g.academic_year}</option>)}
          </select>
        </Field>
        <div className="adm-grid">
          <Field label="Nombre"><input className="dash__field-input" value={cp.name} onChange={e => setCp(p => ({ ...p, name: e.target.value }))} required /></Field>
          <Field label="Orden (1 = primera hora)"><input className="dash__field-input" type="number" min={1} value={cp.period_order} onChange={e => setCp(p => ({ ...p, period_order: e.target.value }))} required /></Field>
          <Field label="Día">
            <select className="dash__field-input" value={cp.day_of_week} onChange={e => setCp(p => ({ ...p, day_of_week: e.target.value }))}>
              {[1, 2, 3, 4, 5].map(d => <option key={d} value={d}>{DAY_NAMES[d]}</option>)}
            </select>
          </Field>
          <Field label="Inicio"><input className="dash__field-input" type="time" value={cp.start_time} onChange={e => setCp(p => ({ ...p, start_time: e.target.value }))} required /></Field>
          <Field label="Fin"><input className="dash__field-input" type="time" value={cp.end_time} onChange={e => setCp(p => ({ ...p, end_time: e.target.value }))} required /></Field>
        </div>
        <button className="btn--confirm" type="submit">Crear bloque</button>
        {selGroup && (
          <div className="adm-chips">
            {periods.length === 0 ? <span className="dash__student-group">Sin bloques aún</span>
              : periods.map(p => <span className="adm-chip" key={p.id}>{DAY_NAMES[p.day_of_week]} {p.start_time.slice(0, 5)} · {p.name}</span>)}
          </div>
        )}
      </form>

      <form className="card att-form" onSubmit={submitAssign}>
        <p className="dash__list-title">Asignar docente a grupo</p>
        <div className="adm-grid">
          <Field label="Docente / operador">
            <select className="dash__field-input" value={assign.user_id} onChange={e => setAssign(p => ({ ...p, user_id: e.target.value }))} required>
              <option value="">Seleccionar…</option>
              {users.filter(u => u.role !== 'ADMIN').map(u => <option key={u.id} value={u.id}>{u.first_name} {u.last_name} ({ROLE_LABEL[u.role]})</option>)}
            </select>
          </Field>
          <Field label="Grupo">
            <select className="dash__field-input" value={assign.group_id} onChange={e => setAssign(p => ({ ...p, group_id: e.target.value }))} required>
              <option value="">Seleccionar…</option>
              {groups.map(g => <option key={g.id} value={g.id}>{g.grade_name} {g.name} · {g.academic_year}</option>)}
            </select>
          </Field>
        </div>
        <button className="btn--confirm" type="submit">Asignar ({YEAR})</button>
      </form>

      <div className="card dash__list-card">
        <div className="dash__list-header"><span className="dash__list-title">Asignaciones docente–grupo</span><span className="dash__student-group">{assignments.length}</span></div>
        {assignments.length === 0 ? <div className="dash__empty" style={{ padding: '24px' }}><span>Sin asignaciones aún.</span></div>
          : assignments.map(a => (
            <div className="dash__student-row" key={a.id}>
              <div className="dash__student-info">
                <p className="dash__student-name">{a.user_name}</p>
                <p className="dash__student-group">{groupLabel(a.group_id)} · {a.academic_year}</p>
              </div>
            </div>
          ))}
      </div>
    </>
  );
}

/* ── Reusable ────────────────────────────────────────────────── */
function Section({ title, children }) {
  return <div className="admin-section"><p className="admin-section__title">{title}</p><div className="dash__stats">{children}</div></div>;
}
function Stat({ icon, value, label, delta }) {
  return (
    <div className="dash__stat-card">
      <div className="dash__stat-icon dash__stat-icon--admin">{icon}</div>
      <p className="dash__stat-value">{value}</p>
      <p className="dash__stat-label">{label}</p>
      {delta && <p className="dash__stat-delta">{delta}</p>}
    </div>
  );
}
function Field({ label, children }) {
  return <label className="dash__field"><span className="dash__field-label">{label}</span>{children}</label>;
}
function NavItem({ id, active, icon, label, onClick }) {
  return (
    <button className={`dash__nav-item${active === id ? ' dash__nav-item--active' : ''}`} onClick={() => onClick(id)}>
      <span className="dash__nav-item-icon">{icon}</span>{label}
    </button>
  );
}

/* ── Icons ─────────────────────────────────────────────────────── */
function LogoIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 100 100" aria-hidden="true" style={{ flexShrink: 0 }}>
      <defs>
        <radialGradient id="ad-p" cx="38%" cy="28%" r="70%"><stop offset="0%" stopColor="#9B3FF5" /><stop offset="100%" stopColor="#4A0A9E" /></radialGradient>
        <radialGradient id="ad-g" cx="33%" cy="28%" r="68%"><stop offset="0%" stopColor="#D4F870" /><stop offset="100%" stopColor="#2E7008" /></radialGradient>
      </defs>
      <circle cx="50" cy="52" r="44" fill="url(#ad-p)" />
      <path d="M50,24 L74,68 L26,68 Z" fill="white" stroke="white" strokeWidth="10" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx="50" cy="11" r="11" fill="url(#ad-g)" /><circle cx="80" cy="70" r="11" fill="url(#ad-g)" /><circle cx="20" cy="70" r="11" fill="url(#ad-g)" />
    </svg>
  );
}
function ChartIcon()  { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></svg>; }
function UsersIcon()  { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 00-3-3.87" /><path d="M16 3.13a4 4 0 010 7.75" /></svg>; }
function CheckIcon()  { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>; }
function AlertIcon({ color = 'currentColor' }) { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>; }
function ClockIcon()  { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>; }
function ShieldIcon() { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>; }
function MailIcon()   { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" /><path d="M22 7l-10 6L2 7" /></svg>; }
function ListIcon()   { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" /></svg>; }
function CalendarIcon() { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>; }
function LogoutIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>; }
function Spinner({ color = '#4f46e5', size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" className="dash__spinner">
      <circle cx="12" cy="12" r="10" stroke="rgba(0,0,0,0.1)" strokeWidth="2.5" />
      <path d="M12 2a10 10 0 0110 10" stroke={color} strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}
