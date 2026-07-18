export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export function extraerMensajeError(detail, mensajePorDefecto) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return mensajePorDefecto;
}
