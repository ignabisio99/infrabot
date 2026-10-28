import { API_URL, crearRecursoApi, extraerMensajeError, fetchConAuth } from './apiClient';

const contratistasApi = crearRecursoApi({
  recursoPlural: 'contratistas',
  recursoSingular: 'contratista',
});

export const crearContratista = contratistasApi.crear;
export const obtenerContratista = contratistasApi.obtener;
export const actualizarContratista = contratistasApi.actualizar;

/** Sin `incluirBaja`, sólo los activos: los que se pueden convocar. */
export async function listarContratistas({ incluirBaja = false } = {}) {
  const query = incluirBaja ? '?incluir_baja=true' : '';
  const response = await fetchConAuth(`${API_URL}/contratistas${query}`);
  if (!response.ok) {
    throw new Error('No se pudo obtener el listado de contratistas.');
  }
  return response.json();
}

/** No lo borra: deja de aparecer para convocar y conserva su historial. */
export async function darDeBajaContratista(id) {
  const response = await fetchConAuth(`${API_URL}/contratistas/${id}`, { method: 'DELETE' });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo dar de baja al contratista.'));
  }
}

export async function reactivarContratista(id) {
  const response = await fetchConAuth(`${API_URL}/contratistas/${id}/reactivar`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo reactivar al contratista.'));
  }
  return response.json();
}

/**
 * Devuelve la ficha de Contratista vinculada al usuario logueado.
 * Lanza error si la cuenta no está vinculada a ninguna ficha.
 */
export async function obtenerMiFicha() {
  const response = await fetchConAuth(`${API_URL}/contratistas/mi-ficha`);

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo obtener tu ficha de contratista.'),
    );
  }

  return response.json();
}

/**
 * El contratista pide información adicional sobre un reclamo.
 * El bot reenvía el mensaje por WhatsApp a quien creó el reclamo.
 */
export async function solicitarInformacionReclamo(reclamoId, mensaje) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/solicitar-informacion`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mensaje }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo enviar la solicitud de información.'),
    );
  }

  return response.json();
}

/** Reclamos donde el contratista logueado fue convocado a presupuestar. */
export async function listarMisSolicitudes() {
  const response = await fetchConAuth(`${API_URL}/contratistas/mis-solicitudes`);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudieron cargar tus solicitudes.'));
  }
  return response.json();
}

/** Presupuestos cargados por el contratista logueado. */
export async function listarMisPresupuestos() {
  const response = await fetchConAuth(`${API_URL}/contratistas/mis-presupuestos`);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudieron cargar tus presupuestos.'));
  }
  return response.json();
}

/** Último presupuesto del contratista logueado para el reclamo, o null si no cargó ninguno. */
export async function obtenerMiPresupuesto(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/contratistas/mi-presupuesto/${reclamoId}`);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo cargar tu presupuesto.'));
  }
  return response.json();
}
