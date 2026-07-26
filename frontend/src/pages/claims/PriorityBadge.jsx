import { Badge } from '@mantine/core';

const colorPorPrioridad = {
  ALTA: 'red',
  MEDIA: 'yellow',
  BAJA: 'green',
};

export function PriorityBadge({ prioridad, ...props }) {
  return (
    <Badge color={colorPorPrioridad[prioridad]} {...props}>
      {prioridad}
    </Badge>
  );
}
