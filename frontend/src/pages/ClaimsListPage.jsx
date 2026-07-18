import { useEffect, useState } from 'react';
import { Alert, Badge, Container, Loader, Table, Text, Title } from '@mantine/core';

import { listarReclamos } from '../api/reclamos';

const colorPorPrioridad = {
  ALTA: 'red',
  MEDIA: 'yellow',
  BAJA: 'green',
};

export function ClaimsListPage() {
  const [reclamos, setReclamos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    listarReclamos()
      .then(setReclamos)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  return (
    <Container size="lg" py="xl">
      <Title order={2} mb="md">
        Reclamos
      </Title>

      {cargando && <Loader />}

      {error && (
        <Alert color="red" title="No se pudo cargar el listado">
          {error}
        </Alert>
      )}

      {!cargando && !error && reclamos.length === 0 && (
        <Text c="dimmed">Todavía no hay reclamos registrados.</Text>
      )}

      {!cargando && !error && reclamos.length > 0 && (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Escuela</Table.Th>
              <Table.Th>Sector</Table.Th>
              <Table.Th>Prioridad</Table.Th>
              <Table.Th>Categoría</Table.Th>
              <Table.Th>Descripción</Table.Th>
              <Table.Th>Fecha</Table.Th>
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
                <Table.Td>{reclamo.descripcion}</Table.Td>
                <Table.Td>{new Date(reclamo.creado_en).toLocaleString('es-AR')}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Container>
  );
}
