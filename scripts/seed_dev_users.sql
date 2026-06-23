-- Institución de prueba
INSERT INTO institutions (id, name, nit, address, city, pae_delivery_end_time, created_at)
VALUES (
  'a0000000-0000-0000-0000-000000000001',
  'Institución Educativa Demo',
  '900123456-7',
  'Calle 1 # 2-3',
  'Bogotá',
  '12:00:00',
  NOW()
)
ON CONFLICT (id) DO NOTHING;

-- Usuario TEACHER  (contraseña: password123)
INSERT INTO users (id, institution_id, document_number, first_name, last_name, email, hashed_password, role, is_active, created_at)
VALUES (
  'b0000000-0000-0000-0000-000000000001',
  'a0000000-0000-0000-0000-000000000001',
  '10000001',
  'Carlos',
  'Docente',
  'teacher@iedemo.edu.co',
  '$2b$12$tGQtfPX82SqMR/wn99nk3u64.mvm/gaAyNfBGCtpvzjthA2uA0p6O',
  'TEACHER',
  true,
  NOW()
)
ON CONFLICT (id) DO NOTHING;

-- Usuario PAE_OPERATOR  (contraseña: password123)
INSERT INTO users (id, institution_id, document_number, first_name, last_name, email, hashed_password, role, is_active, created_at)
VALUES (
  'b0000000-0000-0000-0000-000000000002',
  'a0000000-0000-0000-0000-000000000001',
  '10000002',
  'Ana',
  'PAE',
  'pae@iedemo.edu.co',
  '$2b$12$tGQtfPX82SqMR/wn99nk3u64.mvm/gaAyNfBGCtpvzjthA2uA0p6O',
  'PAE_OPERATOR',
  true,
  NOW()
)
ON CONFLICT (id) DO NOTHING;

-- Estudiantes demo. No se siembran inscripciones PAE aquí: el enrollment_hash
-- depende de PAE_SIGNING_SECRET y del timestamp, así que la inscripción se hace
-- desde la app (vista Estudiantes → "Inscribir en PAE"), lo que ejercita la
-- cadena de doble hash correctamente.
INSERT INTO students (id, institution_id, document_number, first_name, last_name, birth_date, photo_url, is_active, created_at)
VALUES
  ('c0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', '1010100001', 'Mariana', 'Gómez',     '2014-03-12', NULL, true, NOW()),
  ('c0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', '1010100002', 'Santiago', 'Rodríguez', '2013-07-25', NULL, true, NOW()),
  ('c0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', '1010100003', 'Valentina', 'López',    '2015-11-03', NULL, true, NOW()),
  ('c0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', '1010100004', 'Mateo', 'Martínez',      '2014-01-19', NULL, true, NOW())
ON CONFLICT (id) DO NOTHING;
