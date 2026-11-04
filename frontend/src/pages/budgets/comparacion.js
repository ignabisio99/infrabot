import { estaVigente } from './estados';

const vigente = (estado) => estaVigente({ estado });

function orden(estado) {
  if (estado === 'APROBADO') return 0;
  if (vigente(estado)) return 1;
  if (!estado) return 2;
  return 3;
}

// Primero la aprobada, después las que siguen en carrera de la más barata a la más cara,
// las que todavía no llegaron (sin estado) y al final las descartadas.
export function ordenarOfertas(ofertas, estadoDe = (o) => o.estado) {
  return [...ofertas].sort((a, b) => {
    const diferencia = orden(estadoDe(a)) - orden(estadoDe(b));
    if (diferencia !== 0) return diferencia;
    return vigente(estadoDe(a)) ? Number(a.monto) - Number(b.monto) : 0;
  });
}

// Sólo tiene sentido comparar mientras se está eligiendo: con dos o más en carrera y
// ninguna aprobada.
export function masBarata(ofertas, estadoDe = (o) => o.estado) {
  if (ofertas.some((o) => estadoDe(o) === 'APROBADO')) return null;
  const enCarrera = ofertas.filter((o) => vigente(estadoDe(o)) && o.monto != null);
  if (enCarrera.length < 2) return null;
  return enCarrera.reduce((min, o) => (Number(o.monto) < Number(min.monto) ? o : min));
}

export function porcentajeSobre(oferta, referencia) {
  return Math.round((Number(oferta.monto) / Number(referencia.monto) - 1) * 100);
}
