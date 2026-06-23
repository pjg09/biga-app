import { api } from './api';

export const studentService = {
  list: () => api.get('/students'),

  create: ({ document_number, first_name, last_name, birth_date, photo_url }) =>
    api.post('/students', {
      document_number,
      first_name,
      last_name,
      birth_date,
      photo_url: photo_url || null,
    }),
};
