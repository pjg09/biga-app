# Credenciales del seed dev

Usuarios creados por `scripts/seed_dev_users.sql` (correr después de `alembic upgrade head`). Todos usan la contraseña `password123` y pertenecen a la institución demo `a0000000-0000-0000-0000-000000000001`.

Email	Contraseña	Rol	Redirige a
teacher@iedemo.edu.co	password123	TEACHER	/dashboard/teacher
pae@iedemo.edu.co	password123	PAE_OPERATOR	/dashboard/pae
admin@iedemo.edu.co	password123	ADMIN	/dashboard/admin