import { api } from './api';

export const agendatorioService = {
  listArticles: () => api.get('/agendatorio/articles'),

  listRecords: (student_id) => api.get(`/agendatorio/records?student_id=${student_id}`),

  // Crea un registro disciplinario. `signatureBlob` es un PNG de la firma.
  createRecord: ({ student_id, article_ids, observations, date }, signatureBlob) => {
    const fd = new FormData();
    fd.append('data', JSON.stringify({ student_id, article_ids, observations, date }));
    fd.append('signature', signatureBlob, 'firma.png');
    return api.postForm('/agendatorio/records', fd);
  },
};
