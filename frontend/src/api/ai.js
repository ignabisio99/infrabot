import { API_URL, extraerMensajeError, fetchConAuth } from './apiClient';

async function leerJson(response, mensajePorDefecto) {
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, mensajePorDefecto));
  }
  return response.json();
}

export async function clasificarReclamo(reclamoId, { aplicar = false } = {}) {
  const response = await fetchConAuth(
    `${API_URL}/ai/reclamos/${reclamoId}/clasificar?aplicar=${aplicar}`,
    { method: 'POST' },
  );
  return leerJson(response, 'No se pudo clasificar el reclamo.');
}

export async function buscarDuplicados(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/ai/reclamos/${reclamoId}/duplicados`);
  return leerJson(response, 'No se pudieron buscar duplicados.');
}

export async function crearEstimacion(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/ai/reclamos/${reclamoId}/estimacion`, {
    method: 'POST',
  });
  return leerJson(response, 'No se pudo generar la estimación preliminar.');
}

export async function obtenerEstimacion(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/ai/reclamos/${reclamoId}/estimacion`);
  if (response.status === 404) return null;
  return leerJson(response, 'No se pudo obtener la estimación preliminar.');
}

export async function analizarMediaReclamo(reclamoId, { enriquecerDescripcion = false } = {}) {
  const response = await fetchConAuth(
    `${API_URL}/ai/reclamos/${reclamoId}/analizar-media?enriquecer_descripcion=${enriquecerDescripcion}`,
    { method: 'POST' },
  );
  return leerJson(response, 'No se pudieron analizar las fotos del reclamo.');
}

export async function listarRecomendaciones({ reclamoId } = {}) {
  const query = reclamoId != null ? `?reclamo_id=${reclamoId}` : '';
  const response = await fetchConAuth(`${API_URL}/ai/recomendaciones${query}`);
  return leerJson(response, 'No se pudieron listar las recomendaciones.');
}

export async function obtenerAuditoria(presupuestoId) {
  const response = await fetchConAuth(`${API_URL}/ai/presupuestos/${presupuestoId}/auditoria`);
  if (response.status === 404) return null;
  return leerJson(response, 'No se pudo obtener la auditoría del presupuesto.');
}

export async function auditarPresupuesto(presupuestoId) {
  const response = await fetchConAuth(`${API_URL}/ai/presupuestos/${presupuestoId}/auditar`, {
    method: 'POST',
  });
  return leerJson(response, 'No se pudo auditar el presupuesto.');
}

export async function sugerirContratistas(reclamoId) {
  const response = await fetchConAuth(
    `${API_URL}/ai/reclamos/${reclamoId}/contratistas-sugeridos`,
  );
  return leerJson(response, 'No se pudieron obtener contratistas sugeridos.');
}

export async function orquestarReclamo(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/ai/reclamos/${reclamoId}/orquestar`, {
    method: 'POST',
  });
  return leerJson(response, 'No se pudo ejecutar el pipeline de IA.');
}

export async function ejecutarSeguimiento() {
  const response = await fetchConAuth(`${API_URL}/ai/seguimiento/ejecutar`, {
    method: 'POST',
  });
  return leerJson(response, 'No se pudo ejecutar el seguimiento a contratistas.');
}
