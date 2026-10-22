import { API_URL, fetchConAuth } from './apiClient';

/**
 * Trae todo lo que muestra el Dashboard en una sola llamada (ver backend/api/dashboard.py).
 * `prioridad` y `categoria` vacías no se mandan: sin filtro es "todas".
 */
export async function obtenerResumenDashboard({ periodo, prioridad, categoria } = {}) {
  const params = new URLSearchParams();
  if (periodo) params.set('periodo', periodo);
  if (prioridad) params.set('prioridad', prioridad);
  if (categoria) params.set('categoria', categoria);

  const query = params.toString();
  const response = await fetchConAuth(`${API_URL}/dashboard/resumen${query ? `?${query}` : ''}`);

  if (!response.ok) {
    throw new Error('No se pudo obtener el resumen del dashboard.');
  }

  return response.json();
}
