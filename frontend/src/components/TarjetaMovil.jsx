import { Group, Paper, Stack, Text } from '@mantine/core';

/**
 * Una fila de tabla mostrada como tarjeta, para celular: las tablas anchas obligan a
 * moverse de costado, y apiladas se leen de arriba hacia abajo.
 *
 * - `titulo`: lo principal de la fila (ej. el ID o el nombre).
 * - `acciones`: arriba a la derecha (ej. el menú de editar/eliminar). Los clics ahí no
 *   abren la tarjeta.
 * - `badges`: estado, prioridad, etc., debajo del título.
 * - `campos`: [{ etiqueta, valor }]; los que vienen sin valor no se muestran.
 * - `pie`: botones al final, a todo el ancho.
 */
export function TarjetaMovil({ titulo, acciones, badges, campos = [], pie, onClick }) {
  const visibles = campos.filter(
    (campo) => campo.valor !== null && campo.valor !== undefined && campo.valor !== '',
  );

  return (
    <Paper
      withBorder
      radius="md"
      p="sm"
      onClick={onClick}
      style={onClick ? { cursor: 'pointer' } : undefined}
    >
      <Stack gap={6}>
        <Group justify="space-between" align="flex-start" wrap="nowrap" gap="xs">
          <Text fw={600} size="sm" style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
            {titulo}
          </Text>
          {acciones && <div onClick={(event) => event.stopPropagation()}>{acciones}</div>}
        </Group>
        {badges && (
          <Group gap={6} wrap="wrap">
            {badges}
          </Group>
        )}
        {visibles.map((campo) => (
          <Group key={campo.etiqueta} gap={6} wrap="nowrap" align="flex-start">
            <Text size="xs" c="dimmed" w={96} style={{ flexShrink: 0 }}>
              {campo.etiqueta}
            </Text>
            <Text component="div" size="sm" style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
              {campo.valor}
            </Text>
          </Group>
        ))}
        {pie && (
          <Group gap="xs" grow mt={4} onClick={(event) => event.stopPropagation()}>
            {pie}
          </Group>
        )}
      </Stack>
    </Paper>
  );
}
