import { Alert, Badge, Button, Group, Paper, Stack, Text } from '@mantine/core';
import { IconEyeCheck } from '@tabler/icons-react';

import { formatearIdReclamo } from '../../utils/ids';

const fecha = (valor) => new Date(valor).toLocaleString('es-AR');

/**
 * Bandeja del inspector, arriba del listado de reclamos: los reclamos en los que le
 * pidieron información y todavía no aportó nada. Se van solos cuando comenta o sube una foto.
 */
export function MisPedidosInspeccion({ pedidos, onAbrir }) {
  if (pedidos.length === 0) return null;

  return (
    <Alert
      color="orange"
      variant="light"
      mb="md"
      icon={<IconEyeCheck size={20} />}
      title={
        pedidos.length === 1
          ? 'Te pidieron información en 1 reclamo'
          : `Te pidieron información en ${pedidos.length} reclamos`
      }
    >
      <Text size="sm" mb="sm">
        Agregá un comentario o una foto en el reclamo y el pedido queda atendido.
      </Text>
      <Stack gap="xs">
        {pedidos.map((pedido) => (
          <Paper key={pedido.id} withBorder radius="md" p="sm">
            <Group justify="space-between" align="flex-start" gap="xs">
              <div style={{ flex: '1 1 220px', minWidth: 0 }}>
                <Text size="sm" fw={600}>
                  {formatearIdReclamo(pedido.reclamo_id)} · {pedido.nombre_escuela}
                </Text>
                {pedido.mensaje && (
                  <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                    {pedido.mensaje}
                  </Text>
                )}
                <Text size="xs" c="dimmed">
                  {pedido.solicitado_por_nombre
                    ? `Pedido por ${pedido.solicitado_por_nombre} · `
                    : ''}
                  {fecha(pedido.fecha)}
                </Text>
              </div>
              <Button size="xs" onClick={() => onAbrir(pedido.reclamo_id)}>
                Ver reclamo
              </Button>
            </Group>
          </Paper>
        ))}
      </Stack>
    </Alert>
  );
}

/**
 * En la pestaña Inspección del detalle: el admin ve a quién le pidió información y si ya la
 * cargó; el inspector, lo que le pidieron a él mientras siga pendiente.
 */
export function PedidosDelReclamo({ pedidos, esAdmin }) {
  if (esAdmin) {
    if (pedidos.length === 0) return null;
    return (
      <Stack gap={6} mb="md">
        <Text size="sm" fw={600}>
          Pedidos de información a inspectores
        </Text>
        {pedidos.map((pedido) => (
          <Paper key={pedido.id} withBorder radius="md" p="xs">
            <Group justify="space-between" gap="xs">
              <Text size="sm" fw={500}>
                {pedido.inspector_nombre}
              </Text>
              {pedido.atendida_en ? (
                <Badge color="green" variant="light" tt="none">
                  Respondió el {fecha(pedido.atendida_en)}
                </Badge>
              ) : (
                <Badge color="orange" variant="light" tt="none">
                  Pendiente desde el {fecha(pedido.fecha)}
                </Badge>
              )}
            </Group>
            {pedido.mensaje && (
              <Text size="sm" c="dimmed" mt={4} style={{ whiteSpace: 'pre-wrap' }}>
                {pedido.mensaje}
              </Text>
            )}
          </Paper>
        ))}
      </Stack>
    );
  }

  const pendientes = pedidos.filter((pedido) => !pedido.atendida_en);
  if (pendientes.length === 0) return null;
  const [ultimo] = pendientes;
  return (
    <Alert color="orange" variant="light" mb="md" title="Te pidieron información de este reclamo">
      {ultimo.mensaje && (
        <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
          {ultimo.mensaje}
        </Text>
      )}
      <Text size="xs" c="dimmed" mt={4}>
        {ultimo.solicitado_por_nombre ? `Pedido por ${ultimo.solicitado_por_nombre} · ` : ''}
        {fecha(ultimo.fecha)}. Agregá un comentario o una foto y el pedido queda atendido.
      </Text>
    </Alert>
  );
}
