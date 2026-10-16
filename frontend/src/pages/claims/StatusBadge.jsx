import { Badge } from '@mantine/core';

import { colorPorEstado, etiquetaPorEstado } from './estados';

// `tt="none"` porque Badge viene en mayúsculas por defecto y las etiquetas de estado
// son frases largas ("Pendiente de presupuesto"): en mayúscula sostenida cuestan de
// leer y engordan la columna.
// `miw="max-content"`: el texto del Badge tiene overflow hidden, así que sin esto la
// tabla lo considera achicable a cero y le da a la columna menos ancho del que necesita.
export function StatusBadge({ estado, ...props }) {
  return (
    <Badge color={colorPorEstado[estado]} tt="none" miw="max-content" {...props}>
      {etiquetaPorEstado[estado] ?? estado}
    </Badge>
  );
}
