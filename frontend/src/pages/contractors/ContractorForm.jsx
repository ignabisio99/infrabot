import { TextInput, NumberInput, Button, Stack } from '@mantine/core';
import { useForm } from '@mantine/form';

const valoresPorDefecto = {
  companyName: '',
  phone: '',
  address: '',
  specialty: '',
  rating: '',
};

export function ContractorForm({
  initialValues = valoresPorDefecto,
  onSubmit,
  submitting = false,
  submitLabel = 'Guardar Contratista',
}) {
  const form = useForm({
    initialValues,
    validate: {
      companyName: (value) => (value.length < 3 ? 'Ingrese el nombre de la empresa' : null),
      phone: (value) => (value.length < 6 ? 'Ingrese un teléfono válido' : null),
      address: (value) => (value.length < 3 ? 'Ingrese la dirección' : null),
      specialty: (value) => (value.length < 2 ? 'Ingrese la especialidad' : null),
      rating: (value) =>
        value === '' || value < 1 || value > 5 ? 'Ingrese una calificación entre 1 y 5' : null,
    },
  });

  const handleSubmit = (values) => {
    onSubmit({
      nombre_empresa: values.companyName,
      telefono: values.phone,
      direccion: values.address,
      especialidad: values.specialty,
      calificacion: values.rating,
    });
  };

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        <TextInput
          label="Nombre de la empresa"
          placeholder="Ejemplo: Gas Sur SRL"
          key={form.key('companyName')}
          {...form.getInputProps('companyName')}
        />

        <TextInput
          label="Teléfono"
          placeholder="Ejemplo: 011-4555-1234"
          key={form.key('phone')}
          {...form.getInputProps('phone')}
        />

        <TextInput
          label="Dirección"
          placeholder="Ejemplo: Av. Rivadavia 1234"
          key={form.key('address')}
          {...form.getInputProps('address')}
        />

        <TextInput
          label="Especialidad"
          placeholder="Ejemplo: Gas, Electricidad, Plomería..."
          key={form.key('specialty')}
          {...form.getInputProps('specialty')}
        />

        <NumberInput
          label="Calificación"
          placeholder="1 a 5"
          min={1}
          max={5}
          key={form.key('rating')}
          {...form.getInputProps('rating')}
        />

        <Button type="submit" mt="md" loading={submitting}>
          {submitLabel}
        </Button>
      </Stack>
    </form>
  );
}
