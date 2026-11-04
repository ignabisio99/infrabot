import { describe, expect, it } from 'vitest';

import { masBarata, ordenarOfertas, porcentajeSobre } from './comparacion';

const oferta = (id, estado, monto) => ({ id, estado, monto });

describe('ordenarOfertas', () => {
  it('aprobada, en carrera por monto, sin oferta y descartadas', () => {
    const ofertas = [
      oferta(1, 'RECHAZADO', '10'),
      oferta(2, 'RECIBIDO', '500'),
      oferta(3, null, null),
      oferta(4, 'AJUSTES_SOLICITADOS', '300'),
      oferta(5, 'APROBADO', '900'),
    ];
    expect(ordenarOfertas(ofertas).map((o) => o.id)).toEqual([5, 4, 2, 3, 1]);
  });
});

describe('masBarata', () => {
  it('es la más barata entre las que siguen en carrera', () => {
    const ofertas = [
      oferta(1, 'RECIBIDO', '500'),
      oferta(2, 'RECIBIDO', '300'),
      oferta(3, 'RECHAZADO', '1'),
    ];
    expect(masBarata(ofertas).id).toBe(2);
    expect(porcentajeSobre(ofertas[0], ofertas[1])).toBe(67);
  });

  it('no hay con una sola en carrera o si ya se aprobó una', () => {
    expect(masBarata([oferta(1, 'RECIBIDO', '500'), oferta(2, 'RECHAZADO', '1')])).toBeNull();
    expect(
      masBarata([
        oferta(1, 'RECIBIDO', '500'),
        oferta(2, 'RECIBIDO', '300'),
        oferta(3, 'APROBADO', '900'),
      ]),
    ).toBeNull();
  });
});
