import { API_URL, fetchConAuth } from './apiClient';

export async function listarVisitas() {
  const response = await fetchConAuth(`${API_URL}/visitas`);

  if (!response.ok) {
    throw new Error('No se pudieron obtener las visitas.');
  }

  return response.json();
}