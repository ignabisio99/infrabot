import { partirTelefono } from '../components/PhoneInput';

// El simulador de WhatsApp identifica sus chats con el prefijo "sim".
export const esTelefonoSimulado = (telefono) => /^sim/i.test((telefono || '').trim());

// Mismo criterio que `clave_telefono` del backend para decidir si dos teléfonos son el mismo.
export const claveTelefono = (telefono) => (telefono || '').replace(/\D/g, '').slice(-10);

function agruparArgentino(nacional) {
  const movil = nacional.length === 11 && nacional.startsWith('9');
  const numero = movil ? nacional.slice(1) : nacional;
  if (numero.length !== 10) return null;
  // Sólo la característica del 11 se puede asumir; el resto se agrupa como 3 + 7, que es
  // lo más común aunque haya características de 4 dígitos.
  const largoArea = numero.startsWith('11') ? 2 : 3;
  const local = numero.slice(largoArea);
  const agrupado = `${numero.slice(0, largoArea)} ${local.slice(0, -4)}-${local.slice(-4)}`;
  return movil ? `9 ${agrupado}` : agrupado;
}

export function formatearTelefono(telefono) {
  const crudo = (telefono || '').trim();
  const { codigo, nacional } = partirTelefono(crudo.replace(/^sim/i, ''));
  if (!nacional) return crudo;
  const agrupado = codigo === '54' ? agruparArgentino(nacional) : null;
  return `+${codigo} ${agrupado ?? nacional}`;
}
