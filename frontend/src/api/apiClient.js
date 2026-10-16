// La API vive bajo /api del mismo dominio (nginx rutea /api/* al backend y le quita
// el prefijo). Usar ruta relativa evita colisiones con las rutas del SPA (ej: /reclamos)
// y hace que el F5 en cualquier página funcione. En dev, VITE_API_URL apunta al backend.
// Si VITE_API_URL está vacía o sin definir, se usa /api (mismo dominio, ruteado por nginx).
export const API_URL = import.meta.env.VITE_API_URL || '/api';

export function extraerMensajeError(detail, mensajePorDefecto) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0]?.msg) {
    // Pydantic v2 antepone "Value error, " a los mensajes de field_validator
    const msg = detail[0].msg;
    return msg.replace(/^Value error,\s*/i, '');
  }
  return mensajePorDefecto;
}

/**
 * Wrapper de fetch que envía cookies automáticamente (credentials: include).
 * Si recibe un 401, limpia la sesión local y redirige al login.
 */
export async function fetchConAuth(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      ...options.headers,
    },
  });

  if (response.status === 401) {
    localStorage.removeItem('infrabot_user');
    window.location.href = '/';
    throw new Error('Sesión expirada. Iniciá sesión nuevamente.');
  }

  return response;
}

// Genera el set estándar de operaciones CRUD (crear/listar/obtener/actualizar/eliminar)
// contra `${API_URL}/{recursoPlural}`, siguiendo el mismo patrón para cualquier entidad.
export function crearRecursoApi({ recursoPlural, recursoSingular }) {
  const base = `${API_URL}/${recursoPlural}`;

  async function crear(datos) {
    const response = await fetchConAuth(base, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datos),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new Error(
        extraerMensajeError(
          error?.detail,
          `No se pudo guardar el ${recursoSingular}. Intente nuevamente.`,
        ),
      );
    }

    return response.json();
  }

  async function listar() {
    const response = await fetchConAuth(base);

    if (!response.ok) {
      throw new Error(`No se pudo obtener el listado de ${recursoPlural}.`);
    }

    return response.json();
  }

  async function obtener(id) {
    const response = await fetchConAuth(`${base}/${id}`);

    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new Error(
        extraerMensajeError(error?.detail, `No se pudo obtener el ${recursoSingular}.`),
      );
    }

    return response.json();
  }

  async function actualizar(id, datos) {
    const response = await fetchConAuth(`${base}/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datos),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new Error(
        extraerMensajeError(error?.detail, `No se pudo actualizar el ${recursoSingular}.`),
      );
    }

    return response.json();
  }

  async function eliminar(id) {
    const response = await fetchConAuth(`${base}/${id}`, { method: 'DELETE' });

    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new Error(
        extraerMensajeError(error?.detail, `No se pudo eliminar el ${recursoSingular}.`),
      );
    }
  }

  return { crear, listar, obtener, actualizar, eliminar };
}
