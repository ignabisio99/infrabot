import { Alert, Button, Container, Paper, Stack, Text } from '@mantine/core';
import { IconClock } from '@tabler/icons-react';
import logo from '../../assets/logo-infrabot-front.png';

export function PendienteAprobacionPage({ onLogout }) {
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
            <Alert icon={<IconClock size={16} />} color="yellow" variant="light" w="100%">
              <Text fw={500}>Tu cuenta está pendiente de aprobación</Text>
              <Text size="sm" mt="xs">
                Un administrador revisará tu solicitud. Te notificaremos cuando tu cuenta sea
                aprobada.
              </Text>
            </Alert>

            <Button variant="outline" color="gray" fullWidth onClick={onLogout}>
              Cerrar sesión
            </Button>
          </Stack>
        </Paper>
      </Container>
    </div>
  );
}
