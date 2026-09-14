import { API_URL, crearRecursoApi, extraerMensajeError, fetchConAuth } from './apiClient';

const reclamosApi = crearRecursoApi({ recursoPlural: 'reclamos', recursoSingular: 'reclamo' });

export const crearReclamo = reclamosApi.crear;
export const listarReclamos = reclamosApi.listar;
export const obtenerReclamo = reclamosApi.obtener;
export const actualizarReclamo = reclamosApi.actualizar;
export const eliminarReclamo = reclamosApi.eliminar;

export async function cambiarEstadoReclamo(reclamoId, estado, motivo) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/estado`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ estado, motivo: motivo || null }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo cambiar el estado del reclamo.'),
    );
  }

  return response.json();
}

export async function obtenerHistorialReclamo(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/historial`);

  if (!response.ok) {
    throw new Error('No se pudo obtener el historial del reclamo.');
  }

  return response.json();
}

export async function listarComentariosReclamo(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/comentarios`);

  if (!response.ok) {
    throw new Error('No se pudieron obtener los comentarios del reclamo.');
  }

  return response.json();
}

export async function crearComentarioReclamo(reclamoId, texto) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/comentarios`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texto }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo guardar el comentario.'));
  }

  return response.json();
}

/** Devuelve la coordinación de visita del reclamo, o null si no hay. */
export async function obtenerVisitaReclamo(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/visita`);

  if (!response.ok) {
    throw new Error('No se pudo obtener la visita del reclamo.');
  }

  return response.json();
}

export async function subirFotoReclamo(reclamoId, archivo) {
  const formData = new FormData();
  formData.append('archivo', archivo);

  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/fotos`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo subir el archivo. Intente nuevamente.'),
    );
  }

  return response.json();
}

export async function eliminarFotoReclamo(reclamoId, fotoId) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/fotos/${fotoId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo eliminar el archivo.'));
  }
}
