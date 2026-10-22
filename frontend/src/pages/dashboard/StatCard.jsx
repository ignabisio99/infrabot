import { Sparkline } from '@mantine/charts';
import { Card, Group, Text, ThemeIcon } from '@mantine/core';
import { useNavigate } from 'react-router';

import { calcularVariacion, colorVariacion, textoVariacion } from './variacion';

/**
 * Tarjeta de un indicador: el número grande, qué mide y una línea de contexto.
 *
 * `to` es opcional: los indicadores que representan trabajo pendiente llevan al listado
 * ya filtrado, y los que son sólo informativos no llevan a ningún lado.
 *
 * `comparacion` ({ actual, anterior, contra, mejorSi }) agrega la variación contra el
 * período anterior; `contra` es el texto de ese período ("30 días anteriores"). `serie`
 * dibuja la tendencia de los últimos meses debajo, y `etiquetaSerie` aclara su ventana,
 * que es mensual y no la del período del número.
 */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  to,
  comparacion,
  serie,
  etiquetaSerie,
}) {
  const navigate = useNavigate();
  const clickeable = Boolean(to);
  const variacion = comparacion && calcularVariacion(comparacion.actual, comparacion.anterior);

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
      {variacion && (
        <Group gap={6} mt="sm" wrap="nowrap">
          <Text
            size="sm"
            fw={600}
            c={`${colorVariacion(variacion.direccion, comparacion.mejorSi)}.7`}
            style={{ whiteSpace: 'nowrap' }}
          >
            {textoVariacion(variacion)}
          </Text>
          {variacion.direccion !== null && (
            <Text size="xs" c="dimmed" truncate>
              vs. {comparacion.contra}
            </Text>
          )}
        </Group>
      )}
      {hint && (
        <Text size="xs" c="dimmed" mt={variacion ? 4 : 'sm'}>
          {hint}
        </Text>
      )}
      {serie && (
        <Sparkline
          mt="sm"
          h={36}
          data={serie}
          curveType="monotone"
          color="#1fa7b3"
          fillOpacity={0.25}
          strokeWidth={1.5}
        />
      )}
      {serie && etiquetaSerie && (
        <Text size="xs" c="dimmed" mt={2}>
          {etiquetaSerie}
        </Text>
      )}
    </Card>
  );
}
