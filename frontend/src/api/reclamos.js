import { API_URL, extraerMensajeError } from './apiClient';

export async function crearReclamo(reclamo) {
  const response = await fetch(`${API_URL}/reclamos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(reclamo),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      extraerMensajeError(error?.detail, 'No se pudo enviar el reclamo. Intente nuevamente.'),
    );
  }

  return response.json();
}

export async function listarReclamos() {
  const response = await fetch(`${API_URL}/reclamos`);

  if (!response.ok) {
    throw new Error('No se pudo obtener el listado de reclamos.');
  }

  return response.json();
}

export async function obtenerReclamo(id) {
  const response = await fetch(`${API_URL}/reclamos/${id}`);

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo obtener el reclamo.'));
  }

  return response.json();
}

export async function actualizarReclamo(id, reclamo) {
  const response = await fetch(`${API_URL}/reclamos/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(reclamo),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, 'No se pudo actualizar el reclamo.'));
  }

  return response.json();
}

export async function eliminarReclamo(id) {
  const response = await fetch(`${API_URL}/reclamos/${id}`, { method: 'DELETE' });

  if (!response.ok) {
    throw new Error('No se pudo eliminar el reclamo.');
  }
}
