import { useState } from 'react';
import { Badge, Card, Group, Stack, Text, UnstyledButton } from '@mantine/core';
import { IconClock, IconEye } from '@tabler/icons-react';

import { obtenerPresupuesto } from '../../api/presupuestos';
import { formatoMoneda } from '../../utils/formatters';
import { notifyError } from '../../utils/notifications';
import { BudgetItemsModal } from '../budgets/BudgetItemsModal';
import { BudgetStatusBadge } from '../budgets/BudgetStatusBadge';
import { estaVigente } from '../budgets/estados';
import { DadoDeBajaBadge } from '../contractors/DadoDeBajaBadge';

const fecha = (valor) => new Date(valor).toLocaleDateString('es-AR');

const vigente = (s) => s.presupuesto_cargado && estaVigente({ estado: s.presupuesto_estado });
const cerrada = (s) => ['RECHAZADO', 'NO_SELECCIONADO'].includes(s.presupuesto_estado);

// Primero la aprobada, después las que siguen en carrera de la más barata a la más cara,
// las que todavía no llegaron y al final las descartadas.
function orden(s) {
  if (s.presupuesto_estado === 'APROBADO') return 0;
  if (vigente(s)) return 1;
  if (!s.presupuesto_cargado) return 2;
  return 3;
}

function ordenar(solicitudes) {
  return [...solicitudes].sort(
    (a, b) => orden(a) - orden(b) || (vigente(a) ? Number(a.monto) - Number(b.monto) : 0),
  );
}

// Sólo tiene sentido comparar mientras se está eligiendo: con dos o más en carrera y
// ninguna aprobada.
function masBarata(solicitudes) {
  if (solicitudes.some((s) => s.presupuesto_estado === 'APROBADO')) return null;
  const enCarrera = solicitudes.filter((s) => vigente(s) && s.monto != null);
  if (enCarrera.length < 2) return null;
  return enCarrera.reduce((min, s) => (Number(s.monto) < Number(min.monto) ? s : min));
}

function estiloTarjeta(s) {
  if (s.presupuesto_estado === 'APROBADO') {
    return {
      borderColor: 'var(--mantine-color-teal-6)',
      backgroundColor: 'var(--mantine-color-teal-0)',
    };
  }
  if (cerrada(s)) return { opacity: 0.6 };
  return undefined;
}

function TarjetaSolicitud({ solicitud: s, masBarata }) {
  const cargado = s.presupuesto_cargado;
  const esLaMasBarata = masBarata && s.presupuesto_id === masBarata.presupuesto_id;
  const diferencia =
    masBarata && vigente(s) && !esLaMasBarata
      ? Math.round((Number(s.monto) / Number(masBarata.monto) - 1) * 100)
      : null;

  return (
    <Card withBorder radius="md" padding="sm" style={estiloTarjeta(s)}>
      <Group justify="space-between" wrap="nowrap" align="flex-start">
        <div style={{ minWidth: 0 }}>
          <Text fw={600} size="sm" truncate>
            {s.nombre_empresa}
          </Text>
          <Text size="xs" c="dimmed">
            {s.especialidad} ·{' '}
            {cargado && s.presupuesto_fecha
              ? `Oferta del ${fecha(s.presupuesto_fecha)}`
              : `Convocado el ${fecha(s.fecha_solicitud)}`}
          </Text>
          {(esLaMasBarata || (cargado && s.version > 1) || s.contratista_dado_de_baja) && (
            <Group gap={6} mt={4}>
              {esLaMasBarata && (
                <Badge size="xs" variant="light" color="teal" tt="none">
                  Más barata
                </Badge>
              )}
              {cargado && s.version > 1 && (
                <Badge size="xs" color="gray" variant="outline" tt="none">
                  Versión {s.version}
                </Badge>
              )}
              {s.contratista_dado_de_baja && <DadoDeBajaBadge size="xs" />}
            </Group>
          )}
        </div>
        <Stack gap={4} align="flex-end" style={{ flex: 'none' }}>
          {cargado && s.monto != null && (
            <Text fw={700} size="sm" style={{ whiteSpace: 'nowrap' }}>
              {formatoMoneda.format(s.monto)}
            </Text>
          )}
          <Group gap={6} wrap="nowrap">
            {cargado ? (
              <BudgetStatusBadge estado={s.presupuesto_estado} variant="light" />
            ) : (
              // Dado de baja ya no puede ofertar: no hay respuesta que esperar.
              !s.contratista_dado_de_baja && (
                <Badge color="gray" variant="light" leftSection={<IconClock size={12} />}>
                  Pendiente
                </Badge>
              )
            )}
            {cargado && <IconEye size={16} color="var(--mantine-color-teal-6)" />}
          </Group>
          {diferencia != null && (
            <Text size="xs" c="dimmed">
              +{diferencia}% que la más barata
            </Text>
          )}
        </Stack>
      </Group>
    </Card>
  );
}

export function BudgetRequestsList({ solicitudes, onDecidido }) {
  const [presupuestoVisto, setPresupuestoVisto] = useState(null);

  const handleVerPresupuesto = async (presupuestoId) => {
    try {
      setPresupuestoVisto(await obtenerPresupuesto(presupuestoId));
    } catch (err) {
      notifyError(err.message);
    }
  };

  if (solicitudes === null) {
    return (
      <Text c="red" size="sm">
        No se pudieron cargar los presupuestos.
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

  const laMasBarata = masBarata(solicitudes);

  return (
    <>
      <Stack gap="xs">
        {ordenar(solicitudes).map((s) =>
          s.presupuesto_cargado ? (
            <UnstyledButton
              key={s.presupuesto_id}
              onClick={() => handleVerPresupuesto(s.presupuesto_id)}
            >
              <TarjetaSolicitud solicitud={s} masBarata={laMasBarata} />
            </UnstyledButton>
          ) : (
            <TarjetaSolicitud key={`pendiente-${s.contratista_id}`} solicitud={s} />
          ),
        )}
      </Stack>

      <BudgetItemsModal
        presupuesto={presupuestoVisto}
        onClose={() => setPresupuestoVisto(null)}
        onDecidido={() => {
          setPresupuestoVisto(null);
          onDecidido?.();
        }}
      />
    </>
  );
}
