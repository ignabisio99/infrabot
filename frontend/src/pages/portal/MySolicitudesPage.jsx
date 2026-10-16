import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import {
  Alert,
  Badge,
  Button,
  Card,
  Container,
  Group,
  Loader,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconMapPin } from '@tabler/icons-react';

import { listarMisSolicitudes } from '../../api/contratistas';
import { formatearIdReclamo } from '../../utils/ids';
import { BudgetStatusBadge } from '../budgets/BudgetStatusBadge';
import { estaVigente } from '../budgets/estados';

const ETIQUETA_ESTADO = {
  PENDIENTE_REVISION: 'En revisión',
  PENDIENTE_PRESUPUESTO: 'Pendiente de presupuesto',
  EN_EVALUACION: 'En evaluación',
  APROBADO: 'Aprobado',
  PENDIENTE_COORDINACION: 'Pendiente de coordinación',
  VISITA_COORDINADA: 'Visita coordinada',
  EN_EJECUCION: 'En ejecución',
  PENDIENTE_INTERVENCION: 'Pendiente de intervención',
  FINALIZADO: 'Finalizado',
  DESIERTO: 'Desierto',
  RECHAZADO: 'Rechazado',
  CANCELADO: 'Cancelado',
};

export function MySolicitudesPage() {
  const navigate = useNavigate();
  const [solicitudes, setSolicitudes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    listarMisSolicitudes()
      .then(setSolicitudes)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  return (
    <Container size="md" px={0}>
      <Title order={2} mb="lg">
        Mis solicitudes
      </Title>

      {cargando && <Loader />}

      {error && (
        <Alert color="red" title="No se pudieron cargar tus solicitudes">
          {error}
        </Alert>
      )}

      {!cargando && !error && solicitudes.length === 0 && (
        <Text c="dimmed">
          Todavía no fuiste convocado a presupuestar ningún reclamo. Cuando te soliciten un
          presupuesto, va a aparecer acá.
        </Text>
      )}

      <Stack>
        {solicitudes.map((s) => (
          <Card key={s.reclamo_id} withBorder radius="md">
            <Group justify="space-between" mb="xs">
              <Group gap={8}>
                <Text size="sm" c="dimmed" ff="monospace">
                  {formatearIdReclamo(s.reclamo_id)}
                </Text>
                <Badge variant="light">{s.categoria}</Badge>
                <Badge variant="light" color="gray">
                  {ETIQUETA_ESTADO[s.estado_reclamo] ?? s.estado_reclamo}
                </Badge>
              </Group>
              {s.presupuesto_cargado ? (
                <Group gap={6}>
                  {s.version > 1 && (
                    <Badge color="gray" variant="outline" tt="none">
                      Versión {s.version}
                    </Badge>
                  )}
                  {s.estado_reclamo === 'CANCELADO' &&
                  estaVigente({ estado: s.presupuesto_estado }) ? (
                    <Badge color="gray" variant="light" tt="none">
                      Ya no se evalúa
                    </Badge>
                  ) : (
                    <BudgetStatusBadge estado={s.presupuesto_estado} variant="light" />
                  )}
                </Group>
              ) : (
                <Badge color="orange" variant="light">
                  Pendiente de cargar
                </Badge>
              )}
            </Group>

            <Text fw={600}>{s.nombre_escuela}</Text>
            <Group gap={4} c="dimmed" mb="sm">
              <IconMapPin size={14} />
              <Text size="sm">{s.ubicacion}</Text>
            </Group>

            {s.puede_ofertar && (
              <Button
                size="xs"
                onClick={() => navigate(`/portal/reclamos/${s.reclamo_id}/presupuestar`)}
              >
                {s.presupuesto_cargado ? 'Cargar un presupuesto nuevo' : 'Cargar presupuesto'}
              </Button>
            )}
            {s.puede_editar && (
              <Button
                size="xs"
                variant={s.presupuesto_estado === 'AJUSTES_SOLICITADOS' ? 'filled' : 'light'}
                color={s.presupuesto_estado === 'AJUSTES_SOLICITADOS' ? 'orange' : undefined}
                onClick={() => navigate(`/portal/reclamos/${s.reclamo_id}/presupuestar`)}
              >
                {s.presupuesto_estado === 'AJUSTES_SOLICITADOS'
                  ? 'Ajustar presupuesto'
                  : 'Editar presupuesto'}
              </Button>
            )}
          </Card>
        ))}
      </Stack>
    </Container>
  );
}
