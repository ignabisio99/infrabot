import { useEffect, useState } from 'react';
import { Badge, Button, Group, Tooltip } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconClock, IconClockPlay } from '@tabler/icons-react';

import { obtenerEstadoSimulador } from '../api/simuladorTiempo';
import { SimuladorTiempoModal } from './SimuladorTiempoModal';

export function SimuladorTiempoControl() {
  const [opened, { open, close }] = useDisclosure(false);
  const [estado, setEstado] = useState(null);

  const refrescar = async () => {
    try {
      const data = await obtenerEstadoSimulador();
      setEstado(data);
    } catch {
      // Si no es admin o falla de red, ignorar
    }
  };

  useEffect(() => {
    refrescar();
    const interval = setInterval(refrescar, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <Group gap={6}>
        {estado?.es_simulado ? (
          <Tooltip label={`Tiempo simulado: ${estado.ahora_art}. Clic para ajustar.`}>
            <Badge
              variant="filled"
              color="orange"
              size="md"
              leftSection={<IconClockPlay size={14} />}
              style={{ cursor: 'pointer' }}
              onClick={open}
            >
              Simulado ({estado.offset_descripcion})
            </Badge>
          </Tooltip>
        ) : (
          <Tooltip label="Simular el paso de horas o días para probar recordatorios y obras">
            <Button
              variant="subtle"
              color="gray"
              size="xs"
              leftSection={<IconClock size={15} />}
              onClick={open}
            >
              Simulador de tiempo
            </Button>
          </Tooltip>
        )}
      </Group>

      <SimuladorTiempoModal
        opened={opened}
        onClose={close}
        onTiempoActualizado={(nuevo) => setEstado(nuevo)}
      />
    </>
  );
}

