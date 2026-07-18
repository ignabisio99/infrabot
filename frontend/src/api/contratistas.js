import { crearRecursoApi } from './apiClient';

const contratistasApi = crearRecursoApi({
  recursoPlural: 'contratistas',
  recursoSingular: 'contratista',
});

export const crearContratista = contratistasApi.crear;
export const listarContratistas = contratistasApi.listar;
export const obtenerContratista = contratistasApi.obtener;
export const actualizarContratista = contratistasApi.actualizar;
export const eliminarContratista = contratistasApi.eliminar;
