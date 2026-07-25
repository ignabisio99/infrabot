import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ActionIcon,
  Alert,
  Button,
  Container,
  Group,
  Loader,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { IconListDetails } from '@tabler/icons-react';

import { eliminarPresupuesto, listarPresupuestos } from '../../api/presupuestos';
import { formatearIdReclamo } from '../../utils/ids';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { formatoMoneda } from '../../utils/formatters';
import { BudgetItemsModal } from './BudgetItemsModal';

export function BudgetsListPage() {
  const navigate = useNavigate();
  const [presupuestos, setPresupuestos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [eliminandoId, setEliminandoId] = useState(null);
  const [presupuestoSeleccionado, setPresupuestoSeleccionado] = useState(null);

  useEffect(() => {
    listarPresupuestos()
      .then(setPresupuestos)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  const handleEliminar = async (id) => {
    if (!window.confirm('¿Seguro que querés eliminar este presupuesto?')) return;

    setEliminandoId(id);
    try {
      await eliminarPresupuesto(id);
      setPresupuestos((actuales) => actuales.filter((presupuesto) => presupuesto.id !== id));
      notifySuccess('El presupuesto fue eliminado correctamente.');
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEliminandoId(null);
    }
  };

  return (
    <Container fluid py="xl">
      <Group justify="space-between" mb="md">
        <Title order={2}>Presupuestos</Title>
        <Button onClick={() => navigate('/presupuestos/nuevo')}>+ Nuevo Presupuesto</Button>
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
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th />
              <Table.Th>ID Reclamo</Table.Th>
              <Table.Th>Escuela</Table.Th>
              <Table.Th>Contratista</Table.Th>
              <Table.Th>Monto</Table.Th>
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
                <Table.Td>{presupuesto.contratista.nombre_empresa}</Table.Td>
                <Table.Td>{formatoMoneda.format(Number(presupuesto.monto))}</Table.Td>
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
                <Table.Td>
                  <Group gap="xs" wrap="nowrap" onClick={(event) => event.stopPropagation()}>
                    <Button
                      variant="subtle"
                      size="xs"
                      onClick={() => navigate(`/presupuestos/${presupuesto.id}/editar`)}
                    >
                      Editar
                    </Button>
                    <Button
                      color="red"
                      variant="subtle"
                      size="xs"
                      loading={eliminandoId === presupuesto.id}
                      onClick={() => handleEliminar(presupuesto.id)}
                    >
                      Eliminar
                    </Button>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <BudgetItemsModal
        presupuesto={presupuestoSeleccionado}
        onClose={() => setPresupuestoSeleccionado(null)}
      />
    </Container>
  );
}
