import { Card, Group, Text, ThemeIcon } from '@mantine/core';
import { useNavigate } from 'react-router';

/**
 * Tarjeta de un indicador: el número grande, qué mide y una línea de contexto.
 *
 * `to` es opcional: los indicadores que representan trabajo pendiente llevan al listado
 * ya filtrado, y los que son sólo informativos (un monto, un promedio) no llevan a
 * ningún lado.
 */
export function StatCard({ label, value, hint, icon: Icon, to }) {
  const navigate = useNavigate();
  const clickeable = Boolean(to);

  return (
    <Card
      withBorder
      radius="md"
      padding="lg"
      onClick={clickeable ? () => navigate(to) : undefined}
      style={clickeable ? { cursor: 'pointer' } : undefined}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <div>
          <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
            {label}
          </Text>
          <Text fz={30} fw={700} lh={1.2} mt={4}>
            {value}
          </Text>
        </div>
        {Icon && (
          <ThemeIcon variant="light" color="#1fa7b3" size={38} radius="md">
            <Icon size={20} stroke={1.5} />
          </ThemeIcon>
        )}
      </Group>
      {hint && (
        <Text size="xs" c="dimmed" mt="sm">
          {hint}
        </Text>
      )}
    </Card>
  );
}
