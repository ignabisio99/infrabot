import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Container,
  Group,
  NumberInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';

import {
  actualizarUmbralesAuditoria,
  obtenerUmbralesAuditoria,
} from '../../api/configuracion';
import { ejecutarSeguimiento } from '../../api/ai';
import {
  actualizarRolManoObra,
  crearRolManoObra,
  eliminarRolManoObra,
  listarRolesManoObra,
} from '../../api/rolesManoObra';
import { notifyError, notifySuccess } from '../../utils/notifications';

export function SettingsPage() {
  const [aprobarPct, setAprobarPct] = useState(5);
  const [revisarPct, setRevisarPct] = useState(20);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const [enviandoSeguimiento, setEnviandoSeguimiento] = useState(false);
  const [roles, setRoles] = useState([]);
  const [nombresRoles, setNombresRoles] = useState({});
  const [nuevoRol, setNuevoRol] = useState('');
  const [guardandoRolId, setGuardandoRolId] = useState(null);
  const [agregandoRol, setAgregandoRol] = useState(false);

  const cargarRoles = () =>
    listarRolesManoObra().then((data) => {
      setRoles(data);
      setNombresRoles(Object.fromEntries(data.map((rol) => [rol.id, rol.nombre])));
    });

  useEffect(() => {
    Promise.all([obtenerUmbralesAuditoria(), cargarRoles()])
      .then(([data]) => {
        setAprobarPct(Number(data.umbral_aprobar) * 100);
        setRevisarPct(Number(data.umbral_revisar) * 100);
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
          El desvío se calcula contra la estimación preliminar del reclamo. La recomendación es
          solo una sugerencia: no aprueba ni rechaza el presupuesto.
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
          Seguimiento a contratistas
        </Title>
        <Text size="sm" c="dimmed">
          Si un reclamo está en ejecución y pasaron 48 horas sin aviso, se pide un avance por
          WhatsApp al contratista. El job corre en segundo plano; también se puede disparar
          ahora.
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
          Roles de mano de obra
        </Title>
        <Text size="sm" c="dimmed">
          El contratista elige un rol al cargar la mano de obra del presupuesto. Acá se
          agregan, renombran o borran. Si un rol ya está usado en un presupuesto, no se
          puede borrar: el nombre queda en ese ítem.
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
            <Group key={rol.id} align="flex-end" wrap="nowrap">
              <TextInput
                value={nombresRoles[rol.id] ?? rol.nombre}
                onChange={(e) =>
                  setNombresRoles((prev) => ({ ...prev, [rol.id]: e.currentTarget.value }))
                }
                style={{ flex: 1 }}
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
