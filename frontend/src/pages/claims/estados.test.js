import { describe, expect, it } from 'vitest';

import {
  ESTADOS,
  colorPorEstado,
  estadosConMotivoObligatorio,
  estadosFinales,
  etiquetaPorEstado,
  proximoPasoPorEstado,
  textoMotivoPorEstado,
} from './estados';

// Al agregar un estado en el backend hay que completarlo en varios mapas; si falta en
// alguno, la pantalla muestra el enum crudo o un badge sin color.
describe('estados de reclamo', () => {
  it('cada estado tiene etiqueta, color y próximo paso, y no sobran estados', () => {
    for (const mapa of [etiquetaPorEstado, colorPorEstado, proximoPasoPorEstado]) {
      expect(Object.keys(mapa).sort()).toEqual([...ESTADOS].sort());
      expect(Object.values(mapa).every(Boolean)).toBe(true);
    }
    expect(ESTADOS.every((estado) => proximoPasoPorEstado[estado].titulo)).toBe(true);
  });

  it.each(estadosConMotivoObligatorio)('%s tiene el texto del campo de motivo', (estado) => {
    expect(textoMotivoPorEstado[estado]?.label).toBeTruthy();
  });

  it('estadosFinales no tiene typos ni estados que ya no existen', () => {
    expect(ESTADOS).toEqual(expect.arrayContaining(estadosFinales));
  });
});
