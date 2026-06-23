import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/dashboard.css';

const MOCK_STUDENTS = [
  { id: 1, name: 'Valentina Ríos',   group: '7A', status: 'PRESENT', time: '07:12' },
  { id: 2, name: 'Sebastián Mora',   group: '7A', status: 'ABSENT',  time: '—'     },
  { id: 3, name: 'Isabella Castaño', group: '7A', status: 'LATE',    time: '07:48' },
  { id: 4, name: 'Tomás Herrera',    group: '7A', status: 'PRESENT', time: '07:09' },
  { id: 5, name: 'Luciana Vargas',   group: '7B', status: 'PRESENT', time: '07:15' },
];

const STATUS_LABEL = { PRESENT: 'Presente', ABSENT: 'Ausente', LATE: 'Tardanza' };
const STATUS_CLASS  = { PRESENT: 'green',   ABSENT: 'red',     LATE: 'yellow'   };

const AVATARS = [
  { bg: '#ede9fe', color: '#6d28d9' },
  { bg: '#dbeafe', color: '#1d4ed8' },
  { bg: '#fef3c7', color: '#b45309' },
  { bg: '#d1fae5', color: '#065f46' },
  { bg: '#fee2e2', color: '#991b1b' },
];

const NAV_TITLES = {
  attendance: 'Asistencia',
  students:   'Mis estudiantes',
  schedule:   'Horario',
  conduct:    'Convivencia',
  messages:   'Mensajes',
};

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
            <NavItem id="attendance" active={activeNav} icon={<ClipboardIcon />} label="Asistencia"  onClick={setActiveNav} />
            <NavItem id="students"   active={activeNav} icon={<UsersIcon />}     label="Estudiantes" onClick={setActiveNav} />
            <NavItem id="schedule"   active={activeNav} icon={<CalendarIcon />}  label="Horario"     onClick={setActiveNav} />
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
          {activeNav === 'students'   && <Empty icon={<UsersIcon />}    label="Estudiantes" />}
          {activeNav === 'schedule'   && <Empty icon={<CalendarIcon />} label="Horario" />}
          {activeNav === 'conduct'    && <Empty icon={<ShieldIcon />}   label="Convivencia" />}
          {activeNav === 'messages'   && <Empty icon={<MessageIcon />}  label="Mensajes" />}
        </main>
      </div>
    </div>
  );
}

/* ── Attendance view ─────────────────────────────────────────── */
function AttendanceView() {
  const present = MOCK_STUDENTS.filter(s => s.status === 'PRESENT').length;
  const absent  = MOCK_STUDENTS.filter(s => s.status === 'ABSENT').length;
  const late    = MOCK_STUDENTS.filter(s => s.status === 'LATE').length;
  const total   = MOCK_STUDENTS.length;
  const pct     = Math.round(present / total * 100);

  const r    = 60;
  const circ = 2 * Math.PI * r;
  const gap  = 5;

  const presArc = Math.max(0, (present / total) * circ - gap);
  const lateArc = Math.max(0, (late    / total) * circ - gap);
  const absArc  = Math.max(0, (absent  / total) * circ - gap);
  const lateOff = -((present / total) * circ);
  const absOff  = -(((present + late) / total) * circ);

  return (
    <>
      {/* Bento: donut hero + stat stack */}
      <div className="dash__bento">

        {/* Donut hero card */}
        <div className="card dash__donut-hero">
          <div className="dash__donut-wrap">
            <svg width="148" height="148" viewBox="0 0 148 148">
              <circle cx="74" cy="74" r={r} fill="none" stroke="#F2F1F8" strokeWidth="13" />
              <circle cx="74" cy="74" r={r} fill="none" stroke="#6d28d9" strokeWidth="13"
                strokeDasharray={`${presArc} ${circ}`} strokeDashoffset="0" strokeLinecap="butt" />
              {late > 0 && (
                <circle cx="74" cy="74" r={r} fill="none" stroke="#f59e0b" strokeWidth="13"
                  strokeDasharray={`${lateArc} ${circ}`} strokeDashoffset={lateOff} strokeLinecap="butt" />
              )}
              {absent > 0 && (
                <circle cx="74" cy="74" r={r} fill="none" stroke="#ef4444" strokeWidth="13"
                  strokeDasharray={`${absArc} ${circ}`} strokeDashoffset={absOff} strokeLinecap="butt" />
              )}
            </svg>
            <div className="dash__donut-text">
              <span className="dash__donut-pct">{pct}%</span>
              <span className="dash__donut-sub">hoy</span>
            </div>
          </div>

          <div className="dash__donut-info">
            <p className="dash__donut-title">Asistencia del grupo</p>
            <p className="dash__donut-date">{new Date().toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' })}</p>

            <div className="dash__donut-legend">
              {[
                { color: '#6d28d9', label: 'Presentes', val: present, fill: present/total*100 },
                { color: '#f59e0b', label: 'Tardanzas', val: late,    fill: late/total*100    },
                { color: '#ef4444', label: 'Ausentes',  val: absent,  fill: absent/total*100  },
              ].map(item => (
                <div key={item.label}>
                  <div className="dash__legend-row">
                    <div className="dash__legend-dot" style={{ background: item.color }} />
                    <span className="dash__legend-label">{item.label}</span>
                    <span className="dash__legend-val">{item.val}</span>
                  </div>
                  <div className="dash__legend-bar">
                    <div className="dash__legend-bar-fill" style={{ width: `${item.fill}%`, background: item.color }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Stat stack */}
        <div className="card dash__stat-stack">
          <p className="dash__stat-stack-title">Resumen</p>

          <div className="dash__stat-item">
            <div className="dash__stat-item-icon" style={{ background: '#ede9fe' }}>
              <UsersIcon color="#6d28d9" />
            </div>
            <div className="dash__stat-item-body">
              <p className="dash__stat-item-label">Total estudiantes</p>
              <div className="dash__stat-item-bar">
                <div className="dash__stat-item-bar-fill" style={{ width: '100%', background: '#6d28d9' }} />
              </div>
            </div>
            <span className="dash__stat-item-val">{total}</span>
          </div>

          <div className="dash__stat-item">
            <div className="dash__stat-item-icon" style={{ background: '#d1fae5' }}>
              <CheckIcon color="#059669" />
            </div>
            <div className="dash__stat-item-body">
              <p className="dash__stat-item-label">Presentes</p>
              <div className="dash__stat-item-bar">
                <div className="dash__stat-item-bar-fill" style={{ width: `${present/total*100}%`, background: '#059669' }} />
              </div>
            </div>
            <span className="dash__stat-item-val">{present}</span>
          </div>

          <div className="dash__stat-item">
            <div className="dash__stat-item-icon" style={{ background: '#fef3c7' }}>
              <ClockIcon color="#b45309" />
            </div>
            <div className="dash__stat-item-body">
              <p className="dash__stat-item-label">Tardanzas</p>
              <div className="dash__stat-item-bar">
                <div className="dash__stat-item-bar-fill" style={{ width: `${late/total*100}%`, background: '#f59e0b' }} />
              </div>
            </div>
            <span className="dash__stat-item-val">{late}</span>
          </div>

          <div className="dash__stat-item">
            <div className="dash__stat-item-icon" style={{ background: '#fee2e2' }}>
              <AlertIcon color="#991b1b" />
            </div>
            <div className="dash__stat-item-body">
              <p className="dash__stat-item-label">Ausentes</p>
              <div className="dash__stat-item-bar">
                <div className="dash__stat-item-bar-fill" style={{ width: `${absent/total*100}%`, background: '#ef4444' }} />
              </div>
            </div>
            <span className="dash__stat-item-val">{absent}</span>
          </div>
        </div>
      </div>

      {/* Student list */}
      <div className="card dash__list-card">
        <div className="dash__list-header">
          <span className="dash__list-title">Registro de hoy</span>
          <button className="dash__list-action">Exportar</button>
        </div>
        {MOCK_STUDENTS.map((s, i) => {
          const av = AVATARS[i % AVATARS.length];
          return (
            <div className="dash__student-row" key={s.id}>
              <div className="dash__student-avatar" style={{ background: av.bg, color: av.color }}>
                {s.name.split(' ').map(w => w[0]).join('').slice(0, 2)}
              </div>
              <div className="dash__student-info">
                <p className="dash__student-name">{s.name}</p>
                <p className="dash__student-group">Grupo {s.group}</p>
              </div>
              <span className="dash__student-time">{s.time}</span>
              <span className={`dash__badge dash__badge--${STATUS_CLASS[s.status]}`}>
                {STATUS_LABEL[s.status]}
              </span>
            </div>
          );
        })}
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
