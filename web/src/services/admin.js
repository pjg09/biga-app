import { api } from './api';

export const adminService = {
  getStats: () => api.get('/admin/stats'),

  // Personal (usuarios)
  listUsers:  () => api.get('/admin/users'),
  createUser: (u) => api.post('/admin/users', u),

  // Académico
  listGrades:  () => api.get('/admin/grades'),
  createGrade: (g) => api.post('/admin/grades', g),
  listGroups:  () => api.get('/admin/groups'),
  createGroup: (g) => api.post('/admin/groups', g),
  enrollStudentInGroup: (sg) => api.post('/admin/student-groups', sg),

  // Alta completa: estudiante + matrícula opcional + acudientes, atómico.
  createStudentFull: (data) => api.post('/admin/students', data),

  // Horarios
  listClassPeriods: (group_id) => api.get(`/admin/class-periods?group_id=${group_id}`),
  createClassPeriod: (cp) => api.post('/admin/class-periods', cp),
  listAssignments: () => api.get('/admin/teacher-assignments'),
  assignTeacher:   (a) => api.post('/admin/teacher-assignments', a),

  // Leads de la landing. `status` opcional: PENDING | SENT | FAILED | SUPPRESSED
  listLeads: (status) =>
    api.get(`/admin/leads${status ? `?status=${status}` : ''}`),
};
