import { describe, expect, it } from 'vitest';

import { capitalizarMayusculas, nombreCortoEscuela } from './escuelas';

describe('nombreCortoEscuela', () => {
  it.each([
    [
      'ESCUELA DE EDUCACIÓN PRIMARIA N°10 ESTADOS UNIDOS DE NORTEAMERICA',
      'EP N°10 Estados Unidos de Norteamerica',
    ],
    ['ESCUELA DE EDUCACIÓN SECUNDARIA TÉCNICA Nº5 GALILEO GALILEI', 'EEST Nº5 Galileo Galilei'],
    ['ESCUELA DE EDUCACIÓN SECUNDARIA N°52 DOCTOR RENÉ FAVALORO', 'EES N°52 Doctor René Favaloro'],
    ['Escuela de Educación Primaria N°3 Mitre', 'EP N°3 Mitre'],
    ['Escuela de prueba', 'Escuela de prueba'],
    ['N5', 'N5'],
  ])('%s → %s', (nombre, esperado) => {
    expect(nombreCortoEscuela(nombre)).toBe(esperado);
  });
});

describe('capitalizarMayusculas', () => {
  it('capitaliza lo que viene todo en mayúsculas y deja lo demás', () => {
    expect(capitalizarMayusculas('LACROZE ESQ. PUEYRREDON 25')).toBe('Lacroze Esq. Pueyrredon 25');
    expect(capitalizarMayusculas('AVDA. EVA PERÓN 4541')).toBe('Avda. Eva Perón 4541');
    expect(capitalizarMayusculas('Calle Falsa 123')).toBe('Calle Falsa 123');
    expect(capitalizarMayusculas('')).toBe('');
  });
});
