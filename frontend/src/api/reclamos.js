const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export async function crearReclamo(reclamo) {
  const response = await fetch(`${API_URL}/reclamos/crear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(reclamo),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    const mensaje = error?.detail?.[0]?.msg ?? 'No se pudo enviar el reclamo. Intente nuevamente.';
    throw new Error(mensaje);
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
