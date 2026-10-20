import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Checkbox,
  Container,
  Group,
  NumberInput,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';

import {
  actualizarConfiguracionAtencion,
  actualizarUmbralesAuditoria,
  obtenerConfiguracionAtencion,
  obtenerUmbralesAuditoria,
} from '../../api/configuracion';
import { ejecutarSeguimiento, sincronizarReferenciasCsv } from '../../api/ai';
import {
  actualizarRolManoObra,
  crearRolManoObra,
  eliminarRolManoObra,
  listarRolesManoObra,
} from '../../api/rolesManoObra';
import { notifyError, notifySuccess } from '../../utils/notifications';

const DIAS_ATENCION = [
  { value: '0', label: 'Lun' },
  { value: '1', label: 'Mar' },
  { value: '2', label: 'Mié' },
  { value: '3', label: 'Jue' },
  { value: '4', label: 'Vie' },
  { value: '5', label: 'Sáb' },
  { value: '6', label: 'Dom' },
];

export function SettingsPage() {
  const [aprobarPct, setAprobarPct] = useState(5);
  const [revisarPct, setRevisarPct] = useState(20);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const [enviandoSeguimiento, setEnviandoSeguimiento] = useState(false);
  const [sincronizandoCsv, setSincronizandoCsv] = useState(false);
  const [roles, setRoles] = useState([]);
  const [nombresRoles, setNombresRoles] = useState({});
  const [nuevoRol, setNuevoRol] = useState('');
  const [guardandoRolId, setGuardandoRolId] = useState(null);
  const [agregandoRol, setAgregandoRol] = useState(false);
  const [diasAtencion, setDiasAtencion] = useState(['0', '1', '2', '3', '4']);
  const [horaDesde, setHoraDesde] = useState('09:00');
  const [horaHasta, setHoraHasta] = useState('18:00');
  const [mensajeFuera, setMensajeFuera] = useState('');
  const [inactividadMin, setInactividadMin] = useState(60);
  const [guardandoAtencion, setGuardandoAtencion] = useState(false);

  const cargarRoles = () =>
    listarRolesManoObra().then((data) => {
      setRoles(data);
      setNombresRoles(Object.fromEntries(data.map((rol) => [rol.id, rol.nombre])));
    });

  useEffect(() => {
    Promise.all([obtenerUmbralesAuditoria(), obtenerConfiguracionAtencion(), cargarRoles()])
      .then(([data, atencion]) => {
        setAprobarPct(Number(data.umbral_aprobar) * 100);
        setRevisarPct(Number(data.umbral_revisar) * 100);
        setDiasAtencion((atencion.dias || []).map(String));
        setHoraDesde(atencion.hora_desde);
        setHoraHasta(atencion.hora_hasta);
        setMensajeFuera(atencion.mensaje_fuera_horario);
        setInactividadMin(atencion.inactividad_usuario_min);
      })
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  }, []);

  const handleGuardar = async () => {
    setGuardando(true);
    try {
      const data = await actualizarUmbralesAuditoria({
        umbralAprobar: aprobarPct / 100,
        umbralRevisar: revisarPct / 100,
      });
      setAprobarPct(Number(data.umbral_aprobar) * 100);
      setRevisarPct(Number(data.umbral_revisar) * 100);
      notifySuccess('Umbrales de auditoría actualizados.');
    } catch (err) {
      notifyError(err.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Container size="sm" px={0}>
      <Title order={2} mb="md">
        Configuración
      </Title>

      {error && (
        <Alert color="red" title="Ocurrió un error" mb="md">
          {error}
        </Alert>
      )}

      <Stack gap="sm">
        <Title order={4}>Auditoría de presupuestos</Title>
        <Text size="sm" c="dimmed">
          El desvío se calcula contra la estimación preliminar del reclamo. La recomendación es solo
          una sugerencia: no aprueba ni rechaza el presupuesto.
        </Text>
        <NumberInput
          label="Aprobar si el desvío es menor a (%)"
          min={0.1}
          max={99}
          decimalScale={1}
          value={aprobarPct}
          onChange={(value) => setAprobarPct(Number(value) || 0)}
          disabled={cargando}
        />
        <NumberInput
          label="Revisar hasta (%)"
          min={0.2}
          max={100}
          decimalScale={1}
          value={revisarPct}
          onChange={(value) => setRevisarPct(Number(value) || 0)}
          disabled={cargando}
        />
        <Text size="sm">
          Menor a {aprobarPct}% → Aprobar. Entre {aprobarPct}% y {revisarPct}% → Revisar. Mayor a{' '}
          {revisarPct}% → Rechazar.
        </Text>
        <Button onClick={handleGuardar} loading={guardando} disabled={cargando} w="fit-content">
          Guardar umbrales
        </Button>

        <Title order={4} mt="md">
          Horario de atención humana
        </Title>
        <Text size="sm" c="dimmed">
          Fuera de este horario (Argentina) el usuario no entra a la cola: recibe el mensaje de
          abajo y sigue con el bot. También se cierra el chat si el usuario no responde al operador
          en los minutos indicados.
        </Text>
        <Checkbox.Group label="Días" value={diasAtencion} onChange={setDiasAtencion}>
          <Group mt={6} gap="sm">
            {DIAS_ATENCION.map((dia) => (
              <Checkbox key={dia.value} value={dia.value} label={dia.label} disabled={cargando} />
            ))}
          </Group>
        </Checkbox.Group>
        <Group grow>
          <TextInput
            label="Desde"
            type="time"
            value={horaDesde}
            onChange={(e) => setHoraDesde(e.currentTarget.value)}
            disabled={cargando}
          />
          <TextInput
            label="Hasta"
            type="time"
            value={horaHasta}
            onChange={(e) => setHoraHasta(e.currentTarget.value)}
            disabled={cargando}
          />
        </Group>
        <Textarea
          label="Mensaje fuera de horario"
          minRows={3}
          value={mensajeFuera}
          onChange={(e) => setMensajeFuera(e.currentTarget.value)}
          disabled={cargando}
        />
        <NumberInput
          label="Minutos sin respuesta del usuario"
          min={1}
          max={1440}
          value={inactividadMin}
          onChange={(value) => setInactividadMin(Number(value) || 1)}
          disabled={cargando}
        />
        <Button
          w="fit-content"
          loading={guardandoAtencion}
          disabled={cargando}
          onClick={async () => {
            if (diasAtencion.length === 0) {
              notifyError('Elegí al menos un día de atención.');
              return;
            }
            setGuardandoAtencion(true);
            try {
              const data = await actualizarConfiguracionAtencion({
                dias: diasAtencion.map(Number),
                hora_desde: horaDesde,
                hora_hasta: horaHasta,
                mensaje_fuera_horario: mensajeFuera,
                inactividad_usuario_min: inactividadMin,
              });
              setDiasAtencion(data.dias.map(String));
              setHoraDesde(data.hora_desde);
              setHoraHasta(data.hora_hasta);
              setMensajeFuera(data.mensaje_fuera_horario);
              setInactividadMin(data.inactividad_usuario_min);
              notifySuccess('Horario de atención actualizado.');
            } catch (err) {
              notifyError(err.message);
            } finally {
              setGuardandoAtencion(false);
            }
          }}
        >
          Guardar horario
        </Button>

        <Title order={4} mt="md">
          Seguimiento a contratistas
        </Title>
        <Text size="sm" c="dimmed">
          Si un reclamo está en ejecución y pasa el umbral sin aviso, se pide un avance por
          WhatsApp. A los 5 intentos sin respuesta pasa a Pendiente de intervención. El job corre en
          segundo plano; también se puede disparar ahora.
        </Text>
        <Button
          variant="light"
          loading={enviandoSeguimiento}
          w="fit-content"
          onClick={async () => {
            setEnviandoSeguimiento(true);
            try {
              const data = await ejecutarSeguimiento();
              notifySuccess(data.mensaje);
            } catch (err) {
              notifyError(err.message);
            } finally {
              setEnviandoSeguimiento(false);
            }
          }}
        >
          Enviar recordatorios ahora
        </Button>

        <Title order={4} mt="md">
          Referencias de costo
        </Title>
        <Text size="sm" c="dimmed">
          Trae precios de trabajos tipo (tablero, cañería, etc.) desde la lista histórica del
          sistema: agrega ítems nuevos y actualiza monto, fecha o unidad si cambiaron. No pisa
          costos que salieron de un presupuesto aprobado.
        </Text>
        <Button
          variant="light"
          loading={sincronizandoCsv}
          w="fit-content"
          onClick={async () => {
            setSincronizandoCsv(true);
            try {
              const data = await sincronizarReferenciasCsv();
              notifySuccess(data.mensaje);
            } catch (err) {
              notifyError(err.message);
            } finally {
              setSincronizandoCsv(false);
            }
          }}
        >
          Actualizar precios de referencia
        </Button>

        <Title order={4} mt="md">
          Roles de mano de obra
        </Title>
        <Text size="sm" c="dimmed">
          El contratista elige un rol al cargar la mano de obra del presupuesto. Acá se agregan,
          renombran o borran. Si un rol ya está usado en un presupuesto, no se puede borrar: el
          nombre queda en ese ítem.
        </Text>
        <Group align="flex-end" wrap="nowrap">
          <TextInput
            label="Nuevo rol"
            placeholder="Ej: Yesero"
            value={nuevoRol}
            onChange={(e) => setNuevoRol(e.currentTarget.value)}
            style={{ flex: 1 }}
          />
          <Button
            loading={agregandoRol}
            onClick={async () => {
              const nombre = nuevoRol.trim();
              if (nombre.length < 2) {
                notifyError('El nombre del rol debe tener al menos 2 caracteres.');
                return;
              }
              setAgregandoRol(true);
              try {
                await crearRolManoObra({ nombre });
                setNuevoRol('');
                await cargarRoles();
                notifySuccess('Rol agregado.');
              } catch (err) {
                notifyError(err.message);
              } finally {
                setAgregandoRol(false);
              }
            }}
          >
            Agregar
          </Button>
        </Group>
        <Stack gap="xs">
          {roles.map((rol) => (
            // En celular el nombre ocupa su renglón y los botones bajan al siguiente.
            <Group key={rol.id} align="flex-end" gap="xs">
              <TextInput
                value={nombresRoles[rol.id] ?? rol.nombre}
                onChange={(e) =>
                  setNombresRoles((prev) => ({ ...prev, [rol.id]: e.currentTarget.value }))
                }
                style={{ flex: '1 1 220px' }}
              />
              <Button
                variant="light"
                loading={guardandoRolId === rol.id}
                onClick={async () => {
                  const nombre = (nombresRoles[rol.id] ?? rol.nombre).trim();
                  if (nombre.length < 2) {
                    notifyError('El nombre del rol debe tener al menos 2 caracteres.');
                    return;
                  }
                  setGuardandoRolId(rol.id);
                  try {
                    await actualizarRolManoObra(rol.id, { nombre });
                    await cargarRoles();
                    notifySuccess('Rol actualizado.');
                  } catch (err) {
                    notifyError(err.message);
                  } finally {
                    setGuardandoRolId(null);
                  }
                }}
              >
                Guardar
              </Button>
              <Button
                color="red"
                variant="subtle"
                onClick={async () => {
                  try {
                    await eliminarRolManoObra(rol.id);
                    await cargarRoles();
                    notifySuccess('Rol eliminado.');
                  } catch (err) {
                    notifyError(err.message);
                  }
                }}
              >
                Borrar
              </Button>
            </Group>
          ))}
        </Stack>
      </Stack>
    </Container>
  );
}
