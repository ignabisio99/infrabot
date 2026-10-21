import { useEffect, useState } from 'react';
import { Alert, Badge, Container, Group, Loader, Stack, Table, Text, Title } from '@mantine/core';

import { TarjetaMovil } from '../../components/TarjetaMovil';
import { useEsMobile } from '../../hooks/useEsMobile';
import { listarAdministradores } from '../../api/usuarios';

const fechaAlta = (admin) => new Date(admin.fecha_creacion).toLocaleDateString('es-AR');

export function AdminsListPage({ usuarioId }) {
  const [administradores, setAdministradores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    listarAdministradores()
      .then(setAdministradores)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  const esMobile = useEsMobile();

  const nombre = (admin) => (
    <>
      {admin.nombre}
      {admin.id === usuarioId && (
        <Badge component="span" size="xs" variant="light" color="teal" ml={6}>
          Vos
        </Badge>
      )}
    </>
  );

  return (
    <Container fluid px={0}>
      <Group justify="space-between" mb="md" wrap="wrap">
        <Title order={2}>Administradores</Title>
      </Group>

      {cargando && <Loader />}

      {error && (
        <Alert color="red" title="Ocurrió un error" mb="md">
          {error}
        </Alert>
      )}

      {!cargando && !error && administradores.length === 0 && (
        <Text c="dimmed">Todavía no hay administradores registrados.</Text>
      )}

      {!cargando && administradores.length > 0 && esMobile && (
        <Stack gap="sm">
          {administradores.map((admin) => (
            <TarjetaMovil
              key={admin.id}
              titulo={nombre(admin)}
              campos={[
                { etiqueta: 'Email', valor: admin.email },
                { etiqueta: 'Teléfono', valor: admin.telefono || '—' },
                { etiqueta: 'Dirección', valor: admin.direccion || '—' },
                { etiqueta: 'Alta', valor: fechaAlta(admin) },
              ]}
            />
          ))}
        </Stack>
      )}

      {!cargando && administradores.length > 0 && !esMobile && (
        <Table.ScrollContainer minWidth={700}>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Nombre</Table.Th>
                <Table.Th>Email</Table.Th>
                <Table.Th>Teléfono</Table.Th>
                <Table.Th>Dirección</Table.Th>
                <Table.Th>Alta</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {administradores.map((admin) => (
                <Table.Tr key={admin.id}>
                  <Table.Td>{nombre(admin)}</Table.Td>
                  <Table.Td>{admin.email}</Table.Td>
                  <Table.Td>{admin.telefono || '—'}</Table.Td>
                  <Table.Td>{admin.direccion || '—'}</Table.Td>
                  <Table.Td>{fechaAlta(admin)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Container>
  );
}
