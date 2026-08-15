import { api } from './api';

export const adminService = {
  getStats: () => api.get('/admin/stats'),

  // Personal (usuarios)
  listUsers:  () => api.get('/admin/users'),
  createUser: (u) => api.post('/admin/users', u),
  getUserDetail: (id) => api.get(`/admin/users/${id}`),
  updateUser: (id, u) => api.put(`/admin/users/${id}`, u),

  // Académico
  listGrades:  () => api.get('/admin/grades'),
  createGrade: (g) => api.post('/admin/grades', g),
  listGroups:  () => api.get('/admin/groups'),
  createGroup: (g) => api.post('/admin/groups', g),
  listSubjects:  () => api.get('/admin/subjects'),
  createSubject: (s) => api.post('/admin/subjects', s),
  enrollStudentInGroup: (sg) => api.post('/admin/student-groups', sg),

  // Alta completa: estudiante + matrícula opcional + acudientes + inscripción PAE, atómico.
  createStudentFull: (data) => api.post('/admin/students', data),
  // Ficha de detalle (para la ficha Y para precargar el formulario de edición).
  getStudentDetail: (id) => api.get(`/admin/students/${id}`),
  // Edición completa: mismos campos que el alta, mismo atomicidad.
  updateStudentFull: (id, data) => api.put(`/admin/students/${id}`, data),

  // Horarios
  listClassPeriods: (group_id) => api.get(`/admin/class-periods?group_id=${group_id}`),
  createClassPeriod: (cp) => api.post('/admin/class-periods', cp),
  listAssignments: () => api.get('/admin/teacher-assignments'),
  assignTeacher:   (a) => api.post('/admin/teacher-assignments', a),
};
