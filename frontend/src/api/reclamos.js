import { crearRecursoApi } from './apiClient';

const reclamosApi = crearRecursoApi({ recursoPlural: 'reclamos', recursoSingular: 'reclamo' });

export const crearReclamo = reclamosApi.crear;
export const listarReclamos = reclamosApi.listar;
export const obtenerReclamo = reclamosApi.obtener;
export const actualizarReclamo = reclamosApi.actualizar;
export const eliminarReclamo = reclamosApi.eliminar;
