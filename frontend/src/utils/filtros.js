// Los valores del DatePickerInput llegan como string "YYYY-MM-DD". Parsearlos con
// `new Date(string)` los interpreta como medianoche UTC y desfasa el día en timezones
// negativos (ej. UTC-3), por eso se arman a mano como fecha local.
export function parsearFechaFiltro(valor) {
  if (!valor) return null;
  const [anio, mes, dia] = valor.split('-').map(Number);
  return new Date(anio, mes - 1, dia);
}

// `rango` es el valor del DatePickerInput type="range"; el último día se incluye entero.
export function fechaEnRango(fecha, rango) {
  const desde = parsearFechaFiltro(rango[0]);
  const hasta = parsearFechaFiltro(rango[1]);
  const valor = new Date(fecha);
  if (desde && valor < desde) return false;
  if (hasta) {
    const finDia = new Date(hasta);
    finDia.setHours(23, 59, 59, 999);
    if (valor > finDia) return false;
  }
  return true;
}

export const normalizarTexto = (texto) =>
  (texto || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();

// Acepta "34", "0034", "REC-00000034", etc: se queda solo con los dígitos
// escritos y busca esa subcadena dentro del ID completo (con ceros a la izquierda).
export function idCoincideConBusqueda(id, busqueda) {
  const digitos = busqueda.replace(/\D/g, '');
  if (!digitos) return true;
  return String(id).padStart(8, '0').includes(digitos);
}
