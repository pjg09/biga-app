import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminService } from '../services/admin';
import { studentService } from '../services/students';
import { StudentsView } from './PAEDashboard';
import { StudentPhoto } from './TeacherDashboard';
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

  useEffect(() => { document.title = 'BIGA - Administración'; }, []);
  const fullName = `${user.first_name ?? ''} ${user.last_name ?? ''}`.trim();
  const [activeNav, setActiveNav] = useState('overview');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Cierra el cajón móvil al navegar entre secciones sin tocar cada NavItem.
  useEffect(() => { setSidebarOpen(false); }, [activeNav]);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  }, [navigate]);

  return (
    <div className="dash dash--admin">
      {sidebarOpen && <div className="dash__sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      <aside className={`dash__sidebar${sidebarOpen ? ' dash__sidebar--open' : ''}`}>
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
// Sin `password`: el admin no fija contraseñas. Al crear, el backend genera una
// temporal y se la envía por correo al interesado; para cambiarla está
// `/recuperar`. Ver `docs/admin.md`.
const EMPTY_STAFF_FORM = { first_name: '', last_name: '', document_number: '', email: '', role: 'TEACHER' };

function StaffView() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_STAFF_FORM);
  const [saving, setSaving] = useState(false);
  const { toast, showToast } = useToast();

  const [photoFile, setPhotoFile] = useState(null);
  const [photoPreview, setPhotoPreview] = useState(null);
  const photoInputRef = useRef(null);

  // Object URL del preview: se crea al elegir archivo y se revoca al cambiar/
  // quitar la foto o desmontar, para no acumular URLs sin liberar.
  useEffect(() => {
    if (!photoFile) { setPhotoPreview(null); return; }
    const url = URL.createObjectURL(photoFile);
    setPhotoPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photoFile]);

  // Vacía también el input nativo: conserva el archivo internamente y volver a
  // elegir EL MISMO no dispararía `change`, así que "Quitar" parecería roto.
  const clearPhoto = useCallback(() => {
    setPhotoFile(null);
    if (photoInputRef.current) photoInputRef.current.value = '';
  }, []);

  const [query, setQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('');

  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);

  const [includeInactive, setIncludeInactive] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setUsers(await adminService.listUsers({ includeInactive })); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [includeInactive]);
  useEffect(() => { load(); }, [load]);

  const upd = (f) => (e) => setForm(p => ({ ...p, [f]: e.target.value }));

  const openCreate = useCallback(() => {
    setEditingId(null);
    setForm(EMPTY_STAFF_FORM);
    setPhotoFile(null);
    setShowForm(true);
  }, []);

  const openEdit = useCallback((u) => {
    setEditingId(u.id);
    setForm({
      first_name: u.first_name, last_name: u.last_name, document_number: u.document_number,
      email: u.email, role: u.role,
    });
    setPhotoFile(null);
    setSelectedId(null);
    setDetail(null);
    setShowForm(true);
  }, []);

  const closeForm = useCallback(() => {
    if (saving) return;
    setShowForm(false);
    setEditingId(null);
    setForm(EMPTY_STAFF_FORM);
    setPhotoFile(null);
  }, [saving]);

  const openDetail = useCallback(async (id) => {
    setSelectedId(id);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    try {
      setDetail(await adminService.getUserDetail(id));
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
  }, []);

  const submit = useCallback(async (e) => {
    e.preventDefault();
    setSaving(true);
    const isEditing = Boolean(editingId);
    try {
      const payload = {
        first_name: form.first_name, last_name: form.last_name,
        document_number: form.document_number, email: form.email, role: form.role,
      };
      let saved = isEditing
        ? await adminService.updateUser(editingId, payload)
        : await adminService.createUser(payload);
      // La foto va en una segunda petición (multipart) porque el alta es JSON.
      // Si falla, el usuario ya quedó guardado: se avisa sin perder el alta.
      let photoFailed = false;
      if (photoFile) {
        try {
          saved = await adminService.uploadUserPhoto(saved.id, photoFile);
        } catch {
          photoFailed = true;
        }
      }
      showToast(
        photoFailed
          ? `${saved.first_name} ${saved.last_name} ${isEditing ? 'actualizado' : 'creado'}, pero la foto no se pudo subir`
          : `${saved.first_name} ${saved.last_name} ${isEditing ? 'actualizado' : 'creado'}`,
        photoFailed ? 'error' : undefined,
      );
      setShowForm(false);
      setEditingId(null);
      setForm(EMPTY_STAFF_FORM);
      setPhotoFile(null);
      await load();
    } catch (err) {
      showToast(err.message, 'error');
    } finally { setSaving(false); }
  }, [form, editingId, photoFile, showToast, load]);

  // Baja lógica. El backend rechaza con 409 desactivarse a uno mismo; ese
  // mensaje se muestra tal cual en vez de inventar uno propio.
  const doDeactivate = async () => {
    setSaving(true);
    try {
      await adminService.deactivateUser(editingId);
      showToast(`${form.first_name} ${form.last_name} eliminado del panel`);
      setConfirmDelete(false);
      setShowForm(false);
      setEditingId(null);
      setForm(EMPTY_STAFF_FORM);
      setPhotoFile(null);
      await load();
    } catch (err) {
      showToast(err.message, 'error');
    } finally { setSaving(false); }
  };

  const doReactivate = async (u) => {
    try {
      await adminService.reactivateUser(u.id);
      showToast(`${u.first_name} ${u.last_name} reactivado`);
      closeDetail();
      await load();
    } catch (err) { showToast(err.message, 'error'); }
  };

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando personal…</span></div>;
  if (error) return <div className="dash__empty"><AlertIcon color="#ef4444" /><span>{error}</span></div>;

  const filtered = users.filter(u => {
    if (query.trim()) {
      const q = query.toLowerCase();
      const matches = u.first_name.toLowerCase().includes(q)
        || u.last_name.toLowerCase().includes(q)
        || u.document_number.includes(q)
        || u.email.toLowerCase().includes(q);
      if (!matches) return false;
    }
    if (roleFilter && u.role !== roleFilter) return false;
    return true;
  });
  const hasFilters = Boolean(query.trim() || roleFilter);

  return (
    <>
      <Toast toast={toast} />

      <div className="dash__search-wrap dash__search-wrap--btn">
        <div className="dash__search-inner" style={{ flex: 1 }}>
          <SearchIcon />
          <input className="dash__search" type="search" placeholder="Buscar por nombre, documento o correo…"
            value={query} onChange={e => setQuery(e.target.value)} autoComplete="off" />
          {query && (
            <button className="dash__search-clear" onClick={() => setQuery('')} aria-label="Limpiar búsqueda">
              <CloseIcon size={14} />
            </button>
          )}
        </div>
        <select className="dash__field-input" style={{ width: 'auto', flex: '0 0 170px' }}
          value={roleFilter} onChange={e => setRoleFilter(e.target.value)}>
          <option value="">Todos los roles</option>
          <option value="TEACHER">Docente</option>
          <option value="PAE_OPERATOR">Operador PAE</option>
          <option value="ADMIN">Administrador</option>
        </select>
        <label className="dash__inactive-toggle">
          <input type="checkbox" checked={includeInactive}
            onChange={e => setIncludeInactive(e.target.checked)} />
          Ver inactivos
        </label>
        <button className="btn--confirm dash__search-btn" onClick={openCreate}>
          + Agregar miembro del personal
        </button>
      </div>

      <div className="card dash__list-card">
        <div className="dash__list-header"><span className="dash__list-title">Personal de la institución</span><span className="dash__student-group">{filtered.length}</span></div>
        {filtered.length === 0 ? (
          <div className="dash__empty" style={{ padding: '32px 20px' }}>
            <UsersIcon />
            <span>{users.length === 0 ? 'Aún no hay personal registrado.' : hasFilters ? 'Sin resultados para ese criterio.' : 'Sin personal.'}</span>
          </div>
        ) : filtered.map((u, i) => (
          <button type="button" className={`dash__student-row att-class-row stu-row${u.is_active ? '' : ' stu-row--inactive'}`} key={u.id} onClick={() => openDetail(u.id)}>
            <span className="stu-row__detail-icon" aria-hidden="true"><EyeIcon /></span>
            {u.photo_url
              ? <StudentPhoto src={u.photo_url} alt="" caption={`${u.first_name} ${u.last_name}`} className="dash__student-avatar" />
              : <div className="dash__student-avatar" style={{ background: '#e0e7ff', color: '#4f46e5' }}>{initials(u.first_name, u.last_name)}</div>}
            <div className="dash__student-info">
              <p className="dash__student-name">{u.first_name} {u.last_name}</p>
              <p className="dash__student-group">{u.email}</p>
            </div>
            <div className="att-class-row__badges">
              {!u.is_active && <span className="dash__badge dash__badge--red">Inactivo</span>}
              <span className={`dash__badge dash__badge--${ROLE_CLASS[u.role]}`}>{ROLE_LABEL[u.role]}</span>
            </div>
          </button>
        ))}
      </div>

      {showForm && (
        <div className="dash__modal-overlay" onClick={closeForm}>
          <form className="dash__modal dash__modal--form" onClick={e => e.stopPropagation()} onSubmit={submit} role="dialog" aria-modal="true">
            <button type="button" className="dash__modal-close" onClick={closeForm} aria-label="Cerrar" disabled={saving}>
              <CloseIcon />
            </button>
            <p className="dash__modal-label">{editingId ? 'Editar miembro del personal' : 'Agregar miembro del personal'}</p>

            <div className="dash__form-grid">
              <label className="dash__field">
                <span className="dash__field-label">Nombres</span>
                <input className="dash__field-input" value={form.first_name} onChange={upd('first_name')} required maxLength={100} autoComplete="off" />
              </label>
              <label className="dash__field">
                <span className="dash__field-label">Apellidos</span>
                <input className="dash__field-input" value={form.last_name} onChange={upd('last_name')} required maxLength={100} autoComplete="off" />
              </label>
              <label className="dash__field">
                <span className="dash__field-label">Documento</span>
                <input className="dash__field-input" value={form.document_number} onChange={upd('document_number')} required minLength={3} maxLength={20} autoComplete="off" />
              </label>
              <label className="dash__field">
                <span className="dash__field-label">Correo</span>
                <input className="dash__field-input" type="email" value={form.email} onChange={upd('email')} required autoComplete="off" />
              </label>
              <label className="dash__field">
                <span className="dash__field-label">Rol</span>
                <select className="dash__field-input" value={form.role} onChange={upd('role')}>
                  <option value="TEACHER">Docente</option>
                  <option value="PAE_OPERATOR">Operador PAE</option>
                  <option value="ADMIN">Administrador</option>
                </select>
              </label>
              <label className="dash__field dash__field--full">
                <span className="dash__field-label">Foto <span className="dash__field-optional">(opcional)</span></span>
                <span className="dash__file-pick">
                  <input ref={photoInputRef} type="file" accept="image/jpeg,image/png,image/webp"
                    onChange={e => setPhotoFile(e.target.files?.[0] ?? null)} />
                  <span className="dash__file-pick__btn">Examinar</span>
                  {!photoFile && <span className="dash__file-pick__name">Ningún archivo seleccionado</span>}
                </span>
                {/* Guarda sobre `photoFile` y no solo sobre `photoPreview`: el
                    preview se calcula en un useEffect, que corre DESPUÉS del
                    render, así que al pulsar "Quitar" `photoFile` ya es null
                    mientras `photoPreview` aún tiene la URL vieja. */}
                {photoFile && photoPreview && (
                  <div className="dash__field-photo-preview">
                    <img src={photoPreview} alt="" />
                    <span className="dash__field-optional">{photoFile.name}</span>
                    <button type="button" className="dash__guardian-remove" onClick={clearPhoto}>
                      Quitar
                    </button>
                  </div>
                )}
              </label>
            </div>

            {!editingId && (
              <p className="dash__form-hint">
                No se pide contraseña: al crear la cuenta se envía una temporal al correo
                indicado, y la persona la cambia desde «¿Olvidaste tu contraseña?».
              </p>
            )}

            <div className="dash__modal-actions">
              {/* Solo al editar: no hay nada que dar de baja mientras se crea. */}
              {editingId && (
                <button type="button" className="btn--danger" onClick={() => setConfirmDelete(true)} disabled={saving}>
                  Eliminar
                </button>
              )}
              <button type="button" className="btn--secondary" onClick={closeForm} disabled={saving}>Cancelar</button>
              <button type="submit" className="btn--confirm" disabled={saving} aria-busy={saving}>
                {saving ? <><Spinner color="white" size={16} /> Guardando…</> : editingId ? 'Guardar cambios' : 'Crear usuario'}
              </button>
            </div>
          </form>
        </div>
      )}

      {confirmDelete && (
        <div className="dash__modal-overlay" onClick={() => setConfirmDelete(false)}>
          <div className="dash__modal dash__modal--sm" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
            <p className="dash__modal-label">Eliminar del panel</p>
            <p className="dash__modal-warning">
              <strong>{form.first_name} {form.last_name}</strong> dejará de aparecer en el panel y
              perderá el acceso a BIGA de inmediato, aunque tenga la sesión abierta.
              <br /><br />
              No se borra nada: su historial de convivencia, asistencia y PAE se conserva intacto.
              Puedes revertirlo marcando «Ver inactivos» en la lista.
            </p>
            <div className="dash__modal-actions">
              <button type="button" className="btn--secondary" onClick={() => setConfirmDelete(false)} disabled={saving}>
                Cancelar
              </button>
              <button type="button" className="btn--danger" onClick={doDeactivate} disabled={saving} aria-busy={saving}>
                {saving ? <><Spinner color="white" size={16} /> Eliminando…</> : 'Sí, eliminar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedId && (
        <div className="dash__modal-overlay" onClick={closeDetail}>
          <div className="dash__modal" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
            <button className="dash__modal-close" onClick={closeDetail} aria-label="Cerrar"><CloseIcon /></button>
            <p className="dash__modal-label">Ficha del personal</p>

            {detailLoading ? (
              <div className="dash__empty" style={{ padding: '24px 0' }}><Spinner /><span>Cargando…</span></div>
            ) : detailError ? (
              <div className="dash__empty" style={{ padding: '24px 0' }}><AlertIcon color="#ef4444" /><span>{detailError}</span></div>
            ) : detail && (
              <>
                <div className="dash__modal-student">
                  {detail.photo_url
                    ? <StudentPhoto src={detail.photo_url} alt="" caption={`${detail.first_name} ${detail.last_name}`} className="dash__modal-avatar" />
                    : <div className="dash__modal-avatar" style={{ background: '#e0e7ff', color: '#4f46e5' }}>
                        {initials(detail.first_name, detail.last_name)}
                      </div>}
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
                    <span className="dash__field-label">Correo</span>
                    <span className="dash__student-group">{detail.email}</span>
                  </div>
                  <div className="stu-detail__item">
                    <span className="dash__field-label">Rol</span>
                    <span className={`dash__badge dash__badge--${ROLE_CLASS[detail.role]}`} style={{ marginTop: 2 }}>
                      {ROLE_LABEL[detail.role]}
                    </span>
                  </div>
                </div>

                <div className="dash__modal-actions">
                  <button type="button" className="btn--secondary" onClick={closeDetail}>Cerrar</button>
                  {/* La vía de vuelta de una baja: solo aparece si está inactivo. */}
                  {detail.is_active
                    ? <button type="button" className="btn--confirm" onClick={() => openEdit(detail)}>Editar</button>
                    : <button type="button" className="btn--confirm" onClick={() => doReactivate(detail)}>Reactivar</button>}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

/* ── Académico ────────────────────────────────────────────────────
   Dos sub-secciones: Salones (gestión completa: ver por grado, crear, y meter
   o sacar estudiantes) y Materias. Los grados NO se crean acá: son un catálogo
   fijo de 11 niveles sembrado en la BD (ver api/app/core/grades.py). */
function AcademicView() {
  const [tab, setTab] = useState('salones');
  return (
    <>
      <div className="adm-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'salones'}
          className={`adm-tab${tab === 'salones' ? ' adm-tab--active' : ''}`}
          onClick={() => setTab('salones')}>Salones</button>
        <button type="button" role="tab" aria-selected={tab === 'materias'}
          className={`adm-tab${tab === 'materias' ? ' adm-tab--active' : ''}`}
          onClick={() => setTab('materias')}>Materias</button>
      </div>
      {tab === 'salones' ? <SalonesView /> : <MateriasView />}
    </>
  );
}

/* ── Académico › Salones ─────────────────────────────────────────
   Un bloque por grado con sus salones como tarjetas. Se muestran los 11
   grados aunque estén vacíos: el admin necesita ver dónde falta crear salón,
   no solo lo que ya existe. */
function SalonesView() {
  const [grades, setGrades] = useState([]);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const { toast, showToast } = useToast();

  const [creating, setCreating] = useState(null);   // { grade_id, name }
  const [saving, setSaving] = useState(false);
  const [openGroup, setOpenGroup] = useState(null); // salón abierto en el panel

  const load = useCallback(async () => {
    try {
      const [g, gr] = await Promise.all([adminService.listGrades(), adminService.listGroups()]);
      setGrades(g); setGroups(gr);
    } catch (e) { showToast(e.message, 'error'); }
    finally { setLoading(false); }
  }, [showToast]);
  useEffect(() => { load(); }, [load]);

  const submitGroup = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await adminService.createGroup({
        grade_id: creating.grade_id, name: creating.name.trim(), academic_year: YEAR,
      });
      showToast(`Salón ${creating.name.trim().toUpperCase()} creado`);
      setCreating(null);
      await load();
    } catch (err) {
      showToast(err.status === 409 ? 'Ya existe un salón con ese nombre en el grado' : err.message, 'error');
    } finally { setSaving(false); }
  };

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando salones…</span></div>;

  const totalSalones = groups.length;
  const totalEstudiantes = groups.reduce((n, g) => n + (g.student_count ?? 0), 0);

  return (
    <>
      <Toast toast={toast} />

      <div className="sal-summary">
        <span><strong>{totalSalones}</strong> {totalSalones === 1 ? 'salón' : 'salones'}</span>
        <span className="sal-summary__dot">·</span>
        <span><strong>{totalEstudiantes}</strong> {totalEstudiantes === 1 ? 'estudiante matriculado' : 'estudiantes matriculados'}</span>
        <span className="sal-summary__year">Año {YEAR}</span>
      </div>

      <div className="sal-grades">
        {grades.map(gr => {
          const salones = groups.filter(g => g.grade_id === gr.id);
          const est = salones.reduce((n, s) => n + (s.student_count ?? 0), 0);
          return (
            <section className={`card sal-grade${salones.length === 0 ? ' sal-grade--empty' : ''}`} key={gr.id}>
              <div className="sal-grade__head">
                <div>
                  <p className="sal-grade__name">{gr.name}</p>
                  <p className="sal-grade__meta">
                    {salones.length === 0
                      ? 'Sin salones'
                      : `${salones.length} ${salones.length === 1 ? 'salón' : 'salones'} · ${est} ${est === 1 ? 'estudiante' : 'estudiantes'}`}
                  </p>
                </div>
                <button type="button" className="sal-grade__add"
                  onClick={() => setCreating({ grade_id: gr.id, name: '' })}>
                  + Salón
                </button>
              </div>

              {salones.length > 0 && (
                <div className="sal-cards">
                  {salones.map(s => (
                    <button type="button" className="sal-card" key={s.id} onClick={() => setOpenGroup(s)}>
                      <span className="sal-card__name">{gr.name} {s.name}</span>
                      <span className="sal-card__count">
                        {s.student_count} {s.student_count === 1 ? 'estudiante' : 'estudiantes'}
                      </span>
                      <span className="sal-card__year">{s.academic_year}</span>
                    </button>
                  ))}
                </div>
              )}
            </section>
          );
        })}
      </div>

      {creating && (
        <div className="dash__modal-overlay" onClick={() => !saving && setCreating(null)}>
          <form className="dash__modal dash__modal--sm" onSubmit={submitGroup}
            onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
            <p className="dash__modal-label">
              Crear salón · {grades.find(g => g.id === creating.grade_id)?.name}
            </p>
            <Field label="Nombre del salón">
              <input className="dash__field-input" autoFocus required maxLength={10}
                placeholder="A" value={creating.name}
                onChange={e => setCreating(p => ({ ...p, name: e.target.value }))} />
            </Field>
            <p className="dash__form-hint">Se crea para el año académico {YEAR}.</p>
            <div className="dash__modal-actions">
              <button type="button" className="btn--secondary" onClick={() => setCreating(null)} disabled={saving}>
                Cancelar
              </button>
              <button type="submit" className="btn--confirm" disabled={saving} aria-busy={saving}>
                {saving ? <><Spinner color="white" size={16} /> Creando…</> : 'Crear salón'}
              </button>
            </div>
          </form>
        </div>
      )}

      {openGroup && (
        <SalonRoster
          group={openGroup}
          onClose={() => setOpenGroup(null)}
          onChanged={load}
          onRenamed={setOpenGroup}
          showToast={showToast}
        />
      )}
    </>
  );
}

/* Salón actual de un resultado de búsqueda ("Once A"), o null si no tiene.
   Lo usan el dropdown (para avisar) y `add` (para decidir si confirma). */
function salonDe(s) {
  return s.group_name ? `${s.grade_name} ${s.group_name}` : null;
}

/* Panel de un salón: lista de matriculados y buscador para agregar.
   Agregar a alguien que ya está en otro salón lo MUEVE (student_groups es
   único por estudiante y año) — se avisa antes en el propio resultado. */
function SalonRoster({ group, onClose, onChanged, onRenamed, showToast }) {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [confirmMove, setConfirmMove] = useState(null); // estudiante a trasladar
  const [renaming, setRenaming] = useState(null); // nombre nuevo en edición

  const label = `${group.grade_name} ${group.name}`;

  const loadRoster = useCallback(async () => {
    setLoading(true);
    try { setStudents(await studentService.list({ groupId: group.id })); }
    catch (e) { showToast(e.message, 'error'); }
    finally { setLoading(false); }
  }, [group.id, showToast]);
  useEffect(() => { loadRoster(); }, [loadRoster]);

  useEffect(() => {
    if (q.trim().length < 2) { setResults([]); return; }
    let active = true;
    const t = setTimeout(async () => {
      try { const r = await studentService.search(q.trim()); if (active) setResults(r); } catch { /* */ }
    }, 250);
    return () => { active = false; clearTimeout(t); };
  }, [q]);

  const doAdd = async (s) => {
    setBusy(true);
    try {
      await adminService.addStudentToGroup(group.id, s.id);
      showToast(`${s.full_name} → ${label}`);
      setQ(''); setResults([]);
      setConfirmMove(null);
      await loadRoster();
      await onChanged();
    } catch (err) {
      showToast(err.status === 409 ? `${s.full_name} ya está en este salón` : err.message, 'error');
    } finally { setBusy(false); }
  };

  const doRename = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const updated = await adminService.renameGroup(group.id, renaming);
      showToast(`Salón renombrado a ${group.grade_name} ${updated.name}`);
      setRenaming(null);
      // El panel sigue abierto: hay que refrescar su propio título además de
      // la lista de atrás. Se fusiona sobre `group` para no perder
      // `student_count`, que el PUT no recalcula.
      onRenamed({ ...group, name: updated.name });
      await onChanged();
    } catch (err) {
      showToast(err.status === 409 ? `Ya existe un salón «${renaming}» en ${group.grade_name}` : err.message, 'error');
    } finally { setBusy(false); }
  };

  // Si el estudiante ya tiene salón esto es un traslado, no un alta: se pide
  // confirmación antes de sacarlo de donde está. Sin salón previo no hay nada
  // que deshacer, así que se agrega directo y sin fricción.
  const add = (s) => {
    const actual = salonDe(s);
    if (actual && actual !== label) setConfirmMove(s);
    else doAdd(s);
  };

  const remove = async (s) => {
    setBusy(true);
    try {
      await adminService.removeStudentFromGroup(group.id, s.id);
      showToast(`${s.first_name} ${s.last_name} sacado de ${label}`);
      await loadRoster();
      await onChanged();
    } catch (err) { showToast(err.message, 'error'); }
    finally { setBusy(false); }
  };

  return (
    <>
    <div className="dash__modal-overlay" onClick={onClose}>
      <div className="dash__modal sal-roster" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
        <button className="dash__modal-close" onClick={onClose} aria-label="Cerrar"><CloseIcon /></button>
        <p className="dash__modal-label">Salón {label}</p>
        <p className="sal-roster__meta">
          Año {group.academic_year} · {students.length} {students.length === 1 ? 'estudiante' : 'estudiantes'}
        </p>

        <div className="sal-roster__search att-search">
          <input className="dash__field-input" placeholder="Buscar estudiante para agregar…"
            value={q} onChange={e => setQ(e.target.value)} disabled={busy} />
          {results.length > 0 && (
            <div className="att-search__results">
              {results.map(r => {
                const actual = salonDe(r);
                const aqui = actual === label;
                const enOtro = actual && !aqui;
                return (
                  <button type="button" key={r.id} className="att-search__item"
                    disabled={aqui} onClick={() => add(r)}>
                    <span className="dash__student-name">{r.full_name}</span>
                    <span className="dash__student-group">
                      Doc. {r.document_number}
                      {aqui && ' · ya está en este salón'}
                      {enOtro && ` · está en ${actual}`}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {loading ? (
          <div className="dash__empty" style={{ padding: '24px 0' }}><Spinner /><span>Cargando…</span></div>
        ) : students.length === 0 ? (
          <div className="dash__empty" style={{ padding: '24px 0' }}>
            <span>Este salón no tiene estudiantes. Búscalos arriba para agregarlos.</span>
          </div>
        ) : (
          <div className="sal-roster__list">
            {students.map(s => (
              <div className="sal-roster__row" key={s.id}>
                  {s.photo_url
                    ? <StudentPhoto src={s.photo_url} alt="" caption={`${s.first_name} ${s.last_name}`} className="dash__student-avatar" />
                    : <div className="dash__student-avatar" style={{ background: '#e0e7ff', color: '#4f46e5' }}>
                        {initials(s.first_name, s.last_name)}
                      </div>}
                  <div className="dash__student-info">
                    <p className="dash__student-name">{s.first_name} {s.last_name}</p>
                    <p className="dash__student-group">Doc. {s.document_number}</p>
                  </div>
                  <button type="button" className="sal-roster__remove" disabled={busy}
                    onClick={() => remove(s)}>Sacar</button>
              </div>
            ))}
          </div>
        )}

        <div className="dash__modal-actions">
          <button type="button" className="btn--secondary" disabled={busy}
            onClick={() => setRenaming(group.name)}>Renombrar</button>
          <button type="button" className="btn--secondary" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>

    {renaming !== null && (
      <div className="dash__modal-overlay sal-confirm" onClick={() => !busy && setRenaming(null)}>
        <form className="dash__modal dash__modal--sm" onSubmit={doRename}
          onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
          <p className="dash__modal-label">Renombrar salón</p>
          <Field label={`Nombre del salón en ${group.grade_name}`}>
            <input className="dash__field-input" autoFocus required maxLength={10}
              value={renaming} onChange={e => setRenaming(e.target.value)} />
          </Field>
          <p className="dash__form-hint">
            Solo cambia la etiqueta. Los {students.length} estudiantes matriculados, el horario
            y los docentes asignados siguen igual.
          </p>
          <div className="dash__modal-actions">
            <button type="button" className="btn--secondary" disabled={busy}
              onClick={() => setRenaming(null)}>Cancelar</button>
            <button type="submit" className="btn--confirm" disabled={busy} aria-busy={busy}>
              {busy ? <><Spinner color="white" size={16} /> Guardando…</> : 'Guardar nombre'}
            </button>
          </div>
        </form>
      </div>
    )}

    {/* Overlay HERMANO, no anidado: `.dash__modal-overlay` lleva
        `backdrop-filter`, que lo convierte en bloque contenedor de sus
        descendientes `position: fixed` — anidado, este se mediría contra la
        caja del panel y no contra el viewport (ver web/CLAUDE.md). */}
    {confirmMove && (
      <div className="dash__modal-overlay sal-confirm" onClick={() => !busy && setConfirmMove(null)}>
        <div className="dash__modal dash__modal--sm" onClick={e => e.stopPropagation()}
          role="dialog" aria-modal="true">
          <p className="dash__modal-label">Mover de salón</p>
          <p className="dash__modal-warning">
            <strong>{confirmMove.full_name}</strong> está actualmente en{' '}
            <strong>{salonDe(confirmMove)}</strong>.
            <br /><br />
            Un estudiante solo puede estar en un salón por año, así que continuar lo
            <strong> saca de {salonDe(confirmMove)}</strong> y lo matricula en <strong>{label}</strong>.
          </p>
          <div className="dash__modal-actions">
            <button type="button" className="btn--secondary" disabled={busy}
              onClick={() => setConfirmMove(null)}>Cancelar</button>
            <button type="button" className="btn--confirm" disabled={busy} aria-busy={busy}
              onClick={() => doAdd(confirmMove)}>
              {busy ? <><Spinner color="white" size={16} /> Moviendo…</> : `Sí, mover a ${label}`}
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  );
}

/* Color estable por nombre: la misma materia se ve siempre igual entre
   recargas, sin guardar nada en la BD. Hash simple, no criptográfico. */
const SUBJECT_COLORS = [
  { bg: '#ede9fe', fg: '#6d28d9' },
  { bg: '#d1fae5', fg: '#047857' },
  { bg: '#dbeafe', fg: '#1d4ed8' },
  { bg: '#fef3c7', fg: '#b45309' },
  { bg: '#fce7f3', fg: '#be185d' },
  { bg: '#e0e7ff', fg: '#4338ca' },
  { bg: '#ccfbf1', fg: '#0f766e' },
];
function subjectColor(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return SUBJECT_COLORS[h % SUBJECT_COLORS.length];
}
/* "Ciencias Naturales" -> "CN", "Matemáticas" -> "M". */
function subjectInitials(name) {
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();
}

/* ── Académico › Materias ────────────────────────────────────── */
function MateriasView() {
  const [subjects, setSubjects] = useState([]);
  const [name, setName] = useState('');
  const [editing, setEditing] = useState(null);  // { id, name } en edición
  const [saving, setSaving] = useState(false);
  const { toast, showToast } = useToast();

  const load = useCallback(async () => {
    try { setSubjects(await adminService.listSubjects()); }
    catch (e) { showToast(e.message, 'error'); }
  }, [showToast]);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    try { await adminService.createSubject({ name }); showToast('Materia creada'); setName(''); load(); }
    catch (err) { showToast(err.status === 409 ? 'Ya existe una materia con ese nombre' : err.message, 'error'); }
  };

  const doRename = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await adminService.renameSubject(editing.id, editing.name);
      showToast(`Materia renombrada a ${updated.name}`);
      setEditing(null);
      await load();
    } catch (err) {
      showToast(err.status === 409 ? 'Ya existe una materia con ese nombre' : err.message, 'error');
    } finally { setSaving(false); }
  };

  return (
    <>
      <Toast toast={toast} />

      {/* Alta en una sola fila: la materia es un único campo, así que un
          formulario apilado con label y botón de ancho completo ocupaba media
          pantalla para pedir una palabra. */}
      <form className="card mat-add" onSubmit={submit}>
        <input className="dash__field-input mat-add__input" value={name}
          onChange={e => setName(e.target.value)} required maxLength={100}
          placeholder="Nombre de la materia — p. ej. Matemáticas" aria-label="Nombre de la materia" />
        <button className="btn--confirm mat-add__btn" type="submit">+ Agregar</button>
      </form>

      <div className="mat-head">
        <span className="mat-head__title">Catálogo de materias</span>
        <span className="mat-head__count">{subjects.length}</span>
      </div>

      {subjects.length === 0 ? (
        <div className="card mat-empty">
          <p className="mat-empty__title">Todavía no hay materias</p>
          <p className="mat-empty__text">
            Se usan para etiquetar qué dicta cada docente en cada salón, en Horarios.
          </p>
        </div>
      ) : (
        <div className="mat-grid">
          {subjects.map(s => {
            const c = subjectColor(s.name);
            return (
              <button type="button" className="card mat-card" key={s.id}
                onClick={() => setEditing({ id: s.id, name: s.name })}
                title={`Renombrar ${s.name}`}>
                <span className="mat-card__badge" style={{ background: c.bg, color: c.fg }}>
                  {subjectInitials(s.name)}
                </span>
                <span className="mat-card__name">{s.name}</span>
                <span className="mat-card__edit" aria-hidden="true"><PencilIcon /></span>
              </button>
            );
          })}
        </div>
      )}

      {editing && (
        <div className="dash__modal-overlay" onClick={() => !saving && setEditing(null)}>
          <form className="dash__modal dash__modal--sm" onSubmit={doRename}
            onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
            <p className="dash__modal-label">Renombrar materia</p>
            <Field label="Nombre">
              <input className="dash__field-input" autoFocus required maxLength={100}
                value={editing.name}
                onChange={e => setEditing(p => ({ ...p, name: e.target.value }))} />
            </Field>
            <p className="dash__form-hint">
              Solo cambia la etiqueta: las asignaciones de docentes que ya usan esta materia
              en Horarios la siguen referenciando.
            </p>
            <div className="dash__modal-actions">
              <button type="button" className="btn--secondary" disabled={saving}
                onClick={() => setEditing(null)}>Cancelar</button>
              <button type="submit" className="btn--confirm" disabled={saving} aria-busy={saving}>
                {saving ? <><Spinner color="white" size={16} /> Guardando…</> : 'Guardar nombre'}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}

/* ── Horarios ─────────────────────────────────────────────────────
   Dos sub-secciones. **Rejilla** es el horario del salón: qué materia y qué
   docente en cada día y hora. **Docentes por salón** es `user_groups`, que es
   lo que de verdad decide qué clases ve un docente en "Mis clases de hoy"
   (Asistencia une ClassPeriod → UserGroup por salón). Están separadas porque
   responden preguntas distintas y confundirlas fue el problema del diseño
   anterior. */
function ScheduleView() {
  const [tab, setTab] = useState('rejilla');
  return (
    <>
      <div className="adm-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'rejilla'}
          className={`adm-tab${tab === 'rejilla' ? ' adm-tab--active' : ''}`}
          onClick={() => setTab('rejilla')}>Rejilla semanal</button>
        <button type="button" role="tab" aria-selected={tab === 'docentes'}
          className={`adm-tab${tab === 'docentes' ? ' adm-tab--active' : ''}`}
          onClick={() => setTab('docentes')}>Docentes por salón</button>
      </div>
      {tab === 'rejilla' ? <HorarioGrid /> : <TeacherAssignView />}
    </>
  );
}

const DAY_SHORT = { 1: 'Lun', 2: 'Mar', 3: 'Mié', 4: 'Jue', 5: 'Vie', 6: 'Sáb', 7: 'Dom' };
const hhmm = (t) => (t || '').slice(0, 5);

/* Jornada por defecto al crear: 6 bloques de 50 min con descanso a media
   mañana, que es la forma habitual en un colegio público de Medellín. */
const DEFAULT_PERIODS = [
  { period_order: 1, name: 'Primera hora', start_time: '07:00', end_time: '07:50' },
  { period_order: 2, name: 'Segunda hora', start_time: '07:50', end_time: '08:40' },
  { period_order: 3, name: 'Tercera hora', start_time: '08:40', end_time: '09:30' },
  { period_order: 4, name: 'Cuarta hora', start_time: '10:00', end_time: '10:50' },
  { period_order: 5, name: 'Quinta hora', start_time: '10:50', end_time: '11:40' },
  { period_order: 6, name: 'Sexta hora', start_time: '11:40', end_time: '12:30' },
];

function HorarioGrid() {
  const [groups, setGroups] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [users, setUsers] = useState([]);
  const [selGroup, setSelGroup] = useState('');
  const [periods, setPeriods] = useState([]);
  const [loading, setLoading] = useState(true);
  const { toast, showToast } = useToast();

  const [editing, setEditing] = useState(null);   // bloque existente o borrador nuevo
  // TEMPORAL (QA de fin de semana). Fuerza las columnas Sáb/Dom aunque estén
  // vacías, para poder crear bloques ahí. Ver TODO.md antes de producción.
  const [showWeekend, setShowWeekend] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [g, s, u] = await Promise.all([
          adminService.listGroups(), adminService.listSubjects(), adminService.listUsers(),
        ]);
        setGroups(g); setSubjects(s); setUsers(u.filter(x => x.role !== 'ADMIN'));
        if (g.length) setSelGroup(g[0].id);
      } catch (e) { showToast(e.message, 'error'); }
      finally { setLoading(false); }
    })();
  }, [showToast]);

  const loadPeriods = useCallback(async () => {
    if (!selGroup) { setPeriods([]); return; }
    try { setPeriods(await adminService.listClassPeriods(selGroup)); }
    catch (e) { showToast(e.message, 'error'); setPeriods([]); }
  }, [selGroup, showToast]);
  useEffect(() => { loadPeriods(); }, [loadPeriods]);

  const group = groups.find(g => g.id === selGroup);

  // Lun–Vie siempre; sábado y domingo solo si tienen bloques, para no pintar
  // dos columnas vacías en el 99% de los colegios.
  const days = [1, 2, 3, 4, 5];
  for (const d of [6, 7]) if (showWeekend || periods.some(p => p.day_of_week === d)) days.push(d);

  // El eje arranca en la hora en punto anterior al primer bloque y termina en la
  // posterior al último: un colegio de jornada única no tiene por qué mirar 24h.
  const startsMin = periods.map(p => toMin(p.start_time));
  const endsMin = periods.map(p => toMin(p.end_time));
  const axisStart = startsMin.length ? Math.floor(Math.min(...startsMin) / 60) * 60 : 6 * 60;
  const axisEnd = endsMin.length ? Math.ceil(Math.max(...endsMin) / 60) * 60 : 14 * 60;
  const axisHeight = (axisEnd - axisStart) * PX_MIN;
  const hourMarks = [];
  for (let m = axisStart; m <= axisEnd; m += 60) hourMarks.push(m);

  const byDay = {};
  for (const d of days) {
    byDay[d] = layoutDay(
      periods.filter(p => p.day_of_week === d)
        .map(p => ({ p, s: toMin(p.start_time), e: toMin(p.end_time) }))
    );
  }
  const conflictos = days.reduce((n, d) => n + byDay[d].filter(ev => ev.cols > 1).length, 0);

  const draft = (day, startMin, endMin) => ({
    day_of_week: day, name: '', start_time: toHHMM(startMin), end_time: toHHMM(endMin),
    subject_id: '', user_id: '',
  });

  /* Click en un hueco: crea un bloque que empieza en el minuto pinchado
     (redondeado a 15) y dura 50 min, recortado si topa con la siguiente clase.
     Es el "click + formulario": abre el modal ya relleno, no guarda nada. */
  const onColumnClick = (e, day) => {
    if (e.target.closest('.hor-ev')) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const raw = axisStart + (e.clientY - rect.top) / PX_MIN;
    const start = Math.max(axisStart, Math.round(raw / SNAP) * SNAP);
    const ocupados = byDay[day] ?? [];
    if (ocupados.some(ev => start >= ev.s && start < ev.e)) return;  // dentro de una clase
    const siguiente = ocupados.filter(ev => ev.s > start).map(ev => ev.s).sort((a, b) => a - b)[0];
    const tope = Math.min(siguiente ?? 24 * 60, 24 * 60);
    const end = Math.min(start + NEW_BLOCK_MIN, tope);
    if (end - start < SNAP) { showToast('No cabe un bloque en ese hueco', 'error'); return; }
    setEditing(draft(day, start, end));
  };

  const overlapsExisting = (d) => periods.some(p =>
    p.id !== d.id && p.day_of_week === Number(d.day_of_week) &&
    toMin(p.start_time) < toMin(d.end_time) && toMin(p.end_time) > toMin(d.start_time));

  const savePeriod = async (e) => {
    e.preventDefault();
    if (toMin(editing.start_time) >= toMin(editing.end_time)) {
      showToast('La hora de fin debe ser posterior a la de inicio', 'error'); return;
    }
    if (overlapsExisting(editing)) {
      showToast('Ese horario se cruza con otra clase de ese día', 'error'); return;
    }
    setSaving(true);
    const subjectName = subjects.find(s => s.id === editing.subject_id)?.name;
    const body = {
      // La etiqueta es opcional en el formulario pero NOT NULL en la BD: si el
      // admin no escribe nada, la materia es el mejor nombre posible.
      name: editing.name.trim() || subjectName || 'Clase',
      start_time: `${editing.start_time}:00`, end_time: `${editing.end_time}:00`,
      subject_id: editing.subject_id || null, user_id: editing.user_id,
    };
    try {
      if (editing.id) await adminService.updateClassPeriod(editing.id, { ...body, day_of_week: editing.day_of_week });
      else await adminService.createClassPeriod({ ...body, group_id: selGroup, day_of_week: editing.day_of_week });
      showToast('Bloque guardado');
      setEditing(null);
      await loadPeriods();
    } catch (err) {
      showToast(err.message, 'error');
    } finally { setSaving(false); }
  };

  const removePeriod = async () => {
    setSaving(true);
    try {
      await adminService.deleteClassPeriod(editing.id);
      showToast('Bloque eliminado');
      setEditing(null);
      await loadPeriods();
    } catch (err) { showToast(err.message, 'error'); }
    finally { setSaving(false); }
  };

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando horarios…</span></div>;
  if (!groups.length) return (
    <div className="card mat-empty">
      <p className="mat-empty__title">No hay salones todavía</p>
      <p className="mat-empty__text">Crea un salón en Académico › Salones antes de armar su horario.</p>
    </div>
  );

  const gridCols = { gridTemplateColumns: `var(--hor-gutter) repeat(${days.length}, minmax(132px, 1fr))` };

  return (
    <>
      <Toast toast={toast} />

      <div className="hor-bar">
        <select className="dash__field-input hor-bar__select" value={selGroup}
          onChange={e => setSelGroup(e.target.value)} aria-label="Salón">
          {groups.map(g => <option key={g.id} value={g.id}>{g.grade_name} {g.name} · {g.academic_year}</option>)}
        </select>
        <span className="hor-bar__count">
          {periods.length} {periods.length === 1 ? 'bloque' : 'bloques'}
        </span>
        {conflictos > 0 && (
          <span className="hor-bar__warn" title="Hay clases que se pisan en el reloj">
            ⚠ {conflictos} en conflicto
          </span>
        )}
        <label className="dash__inactive-toggle" title="Temporal: para QA de fin de semana">
          <input type="checkbox" checked={showWeekend}
            onChange={e => setShowWeekend(e.target.checked)} />
          Fin de semana
        </label>
      </div>

      <div className="hor-scroll">
        <div className="hor-cal">
          <div className="hor-cal__head" style={gridCols}>
            <div className="hor-cal__gutter-head" />
            {days.map(d => (
              <div key={d} className="hor-cal__day-head">
                <span className="hor-cal__day-full">{DAY_FULL[d]}</span>
                <span className="hor-cal__day-short">{DAY_SHORT[d]}</span>
              </div>
            ))}
          </div>

          <div className="hor-cal__body" style={{ ...gridCols, height: axisHeight }}>
            <div className="hor-cal__gutter">
              {hourMarks.map(m => (
                <span key={m} className="hor-cal__hour" style={{ top: (m - axisStart) * PX_MIN }}>
                  {toHHMM(m)}
                </span>
              ))}
            </div>

            {days.map(d => (
              <div key={d} className="hor-cal__col" onClick={e => onColumnClick(e, d)}
                role="presentation">
                {hourMarks.map(m => (
                  <span key={m} className="hor-cal__line" style={{ top: (m - axisStart) * PX_MIN }} />
                ))}
                {hourMarks.slice(0, -1).map(m => (
                  <span key={`h${m}`} className="hor-cal__line hor-cal__line--half"
                    style={{ top: (m + 30 - axisStart) * PX_MIN }} />
                ))}

                {byDay[d].map(({ p, s, e, col, cols }) => {
                  const c = p.subject_name ? subjectColor(p.subject_name) : null;
                  const mins = e - s;
                  const ancho = 100 / cols;
                  return (
                    <button type="button" key={p.id}
                      className={`hor-ev${mins <= 35 ? ' hor-ev--tiny' : ''}${cols > 1 ? ' hor-ev--clash' : ''}`}
                      style={{
                        top: (s - axisStart) * PX_MIN,
                        height: Math.max(mins * PX_MIN - 2, 16),
                        left: `calc(${col * ancho}% + 3px)`,
                        width: `calc(${ancho}% - 6px)`,
                        ...(c ? { background: c.bg, borderColor: c.fg, color: c.fg } : {}),
                      }}
                      title={`${hhmm(p.start_time)}–${hhmm(p.end_time)} · ${durLabel(mins)}`}
                      onClick={ev => {
                        ev.stopPropagation();
                        setEditing({
                          id: p.id, day_of_week: p.day_of_week, name: p.name,
                          start_time: hhmm(p.start_time), end_time: hhmm(p.end_time),
                          subject_id: p.subject_id || '', user_id: p.user_id || '',
                        });
                      }}>
                      <span className="hor-ev__time">
                        {hhmm(p.start_time)}–{hhmm(p.end_time)}
                        {p.period_order === 1 && <span className="hor-ev__first" title="Primera hora: es la que notifica al acudiente">1ª</span>}
                      </span>
                      <span className="hor-ev__subject">{p.subject_name || p.name}</span>
                      <span className="hor-ev__teacher">{p.teacher_name || 'Sin docente'}</span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>

          {periods.length === 0 && (
            <p className="hor-cal__hint">
              {group ? `${group.grade_name} ${group.name}` : 'Este salón'} no tiene horario.
              Haz clic en cualquier hueco del calendario para crear el primer bloque:
              se abre con la hora ya puesta y solo hay que elegir materia y docente.
            </p>
          )}
        </div>
      </div>

      {editing && (
        <div className="dash__modal-overlay" onClick={() => !saving && setEditing(null)}>
          <form className="dash__modal" onSubmit={savePeriod} onClick={e => e.stopPropagation()}
            role="dialog" aria-modal="true">
            <p className="dash__modal-label">
              {editing.id ? 'Editar bloque' : 'Nuevo bloque'} ·{' '}
              {DAY_FULL[editing.day_of_week]} {editing.start_time}–{editing.end_time}
              {' · '}{durLabel(Math.max(0, toMin(editing.end_time) - toMin(editing.start_time)))}
            </p>
            <div className="dash__form-grid">
              <label className="dash__field">
                <span className="dash__field-label">
                  Etiqueta <span className="dash__field-optional">(opcional)</span>
                </span>
                <input className="dash__field-input" maxLength={100} value={editing.name}
                  placeholder="Se usa el nombre de la materia"
                  onChange={e => setEditing(p => ({ ...p, name: e.target.value }))} />
              </label>
              <label className="dash__field">
                <span className="dash__field-label">Día</span>
                <select className="dash__field-input" value={editing.day_of_week}
                  onChange={e => setEditing(p => ({ ...p, day_of_week: Number(e.target.value) }))}>
                  {[1, 2, 3, 4, 5, 6, 7].map(d => <option key={d} value={d}>{DAY_FULL[d]}</option>)}
                </select>
              </label>
              <label className="dash__field">
                <span className="dash__field-label">Inicio</span>
                <input className="dash__field-input" type="time" required step={300} value={editing.start_time}
                  onChange={e => setEditing(p => ({ ...p, start_time: e.target.value }))} />
              </label>
              <label className="dash__field">
                <span className="dash__field-label">Fin</span>
                <input className="dash__field-input" type="time" required step={300} value={editing.end_time}
                  onChange={e => setEditing(p => ({ ...p, end_time: e.target.value }))} />
              </label>
              <label className="dash__field">
                <span className="dash__field-label">Materia <span className="dash__field-optional">(opcional)</span></span>
                <select className="dash__field-input" value={editing.subject_id}
                  onChange={e => setEditing(p => ({ ...p, subject_id: e.target.value }))}>
                  <option value="">Sin materia</option>
                  {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </label>
              <label className="dash__field">
                <span className="dash__field-label">Docente</span>
                <select className="dash__field-input" required value={editing.user_id}
                  onChange={e => setEditing(p => ({ ...p, user_id: e.target.value }))}>
                  <option value="">Seleccionar…</option>
                  {users.map(u => <option key={u.id} value={u.id}>{u.first_name} {u.last_name}</option>)}
                </select>
              </label>
            </div>
            <p className="dash__form-hint">
              La duración del bloque es la que marquen estas dos horas: no hay bloques de tamaño
              fijo. El orden lo calcula el sistema por la hora de inicio, y la primera clase del
              día es la que dispara la notificación de inasistencia al acudiente. El docente es
              obligatorio: es quien verá el bloque en «Mis clases de hoy» y quien toma lista, y
              no puede tener otra clase a la misma hora en otro salón.
            </p>
            <div className="dash__modal-actions">
              {editing.id && (
                <button type="button" className="btn--danger" disabled={saving} onClick={removePeriod}>
                  Eliminar
                </button>
              )}
              <button type="button" className="btn--secondary" disabled={saving}
                onClick={() => setEditing(null)}>Cancelar</button>
              <button type="submit" className="btn--confirm" disabled={saving} aria-busy={saving}>
                {saving ? <><Spinner color="white" size={16} /> Guardando…</> : 'Guardar'}
              </button>
            </div>
          </form>
        </div>
      )}

    </>
  );
}

/* ── Horarios › Docentes por salón ────────────────────────────────
   Esto es `user_groups`, y **no** es decorativo: Asistencia une
   ClassPeriod → UserGroup por salón, así que esta tabla es la que decide qué
   clases le aparecen a un docente en "Mis clases de hoy". La materia de aquí
   alimenta el filtro "Mis estudiantes por materia". */
function TeacherAssignView() {
  const [groups, setGroups] = useState([]);
  const [users, setUsers] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [assign, setAssign] = useState({ user_id: '', group_id: '', subject_id: '' });
  const [saving, setSaving] = useState(false);
  const { toast, showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const [g, u, a, s] = await Promise.all([
        adminService.listGroups(), adminService.listUsers(),
        adminService.listAssignments(), adminService.listSubjects(),
      ]);
      setGroups(g); setUsers(u.filter(x => x.role !== 'ADMIN')); setAssignments(a); setSubjects(s);
    } catch (e) { showToast(e.message, 'error'); }
    finally { setLoading(false); }
  }, [showToast]);
  useEffect(() => { load(); }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await adminService.assignTeacher({
        user_id: assign.user_id, group_id: assign.group_id,
        academic_year: YEAR, subject_id: assign.subject_id || null,
      });
      showToast('Docente asignado');
      setAssign({ user_id: '', group_id: '', subject_id: '' });
      await load();
    } catch (err) {
      showToast(err.status === 409 ? 'Ese docente ya está asignado a ese salón este año' : err.message, 'error');
    } finally { setSaving(false); }
  };

  const label = (id) => { const g = groups.find(x => x.id === id); return g ? `${g.grade_name} ${g.name}` : '—'; };
  const person = (id) => { const u = users.find(x => x.id === id); return u ? `${u.first_name} ${u.last_name}` : '—'; };
  const subject = (id) => subjects.find(x => x.id === id)?.name ?? null;

  if (loading) return <div className="dash__empty"><Spinner /><span>Cargando asignaciones…</span></div>;

  return (
    <>
      <Toast toast={toast} />

      <p className="dash__form-hint" style={{ marginBottom: 16 }}>
        Esta asignación es la que hace que un salón aparezca en «Mis clases de hoy» del docente.
        Sin ella, aunque el horario tenga su nombre en el calendario, no podrá tomar asistencia.
      </p>

      <form className="card hor-assign" onSubmit={submit}>
        <select className="dash__field-input" required value={assign.user_id}
          onChange={e => setAssign(p => ({ ...p, user_id: e.target.value }))} aria-label="Docente">
          <option value="">Docente…</option>
          {users.map(u => <option key={u.id} value={u.id}>{u.first_name} {u.last_name}</option>)}
        </select>
        <select className="dash__field-input" required value={assign.group_id}
          onChange={e => setAssign(p => ({ ...p, group_id: e.target.value }))} aria-label="Salón">
          <option value="">Salón…</option>
          {groups.map(g => <option key={g.id} value={g.id}>{g.grade_name} {g.name}</option>)}
        </select>
        <select className="dash__field-input" value={assign.subject_id}
          onChange={e => setAssign(p => ({ ...p, subject_id: e.target.value }))} aria-label="Materia">
          <option value="">Materia (opcional)…</option>
          {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <button className="btn--confirm hor-assign__btn" type="submit" disabled={saving}>
          {saving ? <Spinner color="white" size={16} /> : 'Asignar'}
        </button>
      </form>

      <div className="mat-head">
        <span className="mat-head__title">Asignaciones de {YEAR}</span>
        <span className="mat-head__count">{assignments.length}</span>
      </div>

      {assignments.length === 0 ? (
        <div className="card mat-empty">
          <p className="mat-empty__title">Ningún docente asignado</p>
          <p className="mat-empty__text">Ningún docente podrá tomar asistencia hasta que asignes al menos uno.</p>
        </div>
      ) : (
        <div className="mat-grid">
          {assignments.map(a => (
            <div className="card mat-card" key={a.id} style={{ cursor: 'default' }}>
              <span className="mat-card__badge" style={{ background: '#e0e7ff', color: '#4f46e5' }}>
                {label(a.group_id).split(' ').map(w => w[0]).join('').slice(0, 2)}
              </span>
              <span style={{ minWidth: 0 }}>
                <span className="mat-card__name" style={{ display: 'block' }}>{person(a.user_id)}</span>
                <span className="dash__student-group">
                  {label(a.group_id)}{subject(a.subject_id) ? ` · ${subject(a.subject_id)}` : ''}
                </span>
              </span>
            </div>
          ))}
        </div>
      )}
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
function CloseIcon({ size = 18 }) { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>; }
function EyeIcon()   { return <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>; }
function PencilIcon() { return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>; }
function SearchIcon() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>; }
function Spinner({ color = '#4f46e5', size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" className="dash__spinner">
      <circle cx="12" cy="12" r="10" stroke="rgba(0,0,0,0.1)" strokeWidth="2.5" />
      <path d="M12 2a10 10 0 0110 10" stroke={color} strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}
