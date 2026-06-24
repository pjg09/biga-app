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

export const api = {
  get:  (path)       => request(path),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) }),
  patch:(path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body) }),
  postForm: (path, formData) => requestForm(path, formData),
};
