import { Badge, Rating, Stack } from '@mantine/core';

// Qué tan confiable es el contratista según su calificación (1 a 5, o sin calificar).
function nivelCalificacion(calificacion) {
  if (calificacion == null) return { etiqueta: 'Sin calificar', color: 'gray' };
  if (calificacion >= 5) return { etiqueta: 'Excelente', color: 'teal' };
  if (calificacion >= 4) return { etiqueta: 'Buena', color: 'teal' };
  if (calificacion >= 3) return { etiqueta: 'Regular', color: 'yellow' };
  if (calificacion >= 2) return { etiqueta: 'Mala', color: 'red' };
  return { etiqueta: 'Muy mala', color: 'red' };
}

export function CalificacionContratista({ calificacion, align = 'flex-end' }) {
  const nivel = nivelCalificacion(calificacion);
  return (
    <Stack gap={2} align={align} style={{ flex: 'none' }}>
      <Rating value={calificacion ?? 0} readOnly size="sm" color="yellow" />
      <Badge size="xs" variant="light" color={nivel.color} tt="none">
        {calificacion != null ? `${calificacion}/5 · ${nivel.etiqueta}` : nivel.etiqueta}
      </Badge>
    </Stack>
  );
}
