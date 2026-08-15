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

-- Usuario ADMIN  (contraseña: password123)
INSERT INTO users (id, institution_id, document_number, first_name, last_name, email, hashed_password, role, is_active, created_at)
VALUES (
  'b0000000-0000-0000-0000-000000000003',
  'a0000000-0000-0000-0000-000000000001',
  '10000003',
  'Sofía',
  'Admin',
  'admin@iedemo.edu.co',
  '$2b$12$tGQtfPX82SqMR/wn99nk3u64.mvm/gaAyNfBGCtpvzjthA2uA0p6O',
  'ADMIN',
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

-- ───────────────────────────────────────────────────────────────────────────
-- Datos para asistencia y salidas tempranas (academic_year 2026).
-- Crea grado/grupo, primera hora para lun–vie (period_order=1) para que el
-- docente siempre tenga "primera clase hoy", asigna el docente y los 4
-- estudiantes al grupo, y registra un acudiente primario por estudiante
-- (destino del correo de inasistencia / salida anticipada).
-- ───────────────────────────────────────────────────────────────────────────

-- Catálogo de grados (los 11 niveles). No se dan de alta desde la app: ver
-- api/app/core/grades.py y la migración a7c3e9f2b581.
-- El nivel 11 lleva id fijo porque el grupo 11A de más abajo lo referencia.
-- El conflicto se resuelve por (institution_id, level), no por id: en una BD
-- donde la migración ya los sembró, los ids son distintos y por id chocaría.
INSERT INTO grades (id, institution_id, name, level, created_at) VALUES
  (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000001', 'Primero', 1, NOW()),
  (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000001', 'Segundo', 2, NOW()),
  (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000001', 'Tercero', 3, NOW()),
  (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000001', 'Cuarto', 4, NOW()),
  (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000001', 'Quinto', 5, NOW()),
  (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000001', 'Sexto', 6, NOW()),
  (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000001', 'Séptimo', 7, NOW()),
  (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000001', 'Octavo', 8, NOW()),
  (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000001', 'Noveno', 9, NOW()),
  (gen_random_uuid(), 'a0000000-0000-0000-0000-000000000001', 'Décimo', 10, NOW()),
  ('d0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Once', 11, NOW())
ON CONFLICT (institution_id, level) DO NOTHING;

-- Grupo 11A, año académico 2026
INSERT INTO groups (id, institution_id, grade_id, name, academic_year, created_at)
VALUES ('e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'A', 2026, NOW())
ON CONFLICT (id) DO NOTHING;

-- Horario completo de 11A, lunes(1) a viernes(5), 6 periodos por día.
-- Solo period_order=1 (Primera hora, 07:00–07:50) dispara notificación al
-- acudiente; los periodos 2–6 se registran para historial (asistencia clase a
-- clase, scope 3.2). Los UUID de la primera hora (f0...001–005) se conservan;
-- los periodos 2–6 usan el prefijo f1... con el patrón ...00000000{0D}{0P}.
INSERT INTO class_periods (id, institution_id, group_id, name, period_order, start_time, end_time, day_of_week, created_at)
VALUES
  -- Lunes (1)
  ('f0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Primera hora',       1, '07:00:00', '07:50:00', 1, NOW()),
  ('f1000000-0000-0000-0000-000000000102', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Matemáticas',        2, '07:50:00', '08:40:00', 1, NOW()),
  ('f1000000-0000-0000-0000-000000000103', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Lenguaje',           3, '08:40:00', '09:30:00', 1, NOW()),
  ('f1000000-0000-0000-0000-000000000104', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Ciencias Naturales', 4, '10:00:00', '10:50:00', 1, NOW()),
  ('f1000000-0000-0000-0000-000000000105', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Ciencias Sociales',  5, '10:50:00', '11:40:00', 1, NOW()),
  ('f1000000-0000-0000-0000-000000000106', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Inglés',             6, '11:40:00', '12:30:00', 1, NOW()),
  -- Martes (2)
  ('f0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Primera hora',       1, '07:00:00', '07:50:00', 2, NOW()),
  ('f1000000-0000-0000-0000-000000000202', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Matemáticas',        2, '07:50:00', '08:40:00', 2, NOW()),
  ('f1000000-0000-0000-0000-000000000203', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Lenguaje',           3, '08:40:00', '09:30:00', 2, NOW()),
  ('f1000000-0000-0000-0000-000000000204', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Ciencias Naturales', 4, '10:00:00', '10:50:00', 2, NOW()),
  ('f1000000-0000-0000-0000-000000000205', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Ciencias Sociales',  5, '10:50:00', '11:40:00', 2, NOW()),
  ('f1000000-0000-0000-0000-000000000206', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Inglés',             6, '11:40:00', '12:30:00', 2, NOW()),
  -- Miércoles (3)
  ('f0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Primera hora',       1, '07:00:00', '07:50:00', 3, NOW()),
  ('f1000000-0000-0000-0000-000000000302', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Matemáticas',        2, '07:50:00', '08:40:00', 3, NOW()),
  ('f1000000-0000-0000-0000-000000000303', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Lenguaje',           3, '08:40:00', '09:30:00', 3, NOW()),
  ('f1000000-0000-0000-0000-000000000304', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Ciencias Naturales', 4, '10:00:00', '10:50:00', 3, NOW()),
  ('f1000000-0000-0000-0000-000000000305', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Ciencias Sociales',  5, '10:50:00', '11:40:00', 3, NOW()),
  ('f1000000-0000-0000-0000-000000000306', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Inglés',             6, '11:40:00', '12:30:00', 3, NOW()),
  -- Jueves (4)
  ('f0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Primera hora',       1, '07:00:00', '07:50:00', 4, NOW()),
  ('f1000000-0000-0000-0000-000000000402', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Matemáticas',        2, '07:50:00', '08:40:00', 4, NOW()),
  ('f1000000-0000-0000-0000-000000000403', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Lenguaje',           3, '08:40:00', '09:30:00', 4, NOW()),
  ('f1000000-0000-0000-0000-000000000404', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Ciencias Naturales', 4, '10:00:00', '10:50:00', 4, NOW()),
  ('f1000000-0000-0000-0000-000000000405', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Ciencias Sociales',  5, '10:50:00', '11:40:00', 4, NOW()),
  ('f1000000-0000-0000-0000-000000000406', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Inglés',             6, '11:40:00', '12:30:00', 4, NOW()),
  -- Viernes (5)
  ('f0000000-0000-0000-0000-000000000005', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Primera hora',       1, '07:00:00', '07:50:00', 5, NOW()),
  ('f1000000-0000-0000-0000-000000000502', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Matemáticas',        2, '07:50:00', '08:40:00', 5, NOW()),
  ('f1000000-0000-0000-0000-000000000503', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Lenguaje',           3, '08:40:00', '09:30:00', 5, NOW()),
  ('f1000000-0000-0000-0000-000000000504', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Ciencias Naturales', 4, '10:00:00', '10:50:00', 5, NOW()),
  ('f1000000-0000-0000-0000-000000000505', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Ciencias Sociales',  5, '10:50:00', '11:40:00', 5, NOW()),
  ('f1000000-0000-0000-0000-000000000506', 'a0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 'Inglés',             6, '11:40:00', '12:30:00', 5, NOW())
ON CONFLICT (id) DO NOTHING;

-- Catálogo de materias (subjects)
INSERT INTO subjects (id, institution_id, name, created_at)
VALUES
  ('d1000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Matemáticas', NOW()),
  ('d1000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'Ciencias Naturales', NOW())
-- Por (institution_id, name) y no por id: si esas materias ya se crearon desde
-- la consola tienen otro id, y el conflicto que salta es el de
-- `uq_subjects_institution_id_name`. Con `ON CONFLICT (id)` el seed abortaba
-- ahí y todo lo de más abajo no llegaba a ejecutarse.
ON CONFLICT (institution_id, name) DO NOTHING;

-- El docente demo (teacher@iedemo.edu.co) dicta la primera hora de 11A.
-- El operador PAE (pae@iedemo.edu.co) también está asignado a 11A: es un docente
-- con funciones extra del PAE, así que tiene horario, asistencia y convivencia.
INSERT INTO user_groups (id, user_id, group_id, academic_year, subject_id)
VALUES
  ('a1000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 2026, 'd1000000-0000-0000-0000-000000000001'),
  ('a1000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-000000000001', 2026, 'd1000000-0000-0000-0000-000000000002')
ON CONFLICT (id) DO NOTHING;

-- Los 4 estudiantes pertenecen a 11A en 2026
INSERT INTO student_groups (id, student_id, group_id, academic_year, is_active)
VALUES
  ('a2000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'e0000000-0000-0000-0000-000000000001', 2026, true),
  ('a2000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000002', 'e0000000-0000-0000-0000-000000000001', 2026, true),
  ('a2000000-0000-0000-0000-000000000003', 'c0000000-0000-0000-0000-000000000003', 'e0000000-0000-0000-0000-000000000001', 2026, true),
  ('a2000000-0000-0000-0000-000000000004', 'c0000000-0000-0000-0000-000000000004', 'e0000000-0000-0000-0000-000000000001', 2026, true)
ON CONFLICT (id) DO NOTHING;

-- Acudiente primario por estudiante (destino de las notificaciones).
-- En modo test de Resend (sin dominio verificado) solo se puede enviar al correo
-- dueño de la cuenta, así que los 4 apuntan a él para probar cualquier estudiante.
INSERT INTO guardians (id, student_id, full_name, relationship, email, phone, is_primary, created_at)
VALUES
  ('a3000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'Acudiente de Mariana',  'MADRE', 'pedrogomezl1805@gmail.com', NULL, true, NOW()),
  ('a3000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000002', 'Acudiente de Santiago', 'PADRE', 'pedrogomezl1805@gmail.com', NULL, true, NOW()),
  ('a3000000-0000-0000-0000-000000000003', 'c0000000-0000-0000-0000-000000000003', 'Acudiente de Valentina','MADRE', 'pedrogomezl1805@gmail.com', NULL, true, NOW()),
  ('a3000000-0000-0000-0000-000000000004', 'c0000000-0000-0000-0000-000000000004', 'Acudiente de Mateo',    'PADRE', 'pedrogomezl1805@gmail.com', NULL, true, NOW())
ON CONFLICT (id) DO NOTHING;

-- Artículos del manual de convivencia (para la vista Convivencia / agendatorio)
INSERT INTO convivencia_articles (id, institution_id, code, title, description, severity, is_active, created_at)
VALUES
  ('a4000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Art. 15', 'Uso del celular en clase', 'Uso de dispositivos móviles sin autorización durante la clase.', 'LEVE', true, NOW()),
  ('a4000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'Art. 22', 'Agresión verbal', 'Trato irrespetuoso o agresión verbal hacia un compañero o docente.', 'MODERADA', true, NOW()),
  ('a4000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'Art. 31', 'Agresión física', 'Agresión física a cualquier miembro de la comunidad educativa.', 'GRAVE', true, NOW())
ON CONFLICT (id) DO NOTHING;
