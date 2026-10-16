import { API_URL, extraerMensajeError, fetchConAuth } from './apiClient';

async function leerJson(response, mensajePorDefecto) {
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, mensajePorDefecto));
  }
  return response.json();
}

export async function listarHistorial(limit = 50, offset = 0) {
  const response = await fetchConAuth(
    `${API_URL}/conversaciones/historial?limit=${limit}&offset=${offset}`,
  );
  return leerJson(response, 'No se pudo cargar el historial de chats.');
}

export async function historialPorTelefono(telefono, { limit = 30, antesDe } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (antesDe) params.set('antes_de', String(antesDe));
  const response = await fetchConAuth(
    `${API_URL}/conversaciones/telefono/${encodeURIComponent(telefono)}/historial?${params}`,
  );
  return leerJson(response, 'No se pudo cargar el chat de este número.');
}

export async function reabrirConversacion(convId) {
  const response = await fetchConAuth(`${API_URL}/conversaciones/${convId}/reabrir`, {
    method: 'POST',
  });
  return leerJson(response, 'No se pudo reabrir la conversación.');
}

export async function obtenerBandeja() {
  const response = await fetchConAuth(`${API_URL}/conversaciones/bandeja`);
  return leerJson(response, 'No se pudo cargar la bandeja de chats.');
}

export async function listarOperadores() {
  const response = await fetchConAuth(`${API_URL}/conversaciones/operadores`);
  return leerJson(response, 'No se pudieron cargar los operadores.');
}

export async function listarMensajes(convId, despuesDe) {
  const qs = despuesDe ? `?despues_de=${despuesDe}` : '';
  const response = await fetchConAuth(`${API_URL}/conversaciones/${convId}/mensajes${qs}`);
  return leerJson(response, 'No se pudieron cargar los mensajes.');
}

export async function tomarConversacion(convId) {
  const response = await fetchConAuth(`${API_URL}/conversaciones/${convId}/tomar`, {
    method: 'POST',
  });
  return leerJson(response, 'No se pudo tomar la conversación.');
}

export async function liberarConversacion(convId) {
  const response = await fetchConAuth(`${API_URL}/conversaciones/${convId}/liberar`, {
    method: 'POST',
  });
  return leerJson(response, 'No se pudo liberar la conversación.');
}

export async function cerrarConversacion(convId) {
  const response = await fetchConAuth(`${API_URL}/conversaciones/${convId}/cerrar`, {
    method: 'POST',
  });
  return leerJson(response, 'No se pudo cerrar la conversación.');
}

export async function transferirConversacion(convId, operadorId) {
  const response = await fetchConAuth(`${API_URL}/conversaciones/${convId}/transferir`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operador_id: operadorId }),
  });
  return leerJson(response, 'No se pudo transferir la conversación.');
}

export async function enviarMensajeOperador(convId, texto) {
  const response = await fetchConAuth(`${API_URL}/conversaciones/${convId}/mensajes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texto }),
  });
  return leerJson(response, 'No se pudo enviar el mensaje.');
}

export function abrirStreamConversaciones() {
  return new EventSource(`${API_URL}/conversaciones/stream`, { withCredentials: true });
}
