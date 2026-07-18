import { API_URL, extraerMensajeError } from './apiClient';

export async function crearContratista(contratista) {
  const response = await fetch(`${API_URL}/contratistas`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(contratista),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo guardar el contratista. Intente nuevamente.'),
    );
  }

  return response.json();
}

export async function listarContratistas() {
  const response = await fetch(`${API_URL}/contratistas`);

  if (!response.ok) {
    throw new Error('No se pudo obtener el listado de contratistas.');
  }

  return response.json();
}

export async function obtenerContratista(id) {
  const response = await fetch(`${API_URL}/contratistas/${id}`);

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo obtener el contratista.'));
  }

  return response.json();
}

export async function actualizarContratista(id, contratista) {
  const response = await fetch(`${API_URL}/contratistas/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(contratista),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo actualizar el contratista.'));
  }

  return response.json();
}

export async function eliminarContratista(id) {
  const response = await fetch(`${API_URL}/contratistas/${id}`, { method: 'DELETE' });

  if (!response.ok) {
    throw new Error('No se pudo eliminar el contratista.');
  }
}
