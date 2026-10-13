import { useEffect, useState } from 'react';
import { Badge, Card, Group, Loader, Stack, Text, UnstyledButton } from '@mantine/core';
import { IconClock, IconEye } from '@tabler/icons-react';

import { listarSolicitudesPresupuesto } from '../../api/listasContratistas';
import { obtenerPresupuesto } from '../../api/presupuestos';
import { notifyError } from '../../utils/notifications';
import { BudgetItemsModal } from '../budgets/BudgetItemsModal';
import { BudgetStatusBadge } from '../budgets/BudgetStatusBadge';

export function BudgetRequestsList({ reclamoId }) {
  const [solicitudes, setSolicitudes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [presupuestoVisto, setPresupuestoVisto] = useState(null);

  useEffect(() => {
    listarSolicitudesPresupuesto(reclamoId)
      .then(setSolicitudes)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, [reclamoId]);

  const handleVerPresupuesto = async (presupuestoId) => {
    try {
      const presupuesto = await obtenerPresupuesto(presupuestoId);
      setPresupuestoVisto(presupuesto);
    } catch (err) {
      notifyError(err.message);
    }
  };

  if (cargando) return <Loader size="sm" />;

  if (error) {
    return (
      <Text c="red" size="sm">
        {error}
      </Text>
    );
  }

  if (solicitudes.length === 0) {
    return (
      <Text c="dimmed" size="sm">
        Todavía no se solicitó presupuesto a ningún contratista.
      </Text>
    );
  }

  return (
    <>
      <Stack gap="xs">
        {solicitudes.map((s) => {
          const cargado = s.presupuesto_cargado;
          const contenido = (
            <Card withBorder radius="md" padding="sm">
              <Group justify="space-between" wrap="nowrap">
                <div style={{ minWidth: 0 }}>
                  <Text fw={600} size="sm" truncate>
                    {s.nombre_empresa}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {s.especialidad}
                  </Text>
                </div>
                <Group gap="xs" wrap="nowrap">
                  {cargado && s.intentos > 1 && (
                    <Badge color="gray" variant="outline" tt="none">
                      {s.intentos} intentos
                    </Badge>
                  )}
                  {cargado ? (
                    <BudgetStatusBadge estado={s.presupuesto_estado} variant="light" />
                  ) : (
                    <Badge color="gray" variant="light" leftSection={<IconClock size={12} />}>
                      Pendiente
                    </Badge>
                  )}
                  {cargado && <IconEye size={16} color="var(--mantine-color-teal-6)" />}
                </Group>
              </Group>
            </Card>
          );

          return cargado ? (
            <UnstyledButton
              key={s.contratista_id}
              onClick={() => handleVerPresupuesto(s.presupuesto_id)}
            >
              {contenido}
            </UnstyledButton>
          ) : (
            <div key={s.contratista_id}>{contenido}</div>
          );
        })}
      </Stack>

      <BudgetItemsModal
        presupuesto={presupuestoVisto}
        onClose={() => setPresupuestoVisto(null)}
        onDecidido={() => {
          setPresupuestoVisto(null);
          listarSolicitudesPresupuesto(reclamoId)
            .then(setSolicitudes)
            .catch(() => {});
        }}
      />
    </>
  );
}
