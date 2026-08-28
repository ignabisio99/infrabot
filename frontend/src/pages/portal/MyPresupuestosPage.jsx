import { useEffect, useState } from 'react';
import { Alert, Container, Group, Loader, Table, Text, Title } from '@mantine/core';

import { listarMisPresupuestos } from '../../api/contratistas';
import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda } from '../../utils/formatters';
import { BudgetItemsModal } from '../budgets/BudgetItemsModal';

export function MyPresupuestosPage() {
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
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Reclamo</Table.Th>
              <Table.Th>Escuela</Table.Th>
              <Table.Th>Fecha</Table.Th>
              <Table.Th>Monto</Table.Th>
              <Table.Th>Ítems</Table.Th>
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
                <Table.Td>{p.items.length}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <BudgetItemsModal presupuesto={seleccionado} onClose={() => setSeleccionado(null)} />
    </Container>
  );
}
