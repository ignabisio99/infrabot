// Los 12 estados agrupados por etapa del flujo, para la dona y el tiempo por etapa. Las
// tres abiertas son espejo de ESTADOS_POR_ETAPA del backend (api/dashboard.py), que usa
// la misma `clave`.
//
// Las abiertas llevan color (son las que piden trabajo) y las cerradas van en gris para
// no competir con ellas. Los tres colores pasan la validación de daltonismo entre todos
// los pares.
export const ETAPAS = [
  {
    clave: 'REVISION',
    nombre: 'Revisión',
    color: '#2a78d6',
    estados: ['PENDIENTE_REVISION'],
  },
  {
    clave: 'PRESUPUESTO',
    nombre: 'Presupuesto',
    color: '#eb6834',
    estados: ['PENDIENTE_PRESUPUESTO', 'EN_EVALUACION', 'DESIERTO'],
  },
  {
    clave: 'EJECUCION',
    nombre: 'Ejecución',
    color: '#1baf7a',
    estados: [
      'APROBADO',
      'PENDIENTE_COORDINACION',
      'VISITA_COORDINADA',
      'EN_EJECUCION',
      'PENDIENTE_INTERVENCION',
    ],
  },
  {
    clave: 'FINALIZADOS',
    nombre: 'Finalizados',
    color: '#898781',
    estados: ['FINALIZADO'],
    cerrada: true,
  },
  {
    clave: 'RECHAZADOS',
    nombre: 'Rechazados o cancelados',
    color: '#c9c8c3',
    estados: ['RECHAZADO', 'CANCELADO'],
    cerrada: true,
  },
];

export const etapaPorClave = Object.fromEntries(ETAPAS.map((etapa) => [etapa.clave, etapa]));
