import { describe, expect, it } from 'vitest';

import {
  ESTADOS,
  colorPorEstado,
  estaVigente,
  estadosConMotivoObligatorio,
  etiquetaPorEstado,
  textoMotivoPorEstado,
} from './estados';

describe('estados de presupuesto', () => {
  it('cada estado tiene etiqueta y color, y no sobran estados', () => {
    for (const mapa of [etiquetaPorEstado, colorPorEstado]) {
      expect(Object.keys(mapa).sort()).toEqual([...ESTADOS].sort());
      expect(Object.values(mapa).every(Boolean)).toBe(true);
    }
  });

  it.each(estadosConMotivoObligatorio)('%s tiene el texto del campo de motivo', (estado) => {
    expect(textoMotivoPorEstado[estado]?.label).toBeTruthy();
  });

  it('sólo las ofertas sin decidir siguen vigentes', () => {
    const vigentes = ESTADOS.filter((estado) => estaVigente({ estado }));
    expect(vigentes).toEqual(['RECIBIDO', 'AJUSTES_SOLICITADOS']);
  });
});
