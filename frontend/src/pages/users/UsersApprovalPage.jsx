import { useEffect, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Container,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconAlertCircle, IconCheck, IconUserCheck, IconUserX } from '@tabler/icons-react';
import { API_URL } from '../../api/apiClient';
import { formatearTelefono } from '../../utils/telefonos';

export function UsersApprovalPage() {
  const [usuarios, setUsuarios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/auth/pendientes`, { credentials: 'include' })
      .then((response) => {
        if (!response.ok) throw new Error('Error al obtener usuarios pendientes');
        return response.json();
      })
      .then(setUsuarios)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleAprobar = async (id) => {
    setActionLoading(id);
    try {
      const response = await fetch(`${API_URL}/auth/aprobar/${id}`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Error al aprobar usuario');
      setUsuarios((prev) => prev.filter((u) => u.id !== id));
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRechazar = async (id) => {
    setActionLoading(id);
    try {
      const response = await fetch(`${API_URL}/auth/rechazar/${id}`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Error al rechazar usuario');
      setUsuarios((prev) => prev.filter((u) => u.id !== id));
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <Container fluid px={0}>
        <Stack align="center" mt="xl">
          <Loader color="#1fa7b3" />
          <Text>Cargando solicitudes...</Text>
        </Stack>
      </Container>
    );
  }

  return (
    <Container fluid px={0}>
      <Title order={2} mb="lg">
        Solicitudes de registro pendientes
      </Title>

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} color="red" mb="md" variant="light">
          {error}
        </Alert>
      )}

      {usuarios.length === 0 ? (
        <Alert icon={<IconCheck size={16} />} color="green" variant="light">
          No hay solicitudes pendientes de aprobación.
        </Alert>
      ) : (
        <SimpleGrid cols={{ base: 1, lg: 2 }}>
          {usuarios.map((usuario) => (
            <Card key={usuario.id} shadow="sm" padding="lg" radius="md" withBorder>
              <Group justify="space-between" wrap="wrap">
                <div>
                  <Group gap="xs" mb={4}>
                    <Text fw={600} size="lg">
                      {usuario.nombre}
                    </Text>
                    <Badge color="blue" variant="light" size="sm">
                      {usuario.tipo || 'Sin tipo'}
                    </Badge>
                  </Group>
                  <Text size="sm" c="dimmed">
                    {usuario.email}
                  </Text>
                  {usuario.telefono && (
                    <Text size="sm" c="dimmed">
                      Tel: {formatearTelefono(usuario.telefono)}
                    </Text>
                  )}
                  {usuario.direccion && (
                    <Text size="sm" c="dimmed">
                      Dir: {usuario.direccion}
                    </Text>
                  )}
                  {usuario.nombre_empresa && (
                    <Text size="sm" c="dimmed">
                      Empresa: {usuario.nombre_empresa}
                    </Text>
                  )}
                  {usuario.especialidad && (
                    <Text size="sm" c="dimmed">
                      Especialidad: {usuario.especialidad}
                    </Text>
                  )}
                  <Text size="xs" c="dimmed" mt={4}>
                    Registrado: {new Date(usuario.fecha_creacion).toLocaleDateString('es-AR')}
                  </Text>
                </div>

                <Group gap="xs">
                  <Button
                    color="green"
                    leftSection={<IconUserCheck size={16} />}
                    loading={actionLoading === usuario.id}
                    onClick={() => handleAprobar(usuario.id)}
                  >
                    Aprobar
                  </Button>
                  <Button
                    color="red"
                    variant="outline"
                    leftSection={<IconUserX size={16} />}
                    loading={actionLoading === usuario.id}
                    onClick={() => handleRechazar(usuario.id)}
                  >
                    Rechazar
                  </Button>
                </Group>
              </Group>
            </Card>
          ))}
        </SimpleGrid>
      )}
    </Container>
  );
}
