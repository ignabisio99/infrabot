import { describe, expect, it } from 'vitest';

import { fechaRelativa, formatoFechaHoraCorta } from './formatters';

const AHORA = new Date('2026-11-04T12:00:00-03:00');
const hace = (ms) => new Date(AHORA.getTime() - ms);
const MIN = 60 * 1000;

describe('fechaRelativa', () => {
  it.each([
    [hace(20 * 1000), 'recién'],
    [hace(5 * MIN), 'hace 5 min'],
    [hace(3 * 60 * MIN), 'hace 3 h'],
    [hace(30 * 60 * MIN), 'hace 1 día'],
    [hace(10 * 24 * 60 * MIN), 'hace 10 días'],
  ])('%s → %s', (fecha, esperado) => {
    expect(fechaRelativa(fecha, AHORA)).toBe(esperado);
  });

  it('pasado un mes muestra la fecha', () => {
    expect(fechaRelativa('2026-09-15T12:00:00-03:00', AHORA)).toBe('15/9/2026');
  });
});

describe('formatoFechaHoraCorta', () => {
  it('usa 24 horas y no muestra los segundos', () => {
    expect(formatoFechaHoraCorta(new Date(2026, 10, 4, 18, 34, 59))).toBe('4/11/2026, 18:34');
  });
});
