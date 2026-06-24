import { api } from './api';

export const attendanceService = {
  getFirstClass: () => api.get('/attendance/first-class/today'),

  submit: (class_period_id, entries) =>
    api.post('/attendance/first-class', { class_period_id, entries }),

  markArrived: (record_id) =>
    api.post(`/attendance/records/${record_id}/arrived`, {}),

  schedule: () => api.get('/attendance/schedule'),

  justifications: () => api.get('/attendance/justifications'),

  // Público (el padre no está autenticado; el token es la autorización)
  justificationInfo: (token) => api.get(`/attendance/justify/${token}`),

  submitJustification: (token, reason) =>
    api.post(`/attendance/justify/${token}`, { reason }),
};
