import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Badge, Button, Container, Group, Loader, Table, Text, Title } from '@mantine/core';

import { listarMisPresupuestos } from '../../api/contratistas';
import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda } from '../../utils/formatters';
import { BudgetItemsModal } from '../budgets/BudgetItemsModal';
import { BudgetStatusBadge } from '../budgets/BudgetStatusBadge';

export function MyPresupuestosPage() {
  const navigate = useNavigate();
  const [presupuestos, setPresupuestos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [seleccionado, setSeleccionado] = useState(null);

  useEffect(() => {
    listarMisPresupuestos()
      .then(setPresupuestos)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  return (
    <Container size="md" px={0}>
      <Title order={2} mb="lg">
        Mis presupuestos
      </Title>

      {cargando && <Loader />}

      {error && (
        <Alert color="red" title="No se pudieron cargar tus presupuestos">
          {error}
        </Alert>
      )}

      {!cargando && !error && presupuestos.length === 0 && (
        <Text c="dimmed">Todavía no cargaste ningún presupuesto.</Text>
      )}

      {!cargando && !error && presupuestos.length > 0 && (
        <Table.ScrollContainer minWidth={600}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Reclamo</Table.Th>
                <Table.Th>Escuela</Table.Th>
                <Table.Th>Fecha</Table.Th>
                <Table.Th>Monto</Table.Th>
                <Table.Th>Estado</Table.Th>
                <Table.Th>Ítems</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {presupuestos.map((p) => (
                <Table.Tr
                  key={p.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setSeleccionado(p)}
                >
                  <Table.Td>{formatearIdReclamo(p.reclamo.id)}</Table.Td>
                  <Table.Td>{p.reclamo.nombre_escuela}</Table.Td>
                  <Table.Td>{new Date(p.fecha).toLocaleDateString('es-AR')}</Table.Td>
                  <Table.Td>{formatoMoneda.format(Number(p.monto))}</Table.Td>
                  <Table.Td>
                    <Group gap={4}>
                      <BudgetStatusBadge estado={p.estado} />
                      {p.intento > 1 && (
                        <Badge color="gray" variant="outline" tt="none">
                          Intento {p.intento}
                        </Badge>
                      )}
                    </Group>
                  </Table.Td>
                  <Table.Td>{p.items.length}</Table.Td>
                  <Table.Td onClick={(e) => e.stopPropagation()}>
                    {(p.editable || p.reenviable) && (
                      <Button
                        size="xs"
                        variant={p.reenviable ? 'filled' : 'light'}
                        color={p.reenviable ? 'orange' : undefined}
                        onClick={() => navigate(`/portal/reclamos/${p.reclamo.id}/presupuestar`)}
                      >
                        {p.reenviable ? 'Corregir y reenviar' : 'Editar'}
                      </Button>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      <BudgetItemsModal presupuesto={seleccionado} onClose={() => setSeleccionado(null)} />
    </Container>
  );
}
