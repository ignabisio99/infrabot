import { API_URL, extraerMensajeError, fetchConAuth } from './apiClient';

function construirQuery({ desde, hasta, estado } = {}) {
  const params = new URLSearchParams();
  if (desde) params.set('desde', desde);
  if (hasta) params.set('hasta', hasta);
  if (estado) params.set('estado', estado);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

/** Trae los datos del reporte (JSON) para previsualizar en pantalla. */
export async function obtenerReporte(tipo, filtros = {}) {
  const response = await fetchConAuth(`${API_URL}/reportes/${tipo}${construirQuery(filtros)}`);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo generar el reporte.'));
  }
  return response.json();
}

/** Descarga el reporte como CSV, disparando la descarga en el navegador. */
export async function descargarReporteCsv(tipo, filtros = {}) {
  const response = await fetchConAuth(
    `${API_URL}/reportes/${tipo}/csv${construirQuery(filtros)}`,
  );
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo descargar el reporte.'));
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `reporte_${tipo}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
