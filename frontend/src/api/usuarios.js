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
