import { Badge } from '@mantine/core';

const colorPorPrioridad = {
  ALTA: 'red',
  MEDIA: 'yellow',
  BAJA: 'green',
};

const etiquetaPorPrioridad = {
  ALTA: 'Alta',
  MEDIA: 'Media',
  BAJA: 'Baja',
};

// Se dibuja como punto + texto plano (sin fondo ni borde), no como pastilla: en la
// tabla y en el drawer la prioridad va pegada al estado, y si las dos fueran
// pastillas de color no se distinguiría cuál es cuál. Además las paletas se pisan
// (prioridad Baja y estado Finalizado son las dos verdes), así que la diferencia
// tiene que estar en la forma y no sólo en el color.
export function PriorityBadge({ prioridad, ...props }) {
  return (
    <Badge
      variant="dot"
      color={colorPorPrioridad[prioridad]}
      tt="none"
      fw={500}
      styles={{ root: { border: 'none', paddingInline: 0 } }}
      {...props}
    >
      {etiquetaPorPrioridad[prioridad] ?? prioridad}
    </Badge>
  );
}
