import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import {
  ActionIcon,
  Alert,
  Button,
  Container,
  Group,
  Loader,
  Popover,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { IconNote } from '@tabler/icons-react';

import { RowActionsMenu } from '../../components/RowActionsMenu';
import { TarjetaMovil } from '../../components/TarjetaMovil';
import { useEsMobile } from '../../hooks/useEsMobile';
import { eliminarContratista, listarContratistas } from '../../api/contratistas';
import { notifyError, notifySuccess } from '../../utils/notifications';

export function ContractorsListPage() {
  const navigate = useNavigate();
  const [contratistas, setContratistas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [eliminandoId, setEliminandoId] = useState(null);

  useEffect(() => {
    listarContratistas()
      .then(setContratistas)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  const handleEliminar = async (id) => {
    if (!window.confirm('¿Seguro que querés eliminar este contratista?')) return;

    setEliminandoId(id);
    try {
      await eliminarContratista(id);
      setContratistas((actuales) => actuales.filter((contratista) => contratista.id !== id));
      notifySuccess('El contratista fue eliminado correctamente.');
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEliminandoId(null);
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

  const acciones = (contratista) => (
    <RowActionsMenu
      onEdit={() => navigate(`/contratistas/${contratista.id}/editar`)}
      onDelete={() => handleEliminar(contratista.id)}
      deleting={eliminandoId === contratista.id}
    />
  );

  return (
    <Container fluid px={0}>
      <Group justify="space-between" mb="md" wrap="wrap">
        <Title order={2}>Contratistas</Title>
        <Button onClick={() => navigate('/contratistas/nuevo')}>+ Nuevo Contratista</Button>
      </Group>

      {cargando && <Loader />}

      {error && (
        <Alert color="red" title="Ocurrió un error" mb="md">
          {error}
        </Alert>
      )}

      {!cargando && contratistas.length === 0 && (
        <Text c="dimmed">Todavía no hay contratistas registrados.</Text>
      )}

      {!cargando && contratistas.length > 0 && esMobile && (
        <Stack gap="sm">
          {contratistas.map((contratista) => (
            <TarjetaMovil
              key={contratista.id}
              titulo={contratista.nombre_empresa}
              acciones={acciones(contratista)}
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

      {!cargando && contratistas.length > 0 && !esMobile && (
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
              {contratistas.map((contratista) => (
                <Table.Tr key={contratista.id}>
                  <Table.Td>{contratista.nombre_empresa}</Table.Td>
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
    </Container>
  );
}
