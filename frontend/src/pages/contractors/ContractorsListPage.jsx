import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import {
  ActionIcon,
  Alert,
  Button,
  Container,
  Group,
  Loader,
  Menu,
  Modal,
  Popover,
  Stack,
  Switch,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { IconNote, IconUserCheck } from '@tabler/icons-react';

import { RowActionsMenu } from '../../components/RowActionsMenu';
import { TarjetaMovil } from '../../components/TarjetaMovil';
import { useEsMobile } from '../../hooks/useEsMobile';
import {
  darDeBajaContratista,
  listarContratistas,
  reactivarContratista,
} from '../../api/contratistas';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { DadoDeBajaBadge } from './DadoDeBajaBadge';

export function ContractorsListPage() {
  const navigate = useNavigate();
  const [contratistas, setContratistas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [verDadosDeBaja, setVerDadosDeBaja] = useState(false);
  const [aDarDeBaja, setADarDeBaja] = useState(null);
  const [errorBaja, setErrorBaja] = useState(null);
  const [procesandoId, setProcesandoId] = useState(null);

  useEffect(() => {
    listarContratistas({ incluirBaja: true })
      .then(setContratistas)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  const cantidadDadosDeBaja = contratistas.filter((c) => c.fecha_baja).length;
  const visibles = verDadosDeBaja ? contratistas : contratistas.filter((c) => !c.fecha_baja);

  const reemplazar = (actualizado) =>
    setContratistas((actuales) => actuales.map((c) => (c.id === actualizado.id ? actualizado : c)));

  const cerrarBaja = () => {
    setADarDeBaja(null);
    setErrorBaja(null);
  };

  const confirmarBaja = async () => {
    const contratista = aDarDeBaja;
    setProcesandoId(contratista.id);
    setErrorBaja(null);
    try {
      await darDeBajaContratista(contratista.id);
      reemplazar({ ...contratista, fecha_baja: new Date().toISOString() });
      notifySuccess(`${contratista.nombre_empresa} quedó dado de baja.`);
      cerrarBaja();
    } catch (err) {
      setErrorBaja(err.message);
    } finally {
      setProcesandoId(null);
    }
  };

  const handleReactivar = async (contratista) => {
    setProcesandoId(contratista.id);
    try {
      reemplazar(await reactivarContratista(contratista.id));
      notifySuccess(`${contratista.nombre_empresa} volvió a estar activo.`);
    } catch (err) {
      notifyError(err?.message);
    } finally {
      setProcesandoId(null);
    }
  };

  const esMobile = useEsMobile();

  const calificacion = (contratista) => (
    <Group gap={6} wrap="nowrap">
      <Text size="sm">
        {contratista.calificacion != null ? `${contratista.calificacion} / 5` : 'N/A'}
      </Text>
      {contratista.observaciones_calificacion && (
        <Popover width={280} position="top" withArrow shadow="md">
          <Popover.Target>
            <ActionIcon
              variant="subtle"
              color="gray"
              size="sm"
              aria-label="Ver observación de la calificación"
            >
              <IconNote size={16} />
            </ActionIcon>
          </Popover.Target>
          <Popover.Dropdown>
            <Text size="xs" fw={600} c="dimmed" mb={4}>
              Observación
            </Text>
            <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
              {contratista.observaciones_calificacion}
            </Text>
          </Popover.Dropdown>
        </Popover>
      )}
    </Group>
  );

  const acciones = (contratista) =>
    contratista.fecha_baja ? (
      <RowActionsMenu
        onEdit={() => navigate(`/contratistas/${contratista.id}/editar`)}
        extraItems={
          <Menu.Item
            leftSection={<IconUserCheck size={14} />}
            onClick={() => handleReactivar(contratista)}
            disabled={procesandoId === contratista.id}
          >
            Reactivar
          </Menu.Item>
        }
      />
    ) : (
      <RowActionsMenu
        onEdit={() => navigate(`/contratistas/${contratista.id}/editar`)}
        onDelete={() => setADarDeBaja(contratista)}
        deleting={procesandoId === contratista.id}
        deleteLabel="Dar de baja"
        deletingLabel="Dando de baja..."
      />
    );

  return (
    <Container fluid px={0}>
      <Group justify="space-between" mb="md" wrap="wrap">
        <Title order={2}>Contratistas</Title>
        <Group gap="md" wrap="wrap">
          {cantidadDadosDeBaja > 0 && (
            <Switch
              label={`Mostrar dados de baja (${cantidadDadosDeBaja})`}
              checked={verDadosDeBaja}
              onChange={(event) => setVerDadosDeBaja(event.currentTarget.checked)}
            />
          )}
          <Button onClick={() => navigate('/contratistas/nuevo')}>+ Nuevo Contratista</Button>
        </Group>
      </Group>

      {cargando && <Loader />}

      {error && (
        <Alert color="red" title="Ocurrió un error" mb="md">
          {error}
        </Alert>
      )}

      {!cargando && visibles.length === 0 && (
        <Text c="dimmed">
          {contratistas.length === 0
            ? 'Todavía no hay contratistas registrados.'
            : 'No hay contratistas activos.'}
        </Text>
      )}

      {!cargando && visibles.length > 0 && esMobile && (
        <Stack gap="sm">
          {visibles.map((contratista) => (
            <TarjetaMovil
              key={contratista.id}
              titulo={contratista.nombre_empresa}
              acciones={acciones(contratista)}
              badges={contratista.fecha_baja && <DadoDeBajaBadge />}
              campos={[
                { etiqueta: 'Teléfono', valor: contratista.telefono },
                { etiqueta: 'Dirección', valor: contratista.direccion },
                { etiqueta: 'Especialidad', valor: contratista.especialidad },
                { etiqueta: 'Calificación', valor: calificacion(contratista) },
              ]}
            />
          ))}
        </Stack>
      )}

      {!cargando && visibles.length > 0 && !esMobile && (
        <Table.ScrollContainer minWidth={700}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Empresa</Table.Th>
                <Table.Th>Teléfono</Table.Th>
                <Table.Th>Dirección</Table.Th>
                <Table.Th>Especialidad</Table.Th>
                <Table.Th>Calificación</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {visibles.map((contratista) => (
                <Table.Tr key={contratista.id}>
                  <Table.Td>
                    <Group gap="xs" wrap="nowrap">
                      {contratista.nombre_empresa}
                      {contratista.fecha_baja && <DadoDeBajaBadge />}
                    </Group>
                  </Table.Td>
                  <Table.Td>{contratista.telefono}</Table.Td>
                  <Table.Td>{contratista.direccion}</Table.Td>
                  <Table.Td>{contratista.especialidad}</Table.Td>
                  <Table.Td>{calificacion(contratista)}</Table.Td>
                  <Table.Td>{acciones(contratista)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      <Modal
        opened={aDarDeBaja !== null}
        onClose={cerrarBaja}
        title={aDarDeBaja ? `Dar de baja a ${aDarDeBaja.nombre_empresa}` : ''}
        centered
      >
        <Stack>
          <Text size="sm">
            No se lo va a poder convocar ni va a poder cargar presupuestos. Sus presupuestos y
            visitas anteriores se conservan, y podés reactivarlo cuando quieras.
          </Text>
          {errorBaja && (
            <Alert color="red" title="No se pudo dar de baja">
              {errorBaja}
            </Alert>
          )}
          <Group justify="flex-end">
            <Button variant="default" onClick={cerrarBaja}>
              Cancelar
            </Button>
            <Button
              color="red"
              onClick={confirmarBaja}
              loading={aDarDeBaja !== null && procesandoId === aDarDeBaja.id}
            >
              Dar de baja
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  );
}
