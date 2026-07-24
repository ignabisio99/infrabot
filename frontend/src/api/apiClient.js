export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export function extraerMensajeError(detail, mensajePorDefecto) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return mensajePorDefecto;
}

// Genera el set estándar de operaciones CRUD (crear/listar/obtener/actualizar/eliminar)
// contra `${API_URL}/{recursoPlural}`, siguiendo el mismo patrón para cualquier entidad.
export function crearRecursoApi({ recursoPlural, recursoSingular }) {
  const base = `${API_URL}/${recursoPlural}`;

  async function crear(datos) {
    const response = await fetch(base, {
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
    const response = await fetch(base);

    if (!response.ok) {
      throw new Error(`No se pudo obtener el listado de ${recursoPlural}.`);
    }

    return response.json();
  }

  async function obtener(id) {
    const response = await fetch(`${base}/${id}`);

    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new Error(
        extraerMensajeError(error?.detail, `No se pudo obtener el ${recursoSingular}.`),
      );
    }

    return response.json();
  }

  async function actualizar(id, datos) {
    const response = await fetch(`${base}/${id}`, {
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
    const response = await fetch(`${base}/${id}`, { method: 'DELETE' });

    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new Error(
        extraerMensajeError(error?.detail, `No se pudo eliminar el ${recursoSingular}.`),
      );
    }
  }

  return { crear, listar, obtener, actualizar, eliminar };
}
