import { api } from './api';

export const departureService = {
  listToday: () => api.get('/departures'),

  create: ({ student_id, departure_time, reason }) =>
    api.post('/departures', {
      student_id,
      departure_time,
      reason: reason || null,
    }),
};
