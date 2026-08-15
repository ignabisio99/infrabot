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

export async function register({ nombre, email, password, telefono, direccion, tipo, nombre_empresa, especialidad }) {
  const response = await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nombre, email, password, telefono, direccion, tipo, nombre_empresa, especialidad }),
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

export async function getMe() {
  const response = await fetch(`${API_URL}/auth/me`, {
    credentials: 'include',
  });

  if (!response.ok) return null;
  return response.json();
}
