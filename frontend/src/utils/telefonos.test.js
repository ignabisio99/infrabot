import { describe, expect, it } from 'vitest';

import { claveTelefono, esTelefonoSimulado, formatearTelefono } from './telefonos';

describe('formatearTelefono', () => {
  it('agrupa un celular de AMBA', () => {
    expect(formatearTelefono('+5491147779012')).toBe('+54 9 11 4777-9012');
  });

  it('saca el prefijo del simulador', () => {
    expect(formatearTelefono('sim5491147779012')).toBe('+54 9 11 4777-9012');
  });

  it('agrupa como 3 + 7 fuera del 11 y respeta los fijos', () => {
    expect(formatearTelefono('+5493514779012')).toBe('+54 9 351 477-9012');
    expect(formatearTelefono('+541147779012')).toBe('+54 11 4777-9012');
  });

  it('no inventa agrupación para otros países ni largos raros', () => {
    expect(formatearTelefono('+59899123456')).toBe('+598 99123456');
    expect(formatearTelefono('+541111')).toBe('+54 1111');
    expect(formatearTelefono('')).toBe('');
  });
});

describe('claveTelefono', () => {
  it('considera iguales el mismo número con y sin prefijos', () => {
    expect(claveTelefono('sim5491147779012')).toBe(claveTelefono('+54 9 11 4777-9012'));
    expect(claveTelefono('011 4777-9012')).toBe('1147779012');
  });
});

describe('esTelefonoSimulado', () => {
  it('reconoce el prefijo sim', () => {
    expect(esTelefonoSimulado('sim5491147779012')).toBe(true);
    expect(esTelefonoSimulado('+5491147779012')).toBe(false);
  });
});
