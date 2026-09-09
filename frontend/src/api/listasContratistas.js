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
  const response = await fetchConAuth(
    `${API_URL}/reclamos/${reclamoId}/solicitudes-presupuesto`,
  );

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudieron cargar las solicitudes de presupuesto.'),
    );
  }

  return response.json();
}

/**
 * Notifica por WhatsApp a contratistas para que carguen presupuesto de un reclamo.
 * Enviar `contratista_ids` (selección manual) o `lista_id` (lista predefinida).
 */
export async function notificarContratistas(reclamoId, { contratistaIds, listaId }) {
  const body = {};
  if (listaId != null) body.lista_id = listaId;
  if (contratistaIds != null) body.contratista_ids = contratistaIds;

  const response = await fetchConAuth(`${API_URL}/reclamos/${reclamoId}/notificar-contratistas`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo enviar la notificación. Intente nuevamente.'),
    );
  }

  return response.json();
}
