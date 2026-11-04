export const porCalificacion = (a, b) => (b.calificacion ?? -1) - (a.calificacion ?? -1);
export const porNombre = (a, b) => a.nombre_empresa.localeCompare(b.nombre_empresa, 'es');
