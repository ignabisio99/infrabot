import { useCallback, useEffect, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { IconGavel, IconListDetails, IconShieldCheck } from '@tabler/icons-react';

import { listarPresupuestos } from '../../api/presupuestos';
import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda } from '../../utils/formatters';
import { BudgetAuditModal } from './BudgetAuditModal';
import { BudgetItemsModal } from './BudgetItemsModal';
import { BudgetStatusBadge } from './BudgetStatusBadge';
import { DecideBudgetModal } from './DecideBudgetModal';

export function BudgetsListPage() {
  const [presupuestos, setPresupuestos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [presupuestoSeleccionado, setPresupuestoSeleccionado] = useState(null);
  const [presupuestoAAuditar, setPresupuestoAAuditar] = useState(null);
  const [presupuestoADecidir, setPresupuestoADecidir] = useState(null);

  const cargar = useCallback(
    () =>
      listarPresupuestos()
        .then(setPresupuestos)
        .catch((err) => setError(err.message))
        .finally(() => setCargando(false)),
    [],
  );

  useEffect(() => {
    cargar();
  }, [cargar]);

  return (
    <Container fluid px={0}>
      <Group justify="space-between" mb="md">
        <Title order={2}>Presupuestos</Title>
      </Group>

      {cargando && <Loader />}

      {error && (
        <Alert color="red" title="Ocurrió un error" mb="md">
          {error}
        </Alert>
      )}

      {!cargando && presupuestos.length === 0 && (
        <Text c="dimmed">Todavía no hay presupuestos registrados.</Text>
      )}

      {!cargando && presupuestos.length > 0 && (
        <Table.ScrollContainer minWidth={900}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th />
                <Table.Th>ID Reclamo</Table.Th>
                <Table.Th>Escuela</Table.Th>
                <Table.Th>Contratista</Table.Th>
                <Table.Th>Monto</Table.Th>
                <Table.Th miw={130}>Estado</Table.Th>
                <Table.Th>Fecha</Table.Th>
                <Table.Th>Observaciones</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {presupuestos.map((presupuesto) => (
                <Table.Tr
                  key={presupuesto.id}
                  onClick={() => setPresupuestoSeleccionado(presupuesto)}
                  style={{ cursor: 'pointer' }}
                >
                  <Table.Td w={40}>
                    <ActionIcon variant="subtle" size="sm" aria-label="Ver ítems">
                      <IconListDetails size={16} />
                    </ActionIcon>
                  </Table.Td>
                  <Table.Td>{formatearIdReclamo(presupuesto.reclamo.id)}</Table.Td>
                  <Table.Td>{presupuesto.reclamo.nombre_escuela}</Table.Td>
                  <Table.Td>
                    {presupuesto.contratista.nombre_empresa}
                    {presupuesto.intento > 1 && (
                      <Badge ml={6} size="xs" color="gray" variant="outline" tt="none">
                        Intento {presupuesto.intento}
                      </Badge>
                    )}
                  </Table.Td>
                  <Table.Td>{formatoMoneda.format(Number(presupuesto.monto))}</Table.Td>
                  <Table.Td miw={130}>
                    <BudgetStatusBadge estado={presupuesto.estado} />
                  </Table.Td>
                  <Table.Td>{new Date(presupuesto.fecha).toLocaleString('es-AR')}</Table.Td>
                  <Table.Td>
                    {presupuesto.observaciones ? (
                      <Text truncate="end" maw={200} title={presupuesto.observaciones}>
                        {presupuesto.observaciones}
                      </Text>
                    ) : (
                      <Text c="dimmed">—</Text>
                    )}
                  </Table.Td>
                  <Table.Td onClick={(e) => e.stopPropagation()}>
                    <Group gap="xs" wrap="nowrap" justify="flex-end">
                      {presupuesto.estado !== 'APROBADO' && (
                        <Button
                          size="xs"
                          variant="light"
                          color="gray"
                          leftSection={<IconShieldCheck size={14} />}
                          onClick={() => setPresupuestoAAuditar(presupuesto)}
                        >
                          Auditoría
                        </Button>
                      )}
                      <Button
                        size="xs"
                        color="teal"
                        leftSection={<IconGavel size={14} />}
                        onClick={() => setPresupuestoADecidir(presupuesto)}
                        disabled={presupuesto.estados_posibles.length === 0}
                      >
                        Aprobar / Rechazar
                      </Button>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      <BudgetItemsModal
        presupuesto={presupuestoSeleccionado}
        onClose={() => setPresupuestoSeleccionado(null)}
        onDecidido={() => {
          setPresupuestoSeleccionado(null);
          cargar();
        }}
      />

      <BudgetAuditModal
        presupuesto={presupuestoAAuditar}
        onClose={() => setPresupuestoAAuditar(null)}
      />

      {/* Recarga la lista entera y no la fila: aprobar uno deja a los otros del mismo
          reclamo como no seleccionados. */}
      <DecideBudgetModal
        presupuesto={presupuestoADecidir}
        onClose={() => setPresupuestoADecidir(null)}
        onDecidido={cargar}
      />
    </Container>
  );
}
