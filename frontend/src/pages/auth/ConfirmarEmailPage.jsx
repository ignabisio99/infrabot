import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router';
import { Alert, Button, Container, Loader, Paper, Stack, Text } from '@mantine/core';
import { IconCheck, IconX } from '@tabler/icons-react';
import { API_URL } from '../../api/apiClient';
import logo from '../../assets/logo-infrabot-front.png';

export function ConfirmarEmailPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [estado, setEstado] = useState('loading'); // loading | success | error
  const [mensaje, setMensaje] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setEstado('error');
      setMensaje('Token no proporcionado');
      return;
    }

    fetch(`${API_URL}/auth/confirmar?token=${token}`)
      .then(async (res) => {
        const data = await res.json();
        if (res.ok) {
          setEstado('success');
          setMensaje(data.mensaje);
        } else {
          setEstado('error');
          setMensaje(data.detail || 'Error al confirmar el email');
        }
      })
      .catch(() => {
        setEstado('error');
        setMensaje('Error de conexión con el servidor');
      });
  }, [searchParams]);

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #132a4d 0%, #1a3a5c 50%, #1fa7b3 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Container size={440}>
        <Stack align="center" mb="lg">
          <img
            src={logo}
            alt="InfraBot"
            height={72}
            style={{ borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}
          />
        </Stack>

        <Paper radius="md" p="xl" shadow="xl" withBorder>
          <Stack align="center" gap="md">
            {estado === 'loading' && (
              <>
                <Loader color="#1fa7b3" />
                <Text>Confirmando tu email...</Text>
              </>
            )}

            {estado === 'success' && (
              <>
                <Alert icon={<IconCheck size={16} />} color="yellow" variant="light" w="100%">
                  <Text fw={500}>Email confirmado correctamente</Text>
                  <Text size="sm" mt="xs">
                    Tu cuenta está pendiente de aprobación por un administrador. Te notificaremos
                    cuando sea aprobada.
                  </Text>
                </Alert>
                <Button color="#1fa7b3" fullWidth onClick={() => navigate('/')}>
                  Volver al inicio
                </Button>
              </>
            )}

            {estado === 'error' && (
              <>
                <Alert icon={<IconX size={16} />} color="red" variant="light" w="100%">
                  {mensaje}
                </Alert>
                <Button color="#1fa7b3" variant="outline" fullWidth onClick={() => navigate('/')}>
                  Volver al inicio
                </Button>
              </>
            )}
          </Stack>
        </Paper>
      </Container>
    </div>
  );
}
