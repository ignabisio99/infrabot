import { API_URL, crearRecursoApi, extraerMensajeError, fetchConAuth } from './apiClient';

const presupuestosApi = crearRecursoApi({
  recursoPlural: 'presupuestos',
  recursoSingular: 'presupuesto',
});

export const crearPresupuesto = presupuestosApi.crear;
export const listarPresupuestos = presupuestosApi.listar;
export const obtenerPresupuesto = presupuestosApi.obtener;
export const actualizarPresupuesto = presupuestosApi.actualizar;
export const eliminarPresupuesto = presupuestosApi.eliminar;

export async function decidirPresupuesto(presupuestoId, estado, motivo) {
  const response = await fetchConAuth(`${API_URL}/presupuestos/${presupuestoId}/estado`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ estado, motivo: motivo || null }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo registrar la decisión sobre el presupuesto.'),
    );
  }

  return response.json();
}

export async function obtenerHistorialPresupuesto(presupuestoId) {
  const response = await fetchConAuth(`${API_URL}/presupuestos/${presupuestoId}/historial`);

  if (!response.ok) {
    throw new Error('No se pudo obtener el historial del presupuesto.');
  }

  return response.json();
}
