// Mismo umbral que DIAS_SIN_MOVIMIENTO del dashboard (backend/api/dashboard.py).
export const DIAS_ESTANCADO = 7;

// Escalones de antigüedad. Un reclamo abierto hace un mes sin que nadie lo toque es un
// problema distinto a uno que lleva ocho días.
export function colorAntiguedad(dias) {
  if (dias >= 30) return 'red';
  if (dias >= 14) return 'orange';
  return 'gray';
}
