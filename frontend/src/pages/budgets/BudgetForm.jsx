import {
  Button,
  Group,
  NumberInput,
  Select,
  Stack,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';

import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda } from '../../utils/formatters';

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
  reclamoEditable = true,
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

  const total = form.values.items.reduce(
    (acumulado, item) => acumulado + (Number(item.quantity) || 0) * (Number(item.unitCost) || 0),
    0,
  );

  const handleSubmit = (values) => {
    const datos = {
      contratista_id: Number(values.contractorId),
      observaciones: values.notes.trim() === '' ? null : values.notes,
      items: values.items.map((item) => ({
        descripcion: item.description,
        cantidad: item.quantity,
        costo_unitario: item.unitCost,
      })),
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

        <Select
          label="Contratista"
          placeholder="Seleccione un contratista"
          data={opcionesContratistas}
          searchable
          key={form.key('contractorId')}
          {...form.getInputProps('contractorId')}
        />

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
