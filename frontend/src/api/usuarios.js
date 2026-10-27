import { API_URL, extraerMensajeError, fetchConAuth } from './apiClient';

/** Lista los usuarios pendientes de aprobación (solo admins). */
export async function listarUsuariosPendientes() {
  const response = await fetchConAuth(`${API_URL}/auth/pendientes`);

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudieron cargar las solicitudes pendientes.'),
    );
  }

  return response.json();
}

/** Lista los administradores con la cuenta aprobada (solo admins). */
export async function listarAdministradores() {
  const response = await fetchConAuth(`${API_URL}/auth/administradores`);

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudieron cargar los administradores.'),
    );
  }

  return response.json();
}

/** Lista los inspectores con la cuenta aprobada (solo admins). */
export async function listarInspectores() {
  const response = await fetchConAuth(`${API_URL}/auth/inspectores`);

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudieron cargar los inspectores.'));
  }

  return response.json();
}
