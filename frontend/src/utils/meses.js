// El backend manda los meses como "YYYY-MM" (ver backend/api/dashboard.py). Los nombres
// van a mano y no con dayjs para no depender de que el locale global esté configurado.
const MESES = [
  'enero',
  'febrero',
  'marzo',
  'abril',
  'mayo',
  'junio',
  'julio',
  'agosto',
  'septiembre',
  'octubre',
  'noviembre',
  'diciembre',
];

/** "2026-09" → "septiembre" */
export function nombreMes(clave) {
  return MESES[Number(clave.split('-')[1]) - 1];
}

/** "2026-09" → "sep 26", para los ejes de los gráficos. */
export function mesCorto(clave) {
  const [anio, mes] = clave.split('-');
  return `${MESES[Number(mes) - 1].slice(0, 3)} ${anio.slice(2)}`;
}
