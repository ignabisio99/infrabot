import { useState } from 'react';
import { Alert, Button, Group, Modal, Stack, Text, TextInput } from '@mantine/core';
import { IconCheck, IconMail } from '@tabler/icons-react';

import { pedirRestablecerPassword } from '../../api/auth';

/**
 * "¿Olvidaste tu contraseña?": pide el email y manda el link para elegir una nueva. El
 * mensaje de éxito es el mismo exista o no la cuenta (no se revela qué emails hay).
 */
export function OlvidePasswordModal({ opened, onClose, emailInicial = '' }) {
  const [email, setEmail] = useState(emailInicial);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');
  const [enviado, setEnviado] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setEnviando(true);
    try {
      const { mensaje } = await pedirRestablecerPassword(email.trim());
      setEnviado(mensaje);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  const cerrar = () => {
    setEnviado('');
    setError('');
    onClose();
  };

  return (
    <Modal opened={opened} onClose={cerrar} title="Restablecer contraseña" centered>
      {enviado ? (
        <Stack>
          <Alert icon={<IconCheck size={16} />} color="teal" variant="light">
            {enviado}
          </Alert>
          <Text size="sm" c="dimmed">
            El link vence en 1 hora. Si no te llega, revisá que el email esté bien escrito y volvé a
            pedirlo.
          </Text>
          <Group justify="flex-end">
            <Button color="#1fa7b3" onClick={cerrar}>
              Volver a iniciar sesión
            </Button>
          </Group>
        </Stack>
      ) : (
        <form onSubmit={handleSubmit}>
          <Stack>
            <Text size="sm" c="dimmed">
              Ingresá el email de tu cuenta y te mandamos un link para elegir una contraseña nueva.
            </Text>
            {error && (
              <Alert color="red" variant="light">
                {error}
              </Alert>
            )}
            <TextInput
              label="Email"
              placeholder="tu@email.com"
              type="email"
              leftSection={<IconMail size={16} />}
              required
              data-autofocus
              value={email}
              onChange={(e) => setEmail(e.currentTarget.value)}
            />
            <Group justify="flex-end">
              <Button variant="default" onClick={cerrar}>
                Cancelar
              </Button>
              <Button type="submit" color="#1fa7b3" loading={enviando}>
                Enviar link
              </Button>
            </Group>
          </Stack>
        </form>
      )}
    </Modal>
  );
}
