import { useEffect, useState } from 'react';
import {
  Badge,
  Button,
  Group,
  NumberInput,
  Paper,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';

import { sugerirContratistas } from '../../api/ai';
import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda } from '../../utils/formatters';
import { notifyError } from '../../utils/notifications';

const valoresPorDefecto = {
  claimId: '',
  contractorId: '',
  notes: '',
  items: [{ description: '', quantity: '', unitCost: '' }],
};

export function BudgetForm({
  reclamosDisponibles,
  contratistasDisponibles,
  initialValues = valoresPorDefecto,
  onSubmit,
  submitting = false,
  submitLabel = 'Guardar Presupuesto',
}) {
  const form = useForm({
    initialValues,
    validate: {
      claimId: (value) => (value === '' ? 'Seleccione un reclamo' : null),
      contractorId: (value) => (value === '' ? 'Seleccione un contratista' : null),
      items: {
        description: (value) => (value.trim() === '' ? 'Ingrese una descripción' : null),
        quantity: (value) => (value === '' || Number(value) <= 0 ? 'Debe ser mayor a 0' : null),
        unitCost: (value) => (value === '' || Number(value) < 0 ? 'No puede ser negativo' : null),
      },
    },
  });

  const [sugeridos, setSugeridos] = useState([]);
  const [cargandoSugeridos, setCargandoSugeridos] = useState(false);

  useEffect(() => {
    const reclamoId = form.values.claimId;
    if (!reclamoId) {
      setSugeridos([]);
      return;
    }
    let vigente = true;
    setCargandoSugeridos(true);
    sugerirContratistas(Number(reclamoId))
      .then((data) => {
        if (vigente) setSugeridos(data.slice(0, 3));
      })
      .catch((err) => {
        if (vigente) notifyError(err.message);
      })
      .finally(() => {
        if (vigente) setCargandoSugeridos(false);
      });
    return () => {
      vigente = false;
    };
  }, [form.values.claimId]);

  const opcionesReclamos = reclamosDisponibles.map((reclamo) => ({
    value: String(reclamo.id),
    label: `${formatearIdReclamo(reclamo.id)} - ${reclamo.nombre_escuela}`,
  }));

  const opcionesContratistas = contratistasDisponibles.map((contratista) => ({
    value: String(contratista.id),
    label: contratista.nombre_empresa,
  }));

  const total = form.values.items.reduce(
    (acumulado, item) => acumulado + (Number(item.quantity) || 0) * (Number(item.unitCost) || 0),
    0,
  );

  const handleSubmit = (values) => {
    onSubmit({
      reclamo_id: Number(values.claimId),
      contratista_id: Number(values.contractorId),
      observaciones: values.notes.trim() === '' ? null : values.notes,
      items: values.items.map((item) => ({
        descripcion: item.description,
        cantidad: item.quantity,
        costo_unitario: item.unitCost,
      })),
    });
  };

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        <Select
          label="Reclamo"
          placeholder="Seleccione un reclamo"
          data={opcionesReclamos}
          searchable
          key={form.key('claimId')}
          {...form.getInputProps('claimId')}
        />

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
                  <Group justify="space-between" wrap="nowrap">
                    <div>
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

        <Stack gap="xs">
          <Text fw={500} size="sm">
            Ítems del presupuesto
          </Text>

          {form.values.items.map((_, index) => (
            <Group key={form.key(`items.${index}`)} align="flex-start" wrap="nowrap">
              <TextInput
                placeholder="Descripción"
                style={{ flex: 2 }}
                key={form.key(`items.${index}.description`)}
                {...form.getInputProps(`items.${index}.description`)}
              />
              <NumberInput
                placeholder="Cantidad"
                min={0}
                decimalScale={2}
                style={{ flex: 1 }}
                key={form.key(`items.${index}.quantity`)}
                {...form.getInputProps(`items.${index}.quantity`)}
              />
              <NumberInput
                placeholder="Costo unitario"
                min={0}
                decimalScale={2}
                prefix="$"
                style={{ flex: 1 }}
                key={form.key(`items.${index}.unitCost`)}
                {...form.getInputProps(`items.${index}.unitCost`)}
              />
              <Button
                type="button"
                color="red"
                variant="subtle"
                disabled={form.values.items.length === 1}
                onClick={() => form.removeListItem('items', index)}
              >
                Quitar
              </Button>
            </Group>
          ))}

          <Button
            type="button"
            variant="light"
            onClick={() =>
              form.insertListItem('items', { description: '', quantity: '', unitCost: '' })
            }
          >
            + Agregar ítem
          </Button>
        </Stack>

        <Textarea
          label="Observaciones"
          placeholder="Notas adicionales (opcional)..."
          minRows={2}
          autosize
          key={form.key('notes')}
          {...form.getInputProps('notes')}
        />

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
