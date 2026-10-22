import { Badge, Card, Group, Stack, Table, Text, Title } from '@mantine/core';
import { IconCheck } from '@tabler/icons-react';
import { useNavigate } from 'react-router';

import { TarjetaMovil } from '../../components/TarjetaMovil';
import { useEsMobile } from '../../hooks/useEsMobile';
import { PriorityBadge } from '../claims/PriorityBadge';
import { StatusBadge } from '../claims/StatusBadge';
import { formatearIdReclamo } from '../../utils/ids';
import classes from './Dashboard.module.css';

// Escalones de antigüedad. Un reclamo abierto hace un mes sin que nadie lo toque es un
// problema distinto a uno que lleva ocho días.
function colorAntiguedad(dias) {
  if (dias >= 30) return 'red';
  if (dias >= 14) return 'orange';
  return 'gray';
}

/**
 * Reclamos abiertos sin cambio de estado hace más de `umbral` días, del más viejo al más
 * nuevo. `total` es cuántos hay: el backend manda sólo los primeros.
 */
export function StalledClaimsCard({ reclamos, total, umbral }) {
  const navigate = useNavigate();
  const esMobile = useEsMobile();
  const hayMas = total > reclamos.length;
  const abrir = (reclamo) => navigate(`/reclamos?busqueda=${formatearIdReclamo(reclamo.id)}`);

  return (
    <Card withBorder radius="md" padding="lg">
      <Title order={4}>Reclamos estancados</Title>
      <Text size="xs" c="dimmed" mb="md">
        Abiertos y sin cambio de estado hace más de {umbral} días.
        {hayMas && ` Se muestran los ${reclamos.length} más antiguos de ${total}.`}
      </Text>

      {reclamos.length === 0 ? (
        <Group gap="xs">
          <IconCheck size={16} color="var(--mantine-color-green-7)" />
          <Text size="sm" c="dimmed">
            Ningún reclamo lleva más de {umbral} días sin movimiento.
          </Text>
        </Group>
      ) : esMobile ? (
        <Stack gap="sm">
          {reclamos.map((reclamo) => (
            <TarjetaMovil
              key={reclamo.id}
              onClick={() => abrir(reclamo)}
              titulo={`${formatearIdReclamo(reclamo.id)} · ${reclamo.nombre_escuela}`}
              badges={
                <>
                  <StatusBadge estado={reclamo.estado} variant="light" />
                  <PriorityBadge prioridad={reclamo.prioridad} />
                  <Badge color={colorAntiguedad(reclamo.dias_sin_movimiento)} variant="light">
                    {reclamo.dias_sin_movimiento} días sin movimiento
                  </Badge>
                </>
              }
            />
          ))}
        </Stack>
      ) : (
        <Table.ScrollContainer minWidth={560}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>ID</Table.Th>
                <Table.Th>Escuela</Table.Th>
                <Table.Th>Estado</Table.Th>
                <Table.Th>Prioridad</Table.Th>
                <Table.Th ta="right">Sin movimiento</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {reclamos.map((reclamo) => (
                <Table.Tr
                  key={reclamo.id}
                  className={classes.filaClickeable}
                  onClick={() => abrir(reclamo)}
                >
                  <Table.Td>
                    <Text ff="monospace" size="sm">
                      {formatearIdReclamo(reclamo.id)}
                    </Text>
                  </Table.Td>
                  <Table.Td>{reclamo.nombre_escuela}</Table.Td>
                  <Table.Td>
                    <StatusBadge estado={reclamo.estado} variant="light" />
                  </Table.Td>
                  <Table.Td>
                    <PriorityBadge prioridad={reclamo.prioridad} fz="sm" />
                  </Table.Td>
                  <Table.Td ta="right">
                    <Badge color={colorAntiguedad(reclamo.dias_sin_movimiento)} variant="light">
                      {reclamo.dias_sin_movimiento} días
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Card>
  );
}
