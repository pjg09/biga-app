import { api } from './api';

export const attendanceService = {
  // Clases del docente para hoy (selector de asistencia clase a clase)
  getToday: () => api.get('/attendance/today'),

  // Roster + estado de una clase específica de hoy
  getClass: (class_period_id) => api.get(`/attendance/classes/${class_period_id}`),

  submit: (class_period_id, entries) =>
    api.post('/attendance', { class_period_id, entries }),

  markArrived: (record_id) =>
    api.post(`/attendance/records/${record_id}/arrived`, {}),

  schedule: () => api.get('/attendance/schedule'),


  // Inasistencias de primera hora sin justificar.
  absences: ({ studentId, includeClosed } = {}) => {
    const p = new URLSearchParams();
    if (studentId) p.set('student_id', studentId);
    if (includeClosed) p.set('include_closed', 'true');
    const qs = p.toString();
    return api.get(`/attendance/absences${qs ? `?${qs}` : ''}`);
  },
  setAbsenceClosed: (recordId, closed) =>
    api.post(`/attendance/absences/${recordId}/${closed ? 'archive' : 'unarchive'}`),
  absenceDetail: (recordId) => api.get(`/attendance/absences/${recordId}`),
  addAbsenceNote: (recordId, note) => api.post(`/attendance/absences/${recordId}/notes`, { note }),

  // Mensajes: excusas de los acudientes, con filtros y cierre de caso.
  justifications: ({ studentId, includeArchived } = {}) => {
    const p = new URLSearchParams();
    if (studentId) p.set('student_id', studentId);
    if (includeArchived) p.set('include_archived', 'true');
    const qs = p.toString();
    return api.get(`/attendance/justifications${qs ? `?${qs}` : ''}`);
  },
  justificationDetail: (id) => api.get(`/attendance/justifications/${id}`),
  addJustificationNote: (id, note) => api.post(`/attendance/justifications/${id}/notes`, { note }),
  setJustificationArchived: (id, archived) =>
    api.post(`/attendance/justifications/${id}/${archived ? 'archive' : 'unarchive'}`),

  // Público (el acudiente no está autenticado; el token es la autorización)
  justificationInfo: (token) => api.get(`/attendance/justify/${token}`),

  // Multipart: el soporte (PDF o imagen) es opcional.
  submitJustification: (token, reason, file) => {
    const fd = new FormData();
    fd.append('reason', reason);
    if (file) fd.append('attachment', file, file.name);
    return api.postFormPublic(`/attendance/justify/${token}`, fd);
  },
};
