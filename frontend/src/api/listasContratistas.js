import { API_URL, crearRecursoApi, extraerMensajeError, fetchConAuth } from './apiClient';

const listasApi = crearRecursoApi({
  recursoPlural: 'listas-contratistas',
  recursoSingular: 'lista',
});

export const crearLista = listasApi.crear;
export const listarListas = listasApi.listar;
export const obtenerLista = listasApi.obtener;
export const actualizarLista = listasApi.actualizar;
export const eliminarLista = listasApi.eliminar;

/**
 * Lista los contratistas a los que se les solicitó presupuesto para un reclamo,
 * indicando si ya lo cargaron y el id del presupuesto.
 */
export async function listarSolicitudesPresupuesto(reclamoId) {
  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/solicitudes-presupuesto`);

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudieron cargar las solicitudes de presupuesto.'),
    );
  }

  return response.json();
}

export class ContratistasYaNotificadosError extends Error {
  constructor(yaNotificados) {
    super('Algunos contratistas ya fueron notificados para este reclamo.');
    this.yaNotificados = yaNotificados;
  }
}

/**
 * Notifica por WhatsApp a contratistas para que carguen presupuesto de un reclamo.
 * Enviar `contratista_ids` (selección manual) o `lista_id` (lista predefinida).
 *
 * Si alguno ya había sido notificado para el reclamo, no envía nada y lanza
 * `ContratistasYaNotificadosError`; para seguir, repetir con `yaNotificados` en
 * 'reenviar' u 'omitir'.
 */
export async function notificarContratistas(reclamoId, { contratistaIds, listaId, yaNotificados }) {
  const body = {};
  if (listaId != null) body.lista_id = listaId;
  if (contratistaIds != null) body.contratista_ids = contratistaIds;
  if (yaNotificados != null) body.ya_notificados = yaNotificados;

  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/notificar-contratistas`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    // Con el reclamo fuera de "pendiente de presupuesto" también responde 409, con un texto.
    if (response.status === 409 && Array.isArray(error?.detail?.ya_notificados)) {
      throw new ContratistasYaNotificadosError(error.detail.ya_notificados);
    }
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo enviar la notificación. Intente nuevamente.'),
    );
  }

  return response.json();
}
