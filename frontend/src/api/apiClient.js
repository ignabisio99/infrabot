export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export function extraerMensajeError(detail, mensajePorDefecto) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
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
