import { api } from './api';

export const studentService = {
  list: ({ gradeId, groupId } = {}) => {
    const params = new URLSearchParams();
    if (gradeId) params.set('grade_id', gradeId);
    if (groupId) params.set('group_id', groupId);
    const qs = params.toString();
    return api.get(`/students${qs ? `?${qs}` : ''}`);
  },

  // Búsqueda con filtros opcionales. `q` puede ir vacío si se filtra por grado/salón.
  search: (q, { gradeId, groupId } = {}) => {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (gradeId) params.set('grade_id', gradeId);
    if (groupId) params.set('group_id', groupId);
    return api.get(`/students/search?${params.toString()}`);
  },

  create: ({ document_number, first_name, last_name, birth_date }) =>
    api.post('/students', {
      document_number,
      first_name,
      last_name,
      birth_date,
      photo_url: null,
    }),

  // Sube la foto real a MinIO; devuelve el estudiante con la URL presignada.
  uploadPhoto: (id, file) => {
    const fd = new FormData();
    fd.append('photo', file, file.name);
    return api.postForm(`/students/${id}/photo`, fd);
  },
};
