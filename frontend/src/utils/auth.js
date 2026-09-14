/**
 * Utilidades de sesión del lado del cliente.
 * El token real vive en una cookie HttpOnly; en localStorage sólo guardamos
 * datos del usuario para la UI (nombre, tipo, estado).
 */

export function getUsuarioActual() {
  try {
    return JSON.parse(localStorage.getItem('infrabot_user') || 'null');
  } catch {
    return null;
  }
}

export function esAdministrador() {
  const usuario = getUsuarioActual();
  return usuario?.tipo === 'ADMINISTRADOR';
}

export function esInspector() {
  const usuario = getUsuarioActual();
  return usuario?.tipo === 'INSPECTOR';
}
