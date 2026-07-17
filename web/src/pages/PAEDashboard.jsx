import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { paeService } from '../services/pae';
import { studentService } from '../services/students';
import { AttendanceView, DeparturesView, ScheduleView, ConvivenciaView, HistorialView, MensajesView, StudentPhoto } from './TeacherDashboard';
import '../styles/dashboard.css';

const AVATARS = [
  { bg: '#ede9fe', color: '#6d28d9' },
  { bg: '#dbeafe', color: '#1d4ed8' },
  { bg: '#fef3c7', color: '#b45309' },
  { bg: '#d1fae5', color: '#065f46' },
  { bg: '#fee2e2', color: '#991b1b' },
];

const NAV_TITLES = {
  'pae-register': 'Registro PAE',
  'pae-report':   'Reporte diario',
  'pae-enrolled': 'Matriculados',
  students:       'Estudiantes',
  attendance:     'Asistencia',
  departures:     'Salidas tempranas',
  schedule:       'Horario',
  conduct:        'Convivencia',
  history:        'Historial',
  messages:       'Mensajes',
};

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'Buenos días' : h < 18 ? 'Buenas tardes' : 'Buenas noches';
}

function dateLabel() {
  return new Date().toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' });
}

function avatarFor(str, i) {
  return AVATARS[i % AVATARS.length];
}

function initials(first, last) {
  return `${first?.[0] ?? ''}${last?.[0] ?? ''}`.toUpperCase();
}

export default function PAEDashboard() {
  const [activeNav, setActiveNav] = useState('pae-register');
  const navigate = useNavigate();
  const user     = JSON.parse(localStorage.getItem('user') || '{}');

  useEffect(() => { document.title = 'BIGA - PAE'; }, []);
  const userInitials = initials(user.first_name, user.last_name);
  const fullName     = `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim();

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  }, [navigate]);

  return (
    <div className="dash dash--pae">
      {/* Sidebar */}
      <aside className="dash__sidebar">
        <a href="/" className="dash__logo">
          <LogoIcon />
          <span className="dash__logo-text">BIGA</span>
        </a>

        <nav className="dash__nav" aria-label="Navegación">
          <div className="dash__nav-section">
            <p className="dash__nav-label">PAE</p>
            <NavItem id="pae-register" active={activeNav} icon={<ScanIcon />}      label="Registro PAE"   onClick={setActiveNav} pae />
            <NavItem id="pae-report"   active={activeNav} icon={<ChartIcon />}     label="Reporte diario" onClick={setActiveNav} pae />
            <NavItem id="pae-enrolled" active={activeNav} icon={<ListCheckIcon />} label="Matriculados"   onClick={setActiveNav} pae />
          </div>
          <div className="dash__nav-section">
            <p className="dash__nav-label">Aula</p>
            <NavItem id="attendance" active={activeNav} icon={<ClipboardIcon />} label="Asistencia"        onClick={setActiveNav} />
            <NavItem id="departures" active={activeNav} icon={<LogoutIcon />}    label="Salidas tempranas" onClick={setActiveNav} />
            <NavItem id="schedule"   active={activeNav} icon={<CalendarIcon />}  label="Horario"           onClick={setActiveNav} />
            <NavItem id="students"   active={activeNav} icon={<UsersIcon />}     label="Estudiantes"       onClick={setActiveNav} />
          </div>
          <div className="dash__nav-section">
            <p className="dash__nav-label">Seguimiento</p>
            <NavItem id="conduct"  active={activeNav} icon={<ShieldIcon />}  label="Convivencia" onClick={setActiveNav} />
            <NavItem id="history"  active={activeNav} icon={<BookIcon />}    label="Historial"   onClick={setActiveNav} />
            <NavItem id="messages" active={activeNav} icon={<MessageIcon />} label="Mensajes"    onClick={setActiveNav} />
          </div>
        </nav>

        <div className="dash__sidebar-footer">
          <div className="dash__user-card">
            <div className="dash__user-avatar">{userInitials || 'U'}</div>
            <div className="dash__user-info">
              <p className="dash__user-name">{fullName || 'Usuario'}</p>
              <p className="dash__user-role">Operario PAE</p>
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
          <span className="dash__page-badge dash__page-badge--pae">Operario PAE</span>
        </div>

        <main className="dash__content">
          {activeNav === 'pae-register' && <PAERegisterView />}
          {activeNav === 'pae-report'   && <PAEReportView />}
          {activeNav === 'pae-enrolled' && <PAEEnrolledView />}
          {activeNav === 'students'     && <StudentsView />}
          {activeNav === 'attendance'   && <AttendanceView />}
          {activeNav === 'departures'   && <DeparturesView />}
          {activeNav === 'schedule'     && <ScheduleView />}
          {activeNav === 'conduct'      && <ConvivenciaView />}
          {activeNav === 'history'      && <HistorialView />}
          {activeNav === 'messages'     && <MensajesView />}
        </main>
      </div>
    </div>
  );
}

/* ── PAE: Registro ───────────────────────────────────────────────── */
function PAERegisterView() {
  const [students, setStudents]     = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(null);
  const [query, setQuery]           = useState('');
  const [selected, setSelected]     = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [zoomed, setZoomed]         = useState(false);

  // Al abrir/cerrar/cambiar de estudiante, cerrar el zoom de la foto.
  useEffect(() => { setZoomed(false); }, [selected]);

  // Cerrar el zoom con la tecla Esc.
  useEffect(() => {
    if (!zoomed) return;
    const onKey = (e) => { if (e.key === 'Escape') setZoomed(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [zoomed]);
  const [toast, setToast]           = useState(null);
  const searchRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await paeService.listStudentsToday();
      setStudents(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const handleConfirmDelivery = useCallback(async () => {
    if (!selected) return;
    setConfirming(true);
    try {
      await paeService.registerDelivery(selected.student_id);
      setStudents(prev =>
        prev.map(s => s.student_id === selected.student_id ? { ...s, delivered: true } : s)
      );
      showToast(`Entrega registrada para ${selected.first_name} ${selected.last_name}`);
      setSelected(null);
    } catch (e) {
      if (e.status === 409) {
        showToast('Este estudiante ya recibió su entrega hoy.', 'error');
        setSelected(null);
      } else {
        showToast(e.message, 'error');
      }
    } finally {
      setConfirming(false);
    }
  }, [selected, showToast]);

  const enrolled = students.length;
  const delivered = students.filter(s => s.delivered).length;
  const pending   = enrolled - delivered;
  const pct       = enrolled > 0 ? Math.round(delivered / enrolled * 100) : 0;
  const pctPending = enrolled > 0 ? Math.round(pending / enrolled * 100) : 0;

  const filtered = students.filter(s => {
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    return (
      s.first_name.toLowerCase().includes(q) ||
      s.last_name.toLowerCase().includes(q) ||
      s.document_number.includes(q)
    );
  });

  if (loading) {
    return (
      <div className="dash__empty">
        <Spinner color="#059669" />
        <span>Cargando listado del día…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dash__empty">
        <AlertIcon color="#ef4444" />
        <span>{error}</span>
        <button className="btn--secondary" style={{ width: 'auto', marginTop: 8 }} onClick={load}>
          Reintentar
        </button>
      </div>
    );
  }

  return (
    <>
      {/* Toast */}
      {toast && (
        <div className={`dash__toast dash__toast--${toast.type}`} role="alert">
          {toast.type === 'success' ? <CheckIcon /> : <AlertIcon />}
          {toast.msg}
        </div>
      )}

      {/* Confirmation modal */}
      {selected && (
        <div className="dash__modal-overlay" onClick={() => !confirming && setSelected(null)}>
          <div className="dash__modal" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
            <button
              className="dash__modal-close"
              onClick={() => !confirming && setSelected(null)}
              aria-label="Cerrar"
              disabled={confirming}
            >
              <CloseIcon />
            </button>

            <p className="dash__modal-label">Confirmar entrega PAE</p>

            <div className="dash__modal-student">
              {selected.photo_url ? (
                <button
                  type="button"
                  className="dash__modal-photo-btn"
                  onClick={() => setZoomed(true)}
                  title="Ver foto ampliada"
                  aria-label="Ver foto ampliada"
                >
                  <img
                    className="dash__modal-photo"
                    src={selected.photo_url}
                    alt={`${selected.first_name} ${selected.last_name}`}
                  />
                  <span className="dash__modal-photo-zoom"><ZoomIcon /></span>
                </button>
              ) : (
                <div className="dash__modal-avatar">
                  {initials(selected.first_name, selected.last_name)}
                </div>
              )}
              <div className="dash__modal-info">
                <p className="dash__modal-name">{selected.first_name} {selected.last_name}</p>
                <p className="dash__modal-doc">Doc. {selected.document_number}</p>
              </div>
            </div>

            <p className="dash__modal-warning">
              Verifica que el estudiante frente a ti coincide con la foto antes de confirmar.
            </p>

            <div className="dash__modal-actions">
              <button
                className="btn--secondary"
                onClick={() => setSelected(null)}
                disabled={confirming}
              >
                Cancelar
              </button>
              <button
                className="btn--confirm"
                onClick={handleConfirmDelivery}
                disabled={confirming}
                aria-busy={confirming}
              >
                {confirming ? <><Spinner color="white" size={16} /> Registrando…</> : 'Confirmar entrega'}
              </button>
            </div>
          </div>
        </div>
      )}

      {selected && zoomed && selected.photo_url && (
        <div className="pae-lightbox" onClick={() => setZoomed(false)} role="dialog" aria-modal="true">
          <button className="pae-lightbox__close" onClick={() => setZoomed(false)} aria-label="Cerrar">
            <CloseIcon size={22} />
          </button>
          <img
            className="pae-lightbox__img"
            src={selected.photo_url}
            alt={`${selected.first_name} ${selected.last_name}`}
            onClick={e => e.stopPropagation()}
          />
          <p className="pae-lightbox__caption">{selected.first_name} {selected.last_name} · Doc. {selected.document_number}</p>
        </div>
      )}

      {/* Stat cards */}
      <div className="dash__stats">
        <StatCard icon={<ListCheckIcon />} value={enrolled}  label="Matriculados PAE"                                     pae />
        <StatCard icon={<CheckIcon />}     value={delivered} label="Reclamados hoy"   fill={pct}   delta={`${pct}%`}      pae />
        <StatCard icon={<AlertIcon />}     value={pending}   label="Sin reclamar"     fill={pctPending} delta={`${pctPending}%`} fillClass="red" pae />
      </div>

      {/* Search */}
      <div className="dash__search-wrap">
        <div className="dash__search-inner">
          <SearchIcon />
          <input
            ref={searchRef}
            className="dash__search"
            type="search"
            placeholder="Buscar por nombre o documento…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoComplete="off"
          />
          {query && (
            <button className="dash__search-clear" onClick={() => setQuery('')} aria-label="Limpiar búsqueda">
              <CloseIcon size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Student list */}
      <div className="dash__table-card">
        <div className="dash__table-header">
          <span className="dash__table-title">
            Listado del día
            {query && <span className="dash__table-count"> — {filtered.length} resultado{filtered.length !== 1 ? 's' : ''}</span>}
          </span>
        </div>

        {filtered.length === 0 ? (
          <div className="dash__empty" style={{ padding: '48px 20px' }}>
            {query ? <SearchIcon /> : <ListCheckIcon />}
            {query
              ? <span>Sin resultados para <strong>"{query}"</strong></span>
              : <span>No hay estudiantes inscritos en el PAE para hoy. Inscribilos desde <strong>Estudiantes</strong>.</span>}
          </div>
        ) : (
          <table className="dash__table">
            <thead>
              <tr>
                <th>Estudiante</th>
                <th>Documento</th>
                <th>Estado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s, i) => {
                const av = avatarFor(s.first_name, i);
                return (
                  <tr key={s.student_id}>
                    <td>
                      <div className="dash__table-student">
                        {s.photo_url ? (
                          <StudentPhoto src={s.photo_url} alt="" caption={`${s.first_name} ${s.last_name}`} />
                        ) : (
                          <div className="dash__student-avatar" style={{ background: av.bg, color: av.color, width: 32, height: 32, fontSize: '0.62rem' }}>
                            {initials(s.first_name, s.last_name)}
                          </div>
                        )}
                        <span className="dash__table-student-name">{s.first_name} {s.last_name}</span>
                      </div>
                    </td>
                    <td style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--t2)' }}>{s.document_number}</td>
                    <td>
                      {s.delivered
                        ? <span className="dash__badge dash__badge--green">Reclamado</span>
                        : <span className="dash__badge dash__badge--yellow">Pendiente</span>
                      }
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {!s.delivered && (
                        <button
                          className="dash__table-register-btn"
                          onClick={() => setSelected(s)}
                        >
                          Registrar entrega
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

/* ── PAE: Reporte ─────────────────────────────────────────────────── */
const WEEKDAY_LABELS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie'];

function PAEReportView() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  useEffect(() => {
    paeService.weeklyReport()
      .then(setReport)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="dash__empty"><Spinner color="#059669" /><span>Cargando reporte…</span></div>;
  if (error)   return <div className="dash__empty"><AlertIcon color="#ef4444" /><span>{error}</span></div>;

  const vals  = report.items.map(i => i.count);
  const max   = Math.max(...vals, 1);
  const total = report.total;
  const daysWithDeliveries = vals.filter(v => v > 0).length;
  const avg   = daysWithDeliveries > 0 ? Math.round(total / daysWithDeliveries) : 0;
  const best  = vals.reduce((acc, v, i) => v > vals[acc] ? i : acc, 0);

  return (
    <>
      <div className="dash__stats" style={{ marginBottom: 18 }}>
        <StatCard pae icon={<ChartIcon />} value={total} label="Entregas esta semana" fill={100} />
        <StatCard pae icon={<CheckIcon />} value={avg}   label="Promedio por día activo" fill={max > 0 ? avg / max * 100 : 0} />
        <StatCard pae icon={<ListCheckIcon />} value={total > 0 ? WEEKDAY_LABELS[best] : '—'} label="Día con más entregas" fill={total > 0 ? 100 : 0} />
      </div>

      <div className="dash__chart-card">
        <div className="dash__chart-header">
          <span className="dash__chart-title">Entregas por día</span>
          <span className="dash__chart-sub">Semana actual</span>
        </div>
        {total === 0 ? (
          <div className="dash__empty" style={{ padding: '32px 20px' }}>
            <ChartIcon />
            <span>Aún no hay entregas registradas esta semana.</span>
          </div>
        ) : (
          <div className="dash__hbars">
            {report.items.map((item, i) => {
              const pct = Math.round((item.count / max) * 100);
              return (
                <div className="dash__hbar-row" key={item.delivery_date}>
                  <span className="dash__hbar-day">{WEEKDAY_LABELS[i]}</span>
                  <div className="dash__hbar-track">
                    <div className="dash__hbar-fill" style={{ width: `${pct}%` }}>
                      <span className="dash__hbar-val">{item.count}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}

/* ── PAE: Matriculados ────────────────────────────────────────────── */
function PAEEnrolledView() {
  const [students, setStudents] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  useEffect(() => {
    paeService.listStudentsToday()
      .then(setStudents)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="dash__empty"><Spinner color="#059669" /><span>Cargando…</span></div>;
  if (error)   return <div className="dash__empty"><AlertIcon color="#ef4444" /><span>{error}</span></div>;

  return (
    <div className="dash__table-card">
      <div className="dash__table-header">
        <span className="dash__table-title">Estudiantes matriculados en PAE</span>
        <span className="dash__table-count" style={{ fontSize: '0.75rem', color: 'var(--t3)' }}>{students.length} estudiantes</span>
      </div>
      <table className="dash__table">
        <thead>
          <tr><th>Estudiante</th><th>Documento</th><th>Estado hoy</th></tr>
        </thead>
        <tbody>
          {students.map((s, i) => {
            const av = avatarFor(s.first_name, i);
            return (
              <tr key={s.student_id}>
                <td>
                  <div className="dash__table-student">
                    {s.photo_url ? (
                      <StudentPhoto src={s.photo_url} alt="" caption={`${s.first_name} ${s.last_name}`} />
                    ) : (
                      <div className="dash__student-avatar" style={{ background: av.bg, color: av.color, width: 32, height: 32, fontSize: '0.62rem' }}>
                        {initials(s.first_name, s.last_name)}
                      </div>
                    )}
                    <span className="dash__table-student-name">{s.first_name} {s.last_name}</span>
                  </div>
                </td>
                <td style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--t2)' }}>{s.document_number}</td>
                <td>
                  {s.delivered
                    ? <span className="dash__badge dash__badge--green">Reclamado</span>
                    : <span className="dash__badge dash__badge--yellow">Pendiente</span>
                  }
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ── Estudiantes: registro + inscripción PAE ──────────────────────── */
const EMPTY_FORM = { document_number: '', first_name: '', last_name: '', birth_date: '' };

export function StudentsView() {
  const [students, setStudents]   = useState([]);
  const [enrolledIds, setEnrolled] = useState(new Set());
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const [query, setQuery]         = useState('');
  const [showForm, setShowForm]   = useState(false);
  const [form, setForm]           = useState(EMPTY_FORM);
  const [photoFile, setPhotoFile] = useState(null);
  const [saving, setSaving]       = useState(false);
  const [formError, setFormError] = useState(null);
  const [enrollingId, setEnrollingId] = useState(null);
  const [toast, setToast]         = useState(null);

  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [all, enrolled] = await Promise.all([
        studentService.list(),
        paeService.listStudentsToday(),
      ]);
      setStudents(all);
      setEnrolled(new Set(enrolled.map(s => s.student_id)));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const updateField = (field) => (e) => setForm(prev => ({ ...prev, [field]: e.target.value }));

  const closeForm = useCallback(() => {
    if (saving) return;
    setShowForm(false);
    setForm(EMPTY_FORM);
    setPhotoFile(null);
    setFormError(null);
  }, [saving]);

  const handleCreate = useCallback(async (e) => {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    try {
      let created = await studentService.create(form);
      // Si se eligió foto, se sube a MinIO y se usa el estudiante con la URL presignada.
      if (photoFile) {
        try {
          created = await studentService.uploadPhoto(created.id, photoFile);
        } catch {
          showToast('Estudiante creado, pero la foto no se pudo subir.', 'error');
        }
      }
      setStudents(prev => [...prev, created].sort((a, b) =>
        `${a.last_name} ${a.first_name}`.localeCompare(`${b.last_name} ${b.first_name}`)
      ));
      showToast(`Estudiante ${created.first_name} ${created.last_name} registrado`);
      setShowForm(false);
      setForm(EMPTY_FORM);
      setPhotoFile(null);
    } catch (err) {
      setFormError(err.status === 409
        ? 'Ya existe un estudiante con este documento.'
        : err.message);
    } finally {
      setSaving(false);
    }
  }, [form, photoFile, showToast]);

  const handleEnroll = useCallback(async (student) => {
    setEnrollingId(student.id);
    try {
      await paeService.enrollStudent(student.id);
      setEnrolled(prev => new Set(prev).add(student.id));
      showToast(`${student.first_name} ${student.last_name} inscrito en el PAE`);
    } catch (err) {
      showToast(err.status === 409
        ? 'El estudiante ya está inscrito en el PAE este año.'
        : err.message, 'error');
      if (err.status === 409) setEnrolled(prev => new Set(prev).add(student.id));
    } finally {
      setEnrollingId(null);
    }
  }, [showToast]);

  if (loading) return <div className="dash__empty"><Spinner color="#059669" /><span>Cargando estudiantes…</span></div>;
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
    return (
      s.first_name.toLowerCase().includes(q) ||
      s.last_name.toLowerCase().includes(q) ||
      s.document_number.includes(q)
    );
  });

  return (
    <>
      {toast && (
        <div className={`dash__toast dash__toast--${toast.type}`} role="alert">
          {toast.type === 'success' ? <CheckIcon /> : <AlertIcon />}
          {toast.msg}
        </div>
      )}

      {showForm && (
        <div className="dash__modal-overlay" onClick={closeForm}>
          <form className="dash__modal dash__modal--form" onClick={e => e.stopPropagation()} onSubmit={handleCreate} role="dialog" aria-modal="true">
            <button type="button" className="dash__modal-close" onClick={closeForm} aria-label="Cerrar" disabled={saving}>
              <CloseIcon />
            </button>
            <p className="dash__modal-label">Registrar estudiante</p>

            <div className="dash__form-grid">
              <label className="dash__field">
                <span className="dash__field-label">Documento</span>
                <input className="dash__field-input" value={form.document_number} onChange={updateField('document_number')}
                  required minLength={3} maxLength={20} autoComplete="off" inputMode="numeric" />
              </label>
              <label className="dash__field">
                <span className="dash__field-label">Fecha de nacimiento</span>
                <input className="dash__field-input" type="date" value={form.birth_date} onChange={updateField('birth_date')}
                  required max={new Date().toISOString().slice(0, 10)} />
              </label>
              <label className="dash__field">
                <span className="dash__field-label">Nombres</span>
                <input className="dash__field-input" value={form.first_name} onChange={updateField('first_name')}
                  required maxLength={100} autoComplete="off" />
              </label>
              <label className="dash__field">
                <span className="dash__field-label">Apellidos</span>
                <input className="dash__field-input" value={form.last_name} onChange={updateField('last_name')}
                  required maxLength={100} autoComplete="off" />
              </label>
              <label className="dash__field dash__field--full">
                <span className="dash__field-label">Foto del estudiante <span className="dash__field-optional">(opcional)</span></span>
                <input className="dash__field-input" type="file" accept="image/jpeg,image/png,image/webp"
                  onChange={e => setPhotoFile(e.target.files?.[0] ?? null)} />
                {photoFile && <span className="dash__field-optional" style={{ marginTop: 4 }}>{photoFile.name}</span>}
              </label>
            </div>

            {formError && <p className="dash__form-error" role="alert">{formError}</p>}

            <div className="dash__modal-actions">
              <button type="button" className="btn--secondary" onClick={closeForm} disabled={saving}>Cancelar</button>
              <button type="submit" className="btn--confirm" disabled={saving} aria-busy={saving}>
                {saving ? <><Spinner color="white" size={16} /> Guardando…</> : 'Registrar'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="dash__search-wrap" style={{ display: 'flex', gap: 12 }}>
        <div className="dash__search-inner" style={{ flex: 1 }}>
          <SearchIcon />
          <input className="dash__search" type="search" placeholder="Buscar por nombre o documento…"
            value={query} onChange={e => setQuery(e.target.value)} autoComplete="off" />
          {query && (
            <button className="dash__search-clear" onClick={() => setQuery('')} aria-label="Limpiar búsqueda">
              <CloseIcon size={14} />
            </button>
          )}
        </div>
        <button className="btn--confirm" style={{ flex: '0 0 auto', whiteSpace: 'nowrap' }} onClick={() => setShowForm(true)}>
          + Registrar estudiante
        </button>
      </div>

      <div className="dash__table-card">
        <div className="dash__table-header">
          <span className="dash__table-title">
            Estudiantes de la institución
            <span className="dash__table-count"> — {filtered.length}</span>
          </span>
        </div>

        {filtered.length === 0 ? (
          <div className="dash__empty" style={{ padding: '48px 20px' }}>
            <UsersIcon />
            <span>{students.length === 0 ? 'Aún no hay estudiantes registrados.' : `Sin resultados para "${query}"`}</span>
          </div>
        ) : (
          <table className="dash__table">
            <thead>
              <tr><th>Estudiante</th><th>Documento</th><th>PAE</th><th></th></tr>
            </thead>
            <tbody>
              {filtered.map((s, i) => {
                const av = avatarFor(s.first_name, i);
                const enrolled = enrolledIds.has(s.id);
                return (
                  <tr key={s.id}>
                    <td>
                      <div className="dash__table-student">
                        {s.photo_url ? (
                          <StudentPhoto src={s.photo_url} alt="" caption={`${s.first_name} ${s.last_name}`} />
                        ) : (
                          <div className="dash__student-avatar" style={{ background: av.bg, color: av.color, width: 32, height: 32, fontSize: '0.62rem' }}>
                            {initials(s.first_name, s.last_name)}
                          </div>
                        )}
                        <span className="dash__table-student-name">{s.first_name} {s.last_name}</span>
                      </div>
                    </td>
                    <td style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--t2)' }}>{s.document_number}</td>
                    <td>
                      {enrolled
                        ? <span className="dash__badge dash__badge--green">Inscrito</span>
                        : <span className="dash__badge dash__badge--yellow">No inscrito</span>}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {!enrolled && (
                        <button className="dash__table-register-btn" onClick={() => handleEnroll(s)}
                          disabled={enrollingId === s.id} aria-busy={enrollingId === s.id}>
                          {enrollingId === s.id ? 'Inscribiendo…' : 'Inscribir en PAE'}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

/* ── Reusable ─────────────────────────────────────────────────────── */
function StatCard({ icon, value, label, fill, fillClass, delta, pae }) {
  return (
    <div className="dash__stat-card">
      <div className={`dash__stat-icon${pae ? ' dash__stat-icon--pae' : ''}`}>{icon}</div>
      <p className="dash__stat-value">{value}</p>
      <p className="dash__stat-label">{label}</p>
      {delta && <p className={`dash__stat-delta${fillClass ? ` dash__stat-delta--${fillClass}` : ''}`}>{delta}</p>}
      {fill != null && (
        <div className="dash__stat-bar">
          <div
            className={`dash__stat-bar-fill${pae ? ' dash__stat-bar-fill--pae' : ''}${fillClass ? ` dash__stat-bar-fill--${fillClass}` : ''}`}
            style={{ width: `${fill}%` }}
          />
        </div>
      )}
    </div>
  );
}

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

/* ── Icons ────────────────────────────────────────────────────────── */
function LogoIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 100 100" aria-hidden="true" style={{ flexShrink: 0 }}>
      <defs>
        <radialGradient id="p-p2" cx="38%" cy="28%" r="70%">
          <stop offset="0%" stopColor="#9B3FF5"/><stop offset="100%" stopColor="#4A0A9E"/>
        </radialGradient>
        <radialGradient id="p-g2" cx="33%" cy="28%" r="68%">
          <stop offset="0%" stopColor="#D4F870"/><stop offset="100%" stopColor="#2E7008"/>
        </radialGradient>
      </defs>
      <circle cx="50" cy="52" r="44" fill="url(#p-p2)"/>
      <path d="M50,24 L74,68 L26,68 Z" fill="white" stroke="white" strokeWidth="10" strokeLinejoin="round" strokeLinecap="round"/>
      <circle cx="50" cy="11" r="11" fill="url(#p-g2)"/>
      <circle cx="80" cy="70" r="11" fill="url(#p-g2)"/>
      <circle cx="20" cy="70" r="11" fill="url(#p-g2)"/>
    </svg>
  );
}
function ScanIcon({ size = 18 })      { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7V5a2 2 0 012-2h2M17 3h2a2 2 0 012 2v2M21 17v2a2 2 0 01-2 2h-2M7 21H5a2 2 0 01-2-2v-2"/><rect x="7" y="7" width="10" height="10" rx="1"/></svg>; }
function ChartIcon({ size = 18 })     { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>; }
function ListCheckIcon({ size = 18 }) { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>; }
function ClipboardIcon()              { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="12" y2="16"/></svg>; }
function UsersIcon({ color = 'currentColor' })    { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>; }
function CalendarIcon()               { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>; }
function ShieldIcon()                 { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>; }
function BookIcon()                    { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>; }
function MessageIcon()                { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>; }
function LogoutIcon()                 { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>; }
function CheckIcon({ color = 'currentColor' })    { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>; }
function AlertIcon({ color = 'currentColor' })    { return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>; }
function SearchIcon()                 { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>; }
function CloseIcon({ size = 18 })     { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>; }
function ZoomIcon({ size = 14 })      { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>; }
function Spinner({ color = '#059669', size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" className="dash__spinner">
      <circle cx="12" cy="12" r="10" stroke="rgba(0,0,0,0.1)" strokeWidth="2.5"/>
      <path d="M12 2a10 10 0 0110 10" stroke={color} strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  );
}
