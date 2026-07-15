import { api } from './api';

export const agendatorioService = {
  listArticles: () => api.get('/agendatorio/articles'),

  // Catálogo académico para los selectores de búsqueda de estudiantes
  listGrades: () => api.get('/agendatorio/grades'),
  listGroups: () => api.get('/agendatorio/groups'),

  listRecords: (student_id) => api.get(`/agendatorio/records?student_id=${student_id}`),

  // Historial del docente (registros propios)
  listMyRecords: ({ studentId, includeArchived } = {}) => {
    const params = new URLSearchParams();
    if (studentId) params.set('student_id', studentId);
    if (includeArchived) params.set('include_archived', 'true');
    const qs = params.toString();
    return api.get(`/agendatorio/my-records${qs ? `?${qs}` : ''}`);
  },
  recordDetail: (id) => api.get(`/agendatorio/records/${id}`),
  addNote: (id, note) => api.post(`/agendatorio/records/${id}/notes`, { note }),
  archiveRecord: (id) => api.post(`/agendatorio/records/${id}/archive`, {}),
  unarchiveRecord: (id) => api.post(`/agendatorio/records/${id}/unarchive`, {}),

  // Crea un registro disciplinario. `signatureBlob` es un PNG de la firma.
  createRecord: ({ student_id, article_ids, observations, date }, signatureBlob) => {
    const fd = new FormData();
    fd.append('data', JSON.stringify({ student_id, article_ids, observations, date }));
    fd.append('signature', signatureBlob, 'firma.png');
    return api.postForm('/agendatorio/records', fd);
  },
};
