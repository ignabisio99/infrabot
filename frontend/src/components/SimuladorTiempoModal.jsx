import { useEffect, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Divider,
  Grid,
  Group,
  Modal,
  NumberInput,
  Paper,
  ScrollArea,
  Stack,
  Table,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
} from '@mantine/core';
import {
  IconArrowRight,
  IconCalendarEvent,
  IconCalendarTime,
  IconCheck,
  IconClock,
  IconClockFastForward,
  IconClockPlay,
  IconInfoCircle,
  IconMessageDots,
  IconPlayerPlay,
  IconRefresh,
  IconRotateClockwise2,
  IconTools,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';

import {
  avanzarTiempo,
  obtenerEstadoSimulador,
  resetearTiempo,
} from '../api/simuladorTiempo';
import { notifyError, notifySuccess } from '../utils/notifications';

export function SimuladorTiempoModal({ opened, onClose, onTiempoActualizado }) {
  const navigate = useNavigate();
  const [cargando, setCargando] = useState(false);
  const [estado, setEstado] = useState(null);
  const [diasInput, setDiasInput] = useState(1);
  const [horasInput, setHorasInput] = useState(0);
  const [ultimasAcciones, setUltimasAcciones] = useState([]);

  const cargarEstado = async () => {
    try {
      setCargando(true);
      const data = await obtenerEstadoSimulador();
      setEstado(data);
      if (data.acciones_disparadas?.length > 0) {
        setUltimasAcciones(data.acciones_disparadas);
      }
      onTiempoActualizado?.(data);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    if (opened) {
      cargarEstado();
    }
  }, [opened]);

  const handleAvanzar = async ({ horas = 0, dias = 0, hasta_proxima_visita = false }) => {
    try {
      setCargando(true);
      const res = await avanzarTiempo({ horas, dias, hasta_proxima_visita });
      setEstado(res);
      setUltimasAcciones(res.acciones_disparadas || []);
      notifySuccess(`Reloj virtual actualizado: ${res.ahora_art}`);
      onTiempoActualizado?.(res);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setCargando(false);
    }
  };

  const handleReset = async () => {
    try {
      setCargando(true);
      const res = await resetearTiempo();
      setEstado(res);
      setUltimasAcciones(res.acciones_disparadas || []);
      notifySuccess('Reloj restablecido al tiempo real.');
      onTiempoActualizado?.(res);
    } catch (err) {
      notifyError(err.message);
    } finally {
      setCargando(false);
    }
  };

  const irAWhatsAppConNumero = (numero) => {
    if (!numero) return;
    try {
      localStorage.setItem('infrabot_whatsapp_sim_origen', numero);
    } catch {}
    onClose();
    navigate('/whatsapp');
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap="xs">
          <ThemeIcon color="teal" variant="light" size="lg" radius="md">
            <IconClockFastForward size={20} />
          </ThemeIcon>
          <div>
            <Group gap="xs">
              <Text fw={700} size="md">
                Simulador de Avance del Tiempo
              </Text>
              <Badge color="blue" size="xs" variant="filled">
                Solo Admins
              </Badge>
            </Group>
            <Text size="xs" c="dimmed">
              Pruebas y demostración de recordatorios, visitas, ejecución y cierre
            </Text>
          </div>
        </Group>
      }
      size="xl"
      centered
      padding="lg"
    >
      <Stack gap="md">
        {/* Panel de hora actual simulada */}
        <Paper
          withBorder
          p="md"
          radius="md"
          style={{
            background: estado?.es_simulado
              ? 'linear-gradient(135deg, rgba(255, 146, 43, 0.08) 0%, rgba(255, 107, 107, 0.08) 100%)'
              : 'rgba(0, 0, 0, 0.02)',
            borderColor: estado?.es_simulado ? '#ffa94d' : undefined,
          }}
        >
          <Group justify="space-between" align="center" wrap="wrap">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700} lts={1}>
                Fecha y Hora Virtual Activa (ART UTC-3)
              </Text>
              <Group gap="xs" align="baseline">
                <Title order={2} style={{ letterSpacing: -0.5 }}>
                  {estado?.ahora_art || 'Cargando...'}
                </Title>
                <Badge
                  color={estado?.es_simulado ? 'orange' : 'teal'}
                  variant="light"
                  size="md"
                >
                  {estado?.offset_descripcion || 'Tiempo real'}
                </Badge>
              </Group>
            </div>

            <Group gap="xs">
              <Button
                variant="default"
                size="xs"
                leftSection={<IconRefresh size={14} />}
                onClick={cargarEstado}
                loading={cargando}
              >
                Actualizar
              </Button>
              {estado?.es_simulado && (
                <Button
                  color="red"
                  variant="light"
                  size="xs"
                  leftSection={<IconRotateClockwise2 size={14} />}
                  onClick={handleReset}
                  loading={cargando}
                >
                  Volver a tiempo real
                </Button>
              )}
            </Group>
          </Group>
        </Paper>

        {/* Acciones de avance rápido */}
        <div>
          <Text size="sm" fw={600} mb="xs">
            Botones de avance rápido:
          </Text>
          <Group gap="xs" wrap="wrap">
            <Button
              variant="light"
              color="teal"
              size="xs"
              leftSection={<IconClock size={14} />}
              onClick={() => handleAvanzar({ horas: 6 })}
              loading={cargando}
            >
              +6 Horas
            </Button>
            <Button
              variant="light"
              color="teal"
              size="xs"
              leftSection={<IconClock size={14} />}
              onClick={() => handleAvanzar({ horas: 12 })}
              loading={cargando}
            >
              +12 Horas
            </Button>
            <Button
              variant="filled"
              color="teal"
              size="xs"
              leftSection={<IconClockPlay size={14} />}
              onClick={() => handleAvanzar({ dias: 1 })}
              loading={cargando}
            >
              +1 Día
            </Button>
            <Button
              variant="filled"
              color="teal"
              size="xs"
              leftSection={<IconClockPlay size={14} />}
              onClick={() => handleAvanzar({ dias: 2 })}
              loading={cargando}
            >
              +2 Días
            </Button>
            <Button
              variant="light"
              color="blue"
              size="xs"
              leftSection={<IconClockPlay size={14} />}
              onClick={() => handleAvanzar({ dias: 7 })}
              loading={cargando}
            >
              +7 Días (1 sem.)
            </Button>
            <Button
              variant="gradient"
              gradient={{ from: 'teal', to: 'cyan', deg: 90 }}
              size="xs"
              leftSection={<IconCalendarTime size={14} />}
              onClick={() => handleAvanzar({ hasta_proxima_visita: true })}
              loading={cargando}
            >
              Ir a la próxima visita agendada
            </Button>
          </Group>
        </div>

        {/* Avance personalizado */}
        <Paper withBorder p="sm" radius="md">
          <Text size="xs" fw={600} c="dimmed" mb="xs">
            Avance personalizado:
          </Text>
          <Group align="flex-end" gap="sm">
            <NumberInput
              label="Días"
              min={0}
              max={365}
              value={diasInput}
              onChange={(val) => setDiasInput(Number(val) || 0)}
              size="xs"
              style={{ width: 100 }}
            />
            <NumberInput
              label="Horas"
              min={0}
              max={23}
              value={horasInput}
              onChange={(val) => setHorasInput(Number(val) || 0)}
              size="xs"
              style={{ width: 100 }}
            />
            <Button
              variant="default"
              size="xs"
              onClick={() => handleAvanzar({ dias: diasInput, horas: horasInput })}
              disabled={diasInput === 0 && horasInput === 0}
              loading={cargando}
              leftSection={<IconArrowRight size={14} />}
            >
              Aplicar avance
            </Button>
          </Group>
        </Paper>

        {/* Registro de acciones disparadas tras el último avance */}
        {ultimasAcciones.length > 0 && (
          <Alert
            color="teal"
            variant="light"
            title="Acciones disparadas en esta simulación"
            icon={<IconCheck size={18} />}
          >
            <Stack gap={4} mt={4}>
              {ultimasAcciones.map((acc, idx) => (
                <Text key={idx} size="xs" style={{ whiteSpace: 'pre-line' }}>
                  • {acc}
                </Text>
              ))}
            </Stack>
          </Alert>
        )}

        <Divider my="xs" label="Estado operativo de visitas y obras" labelPosition="center" />

        {/* Próximas visitas confirmadas */}
        <div>
          <Group justify="space-between" mb={6}>
            <Group gap={6}>
              <IconCalendarEvent size={16} />
              <Text size="sm" fw={600}>
                Visitas confirmadas ({estado?.proximas_visitas?.length || 0})
              </Text>
            </Group>
          </Group>

          {(!estado?.proximas_visitas || estado.proximas_visitas.length === 0) ? (
            <Paper p="sm" withBorder radius="md">
              <Text size="xs" c="dimmed" ta="center">
                No hay visitas confirmadas pendientes en este momento.
              </Text>
            </Paper>
          ) : (
            <Table striped highlightOnHover withTableBorder withColumnBorders fz="xs">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Reclamo / Escuela</Table.Th>
                  <Table.Th>Contratista</Table.Th>
                  <Table.Th>Fecha de Visita</Table.Th>
                  <Table.Th>Faltante</Table.Th>
                  <Table.Th>Recordatorios</Table.Th>
                  <Table.Th>Acción WhatsApp</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {estado.proximas_visitas.map((v) => {
                  const yaPaso = v.horas_faltantes <= 0;
                  return (
                    <Table.Tr key={v.id}>
                      <Table.Td>
                        <Text fw={600} size="xs">
                          #{v.reclamo_id}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {v.escuela}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="xs">{v.contratista}</Text>
                        <Text size="xs" c="dimmed">
                          {v.contratista_telefono || 'Sin tel'}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="xs" fw={500}>
                          {v.fecha_visita_art || v.horario_confirmado}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        {yaPaso ? (
                          <Badge color="orange" size="xs" variant="light">
                            Hora cumplida
                          </Badge>
                        ) : (
                          <Badge color="blue" size="xs" variant="light">
                            En {v.horas_faltantes} h
                          </Badge>
                        )}
                      </Table.Td>
                      <Table.Td>
                        <Stack gap={2}>
                          <Badge
                            size="xs"
                            variant="dot"
                            color={v.dia_antes_enviado ? 'green' : 'gray'}
                          >
                            24h antes: {v.dia_antes_enviado ? 'Enviado' : 'Pendiente'}
                          </Badge>
                          <Badge
                            size="xs"
                            variant="dot"
                            color={v.mismo_dia_enviado ? 'green' : 'gray'}
                          >
                            Mismo día: {v.mismo_dia_enviado ? 'Enviado' : 'Pendiente'}
                          </Badge>
                          <Badge
                            size="xs"
                            variant="dot"
                            color={v.pregunta_inicio_enviada ? 'green' : 'gray'}
                          >
                            Preg. inicio: {v.pregunta_inicio_enviada ? 'Enviada' : 'Pendiente'}
                          </Badge>
                        </Stack>
                      </Table.Td>
                      <Table.Td>
                        {v.contratista_telefono && (
                          <Button
                            size="compact-xs"
                            variant="light"
                            color="teal"
                            leftSection={<IconMessageDots size={12} />}
                            onClick={() => irAWhatsAppConNumero(v.contratista_telefono)}
                          >
                            Simular contratista
                          </Button>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          )}
        </div>

        {/* Reclamos en ejecución */}
        <div>
          <Group justify="space-between" mb={6}>
            <Group gap={6}>
              <IconTools size={16} />
              <Text size="sm" fw={600}>
                Obras en ejecución ({estado?.reclamos_en_ejecucion?.length || 0})
              </Text>
            </Group>
          </Group>

          {(!estado?.reclamos_en_ejecucion || estado.reclamos_en_ejecucion.length === 0) ? (
            <Paper p="sm" withBorder radius="md">
              <Text size="xs" c="dimmed" ta="center">
                No hay reclamos actualmente en ejecución.
              </Text>
            </Paper>
          ) : (
            <Table striped highlightOnHover withTableBorder withColumnBorders fz="xs">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Reclamo</Table.Th>
                  <Table.Th>Contratista</Table.Th>
                  <Table.Th>Seguimiento</Table.Th>
                  <Table.Th>Próxima consulta</Table.Th>
                  <Table.Th>Acciones de prueba</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {estado.reclamos_en_ejecucion.map((r) => (
                  <Table.Tr key={r.id}>
                    <Table.Td>
                      <Text fw={600} size="xs">
                        #{r.id} - {r.escuela}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs">{r.contratista || 'Sin asignar'}</Text>
                      <Text size="xs" c="dimmed">
                        {r.contratista_telefono || ''}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Stack gap={2}>
                        <Badge size="xs" color="blue" variant="light">
                          Envíos: {r.cantidad_envios}
                        </Badge>
                        {r.consulto_escuela && (
                          <Badge size="xs" color="green" variant="light">
                            Consultando a escuela
                          </Badge>
                        )}
                      </Stack>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs">{r.proxima_pregunta_art || 'Por umbral estándar (6 h)'}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap={6}>
                        {r.contratista_telefono && (
                          <Button
                            size="compact-xs"
                            variant="light"
                            color="teal"
                            leftSection={<IconMessageDots size={12} />}
                            onClick={() => irAWhatsAppConNumero(r.contratista_telefono)}
                          >
                            Simular contratista
                          </Button>
                        )}
                        {r.creador_telefono && r.consulto_escuela && (
                          <Button
                            size="compact-xs"
                            variant="light"
                            color="blue"
                            leftSection={<IconMessageDots size={12} />}
                            onClick={() => irAWhatsAppConNumero(r.creador_telefono)}
                          >
                            Simular escuela
                          </Button>
                        )}
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </div>

        {/* Últimos mensajes de WhatsApp enviados por InfraBot */}
        {estado?.ultimos_mensajes?.length > 0 && (
          <div>
            <Text size="sm" fw={600} mb={6}>
              Últimos mensajes WhatsApp emitidos por el bot ({estado.ultimos_mensajes.length}):
            </Text>
            <ScrollArea.Autosize mah={180}>
              <Stack gap={6}>
                {estado.ultimos_mensajes.slice(0, 5).map((m) => (
                  <Paper key={m.id} p="xs" withBorder radius="sm" style={{ background: '#f8f9fa' }}>
                    <Group justify="space-between" mb={2}>
                      <Badge size="xs" color="gray">
                        Para: {m.to} ({m.fecha_art})
                      </Badge>
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        color="teal"
                        onClick={() => irAWhatsAppConNumero(m.to)}
                      >
                        Abrir este chat
                      </Button>
                    </Group>
                    <Text size="xs" style={{ whiteSpace: 'pre-line' }}>
                      {m.body}
                    </Text>
                    {m.botones?.length > 0 && (
                      <Group gap={4} mt={4}>
                        {m.botones.map((b) => (
                          <Badge key={b.id} size="xs" color="teal" variant="outline">
                            [{b.title}]
                          </Badge>
                        ))}
                      </Group>
                    )}
                  </Paper>
                ))}
              </Stack>
            </ScrollArea.Autosize>
          </div>
        )}
      </Stack>
    </Modal>
  );
}

