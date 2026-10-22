import { DonutChart } from '@mantine/charts';
import { Box, Card, Group, Paper, Stack, Text, Title, UnstyledButton } from '@mantine/core';
import { useNavigate } from 'react-router';

import { etiquetaPorEstado } from '../claims/estados';
import classes from './Dashboard.module.css';

// Los 12 estados en una dona son porciones finitas y colores que no se distinguen, así
// que se agrupan por etapa del flujo. Las tres abiertas llevan color (son las que piden
// trabajo) y las cerradas van en gris para no competir con ellas. Los tres colores
// pasan la validación de daltonismo entre todos los pares.
const ETAPAS = [
  {
    nombre: 'Revisión',
    color: '#2a78d6',
    estados: ['PENDIENTE_REVISION'],
  },
  {
    nombre: 'Presupuesto',
    color: '#eb6834',
    estados: ['PENDIENTE_PRESUPUESTO', 'EN_EVALUACION', 'DESIERTO'],
  },
  {
    nombre: 'Ejecución',
    color: '#1baf7a',
    estados: [
      'APROBADO',
      'PENDIENTE_COORDINACION',
      'VISITA_COORDINADA',
      'EN_EJECUCION',
      'PENDIENTE_INTERVENCION',
    ],
  },
  {
    nombre: 'Finalizados',
    color: '#898781',
    estados: ['FINALIZADO'],
    cerrada: true,
  },
  {
    nombre: 'Rechazados o cancelados',
    color: '#c9c8c3',
    estados: ['RECHAZADO', 'CANCELADO'],
    cerrada: true,
  },
];

function TooltipEtapa({ active, payload }) {
  if (!active || !payload?.length) return null;
  const { nombre, detalle, value } = payload[0].payload;

  return (
    <Paper withBorder shadow="sm" radius="md" p="xs">
      <Text size="sm" fw={600}>
        {nombre}: {value}
      </Text>
      {detalle.map(({ estado, cantidad }) => (
        <Group key={estado} justify="space-between" gap="lg" wrap="nowrap">
          <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
            {etiquetaPorEstado[estado]}
          </Text>
          <Text size="xs">{cantidad}</Text>
        </Group>
      ))}
    </Paper>
  );
}

/**
 * Reclamos por etapa del flujo: una dona con los abiertos en el centro y, al lado, cada
 * etapa con su total y el desglose por estado. Tanto las porciones como las filas llevan
 * al listado filtrado por los estados de esa etapa.
 */
export function ClaimsByStateChart({ datos, linkReclamos }) {
  const navigate = useNavigate();
  const cantidadPorEstado = Object.fromEntries(datos.map((fila) => [fila.estado, fila.cantidad]));
  const total = datos.reduce((suma, fila) => suma + fila.cantidad, 0);

  const etapas = ETAPAS.map((etapa) => {
    const detalle = etapa.estados
      .map((estado) => ({ estado, cantidad: cantidadPorEstado[estado] ?? 0 }))
      .filter(({ cantidad }) => cantidad > 0);
    return { ...etapa, detalle, cantidad: detalle.reduce((suma, d) => suma + d.cantidad, 0) };
  });
  const abiertos = etapas
    .filter((etapa) => !etapa.cerrada)
    .reduce((suma, e) => suma + e.cantidad, 0);
  const abrir = (etapa) => navigate(linkReclamos(etapa.estados));

  return (
    <Card withBorder radius="md" padding="lg" h="100%">
      <Title order={4}>Reclamos por etapa</Title>
      <Text size="xs" c="dimmed" mb="md">
        Dónde está cada reclamo dentro del flujo. Hacé clic para ver el listado filtrado.
      </Text>

      {total === 0 ? (
        <Text c="dimmed" size="sm">
          Todavía no hay reclamos registrados.
        </Text>
      ) : (
        <Group align="center" gap="xl" wrap="wrap" justify="center">
          <Box pos="relative">
            {/* Antes que la dona en el DOM y sin capturar el mouse: así el tooltip de la
                dona queda por encima del número y el hover sigue llegando a las porciones. */}
            <Stack
              gap={0}
              align="center"
              pos="absolute"
              inset={0}
              justify="center"
              style={{ pointerEvents: 'none' }}
            >
              <Text fz={30} fw={700} lh={1}>
                {abiertos}
              </Text>
              <Text size="xs" c="dimmed">
                abiertos de {total}
              </Text>
            </Stack>
            <DonutChart
              pos="relative"
              data={etapas
                .filter((etapa) => etapa.cantidad > 0)
                .map((etapa) => ({
                  name: etapa.nombre,
                  value: etapa.cantidad,
                  color: etapa.color,
                  nombre: etapa.nombre,
                  detalle: etapa.detalle,
                }))}
              size={190}
              thickness={26}
              strokeWidth={2}
              strokeColor="var(--mantine-color-body)"
              tooltipDataSource="segment"
              tooltipProps={{ content: TooltipEtapa }}
              cellProps={(celda) => ({
                cursor: 'pointer',
                onClick: () => abrir(ETAPAS.find((etapa) => etapa.nombre === celda.name)),
              })}
            />
          </Box>

          <Stack gap={4} style={{ flex: 1, minWidth: 220 }}>
            {etapas.map((etapa) => (
              <UnstyledButton
                key={etapa.nombre}
                className={classes.etapaFila}
                onClick={() => abrir(etapa)}
              >
                <Group justify="space-between" wrap="nowrap" gap="sm">
                  <Group gap={8} wrap="nowrap">
                    <Box
                      w={10}
                      h={10}
                      style={{ borderRadius: 2, backgroundColor: etapa.color, flexShrink: 0 }}
                    />
                    <Text size="sm" fw={etapa.cerrada ? 400 : 500}>
                      {etapa.nombre}
                    </Text>
                  </Group>
                  <Text size="sm" fw={600}>
                    {etapa.cantidad}
                    <Text span size="xs" c="dimmed" fw={400} ml={6}>
                      {Math.round((etapa.cantidad / total) * 100)}%
                    </Text>
                  </Text>
                </Group>
                {/* En las etapas de varios estados el desglose va siempre, aunque los
                    reclamos estén en uno solo: si no, no se sabe en cuál. */}
                {etapa.estados.length > 1 && etapa.detalle.length > 0 && (
                  <Group gap={4} ml={18} c="dimmed" fz="xs" style={{ rowGap: 0 }}>
                    {etapa.detalle.map(({ estado, cantidad }, i) => (
                      // Cada "estado cantidad" junto, para que el corte de línea caiga
                      // entre estados y no separe un número de su nombre.
                      <span key={estado} style={{ whiteSpace: 'nowrap' }}>
                        {etiquetaPorEstado[estado]} {cantidad}
                        {i < etapa.detalle.length - 1 && ' ·'}
                      </span>
                    ))}
                  </Group>
                )}
              </UnstyledButton>
            ))}
          </Stack>
        </Group>
      )}
    </Card>
  );
}
