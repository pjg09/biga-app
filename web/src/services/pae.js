import { api } from './api';

export const paeService = {
  listStudentsToday: () => api.get('/pae/students/today'),

  getDeliveryWindow: () => api.get('/pae/delivery-window'),

  registerDelivery: (student_id) =>
    api.post('/pae/deliveries', {
      student_id,
      identification_method: 'DOCUMENT',
    }),

  enrollStudent: (student_id) =>
    api.post('/pae/enrollments', { student_id }),

  weeklyReport: () => api.get('/pae/report/weekly'),

  auditDeliveries: () => api.get('/pae/audit'),
};
