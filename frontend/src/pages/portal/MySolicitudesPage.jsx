import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
                  {s.intentos > 1 && (
                    <Badge color="gray" variant="outline" tt="none">
                      Intento {s.intentos}
                    </Badge>
                  )}
                  <BudgetStatusBadge estado={s.presupuesto_estado} variant="light" />
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

            {!s.presupuesto_cargado && (
              <Button
                size="xs"
                onClick={() => navigate(`/portal/reclamos/${s.reclamo_id}/presupuestar`)}
              >
                Cargar presupuesto
              </Button>
            )}
            {(s.puede_editar || s.puede_reenviar) && (
              <Button
                size="xs"
                variant={s.puede_reenviar ? 'filled' : 'light'}
                color={s.puede_reenviar ? 'orange' : undefined}
                onClick={() => navigate(`/portal/reclamos/${s.reclamo_id}/presupuestar`)}
              >
                {s.puede_reenviar ? 'Corregir y reenviar' : 'Editar presupuesto'}
              </Button>
            )}
          </Card>
        ))}
      </Stack>
    </Container>
  );
}
