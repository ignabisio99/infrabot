import { API_URL, extraerMensajeError, fetchConAuth } from './apiClient';

async function leerJson(response, mensajePorDefecto) {
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, mensajePorDefecto));
  }
  return response.json();
}

export async function obtenerEstadoSimulador() {
  const response = await fetchConAuth(`${API_URL}/simulador-tiempo/estado`);
  return leerJson(response, 'No se pudo obtener el estado del simulador de tiempo.');
}

export async function avanzarTiempo({
  horas = 0,
  dias = 0,
  hasta_proxima_visita = false,
  horas_despues_visita = 0.1,
} = {}) {
  const response = await fetchConAuth(`${API_URL}/simulador-tiempo/avanzar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      horas,
      dias,
      hasta_proxima_visita,
      horas_despues_visita,
    }),
  });
  return leerJson(response, 'No se pudo avanzar el tiempo simulado.');
}

export async function resetearTiempo() {
  const response = await fetchConAuth(`${API_URL}/simulador-tiempo/reset`, {
    method: 'POST',
  });
  return leerJson(response, 'No se pudo resetear el tiempo.');
}

export async function obtenerMensajesSalientes(destinatario = null, limite = 50) {
  const params = new URLSearchParams();
  if (destinatario) params.append('destinatario', destinatario);
  params.append('limite', String(limite));

  const response = await fetchConAuth(`${API_URL}/simulador-tiempo/mensajes?${params.toString()}`);
  return leerJson(response, 'No se pudieron obtener los mensajes enviados.');
}

