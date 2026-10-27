import { API_URL, extraerMensajeError } from './apiClient';

export async function login(email, password) {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'Email o contraseña incorrectos'));
  }

  return response.json();
}

export async function register({
  nombre,
  email,
  password,
  telefono,
  direccion,
  tipo,
  nombre_empresa,
  especialidad,
}) {
  const response = await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      nombre,
      email,
      password,
      telefono,
      direccion,
      tipo,
      nombre_empresa,
      especialidad,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo crear la cuenta'));
  }

  return response.json();
}

export async function loginWithGoogle(credential) {
  const response = await fetch(`${API_URL}/auth/google`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'Error al iniciar sesión con Google'));
  }

  return response.json();
}

export async function logout() {
  await fetch(`${API_URL}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  });
}

export async function getMe(signal) {
  const response = await fetch(`${API_URL}/auth/me`, {
    credentials: 'include',
    signal,
  });

  if (response.status === 401) return null;
  if (!response.ok) throw new Error('No se pudo verificar la sesión');
  return response.json();
}

export async function actualizarPerfil(datos) {
  const response = await fetch(`${API_URL}/auth/me`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo guardar el perfil'));
  }

  return response.json();
}

/** Pide el email con el link para restablecer la contraseña. Responde igual exista o no la cuenta. */
export async function pedirRestablecerPassword(email) {
  const response = await fetch(`${API_URL}/auth/olvide-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo enviar el email. Intentá de nuevo.'),
    );
  }

  return response.json();
}

/** Verifica que el link del email siga sirviendo. Devuelve el email de la cuenta. */
export async function validarLinkRestablecer(token) {
  const response = await fetch(
    `${API_URL}/auth/restablecer-password?token=${encodeURIComponent(token)}`,
  );

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'El link no es válido o ya venció.'));
  }

  return response.json();
}

export async function restablecerPassword(token, password) {
  const response = await fetch(`${API_URL}/auth/restablecer-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, password }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo cambiar la contraseña.'));
  }

  return response.json();
}
