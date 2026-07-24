import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Container, Group, Loader, Table, Text, Title } from '@mantine/core';

import { eliminarContratista, listarContratistas } from '../api/contratistas';
import { notifyError } from '../utils/notifications';

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
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEliminandoId(null);
    }
  };

  return (
    <Container fluid py="xl">
      <Group justify="space-between" mb="md">
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

      {!cargando && contratistas.length > 0 && (
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
                <Table.Td>{contratista.calificacion} / 5</Table.Td>
                <Table.Td>
                  <Group gap="xs" wrap="nowrap">
                    <Button
                      variant="subtle"
                      size="xs"
                      onClick={() => navigate(`/contratistas/${contratista.id}/editar`)}
                    >
                      Editar
                    </Button>
                    <Button
                      color="red"
                      variant="subtle"
                      size="xs"
                      loading={eliminandoId === contratista.id}
                      onClick={() => handleEliminar(contratista.id)}
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
    </Container>
  );
}
