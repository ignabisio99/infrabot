import { API_URL, crearRecursoApi, extraerMensajeError, fetchConAuth } from './apiClient';

const contratistasApi = crearRecursoApi({
  recursoPlural: 'contratistas',
  recursoSingular: 'contratista',
});

export const crearContratista = contratistasApi.crear;
export const listarContratistas = contratistasApi.listar;
export const obtenerContratista = contratistasApi.obtener;
export const actualizarContratista = contratistasApi.actualizar;
export const eliminarContratista = contratistasApi.eliminar;

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
