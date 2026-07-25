export const formatoMoneda = new Intl.NumberFormat('es-AR', {
  style: 'currency',
  currency: 'ARS',
});

export const formatoNumero = new Intl.NumberFormat('es-AR', { minimumFractionDigits: 2 });
