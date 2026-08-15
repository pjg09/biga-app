import { api } from './api';

export const adminService = {
  getStats: () => api.get('/admin/stats'),

  // Personal (usuarios)
  listUsers:  ({ includeInactive = false } = {}) =>
    api.get(`/admin/users${includeInactive ? '?include_inactive=true' : ''}`),
  // Baja lógica: apaga is_active, no borra la fila. El histórico se conserva.
  deactivateUser: (id) => api.del(`/admin/users/${id}`),
  reactivateUser: (id) => api.post(`/admin/users/${id}/reactivate`),
  deactivateStudent: (id) => api.del(`/admin/students/${id}`),
  reactivateStudent: (id) => api.post(`/admin/students/${id}/reactivate`),
  // Salones: agregar mueve al estudiante si ya estaba en otro salón
  // (student_groups es único por estudiante y año). Sacar = is_active=false.
  renameGroup: (id, name) => api.put(`/admin/groups/${id}`, { name }),
  addStudentToGroup: (groupId, studentId) =>
    api.post(`/admin/groups/${groupId}/students`, { student_id: studentId }),
  removeStudentFromGroup: (groupId, studentId) =>
    api.del(`/admin/groups/${groupId}/students/${studentId}`),
  createUser: (u) => api.post('/admin/users', u),
  getUserDetail: (id) => api.get(`/admin/users/${id}`),
  updateUser: (id, u) => api.put(`/admin/users/${id}`, u),
  uploadUserPhoto: (id, file) => {
    const fd = new FormData();
    fd.append('photo', file, file.name);
    return api.postForm(`/admin/users/${id}/photo`, fd);
  },

  // Académico
  listGrades:  () => api.get('/admin/grades'),
  listGroups:  () => api.get('/admin/groups'),
  createGroup: (g) => api.post('/admin/groups', g),
  listSubjects:  () => api.get('/admin/subjects'),
  renameSubject: (id, name) => api.put(`/admin/subjects/${id}`, { name }),
  createSubject: (s) => api.post('/admin/subjects', s),
  enrollStudentInGroup: (sg) => api.post('/admin/student-groups', sg),

  // Alta completa: estudiante + matrícula opcional + acudientes + inscripción PAE, atómico.
  createStudentFull: (data) => api.post('/admin/students', data),
  // Ficha de detalle (para la ficha Y para precargar el formulario de edición).
  getStudentDetail: (id) => api.get(`/admin/students/${id}`),
  // Edición completa: mismos campos que el alta, mismo atomicidad.
  updateStudentFull: (id, data) => api.put(`/admin/students/${id}`, data),

  // Horarios
  bulkCreateClassPeriods: (payload) => api.post('/admin/class-periods/bulk', payload),
  updateClassPeriod: (id, payload) => api.put(`/admin/class-periods/${id}`, payload),
  deleteClassPeriod: (id) => api.del(`/admin/class-periods/${id}`),
  listClassPeriods: (group_id) => api.get(`/admin/class-periods?group_id=${group_id}`),
  createClassPeriod: (cp) => api.post('/admin/class-periods', cp),
  listAssignments: () => api.get('/admin/teacher-assignments'),
  assignTeacher:   (a) => api.post('/admin/teacher-assignments', a),
};
