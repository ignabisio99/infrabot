/**
 * Cuánto cambió un indicador contra el período anterior.
 *
 * `porcentaje` es null cuando no hay contra qué comparar (el anterior es cero o no
 * existe): un "+∞%" no dice nada, así que en ese caso sólo se informa la dirección.
 */
export function calcularVariacion(actual, anterior) {
  const a = actual === null ? null : Number(actual);
  const b = anterior === null ? null : Number(anterior);

  if (a === null || b === null) return { direccion: null, porcentaje: null };
  if (a === b) return { direccion: 'igual', porcentaje: 0 };

  const direccion = a > b ? 'sube' : 'baja';
  if (b === 0) return { direccion, porcentaje: null };

  return { direccion, porcentaje: Math.round(((a - b) / b) * 100) };
}

/**
 * Color de la variación según si para ese indicador subir es bueno (`mejorSi="sube"`),
 * malo (`"baja"`) o ninguna de las dos (sin `mejorSi`, por ejemplo los ingresados: que
 * entren más reclamos no es mérito ni culpa de nadie).
 */
export function colorVariacion(direccion, mejorSi) {
  if (!mejorSi || direccion === 'igual' || direccion === null) return 'gray';
  return direccion === mejorSi ? 'teal' : 'red';
}

export function textoVariacion({ direccion, porcentaje }) {
  if (direccion === null) return 'Sin datos para comparar';
  if (direccion === 'igual') return 'Sin cambios';

  const flecha = direccion === 'sube' ? '↑' : '↓';
  return porcentaje === null ? `${flecha} desde 0` : `${flecha} ${Math.abs(porcentaje)}%`;
}
