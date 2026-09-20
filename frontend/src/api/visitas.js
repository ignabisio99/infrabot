import { API_URL, extraerMensajeError, fetchConAuth } from './apiClient';

export async function listarVisitas() {
  const response = await fetchConAuth(`${API_URL}/visitas`);

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudieron obtener las visitas.'));
  }

  return response.json();
}
