import { Alert, Button, Container, Paper, Stack, Text } from '@mantine/core';
import { IconBan } from '@tabler/icons-react';
import logo from '../../assets/logo-infrabot-front.png';

/**
 * Para una sesión que quedó abierta cuando un admin rechazó la cuenta (por ejemplo, la
 * persona se registró con Google y esperaba la aprobación). La cuenta queda bloqueada:
 * no hay nada que esperar, así que no se muestra la pantalla de "pendiente".
 */
export function CuentaRechazadaPage({ onLogout }) {
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
            <Alert icon={<IconBan size={16} />} color="red" variant="light" w="100%">
              <Text fw={500}>Tu solicitud de cuenta fue rechazada</Text>
              <Text size="sm" mt="xs">
                Un administrador revisó tu solicitud y no fue aprobada, así que no podés usar el
                sistema con esta cuenta. Si creés que es un error, contactá a un administrador.
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
