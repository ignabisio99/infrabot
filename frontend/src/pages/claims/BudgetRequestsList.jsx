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
          const rechazado = s.presupuesto_estado === 'RECHAZADO';
          const contenido = (
            <Card
              withBorder
              radius="md"
              padding="sm"
              style={rechazado ? { borderColor: 'var(--mantine-color-red-6)' } : undefined}
            >
              <Group justify="space-between" wrap="nowrap">
                <div style={{ minWidth: 0 }}>
                  <Text fw={600} size="sm" truncate>
                    {s.nombre_empresa}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {s.especialidad}
                  </Text>
                  {cargado && s.presupuesto_fecha && (
                    <Text size="xs" c={rechazado ? 'red' : 'dimmed'}>
                      Oferta del {new Date(s.presupuesto_fecha).toLocaleDateString('es-AR')}
                    </Text>
                  )}
                </div>
                <Group gap="xs" wrap="nowrap">
                  {cargado && s.version > 1 && (
                    <Badge color="gray" variant="outline" tt="none">
                      Versión {s.version}
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
              key={s.presupuesto_id}
              onClick={() => handleVerPresupuesto(s.presupuesto_id)}
            >
              {contenido}
            </UnstyledButton>
          ) : (
            <div key={`pendiente-${s.contratista_id}`}>{contenido}</div>
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
