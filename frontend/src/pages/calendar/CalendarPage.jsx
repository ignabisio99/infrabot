import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar, dayjsLocalizer } from 'react-big-calendar';
import dayjs from 'dayjs';
import {
  Badge,
  Button,
  Container,
  Group,
  Loader,
  Modal,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { IconArrowRight } from '@tabler/icons-react';

import { listarVisitas } from '../../api/visitas';
import { esAdministrador, esInspector } from '../../utils/auth';
import { formatearIdReclamo } from '../../utils/ids';
import { ClaimDetailDrawer } from '../claims/ClaimDetailDrawer';

const localizer = dayjsLocalizer(dayjs);

const mensajes = {
  allDay: 'Todo el día',
  previous: 'Anterior',
  next: 'Siguiente',
  today: 'Hoy',
  month: 'Mes',
  week: 'Semana',
  day: 'Día',
  agenda: 'Agenda',
  date: 'Fecha',
  time: 'Hora',
  event: 'Evento',
  noEventsInRange: 'No hay eventos en este período.',
  showMore: (total) => `+${total} más`,
};

const vistas = [
  { label: 'Mes', value: 'month' },
  { label: 'Semana', value: 'week' },
  { label: 'Día', value: 'day' },
  { label: 'Agenda', value: 'agenda' },
];

const etiquetasEstado = {
  CONFIRMADA: 'Confirmada',
  CANCELADA: 'Cancelada',
  ESPERANDO_DISPONIBILIDAD: 'Esperando disponibilidad',
  ESPERANDO_ELECCION: 'Esperando elección',
};

function BarraCalendario({ date, label, onNavigate, onView, view }) {
  const unidadPorVista = {
    month: 'month',
    week: 'week',
    day: 'day',
    agenda: 'week',
  };

  const navegar = (direccion) => {
    if (direccion === 'TODAY') {
      onNavigate('TODAY');
      return;
    }

    const cantidad = direccion === 'NEXT' ? 1 : -1;
    onNavigate('DATE', dayjs(date).add(cantidad, unidadPorVista[view]).toDate());
  };

  return (
    <Group justify="space-between" mb="sm" wrap="wrap">
      <Group gap="xs">
        <Button variant="default" onClick={() => navegar('TODAY')}>
          Hoy
        </Button>
        <Button variant="default" onClick={() => navegar('PREV')}>
          Anterior
        </Button>
        <Button variant="default" onClick={() => navegar('NEXT')}>
          Siguiente
        </Button>
        <Title order={3} size="h4">
          {label}
        </Title>
      </Group>
      <SegmentedControl color="#1fa7b3" data={vistas} onChange={onView} value={view} />
    </Group>
  );
}

const componentes = { toolbar: BarraCalendario };

export function CalendarPage() {
  const navigate = useNavigate();
  const [fecha, setFecha] = useState(new Date());
  const [vista, setVista] = useState('month');
  const [visitas, setVisitas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [visitaSeleccionada, setVisitaSeleccionada] = useState(null);
  const [reclamoId, setReclamoId] = useState(null);

  const abrirReclamo = (id) => {
    if (esAdministrador() || esInspector()) {
      setVisitaSeleccionada(null);
      setReclamoId(id);
      return;
    }
    navigate(`/portal/reclamos/${id}/presupuestar`);
  };

  useEffect(() => {
    listarVisitas()
      .then(setVisitas)
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  const eventos = useMemo(
    () =>
      visitas
        .filter((visita) => visita.fecha_visita)
        .map((visita) => {
          const inicio = new Date(visita.fecha_visita);
          return {
            allDay: false,
            end: new Date(inicio.getTime() + 60 * 60 * 1000),
            resource: visita,
            start: inicio,
            title: `Visita - ${visita.nombre_escuela}`,
          };
        }),
    [visitas],
  );

  return (
    <Container fluid px={0}>
      <Stack gap="lg">
        <Title order={2}>Calendario</Title>
        {cargando && <Loader color="#1fa7b3" size="sm" />}
        {error && <Text c="red">{error}</Text>}
        <Calendar
          culture="es"
          date={fecha}
          events={eventos}
          localizer={localizer}
          messages={mensajes}
          onNavigate={setFecha}
          onSelectEvent={(evento) => setVisitaSeleccionada(evento.resource)}
          onView={setVista}
          popup
          components={componentes}
          style={{ height: 'calc(100vh - 240px)', minHeight: 560 }}
          view={vista}
          views={{ month: true, week: true, day: true, agenda: true }}
        />
        <Modal
          opened={visitaSeleccionada !== null}
          onClose={() => setVisitaSeleccionada(null)}
          title="Detalle de la visita"
          centered
          overlayProps={{ backgroundOpacity: 0.35, blur: 2 }}
        >
          {visitaSeleccionada && (
            <Stack gap="md">
              <Group justify="space-between">
                <Text fw={700} size="lg">
                  {visitaSeleccionada.nombre_escuela}
                </Text>
                <Badge color="#1fa7b3">
                  {etiquetasEstado[visitaSeleccionada.estado] || visitaSeleccionada.estado}
                </Badge>
              </Group>
              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                <div>
                  <Text size="xs" c="dimmed">
                    Ubicación
                  </Text>
                  <Text>{visitaSeleccionada.ubicacion}</Text>
                </div>
                <div>
                  <Text size="xs" c="dimmed">
                    Contratista
                  </Text>
                  <Text>{visitaSeleccionada.nombre_empresa}</Text>
                </div>
                <div>
                  <Text size="xs" c="dimmed">
                    Fecha y hora
                  </Text>
                  <Text>
                    {visitaSeleccionada.fecha_visita
                      ? dayjs(visitaSeleccionada.fecha_visita).format('DD/MM/YYYY HH:mm')
                      : 'A confirmar'}
                  </Text>
                </div>
                <div>
                  <Text size="xs" c="dimmed">
                    Reclamo
                  </Text>
                  <Text>{formatearIdReclamo(visitaSeleccionada.reclamo_id)}</Text>
                </div>
              </SimpleGrid>
              {visitaSeleccionada.horario_confirmado && (
                <Text size="sm">
                  <Text span fw={600}>
                    Horario confirmado:{' '}
                  </Text>
                  {visitaSeleccionada.horario_confirmado}
                </Text>
              )}
              <Button
                rightSection={<IconArrowRight size={16} />}
                onClick={() => abrirReclamo(visitaSeleccionada.reclamo_id)}
              >
                Ver reclamo
              </Button>
            </Stack>
          )}
        </Modal>
        <ClaimDetailDrawer reclamoId={reclamoId} onClose={() => setReclamoId(null)} />
      </Stack>
    </Container>
  );
}
