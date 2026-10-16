export const formatoMoneda = new Intl.NumberFormat('es-AR', {
  style: 'currency',
  currency: 'ARS',
});

export const formatoNumero = new Intl.NumberFormat('es-AR', { minimumFractionDigits: 2 });

const formatoHora = new Intl.DateTimeFormat('es-AR', { hour: '2-digit', minute: '2-digit' });

export function formatoHoraMensaje(fecha) {
  if (!fecha) return '';
  const date = fecha instanceof Date ? fecha : new Date(fecha);
  if (Number.isNaN(date.getTime())) return '';
  return formatoHora.format(date);
}
