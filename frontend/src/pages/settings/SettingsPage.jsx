import { useEffect, useState } from 'react';
import { Alert, Button, Container, NumberInput, Stack, Text, Title } from '@mantine/core';

import {
  actualizarUmbralesAuditoria,
  obtenerUmbralesAuditoria,
} from '../../api/configuracion';
import { ejecutarSeguimiento } from '../../api/ai';
import { notifyError, notifySuccess } from '../../utils/notifications';

export function SettingsPage() {
  const [aprobarPct, setAprobarPct] = useState(5);
  const [revisarPct, setRevisarPct] = useState(20);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const [enviandoSeguimiento, setEnviandoSeguimiento] = useState(false);

  useEffect(() => {
    obtenerUmbralesAuditoria()
      .then((data) => {
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
      </Stack>
    </Container>
  );
}
