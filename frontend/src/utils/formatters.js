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

const formatoFechaHora = new Intl.DateTimeFormat('es-AR', {
  day: 'numeric',
  month: 'numeric',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

export const formatoFechaHoraCorta = (fecha) => formatoFechaHora.format(new Date(fecha));

export function fechaRelativa(fecha, ahora = new Date()) {
  const date = new Date(fecha);
  const minutos = Math.floor((ahora - date) / 60000);
  if (minutos < 1) return 'recién';
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  const dias = Math.floor(horas / 24);
  if (dias < 30) return dias === 1 ? 'hace 1 día' : `hace ${dias} días`;
  return date.toLocaleDateString('es-AR');
}
