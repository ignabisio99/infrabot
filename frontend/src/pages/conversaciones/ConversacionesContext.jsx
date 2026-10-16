import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { abrirStreamConversaciones, obtenerBandeja } from '../../api/conversaciones';
import { esAdministrador, getUsuarioActual } from '../../utils/auth';

const ConversacionesContext = createContext(null);

function upsertPorId(lista, item) {
  const resto = lista.filter((c) => c.id !== item.id);
  return [item, ...resto];
}

function mismoId(a, b) {
  const na = Number(a);
  const nb = Number(b);
  return Number.isFinite(na) && na === nb;
}

function firmaBandeja(espera, propias) {
  const pieza = (c) => `${c.id}:${c.estado}:${c.operador_id}:${c.ultimo_id}:${c.ultimo_autor}`;
  return `${espera.map(pieza).join(',')}|${propias.map(pieza).join(',')}`;
}

function setsIguales(a, b) {
  if (a.size !== b.size) return false;
  for (const x of a) {
    let esta = false;
    b.forEach((y) => {
      if (mismoId(x, y)) esta = true;
    });
    if (!esta) return false;
  }
  return true;
}

export function ConversacionesProvider({ children }) {
  const [enEspera, setEnEspera] = useState([]);
  const [mias, setMias] = useState([]);
  const [conNuevos, setConNuevos] = useState(() => new Set());
  const vistoHastaId = useRef(new Map());
  const abiertaRef = useRef(null);
  const firmaRef = useRef('');

  const marcarLeida = useCallback((id, ultimoId) => {
    if (id == null) return;
    const n = Number(ultimoId);
    const prev = vistoHastaId.current.get(id) || 0;
    if (Number.isFinite(n) && n > 0) {
      vistoHastaId.current.set(id, Math.max(prev, n));
    }
    setConNuevos((actual) => {
      if (![...actual].some((x) => mismoId(x, id))) return actual;
      const siguiente = new Set();
      actual.forEach((x) => {
        if (!mismoId(x, id)) siguiente.add(x);
      });
      return siguiente;
    });
  }, []);

  const setChatAbierto = useCallback(
    (id, ultimoId) => {
      abiertaRef.current = id ?? null;
      if (id != null) marcarLeida(id, ultimoId);
    },
    [marcarLeida],
  );

  const aplicarBandeja = useCallback((data) => {
    const espera = data.en_espera || [];
    const propias = data.mias || [];
    const firma = firmaBandeja(espera, propias);
    if (firma !== firmaRef.current) {
      firmaRef.current = firma;
      setEnEspera(espera);
      setMias(propias);
    }
    const siguiente = new Set();
    propias.forEach((c) => {
      if (c.ultimo_autor !== 'USUARIO' || !c.ultimo_id) return;
      if (mismoId(abiertaRef.current, c.id)) {
        vistoHastaId.current.set(
          c.id,
          Math.max(vistoHastaId.current.get(c.id) || 0, Number(c.ultimo_id) || 0),
        );
        return;
      }
      const visto = vistoHastaId.current.get(c.id) || 0;
      if (Number(c.ultimo_id) > visto) siguiente.add(c.id);
    });
    setConNuevos((actual) => (setsIguales(actual, siguiente) ? actual : siguiente));
  }, []);

  const recargar = useCallback(() => {
    obtenerBandeja()
      .then(aplicarBandeja)
      .catch(() => {});
  }, [aplicarBandeja]);

  useEffect(() => {
    if (!esAdministrador()) return undefined;
    recargar();
    const poll = setInterval(recargar, 12000);
    const source = abrirStreamConversaciones();
    const yo = getUsuarioActual()?.id;

    source.addEventListener('en_espera', () => recargar());
    source.addEventListener('asignada', (ev) => {
      const data = JSON.parse(ev.data);
      setEnEspera((actual) => actual.filter((c) => c.id !== data.id));
      if (mismoId(data.operador_id, yo)) {
        setMias((actual) => upsertPorId(actual, data));
      } else {
        setMias((actual) => actual.filter((c) => c.id !== data.id));
      }
      recargar();
    });
    source.addEventListener('liberada', () => recargar());
    source.addEventListener('cerrada', (ev) => {
      const data = JSON.parse(ev.data);
      setEnEspera((actual) => actual.filter((c) => c.id !== data.id));
      setMias((actual) => actual.filter((c) => c.id !== data.id));
      setConNuevos((actual) => {
        const siguiente = new Set();
        actual.forEach((x) => {
          if (!mismoId(x, data.id)) siguiente.add(x);
        });
        return siguiente;
      });
    });
    source.addEventListener('mensaje', (ev) => {
      const data = JSON.parse(ev.data);
      if (data.mensaje?.autor === 'USUARIO' && data.conversacion_id != null) {
        const cid = data.conversacion_id;
        const mid = Number(data.mensaje.id);
        if (mismoId(abiertaRef.current, cid)) {
          if (Number.isFinite(mid)) {
            vistoHastaId.current.set(cid, Math.max(vistoHastaId.current.get(cid) || 0, mid));
          }
        } else {
          setConNuevos((actual) => new Set(actual).add(cid));
        }
      }
    });

    return () => {
      clearInterval(poll);
      source.close();
    };
  }, [recargar]);

  const miasNuevosCount = mias.filter((c) => [...conNuevos].some((id) => mismoId(id, c.id))).length;

  const value = useMemo(
    () => ({
      enEspera,
      mias,
      conNuevos,
      esperaCount: enEspera.length,
      miasNuevosCount,
      marcarLeida,
      setChatAbierto,
      recargar,
    }),
    [enEspera, mias, conNuevos, miasNuevosCount, marcarLeida, setChatAbierto, recargar],
  );

  return <ConversacionesContext.Provider value={value}>{children}</ConversacionesContext.Provider>;
}

export function useConversaciones() {
  const ctx = useContext(ConversacionesContext);
  if (!ctx) {
    return {
      enEspera: [],
      mias: [],
      conNuevos: new Set(),
      esperaCount: 0,
      miasNuevosCount: 0,
      marcarLeida: () => {},
      setChatAbierto: () => {},
      recargar: () => {},
    };
  }
  return ctx;
}
