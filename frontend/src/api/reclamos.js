import { API_URL, crearRecursoApi, extraerMensajeError, fetchConAuth } from './apiClient';

const reclamosApi = crearRecursoApi({ recursoPlural: 'reclamos', recursoSingular: 'reclamo' });

export const crearReclamo = reclamosApi.crear;
export const listarReclamos = reclamosApi.listar;
export const obtenerReclamo = reclamosApi.obtener;
export const actualizarReclamo = reclamosApi.actualizar;
export const eliminarReclamo = reclamosApi.eliminar;

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
