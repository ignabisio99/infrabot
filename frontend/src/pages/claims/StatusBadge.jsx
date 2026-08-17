import { Badge } from '@mantine/core';

import { colorPorEstado, etiquetaPorEstado } from './estados';

// `tt="none"` porque Badge viene en mayúsculas por defecto y las etiquetas de estado
// son frases largas ("Pendiente de presupuesto"): en mayúscula sostenida cuestan de
// leer y engordan la columna.
export function StatusBadge({ estado, ...props }) {
  return (
    <Badge color={colorPorEstado[estado]} tt="none" {...props}>
      {etiquetaPorEstado[estado] ?? estado}
    </Badge>
  );
}
