import { API_URL, extraerMensajeError, fetchConAuth } from './apiClient';

async function leerJson(response, mensajePorDefecto) {
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, mensajePorDefecto));
  }
  return response.json();
}

export async function obtenerUmbralesAuditoria() {
  const response = await fetchConAuth(`${API_URL}/configuracion/auditoria`);
  return leerJson(response, 'No se pudieron obtener los umbrales de auditoría.');
}

export async function actualizarUmbralesAuditoria({ umbralAprobar, umbralRevisar }) {
  const response = await fetchConAuth(`${API_URL}/configuracion/auditoria`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      umbral_aprobar: umbralAprobar,
      umbral_revisar: umbralRevisar,
    }),
  });
  return leerJson(response, 'No se pudieron guardar los umbrales de auditoría.');
}
