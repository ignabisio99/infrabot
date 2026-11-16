import { describe, expect, it } from 'vitest';

import {
  PRESUPUESTOS_DEMO,
  presupuestoDemoPara,
  totalDemo,
  valoresFormularioDemo,
} from './presupuestosDemo';
import { serializarItems, totalLineas, validarLineasPresupuesto } from './presupuestoItems';

describe('presupuestoDemoPara', () => {
  it('reconoce a Rodriguez Repara SRL con o sin acento y en cualquier mayúscula', () => {
    expect(presupuestoDemoPara('Rodriguez Repara SRL')).toBe(PRESUPUESTOS_DEMO[0]);
    expect(presupuestoDemoPara('RODRÍGUEZ  REPARA srl')).toBe(PRESUPUESTOS_DEMO[0]);
  });

  it('reconoce a la Cooperativa La Nueva Fabriquera', () => {
    expect(presupuestoDemoPara('Cooperativa La Nueva Fabriquera')).toBe(PRESUPUESTOS_DEMO[1]);
  });

  it('prueba con todos los nombres que se le pasan, ignorando los vacíos', () => {
    expect(presupuestoDemoPara(undefined, null, '', 'Cooperativa La Nueva Fabriquera')).toBe(
      PRESUPUESTOS_DEMO[1],
    );
  });

  it('no le da el botón a otros contratistas', () => {
    expect(presupuestoDemoPara('Plomería Integral SA')).toBeNull();
    expect(presupuestoDemoPara('Joaco Repara SRL', 'Igna Repara SA')).toBeNull();
    expect(presupuestoDemoPara()).toBeNull();
  });
});

describe('presupuestos de demo', () => {
  it('el 1 suma $90.000 y el 2 suma $1.080.000', () => {
    expect(totalDemo(PRESUPUESTOS_DEMO[0])).toBe(90000);
    expect(totalDemo(PRESUPUESTOS_DEMO[1])).toBe(1080000);
  });

  it.each(PRESUPUESTOS_DEMO.map((demo) => [demo.etiqueta, demo]))(
    '%s llena un formulario válido con el mismo total',
    (_etiqueta, demo) => {
      const valores = valoresFormularioDemo(demo);

      expect(validarLineasPresupuesto(valores.materials, valores.labor)).toEqual({});
      expect(totalLineas(valores.materials, valores.labor)).toBe(totalDemo(demo));
      expect(valores.materials).toHaveLength(demo.items.length);
      expect(valores.taskDetail).toBe(demo.detalle_tarea);
      expect(valores.notes).toBe(demo.observaciones);
    },
  );

  it('se envía con los nombres exactos de cada ítem, cantidad 1 y unidad', () => {
    const { materials, labor } = valoresFormularioDemo(PRESUPUESTOS_DEMO[0]);

    expect(serializarItems(materials, labor)).toEqual([
      {
        tipo: 'MATERIAL',
        descripcion: 'Visita y diagnóstico',
        cantidad: 1,
        unidad: 'unidad',
        costo_unitario: 20000,
      },
      {
        tipo: 'MATERIAL',
        descripcion: 'Destapación de sifón (sonda manual / desarme y limpieza)',
        cantidad: 1,
        unidad: 'unidad',
        costo_unitario: 45000,
      },
      {
        tipo: 'MATERIAL',
        descripcion: 'Sifón de reemplazo (PVC, si hace falta) + juntas',
        cantidad: 1,
        unidad: 'unidad',
        costo_unitario: 15000,
      },
      {
        tipo: 'MATERIAL',
        descripcion: 'Limpieza y secado básico del área',
        cantidad: 1,
        unidad: 'unidad',
        costo_unitario: 10000,
      },
    ]);
  });
});
