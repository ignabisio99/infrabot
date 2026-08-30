// Espejo de EstadoPresupuesto del backend (backend/models/presupuesto.py). El backend es
// el que valida las transiciones; acá sólo definimos cómo se muestran.

export const ESTADOS = ['RECIBIDO', 'APROBADO', 'RECHAZADO', 'NO_SELECCIONADO'];

export const etiquetaPorEstado = {
  RECIBIDO: 'Recibido',
  APROBADO: 'Aprobado',
  RECHAZADO: 'Rechazado',
  NO_SELECCIONADO: 'No seleccionado',
};

export const colorPorEstado = {
  RECIBIDO: 'blue',
  APROBADO: 'green',
  RECHAZADO: 'red',
  // Gris y no rojo: no se lo juzgó, ganó otro.
  NO_SELECCIONADO: 'gray',
};

// Espejo de ESTADOS_CON_MOTIVO_OBLIGATORIO en backend/services/estados_presupuesto.py.
// Es sólo para avisar antes de mandar el request; el backend igual lo rechaza.
export const estadosConMotivoObligatorio = ['RECHAZADO'];

export function requiereMotivo(estado) {
  return estadosConMotivoObligatorio.includes(estado);
}

export const textoMotivoPorEstado = {
  RECHAZADO: {
    label: 'Motivo del rechazo',
    placeholder: 'Ej: supera el presupuesto disponible para la obra',
  },
};

export function estaVigente(presupuesto) {
  return presupuesto.estado === 'RECIBIDO';
}
