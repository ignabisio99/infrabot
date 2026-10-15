import { Badge } from '@mantine/core';

import { colorPorEstado, etiquetaPorEstado } from './estados';

// Mismo criterio que StatusBadge de reclamos: `tt="none"` porque las etiquetas son
// frases ("No seleccionado") y en mayúscula sostenida cuestan de leer. También el mismo
// `miw="max-content"`, para que la tabla no lo achique y corte la etiqueta.
export function BudgetStatusBadge({ estado, ...props }) {
  return (
    <Badge color={colorPorEstado[estado]} tt="none" miw="max-content" {...props}>
      {etiquetaPorEstado[estado] ?? estado}
    </Badge>
  );
}
