import { Badge } from '@mantine/core';

import { colorPorEstado, etiquetaPorEstado } from './estados';

// Mismo criterio que StatusBadge de reclamos: `tt="none"` porque las etiquetas son
// frases ("No seleccionado") y en mayúscula sostenida cuestan de leer.
export function BudgetStatusBadge({ estado, ...props }) {
  return (
    <Badge color={colorPorEstado[estado]} tt="none" style={{ whiteSpace: 'nowrap' }} {...props}>
      {etiquetaPorEstado[estado] ?? estado}
    </Badge>
  );
}
