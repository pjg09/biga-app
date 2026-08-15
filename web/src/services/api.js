const BASE = import.meta.env.VITE_API_URL;

function getToken() {
  return localStorage.getItem('token');
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw Object.assign(new Error(err.detail ?? 'Error de servidor'), { status: res.status });
  }

  if (res.status === 204) return null;  // No Content (ej. archive/unarchive)
  return res.json();
}

async function requestForm(path, formData) {
  // No fijar Content-Type: el browser pone el boundary del multipart.
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${getToken()}` },
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw Object.assign(new Error(err.detail ?? 'Error de servidor'), { status: res.status });
  }

  return res.json();
}

// Endpoints públicos (landing, justificación): sin Authorization. Mandar
// `Bearer null` desde un visitante anónimo no rompe nada, pero ensucia los logs
// y sugiere una sesión que no existe.
async function requestPublic(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw Object.assign(new Error(err.detail ?? 'Error de servidor'), { status: res.status });
  }

  return res.json();
}

// Multipart sin Authorization: lo usa el acudiente desde el enlace temporal,
// que no tiene sesión. No se fija Content-Type — el browser pone el boundary.
async function requestFormPublic(path, formData) {
  const res = await fetch(`${BASE}${path}`, { method: 'POST', body: formData });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = Array.isArray(err.detail)
      ? (err.detail[0]?.msg ?? 'Datos inválidos')   // errores de validación de FastAPI
      : err.detail;
    throw Object.assign(new Error(detail ?? 'Error de servidor'), { status: res.status });
  }

  return res.json();
}

export const api = {
  get:  (path)       => request(path),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) }),
  put:  (path, body) => request(path, { method: 'PUT', body: JSON.stringify(body) }),
  patch:(path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body) }),
  postForm: (path, formData) => requestForm(path, formData),
  postPublic: (path, body) => requestPublic(path, { method: 'POST', body: JSON.stringify(body) }),
  postFormPublic: (path, formData) => requestFormPublic(path, formData),
};
