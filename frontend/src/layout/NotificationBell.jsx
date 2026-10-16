import { useCallback, useEffect, useState } from 'react';
import { ActionIcon, Button, Indicator, Menu, Text } from '@mantine/core';
import { IconBell } from '@tabler/icons-react';
import { useNavigate } from 'react-router';

import { conteoNotificaciones } from '../api/notificaciones';

const EVENTO_NOTIFICACIONES = 'infrabot-notificaciones';

// Lo usan ClaimDetailDrawer y DecideBudgetModal; pasarlo a su propio módulo implica tocar
// ClaimDetailDrawer, que tiene errores de lint propios.
// eslint-disable-next-line react-refresh/only-export-components
export function avisarNotificacionesCambiaron() {
  window.dispatchEvent(new Event(EVENTO_NOTIFICACIONES));
}

export function NotificationBell() {
  const navigate = useNavigate();
  const [abierto, setAbierto] = useState(false);
  const [noLeidas, setNoLeidas] = useState(0);
  const [mensaje, setMensaje] = useState('No hay reclamos en estado pendiente de intervención.');
  const [versiones, setVersiones] = useState(0);

  const refrescarConteo = useCallback(() => {
    conteoNotificaciones()
      .then((data) => {
        setNoLeidas(data.no_leidas || 0);
        setVersiones(data.versiones_por_decidir || 0);
        if (data.mensaje) setMensaje(data.mensaje);
      })
      .catch(() => setNoLeidas(0));
  }, []);

  useEffect(() => {
    refrescarConteo();
    const id = setInterval(refrescarConteo, 45000);
    window.addEventListener(EVENTO_NOTIFICACIONES, refrescarConteo);
    return () => {
      clearInterval(id);
      window.removeEventListener(EVENTO_NOTIFICACIONES, refrescarConteo);
    };
  }, [refrescarConteo]);

  useEffect(() => {
    if (abierto) refrescarConteo();
  }, [abierto, refrescarConteo]);

  const intervenciones = noLeidas - versiones;

  const ir = (ruta) => {
    setAbierto(false);
    navigate(ruta);
  };

  return (
    <Menu shadow="md" width={360} position="bottom-end" opened={abierto} onChange={setAbierto}>
      <Menu.Target>
        <Indicator
          inline
          label={noLeidas > 0 ? (noLeidas > 9 ? '9+' : noLeidas) : undefined}
          size={16}
          color="red"
          disabled={noLeidas === 0}
        >
          <ActionIcon variant="subtle" color="gray" aria-label="Notificaciones">
            <IconBell size={20} />
          </ActionIcon>
        </Indicator>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>Pendientes de intervención</Menu.Label>
        <Text size="sm" px="sm" py="xs">
          {mensaje}
        </Text>
        {intervenciones > 0 && (
          <Button
            fullWidth
            size="xs"
            mx="xs"
            mb="xs"
            w="calc(100% - 16px)"
            onClick={() => ir('/reclamos?estado=PENDIENTE_INTERVENCION')}
          >
            Ver reclamos
          </Button>
        )}
        {versiones > 0 && (
          <>
            <Menu.Divider />
            <Menu.Label>Presupuestos corregidos</Menu.Label>
            <Text size="sm" px="sm" py="xs">
              {versiones === 1
                ? 'Un contratista envió la versión corregida que le pediste y espera tu decisión.'
                : `${versiones} contratistas enviaron la versión corregida que les pediste y esperan tu decisión.`}
            </Text>
            <Button
              fullWidth
              size="xs"
              mx="xs"
              mb="xs"
              w="calc(100% - 16px)"
              onClick={() => ir('/presupuestos')}
            >
              Ver presupuestos
            </Button>
          </>
        )}
      </Menu.Dropdown>
    </Menu>
  );
}
