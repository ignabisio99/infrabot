import { useEffect, useState } from 'react';
import { Badge, Button, Group, Paper, Select, Stack, Text, Textarea } from '@mantine/core';
import { useForm } from '@mantine/form';

import { sugerirContratistas } from '../../api/ai';
import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda } from '../../utils/formatters';
import { notifyError } from '../../utils/notifications';
import {
  LABOR_VACIA,
  MATERIAL_VACIO,
  serializarItems,
  totalLineas,
  validarLineasPresupuesto,
} from '../../utils/presupuestoItems';
import { ClaimComments } from '../claims/ClaimComments';
import { BudgetLineItems } from './BudgetLineItems';

const valoresPorDefecto = {
  claimId: '',
  contractorId: '',
  taskDetail: '',
  notes: '',
  materials: [{ ...MATERIAL_VACIO }],
  labor: [{ ...LABOR_VACIA }],
};

export function BudgetForm({
  reclamosDisponibles,
  contratistasDisponibles,
  initialValues = valoresPorDefecto,
  onSubmit,
  submitting = false,
  submitLabel = 'Guardar Presupuesto',
  reclamoEditable = true,
}) {
  const form = useForm({
    initialValues: {
      ...valoresPorDefecto,
      ...initialValues,
      materials: initialValues.materials ?? valoresPorDefecto.materials,
      labor: initialValues.labor ?? valoresPorDefecto.labor,
    },
    validate: (values) => {
      const errors = {
        ...validarLineasPresupuesto(values.materials, values.labor),
      };
      if (values.claimId === '') errors.claimId = 'Seleccione un reclamo';
      if (values.contractorId === '') errors.contractorId = 'Seleccione un contratista';
      return errors;
    },
  });

  const claimId = form.values.claimId;
  // Se guarda para qué reclamo son las sugerencias: si no coincide con el elegido,
  // todavía se están buscando.
  const [sugerencias, setSugerencias] = useState({ reclamoId: null, lista: [] });

  useEffect(() => {
    if (!claimId) return;
    let vigente = true;
    sugerirContratistas(Number(claimId))
      .then((data) => {
        if (vigente) setSugerencias({ reclamoId: claimId, lista: data.slice(0, 3) });
      })
      .catch((err) => {
        if (!vigente) return;
        notifyError(err.message);
        setSugerencias({ reclamoId: claimId, lista: [] });
      });
    return () => {
      vigente = false;
    };
  }, [claimId]);

  const cargandoSugeridos = sugerencias.reclamoId !== claimId;
  const sugeridos = cargandoSugeridos ? [] : sugerencias.lista;

  // El backend sólo acepta presupuestos sobre reclamos que estén pendientes de
  // presupuesto o en evaluación, y lo informa en `admite_presupuesto`. El reclamo ya
  // elegido se mantiene en la lista aunque haya dejado de admitirlos, así al editar
  // un presupuesto el select muestra a qué reclamo pertenece.
  const opcionesReclamos = reclamosDisponibles
    .filter((reclamo) => reclamo.admite_presupuesto || String(reclamo.id) === initialValues.claimId)
    .map((reclamo) => ({
      value: String(reclamo.id),
      label: `${formatearIdReclamo(reclamo.id)} - ${reclamo.nombre_escuela}`,
    }));

  const opcionesContratistas = contratistasDisponibles.map((contratista) => ({
    value: String(contratista.id),
    label: contratista.nombre_empresa,
  }));

  const total = totalLineas(form.values.materials, form.values.labor);

  const handleSubmit = (values) => {
    const items = serializarItems(values.materials, values.labor);
    const datos = {
      contratista_id: Number(values.contractorId),
      detalle_tarea: values.taskDetail.trim() === '' ? null : values.taskDetail,
      observaciones: values.notes.trim() === '' ? null : values.notes,
      items,
    };

    // Al editar, el reclamo no viaja: el PUT lo rechaza con un 422.
    onSubmit(reclamoEditable ? { reclamo_id: Number(values.claimId), ...datos } : datos);
  };

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        <Select
          label="Reclamo"
          placeholder="Seleccione un reclamo"
          description={
            reclamoEditable
              ? 'Sólo se listan los reclamos pendientes de presupuesto o en evaluación.'
              : 'Un presupuesto no se puede pasar a otro reclamo. Si se cargó en el equivocado, dalo de baja y cargalo de nuevo.'
          }
          data={opcionesReclamos}
          searchable={reclamoEditable}
          disabled={!reclamoEditable}
          nothingFoundMessage="Ningún reclamo está esperando presupuestos"
          key={form.key('claimId')}
          {...form.getInputProps('claimId')}
        />

        {form.values.claimId && <ClaimComments reclamoId={Number(form.values.claimId)} />}

        <Select
          label="Contratista"
          placeholder="Seleccione un contratista"
          data={opcionesContratistas}
          searchable
          key={form.key('contractorId')}
          {...form.getInputProps('contractorId')}
        />

        {form.values.claimId && (
          <Paper withBorder p="sm" radius="md">
            <Text fw={500} size="sm" mb="xs">
              Contratistas sugeridos
            </Text>
            {cargandoSugeridos && (
              <Text size="sm" c="dimmed">
                Buscando sugerencias…
              </Text>
            )}
            {!cargandoSugeridos && sugeridos.length === 0 && (
              <Text size="sm" c="dimmed">
                No hay contratistas para sugerir.
              </Text>
            )}
            <Stack gap={6}>
              {sugeridos.map((s) => (
                <Paper key={s.contratista_id} withBorder p="xs">
                  <Group justify="space-between" gap="xs">
                    <div style={{ flex: '1 1 200px', minWidth: 0 }}>
                      <Text size="sm" fw={500}>
                        {s.nombre_empresa}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {s.especialidad} · {s.calificacion}/5 · {s.carga_activa} obra(s) activa(s)
                      </Text>
                    </div>
                    <Group gap="xs" wrap="nowrap">
                      <Badge variant="light">{s.score}</Badge>
                      <Button
                        type="button"
                        size="xs"
                        variant="light"
                        onClick={() => form.setFieldValue('contractorId', String(s.contratista_id))}
                      >
                        Elegir
                      </Button>
                    </Group>
                  </Group>
                </Paper>
              ))}
            </Stack>
          </Paper>
        )}

        <Textarea
          label="Detalle de la tarea a realizar"
          placeholder="Describí el trabajo que cubre este presupuesto..."
          minRows={3}
          autosize
          key={form.key('taskDetail')}
          {...form.getInputProps('taskDetail')}
        />

        <Textarea
          label="Observaciones"
          placeholder="Notas adicionales (opcional)..."
          minRows={2}
          autosize
          key={form.key('notes')}
          {...form.getInputProps('notes')}
        />

        <BudgetLineItems form={form} />

        <Group justify="flex-end">
          <Text fw={700} size="lg">
            Total: {formatoMoneda.format(total)}
          </Text>
        </Group>

        <Button type="submit" mt="md" loading={submitting}>
          {submitLabel}
        </Button>
      </Stack>
    </form>
  );
}
