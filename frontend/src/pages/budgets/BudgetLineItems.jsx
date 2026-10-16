import { useEffect, useState } from 'react';
import {
  Autocomplete,
  Button,
  NumberInput,
  Paper,
  Select,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';

import { listarRolesManoObra } from '../../api/rolesManoObra';
import { LABOR_VACIA, MATERIAL_VACIO } from '../../utils/presupuestoItems';
import { notifyError } from '../../utils/notifications';

const UNIDADES = [
  'kg',
  'gramos',
  'metros',
  'metros²',
  'metros³',
  'litros',
  'horas',
  'cajas',
  'rollos',
  'bolsas',
  'unidad',
];

export function BudgetLineItems({ form }) {
  const [roles, setRoles] = useState([]);

  useEffect(() => {
    listarRolesManoObra()
      .then(setRoles)
      .catch((err) => notifyError(err.message));
  }, []);

  const opcionesRoles = roles.map((rol) => ({
    value: rol.nombre,
    label: rol.nombre,
  }));

  return (
    <Stack gap="md">
      <Stack gap="xs">
        <Text fw={500} size="sm">
          Materiales
        </Text>
        {form.values.materials.map((_, index) => (
          <Paper
            key={form.key(`materials.${index}`)}
            withBorder
            p="sm"
            radius="md"
            className="line-item-row"
          >
            <TextInput
              label="Material"
              placeholder="Material"
              style={{ flex: 2 }}
              key={form.key(`materials.${index}.description`)}
              {...form.getInputProps(`materials.${index}.description`)}
            />
            <NumberInput
              label="Cantidad"
              placeholder="Cantidad"
              min={0}
              decimalScale={2}
              style={{ flex: 1 }}
              key={form.key(`materials.${index}.quantity`)}
              {...form.getInputProps(`materials.${index}.quantity`)}
            />
            <Autocomplete
              label="Unidad"
              placeholder="Unidad"
              data={UNIDADES}
              maxDropdownHeight={260}
              comboboxProps={{ withinPortal: true }}
              style={{ flex: 1 }}
              key={form.key(`materials.${index}.unit`)}
              {...form.getInputProps(`materials.${index}.unit`)}
            />
            <NumberInput
              label="Costo unitario"
              placeholder="Costo unitario"
              min={0}
              decimalScale={2}
              prefix="$"
              style={{ flex: 1 }}
              key={form.key(`materials.${index}.unitCost`)}
              {...form.getInputProps(`materials.${index}.unitCost`)}
            />
            <Button
              type="button"
              color="red"
              variant="light"
              className="line-item-remove"
              disabled={form.values.materials.length === 1}
              onClick={() => form.removeListItem('materials', index)}
            >
              Quitar
            </Button>
          </Paper>
        ))}
        <Button
          type="button"
          variant="light"
          onClick={() => form.insertListItem('materials', { ...MATERIAL_VACIO })}
        >
          + Agregar material
        </Button>
      </Stack>

      <Stack gap="xs">
        <Text fw={500} size="sm">
          Mano de obra
        </Text>
        {form.values.labor.map((_, index) => (
          <Paper
            key={form.key(`labor.${index}`)}
            withBorder
            p="sm"
            radius="md"
            className="line-item-row"
          >
            <Select
              label="Rol"
              placeholder="Rol"
              data={opcionesRoles}
              searchable
              nothingFoundMessage="No hay roles. Un administrador puede cargarlos en Configuración."
              style={{ flex: 2 }}
              key={form.key(`labor.${index}.description`)}
              {...form.getInputProps(`labor.${index}.description`)}
            />
            <NumberInput
              label="Horas"
              placeholder="Horas"
              min={0}
              decimalScale={2}
              style={{ flex: 1 }}
              key={form.key(`labor.${index}.quantity`)}
              {...form.getInputProps(`labor.${index}.quantity`)}
            />
            <NumberInput
              label="Costo por hora"
              placeholder="Costo por hora"
              min={0}
              decimalScale={2}
              prefix="$"
              style={{ flex: 1 }}
              key={form.key(`labor.${index}.unitCost`)}
              {...form.getInputProps(`labor.${index}.unitCost`)}
            />
            <Button
              type="button"
              color="red"
              variant="light"
              className="line-item-remove"
              disabled={form.values.labor.length === 1}
              onClick={() => form.removeListItem('labor', index)}
            >
              Quitar
            </Button>
          </Paper>
        ))}
        <Button
          type="button"
          variant="light"
          onClick={() => form.insertListItem('labor', { ...LABOR_VACIA })}
        >
          + Agregar mano de obra
        </Button>
      </Stack>

      {form.errors.lineas && (
        <Text size="sm" c="red">
          {form.errors.lineas}
        </Text>
      )}
    </Stack>
  );
}
