import { describe, expect, it } from 'vitest';

import { calcularVariacion, colorVariacion, textoVariacion } from './variacion';

describe('calcularVariacion', () => {
  it('calcula el porcentaje redondeado contra el anterior', () => {
    expect(calcularVariacion(12, 10)).toEqual({ direccion: 'sube', porcentaje: 20 });
    expect(calcularVariacion(2, 3)).toEqual({ direccion: 'baja', porcentaje: -33 });
  });

  it('acepta montos que llegan como texto (Decimal serializado)', () => {
    expect(calcularVariacion('1500.00', '1000.00')).toEqual({ direccion: 'sube', porcentaje: 50 });
  });

  it('sin anterior en cero da la dirección pero no un porcentaje', () => {
    expect(calcularVariacion(5, 0)).toEqual({ direccion: 'sube', porcentaje: null });
  });

  it('iguales es "igual", también en cero', () => {
    expect(calcularVariacion(0, 0)).toEqual({ direccion: 'igual', porcentaje: 0 });
  });

  it('con un lado null no compara', () => {
    expect(calcularVariacion(4.5, null)).toEqual({ direccion: null, porcentaje: null });
    expect(calcularVariacion(null, 3)).toEqual({ direccion: null, porcentaje: null });
  });
});

describe('colorVariacion', () => {
  it('verde cuando va para el lado bueno y rojo cuando no', () => {
    expect(colorVariacion('sube', 'sube')).toBe('teal');
    expect(colorVariacion('sube', 'baja')).toBe('red');
    expect(colorVariacion('baja', 'baja')).toBe('teal');
  });

  it('gris si el indicador es neutro o no cambió', () => {
    expect(colorVariacion('sube', undefined)).toBe('gray');
    expect(colorVariacion('igual', 'sube')).toBe('gray');
    expect(colorVariacion(null, 'sube')).toBe('gray');
  });
});

describe('textoVariacion', () => {
  it('muestra flecha y porcentaje sin signo', () => {
    expect(textoVariacion({ direccion: 'baja', porcentaje: -33 })).toBe('↓ 33%');
    expect(textoVariacion({ direccion: 'sube', porcentaje: null })).toBe('↑ desde 0');
    expect(textoVariacion({ direccion: 'igual', porcentaje: 0 })).toBe('Sin cambios');
    expect(textoVariacion({ direccion: null, porcentaje: null })).toBe('Sin datos para comparar');
  });
});
