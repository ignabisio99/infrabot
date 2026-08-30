import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ActionIcon,
  Alert,
  Button,
  Container,
  Group,
  Loader,
  Menu,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { IconGavel, IconListDetails } from '@tabler/icons-react';

import { RowActionsMenu } from '../../components/RowActionsMenu';
import { eliminarPresupuesto, listarPresupuestos } from '../../api/presupuestos';
import { formatearIdReclamo } from '../../utils/ids';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { formatoMoneda } from '../../utils/formatters';
import { BudgetItemsModal } from './BudgetItemsModal';
import { BudgetStatusBadge } from './BudgetStatusBadge';
import { DecideBudgetModal } from './DecideBudgetModal';
import { estaVigente } from './estados';

export function BudgetsListPage() {
  const navigate = useNavigate();
  const [presupuestos, setPresupuestos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [eliminandoId, setEliminandoId] = useState(null);
  const [presupuestoSeleccionado, setPresupuestoSeleccionado] = useState(null);
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
    <Container fluid px={0}>
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
              <Table.Th>Estado</Table.Th>
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
                <Table.Td>
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
                <Table.Td>
                  {/* Un presupuesto ya decidido es parte del expediente: el backend
                      rechaza editarlo y darlo de baja con un 409. */}
                  <RowActionsMenu
                    onEdit={() => navigate(`/presupuestos/${presupuesto.id}/editar`)}
                    onDelete={() => handleEliminar(presupuesto.id)}
                    deleting={eliminandoId === presupuesto.id}
                    editDisabled={!estaVigente(presupuesto)}
                    deleteDisabled={!estaVigente(presupuesto)}
                    extraItems={
                      <Menu.Item
                        leftSection={<IconGavel size={14} />}
                        onClick={() => setPresupuestoADecidir(presupuesto)}
                        disabled={presupuesto.estados_posibles.length === 0}
                      >
                        Decidir
                      </Menu.Item>
                    }
                  />
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
