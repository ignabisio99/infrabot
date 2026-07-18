import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Badge, Button, Container, Group, Loader, Table, Text, Title } from '@mantine/core';

import { eliminarReclamo, listarReclamos } from '../api/reclamos';

const colorPorPrioridad = {
  ALTA: 'red',
  MEDIA: 'yellow',
  BAJA: 'green',
};

export function ClaimsListPage() {
  const navigate = useNavigate();
  const [reclamos, setReclamos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [eliminandoId, setEliminandoId] = useState(null);

  useEffect(() => {
    listarReclamos()
      .then(setReclamos)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  const handleEliminar = async (id) => {
    if (!window.confirm('¿Seguro que querés eliminar este reclamo?')) return;

    setError(null);
    setEliminandoId(id);
    try {
      await eliminarReclamo(id);
      setReclamos((actuales) => actuales.filter((reclamo) => reclamo.id !== id));
    } catch (err) {
      setError(err.message);
    } finally {
      setEliminandoId(null);
    }
  };

  return (
    <Container size="lg" py="xl">
      <Title order={2} mb="md">
        Reclamos
      </Title>

      {cargando && <Loader />}

      {error && (
        <Alert color="red" title="Ocurrió un error" mb="md">
          {error}
        </Alert>
      )}

      {!cargando && reclamos.length === 0 && (
        <Text c="dimmed">Todavía no hay reclamos registrados.</Text>
      )}

      {!cargando && reclamos.length > 0 && (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Escuela</Table.Th>
              <Table.Th>Sector</Table.Th>
              <Table.Th>Prioridad</Table.Th>
              <Table.Th>Categoría</Table.Th>
              <Table.Th>Descripción</Table.Th>
              <Table.Th>Fecha</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {reclamos.map((reclamo) => (
              <Table.Tr key={reclamo.id}>
                <Table.Td>{reclamo.nombre_escuela}</Table.Td>
                <Table.Td>{reclamo.sector}</Table.Td>
                <Table.Td>
                  <Badge color={colorPorPrioridad[reclamo.prioridad]}>{reclamo.prioridad}</Badge>
                </Table.Td>
                <Table.Td>{reclamo.categoria}</Table.Td>
                <Table.Td>
                  <Text truncate="end" maw={280} title={reclamo.descripcion}>
                    {reclamo.descripcion}
                  </Text>
                </Table.Td>
                <Table.Td>{new Date(reclamo.creado_en).toLocaleString('es-AR')}</Table.Td>
                <Table.Td>
                  <Group gap="xs" wrap="nowrap">
                    <Button
                      variant="subtle"
                      size="xs"
                      onClick={() => navigate(`/reclamos/${reclamo.id}/editar`)}
                    >
                      Editar
                    </Button>
                    <Button
                      color="red"
                      variant="subtle"
                      size="xs"
                      loading={eliminandoId === reclamo.id}
                      onClick={() => handleEliminar(reclamo.id)}
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
