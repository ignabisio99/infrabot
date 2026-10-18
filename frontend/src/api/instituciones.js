import { API_URL, extraerMensajeError, fetchConAuth } from './apiClient';

export async function buscarInstituciones(consulta) {
  const params = new URLSearchParams({ q: consulta });
  const response = await fetchConAuth(`${API_URL}/instituciones?${params}`);

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo buscar en el padrón de escuelas.'),
    );
  }

  return response.json();
}
