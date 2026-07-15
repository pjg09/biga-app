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

  justifications: () => api.get('/attendance/justifications'),

  // Público (el padre no está autenticado; el token es la autorización)
  justificationInfo: (token) => api.get(`/attendance/justify/${token}`),

  submitJustification: (token, reason) =>
    api.post(`/attendance/justify/${token}`, { reason }),
};
