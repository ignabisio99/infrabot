import { API_URL, extraerMensajeError, fetchConAuth } from './apiClient';

export async function conteoNotificaciones() {
  const response = await fetchConAuth(`${API_URL}/notificaciones/conteo`);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo contar las notificaciones.'));
  }
  return response.json();
}
