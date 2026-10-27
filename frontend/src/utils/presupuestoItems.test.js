import { describe, expect, it } from 'vitest';

import { validarLineasPresupuesto } from './presupuestoItems';

const material = (datos) => ({
  description: 'Membrana',
  quantity: 2,
  unit: 'm2',
  unitCost: 1000,
  ...datos,
});

describe('validarLineasPresupuesto', () => {
  it('no deja cargar un ítem en $0', () => {
    const errores = validarLineasPresupuesto([material({ unitCost: 0 })], []);

    expect(errores['materials.0.unitCost']).toBe('Debe ser mayor a 0');
    // Un ítem en $0 no cuenta como línea completa: no hay presupuesto.
    expect(errores.lineas).toBeDefined();
  });

  it('acepta un ítem con costo y cantidad mayores a 0', () => {
    expect(validarLineasPresupuesto([material()], [])).toEqual({});
  });

  it('tampoco deja mano de obra en $0', () => {
    const errores = validarLineasPresupuesto(
      [material()],
      [{ description: 'Albañil', quantity: 8, unitCost: 0 }],
    );

    expect(errores['labor.0.unitCost']).toBe('Debe ser mayor a 0');
  });
});
