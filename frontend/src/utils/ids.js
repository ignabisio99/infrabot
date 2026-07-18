export function formatearIdReclamo(id) {
  return `REC-${String(id).padStart(8, '0')}`;
}
