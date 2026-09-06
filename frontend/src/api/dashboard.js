import { API_URL, fetchConAuth } from './apiClient';

/** Trae todo lo que muestra el Dashboard en una sola llamada (ver backend/api/dashboard.py). */
export async function obtenerResumenDashboard() {
  const response = await fetchConAuth(`${API_URL}/dashboard/resumen`);

  if (!response.ok) {
    throw new Error('No se pudo obtener el resumen del dashboard.');
  }

  return response.json();
}
