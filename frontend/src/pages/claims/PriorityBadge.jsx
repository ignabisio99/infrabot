import { Badge } from '@mantine/core';

const colorPorPrioridad = {
  ALTA: 'red',
  MEDIA: 'yellow',
  BAJA: 'green',
};

const etiquetaPorPrioridad = {
  ALTA: 'ALTA',
  MEDIA: 'MEDIA',
  BAJA: 'BAJA',
};

// Se dibuja como punto + texto (sin fondo ni borde), no como pastilla: en la tabla y en
// el drawer la prioridad va pegada al estado, y si las dos fueran pastillas de color no
// se distinguiría cuál es cuál. Además las paletas se pisan (prioridad Baja y estado
// Finalizado son las dos verdes), así que la diferencia está en la forma, no sólo el color.
//
// `fz` (opcional): fija el tamaño de fuente del texto para igualarlo al de otras columnas
// de una tabla (el Badge por defecto usa una fuente más chica que su `size`). Si no se
// pasa, el texto toma el tamaño propio del badge.
export function PriorityBadge({ prioridad, fz, ...props }) {
  return (
    <Badge
      variant="dot"
      color={colorPorPrioridad[prioridad]}
      tt="uppercase"
      fw={600}
      styles={{
        root: { border: 'none', paddingInline: 0 },
        // Color de texto normal (oscuro), no el gris tenue del badge dot. Y, si se pide,
        // el tamaño de fuente explícito para quedar igual que el resto de la columna.
        label: { color: 'var(--mantine-color-text)', ...(fz ? { fontSize: fz } : {}) },
      }}
      {...props}
    >
      {etiquetaPorPrioridad[prioridad] ?? prioridad}
    </Badge>
  );
}
