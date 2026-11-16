// Presupuestos de demostración para la exposición.
//
// Dos contratistas tienen un botón "Autocompletar presupuesto" en el formulario de carga
// (PresupuestarReclamoPage) que llena detalle, observaciones y todos los ítems de una vez:
//   - Rodriguez Repara SRL            -> Presupuesto 1, a valores de mercado ($90.000).
//   - Cooperativa La Nueva Fabriquera -> Presupuesto 2, con sobreprecio ($1.080.000).
// Sirve para mostrar cómo la auditoría de IA aprueba el primero y rechaza el segundo.
//
// Para sacarlo después de la exposición: borrar este archivo y el bloque `demo` de
// PresupuestarReclamoPage.jsx.
//
// Los ítems usan el mismo formato que devuelve la API (así `partirItems` los parte en
// materiales y mano de obra igual que cuando se edita un presupuesto). Van todos como
// material porque su descripción es texto libre: la mano de obra solo admite roles del
// catálogo (Plomero, Oficial...) y perdería el nombre de cada servicio.
import { partirItems } from './presupuestoItems';

const normalizar = (texto) =>
  (texto || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();

const item = (descripcion, costoUnitario) => ({
  tipo: 'MATERIAL',
  descripcion,
  cantidad: 1,
  unidad: 'unidad',
  costo_unitario: costoUnitario,
});

export const PRESUPUESTOS_DEMO = [
  {
    // Se busca dentro del nombre de la empresa, sin acentos ni mayúsculas.
    empresa: 'rodriguez repara',
    etiqueta: 'Presupuesto 1 · valores de mercado',
    detalle_tarea:
      'Destapación del inodoro con desborde: visita y diagnóstico de la causa, destapación ' +
      'del sifón (sonda manual o desarme y limpieza), reemplazo del sifón de PVC con juntas ' +
      'si hace falta, y limpieza y secado básico del área afectada.',
    observaciones:
      'Valores de mercado. El sifón de reemplazo solo se coloca si el diagnóstico lo requiere.',
    items: [
      item('Visita y diagnóstico', 20000),
      item('Destapación de sifón (sonda manual / desarme y limpieza)', 45000),
      item('Sifón de reemplazo (PVC, si hace falta) + juntas', 15000),
      item('Limpieza y secado básico del área', 10000),
    ],
  },
  {
    empresa: 'nueva fabriquera',
    etiqueta: 'Presupuesto 2 · con sobreprecio',
    detalle_tarea:
      'Resolución integral del desborde del inodoro: visita técnica con diagnóstico ' +
      'especializado, inspección de la cañería con cámara, destapación con máquina eléctrica, ' +
      'reemplazo completo del sifón y la descarga de la bacha, tratamiento antihumedad y ' +
      'secado profesional.',
    observaciones:
      'Incluye kit de materiales premium, atención con recargo por urgencia y garantía extendida.',
    items: [
      item('Visita técnica con diagnóstico especializado', 85000),
      item('Inspección con cámara de cañería', 180000),
      item('Destapación con máquina eléctrica', 220000),
      item('Reemplazo completo de sifón y descarga de bacha', 120000),
      item('Kit de materiales “premium”', 95000),
      item('Recargo por urgencia', 150000),
      item('Tratamiento antihumedad y secado profesional', 160000),
      item('Garantía extendida', 70000),
    ],
  },
];

/** El presupuesto de demo que le corresponde a una empresa, o null si no tiene. */
export function presupuestoDemoPara(...nombres) {
  const candidatos = nombres.map(normalizar).filter(Boolean);
  return (
    PRESUPUESTOS_DEMO.find((demo) => candidatos.some((nombre) => nombre.includes(demo.empresa))) ??
    null
  );
}

/** Los valores con los que se llena el formulario (mismo formato que `useForm`). */
export function valoresFormularioDemo(demo) {
  return {
    ...partirItems(demo.items),
    taskDetail: demo.detalle_tarea,
    notes: demo.observaciones,
  };
}

export function totalDemo(demo) {
  return demo.items.reduce((suma, i) => suma + i.cantidad * i.costo_unitario, 0);
}
