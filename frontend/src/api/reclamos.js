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

/** Cambios de estado de los presupuestos del reclamo, para la línea de tiempo. Solo admins. */
export async function obtenerMovimientosPresupuestos(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/movimientos-presupuestos`);

  if (!response.ok) {
    throw new Error('No se pudieron obtener los movimientos de los presupuestos del reclamo.');
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

export async function reabrirConvocatoria(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/reabrir-convocatoria`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo cancelar el presupuesto y volver a convocar.'),
    );
  }
  return response.json();
}

export async function listarOfertasReutilizables(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/ofertas-reutilizables`);
  if (!response.ok) {
    throw new Error('No se pudieron cargar las ofertas ya enviadas.');
  }
  return response.json();
}

export async function asignarOfertaExistente(reclamoId, presupuestoId) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/asignar-oferta-existente`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ presupuesto_id: presupuestoId }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo asignar esa oferta.'));
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

/** Pide a inspectores información adicional del reclamo (WhatsApp, email y aviso en la app). */
export async function notificarInspectores(reclamoId, { inspectorIds, mensaje }) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/notificar-inspectores`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ inspector_ids: inspectorIds, mensaje: mensaje || null }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo avisar a los inspectores. Intentá de nuevo.'),
    );
  }

  return response.json();
}

/** Pedidos de información del reclamo: todos para el admin, los propios para el inspector. */
export async function listarSolicitudesInspeccion(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/solicitudes-inspeccion`);

  if (!response.ok) {
    throw new Error('No se pudieron obtener los pedidos de información del reclamo.');
  }

  return response.json();
}

/** Reclamos en los que le pidieron información al inspector logueado y todavía no aportó nada. */
export async function listarMisPedidosInspeccion() {
  const response = await fetchConAuth(`${API_URL}/reclamos/inspeccion/pendientes`);

  if (!response.ok) {
    throw new Error('No se pudieron obtener tus pedidos de información.');
  }

  return response.json();
}
