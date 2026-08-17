// Espejo de EstadoReclamo del backend (backend/models/reclamo.py). El backend es el
// que valida las transiciones; acá sólo definimos cómo se muestran y qué habilitar.

export const ESTADOS = [
  'PENDIENTE_REVISION',
  'PENDIENTE_PRESUPUESTO',
  'EN_EVALUACION',
  'APROBADO',
  'EN_EJECUCION',
  'FINALIZADO',
  'DESIERTO',
  'RECHAZADO',
  'CANCELADO',
];

export const etiquetaPorEstado = {
  PENDIENTE_REVISION: 'Pendiente de revisión',
  PENDIENTE_PRESUPUESTO: 'Pendiente de presupuesto',
  EN_EVALUACION: 'En evaluación',
  APROBADO: 'Aprobado',
  EN_EJECUCION: 'En ejecución',
  FINALIZADO: 'Finalizado',
  DESIERTO: 'Desierto',
  RECHAZADO: 'Rechazado',
  CANCELADO: 'Cancelado',
};

export const colorPorEstado = {
  PENDIENTE_REVISION: 'gray',
  PENDIENTE_PRESUPUESTO: 'orange',
  EN_EVALUACION: 'blue',
  APROBADO: 'teal',
  EN_EJECUCION: 'indigo',
  FINALIZADO: 'green',
  DESIERTO: 'yellow',
  RECHAZADO: 'red',
  CANCELADO: 'dark',
};

// Espejo de ESTADOS_CON_MOTIVO_OBLIGATORIO en backend/services/estados_reclamo.py.
// Es sólo para avisar antes de mandar el request; el backend igual lo rechaza.
export const estadosConMotivoObligatorio = ['RECHAZADO', 'CANCELADO', 'DESIERTO'];

export function requiereMotivo(estado) {
  return estadosConMotivoObligatorio.includes(estado);
}

// Copy del campo de texto según el estado destino. Sólo los estados que cortan el
// flujo piden una justificación concreta; en el resto el texto es un comentario
// suelto, así que no corresponde sugerir un ejemplo de "motivo".
export const textoMotivoPorEstado = {
  RECHAZADO: {
    label: 'Motivo del rechazo',
    placeholder: 'Ej: duplicado del reclamo REC-00000002',
  },
  CANCELADO: {
    label: 'Motivo de la cancelación',
    placeholder: 'Ej: la escuela resolvió el arreglo por su cuenta',
  },
  DESIERTO: {
    label: 'Motivo',
    placeholder: 'Ej: ningún contratista cotizó dentro del plazo de 15 días',
  },
};

export const proximoPasoPorEstado = {
  PENDIENTE_REVISION: {
    titulo: 'Revisar el reclamo',
    descripcion: 'Validar que el reclamo corresponde y mandarlo a pedir presupuestos.',
  },
  PENDIENTE_PRESUPUESTO: {
    titulo: 'Esperando presupuestos',
    descripcion: 'Todavía no cargó ningún contratista un presupuesto para este reclamo.',
  },
  EN_EVALUACION: {
    titulo: 'Evaluar presupuestos',
    descripcion: 'Comparar los presupuestos recibidos y aprobar uno.',
  },
  APROBADO: {
    titulo: 'Coordinación de trabajo',
    descripcion: 'Coordinar con el contratista la fecha de inicio de la obra.',
  },
  EN_EJECUCION: {
    titulo: 'Obra en curso',
    descripcion: 'Verificar el avance y dar por finalizado el trabajo cuando esté listo.',
  },
  FINALIZADO: {
    titulo: 'Reclamo finalizado',
    descripcion: 'El trabajo se completó. No quedan acciones pendientes.',
  },
  DESIERTO: {
    titulo: 'Sin ofertas',
    descripcion: 'Ningún contratista cotizó. Se puede volver a llamar a presupuesto.',
  },
  RECHAZADO: {
    titulo: 'Reclamo rechazado',
    descripcion: 'El reclamo se descartó en la revisión inicial.',
  },
  CANCELADO: {
    titulo: 'Reclamo cancelado',
    descripcion: 'El reclamo se dio de baja antes de completarse.',
  },
};
