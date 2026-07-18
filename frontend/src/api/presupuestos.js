import { crearRecursoApi } from './apiClient';

const presupuestosApi = crearRecursoApi({
  recursoPlural: 'presupuestos',
  recursoSingular: 'presupuesto',
});

export const crearPresupuesto = presupuestosApi.crear;
export const listarPresupuestos = presupuestosApi.listar;
export const obtenerPresupuesto = presupuestosApi.obtener;
export const actualizarPresupuesto = presupuestosApi.actualizar;
export const eliminarPresupuesto = presupuestosApi.eliminar;
