import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import {
  Alert,
  Button,
  Container,
  List,
  Loader,
  Paper,
  PasswordInput,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconCheck, IconLock, IconX } from '@tabler/icons-react';

import { restablecerPassword, validarLinkRestablecer } from '../../api/auth';
import logo from '../../assets/logo-infrabot-front.png';

/**
 * Pantalla del link "Elegir una contraseña nueva" que llega por email
 * (/restablecer-password?token=...). Primero verifica que el link siga sirviendo, así si
 * venció o ya se usó lo dice antes de que la persona escriba nada.
 */
export function RestablecerPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') ?? '';

  // Resultado de validar el link: { token, email } o { token, error }.
  const [validacion, setValidacion] = useState(null);
  const [password, setPassword] = useState('');
  const [confirmacion, setConfirmacion] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [listo, setListo] = useState(false);

  useEffect(() => {
    if (!token) return;
    let vigente = true;
    validarLinkRestablecer(token)
      .then(({ email }) => {
        if (vigente) setValidacion({ token, email });
      })
      .catch((err) => {
        if (vigente) setValidacion({ token, error: err.message });
      });
    return () => {
      vigente = false;
    };
  }, [token]);

  const actual = validacion?.token === token ? validacion : null;
  const linkInvalido = !token
    ? 'El link no es válido. Pedí uno nuevo desde el inicio de sesión.'
    : actual?.error;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    if (password !== confirmacion) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    setEnviando(true);
    try {
      await restablecerPassword(token, password);
      setListo(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  // Al volver al login se saca el token de la URL: no tiene que quedar en el historial.
  const irAlLogin = () => navigate('/', { replace: true });

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
      <Container size={440} w="100%">
        <Stack align="center" mb="lg">
          <img
            src={logo}
            alt="InfraBot"
            height={72}
            style={{ borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}
          />
        </Stack>

        <Paper radius="md" p="xl" shadow="xl" withBorder>
          {linkInvalido ? (
            <Stack gap="md">
              <Alert icon={<IconX size={16} />} color="red" variant="light">
                {linkInvalido}
              </Alert>
              <Button color="#1fa7b3" fullWidth onClick={irAlLogin}>
                Ir a iniciar sesión
              </Button>
            </Stack>
          ) : listo ? (
            <Stack gap="md">
              <Alert icon={<IconCheck size={16} />} color="teal" variant="light">
                Listo, cambiaste tu contraseña. Ya podés iniciar sesión con la nueva.
              </Alert>
              <Button color="#1fa7b3" fullWidth onClick={irAlLogin}>
                Ir a iniciar sesión
              </Button>
            </Stack>
          ) : !actual ? (
            <Stack align="center" gap="md">
              <Loader color="#1fa7b3" />
              <Text>Verificando el link…</Text>
            </Stack>
          ) : (
            <form onSubmit={handleSubmit}>
              <Stack>
                <div>
                  <Title order={3}>Elegí una contraseña nueva</Title>
                  <Text size="sm" c="dimmed">
                    Para la cuenta {actual.email}
                  </Text>
                </div>

                {error && (
                  <Alert color="red" variant="light">
                    {error}
                  </Alert>
                )}

                <PasswordInput
                  label="Contraseña nueva"
                  placeholder="Mínimo 8 caracteres"
                  leftSection={<IconLock size={16} />}
                  required
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.currentTarget.value)}
                />
                <List size="xs" c="dimmed" spacing={4}>
                  <List.Item>Mínimo 8 caracteres</List.Item>
                  <List.Item>Al menos una mayúscula</List.Item>
                  <List.Item>Al menos un símbolo especial (!@#$%...)</List.Item>
                </List>
                <PasswordInput
                  label="Repetí la contraseña"
                  placeholder="Repetí la contraseña nueva"
                  leftSection={<IconLock size={16} />}
                  required
                  autoComplete="new-password"
                  value={confirmacion}
                  onChange={(e) => setConfirmacion(e.currentTarget.value)}
                />
                <Button type="submit" fullWidth color="#1fa7b3" loading={enviando}>
                  Cambiar contraseña
                </Button>
              </Stack>
            </form>
          )}
        </Paper>
      </Container>
    </div>
  );
}
