import { useState } from 'react';
import { Badge, Card, Group, Stack, Text, UnstyledButton } from '@mantine/core';
import { IconClock, IconEye } from '@tabler/icons-react';

import { obtenerPresupuesto } from '../../api/presupuestos';
import { formatoMoneda } from '../../utils/formatters';
import { notifyError } from '../../utils/notifications';
import { BudgetItemsModal } from '../budgets/BudgetItemsModal';
import { BudgetStatusBadge } from '../budgets/BudgetStatusBadge';
import { masBarata, ordenarOfertas, porcentajeSobre } from '../budgets/comparacion';
import { estaVigente } from '../budgets/estados';
import { DadoDeBajaBadge } from '../contractors/DadoDeBajaBadge';

const fecha = (valor) => new Date(valor).toLocaleDateString('es-AR');

const estadoDe = (s) => s.presupuesto_estado;
const vigente = (s) => estaVigente({ estado: estadoDe(s) });
const cerrada = (s) => ['RECHAZADO', 'NO_SELECCIONADO'].includes(estadoDe(s));

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
    masBarata && vigente(s) && !esLaMasBarata ? porcentajeSobre(s, masBarata) : null;

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

  const laMasBarata = masBarata(solicitudes, estadoDe);

  return (
    <>
      <Stack gap="xs">
        {ordenarOfertas(solicitudes, estadoDe).map((s) =>
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
